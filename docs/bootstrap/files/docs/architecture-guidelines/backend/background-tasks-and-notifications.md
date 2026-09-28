<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Background Tasks & Notifications

> Anything slow, external, or retryable runs **off the request path** as a Celery task — email/SMS
> sending, exports/imports, third-party sync, scheduled maintenance. The broker is **RabbitMQ**
> (AMQP); Redis is the cache (and the Channels layer when a project uses websockets), never the
> broker. Notifications (email, SMS, push) share one async pattern. See
> [configuration-and-settings](configuration-and-settings.md), [core-app-reference](core-app-reference.md),
> [accounts-and-auth](accounts-and-auth.md), [containerization-and-deployment](containerization-and-deployment.md).

---

## 1. Celery setup

- `app/celery.py` creates the app, `config_from_object("django.conf:settings", namespace="CELERY")`,
  and `autodiscover_tasks()` so every app's `tasks.py` is picked up.
- `app/__init__.py` exposes `celery_app` so `@shared_task` binds everywhere.
- **Broker = RabbitMQ** with a **dedicated user + vhost per project** (least privilege: the user
  has permissions on its own vhost only). `base.py` builds the URL from
  `RABBITMQ_HOST/PORT/USER/PASSWORD/VHOST` (URL-quoted), e.g.
  `amqp://<project_slug>:***@rabbitmq:5672/<project_slug>`.
- **No result backend** (`CELERY_TASK_IGNORE_RESULT = True`) unless a feature actually consumes
  results.
- `USE_CELERY=False` sets `CELERY_TASK_ALWAYS_EAGER = True` — tasks run inline, no broker needed
  (quick local runs; tests always run eager).

Baseline reliability settings (new-style lowercase names under the `CELERY_` namespace — never mix
them with the old uppercase names such as `CELERYD_PREFETCH_MULTIPLIER` / `CELERY_ACKS_LATE`, Celery
refuses mixed configs):

```python
CELERY_TASK_ACKS_LATE = True               # re-deliver if a worker dies mid-task
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1      # fair dispatch for long tasks
CELERY_TASK_TIME_LIMIT = 300               # hard kill
CELERY_TASK_SOFT_TIME_LIMIT = 240          # SoftTimeLimitExceeded → clean up
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_DEFAULT_QUEUE = "default"
```

---

## 2. Writing tasks

Tasks live in each app's `tasks.py` as `@shared_task`. Keep them **small, idempotent, and
crash-safe**.

```python
@shared_task(bind=True, max_retries=5, default_retry_delay=60, acks_late=True)
def sync_order_to_provider(self, order_id: str) -> None:
    order = Order.objects.filter(pk=order_id).first()   # pass IDs, not model instances
    if order is None:
        return                                          # object gone — nothing to do (idempotent)
    try:
        order.push_to_provider()                        # heavy lifting on the model
    except ProviderTemporaryError as exc:
        raise self.retry(exc=exc, countdown=60 * 2**self.request.retries) from exc
```

**Rules**
- **Pass primitive arguments (IDs), never ORM objects or querysets** — they don't serialize cleanly
  and go stale. Re-fetch inside the task — and for tenant data, re-fetch **through the tenant scope**
  (pass the org id too).
- **Idempotent**: a task may run more than once (`acks_late` re-delivery). Guard with existence
  checks / idempotency keys / `get_or_create` so a re-run is harmless.
- **Retry transient failures** with exponential backoff and a `max_retries` cap; let permanent
  failures fail loudly (they surface in error monitoring).
- Keep business logic on the **model/service**; the task is a thin async wrapper (fat models, thin
  tasks — same rule as views).
- **Never block the request** waiting on a task. Enqueue with `.delay(id)` / `.apply_async` and
  return immediately. When the enqueued work depends on rows written in an `atomic()` block, enqueue
  in `transaction.on_commit(...)`.

---

## 3. Queues & routing — one worker per queue

Route classes of work to **dedicated queues** so a burst of one kind can't starve another, and run
**one worker process/container per queue** so they scale independently.

```python
CELERY_TASK_QUEUES = (Queue("default"), Queue("emails"), Queue("maintenance"))
CELERY_TASK_ROUTES = {
    "apps.core.tasks.send_email":             {"queue": "emails"},
    "apps.core.tasks.purge_audit_logs":       {"queue": "maintenance"},
    "apps.accounts.tasks.purge_stale_tokens": {"queue": "maintenance"},
    # "apps.stats.tasks.*":                   {"queue": "stats"},   # glob patterns allowed
    # everything else → "default"
}
```

Each queue gets its own worker, named after the queue:

```bash
celery -A app worker -Q default     -n default@%h
celery -A app worker -Q emails      -n emails@%h
celery -A app worker -Q maintenance -n maintenance@%h
```

(In containers, whose working dir is the repo root, add `--workdir app`.) In the infra compose
file that's one service per queue; in Kubernetes one deployment per queue,
scaled to that queue's depth. A new queue means: add it to `CELERY_TASK_QUEUES`, route tasks to it,
and add a worker service ([containerization-and-deployment](containerization-and-deployment.md)).

---

## 4. Periodic tasks (beat)

Scheduled/maintenance work runs via `CELERY_BEAT_SCHEDULE` (crontab), executed by a **single**
`celery -A app beat` process (never run two — you'll double-fire).

```python
CELERY_BEAT_SCHEDULE = {
    "purge-audit-logs":   {"task": "apps.core.tasks.purge_audit_logs",       "schedule": crontab(hour=2, minute=0)},
    "purge-stale-tokens": {"task": "apps.accounts.tasks.purge_stale_tokens", "schedule": crontab(hour=2, minute=30)},
    # "renew-subscriptions": {"task": "apps.billing.tasks.renew_subscriptions", "schedule": crontab(minute="*/15")},
}
```

Periodic tasks are just tasks — keep them idempotent (a missed/duplicated tick must be safe).

---

## 5. Notifications (email / SMS / push)

**Domain code enqueues, it never sends.** The scaffold ships the minimum: `apps.core.tasks.send_email`
(routed to `emails`, retries with backoff, HTML + text alternatives) and plain-text templates in each
app's `templates/<app>/email/`. When a project sends more than a handful of messages, grow this into
a dedicated **notifications app** so every channel shares templating, provider config, retries and
logging:

```
apps/notifications/
  tasks.py           # send_email / send_sms / send_push (@shared_task, routed to their queues)
  providers/         # thin adapters: SMTP/SES (email), an SMS gateway, a push service
  services.py        # channel-agnostic Notifier (pick channel, render, enqueue)
  templates/         # email HTML + text bodies, SMS/push copy
  models.py          # optional: NotificationLog for delivery status
```

```python
class Notifier:
    @staticmethod
    def email(to: str, template: str, context: dict) -> None:
        # render now (so template errors surface in the request), enqueue the actual send
        subject, html, text = render_email(template, context)
        send_email.delay(to, subject, text, html)
```

**Rules**
- Auth/tenancy flows (password reset, invites, activation) enqueue — they never touch SMTP.
- **Provider is swappable** behind an adapter; credentials come from env (or the Options registry
  for non-secret tunables), so ops can rotate them without code changes.
- **Every email has a plain-text body**, HTML optional; copy lives in `templates/`, not inline
  strings. Footers use `PROJECT_NAME` / `LEGAL_ENTITY_NAME` from settings — never a hard-coded name.
- Route email to its **own queue** (`emails`) — a slow mailer must not delay other work.
- **Never log** OTP codes, reset links, tokens, or bodies containing secrets.

---

## 6. Reliability & observability

- **Retries with backoff** for transient errors; a sensible `max_retries`; an alert for exhausted
  tasks.
- **Idempotency**: design every task to be safe to run twice (`acks_late` + at-least-once delivery
  means it *will* happen eventually).
- **Time limits** are set globally; override per task when a job legitimately runs longer.
- **Monitoring**: Sentry's `CeleryIntegration` reports task failures with the same release as the
  web app; watch queue depth (RabbitMQ management UI/metrics) to scale workers.

---

## 7. Local development & testing

- Locally either run a worker (backgrounded) against the dev RabbitMQ, or set `USE_CELERY=False`
  to run tasks eagerly in-process.
- `testing.py` forces `CELERY_TASK_ALWAYS_EAGER = True`, `CELERY_TASK_EAGER_PROPAGATES = True` and a
  `memory://` broker — CI never needs RabbitMQ. Email goes to the locmem backend (`mailoutbox`).
- **Unit-test the task function directly** (call it, assert side effects) and the enqueue call
  (assert `.delay` was invoked with the right IDs via `mocker.patch`) — see [testing](testing.md).
- Test provider adapters against a fake/sandbox provider, never a real one.

---

## 8. Checklist

- [ ] Slow/external/retryable work runs in a `@shared_task`, enqueued with IDs (not objects).
- [ ] Tasks are idempotent and retry transient errors with backoff + a `max_retries` cap.
- [ ] Broker is RabbitMQ with a project-specific user + vhost; no result backend unless needed.
- [ ] Every queue is declared, routed, and has exactly one worker service; exactly one `beat`.
- [ ] Only new-style `CELERY_*` setting names.
- [ ] Outbound messaging is enqueued; templates hold the copy; no secrets in logs.
- [ ] Task failures reach error monitoring; time limits are set.
