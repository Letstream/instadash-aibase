<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Audit Logging

> Who changed what, when, from where — and every security-relevant event — recorded in an
> **append-only** trail. Two layers: [`django-auditlog`](https://django-auditlog.readthedocs.io/)
> captures **model changes** (field-level diffs with actor, IP, correlation id), and core's
> **`SecurityEvent`** table captures **security events** that are not model diffs (logins, failed
> logins, token revocation, exports…). This is the evidence base for SOC 2. Runnable code:
> [scaffold/core](../../bootstrap/scaffold/backend/core.md) (`SecurityEvent`, middleware, retention task,
> read-only admin) and [scaffold/accounts](../../bootstrap/scaffold/backend/accounts.md) (registrations and
> events). See [accounts-and-auth](accounts-and-auth.md), [multi-tenancy](multi-tenancy.md),
> [security](../../security.md).

---

## 1. Why two layers

| Layer | Captures | Written by | Example |
|-------|----------|-----------|---------|
| `auditlog.LogEntry` | Create/update/delete of **registered models**, with a per-field `changes` diff | django-auditlog signals, automatically | "member Carol's role changed Member → Admin" |
| `core.SecurityEvent` | **Events** — often with no model row to attach to | `SecurityEvent.record(...)` explicitly, at the point it happens | "login failed for x@example.com from 203.0.113.9" |

A failed login for an unknown email, a data export, or an integration connect has no meaningful
"object diff", so forcing them into `LogEntry.objects.log_create(...)` would mean inventing target
objects. The chosen approach is therefore **one small append-only model in `core` with a
`record()` classmethod** for events, and auditlog for everything that *is* a model change. Actor and
tenant are stored on `SecurityEvent` as plain identifiers (`actor_id`, `actor_email`,
`organization_id`) — not foreign keys — so the trail survives user/org deletion.

---

## 2. Installing django-auditlog

```bash
poetry add django-auditlog
```

```python
# settings/base.py
INSTALLED_APPS = [
    ...,
    "auditlog",        # before apps.core — core re-registers LogEntry's admin as read-only
    "apps.core",
    ...,
]

MIDDLEWARE = [
    ...,
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    ...,
    "apps.core.middleware.AuditActorMiddleware",   # instead of auditlog.middleware.AuditlogMiddleware
]
```

Then `python manage.py migrate` (auditlog ships its own migrations).

**Actor capture under token auth.** auditlog's own `AuditlogMiddleware` reads `request.user`
*eagerly* — but DRF authenticates `Authorization: Token …` inside the view, after middleware ran,
so every API write would be logged with no actor. The scaffold's `AuditActorMiddleware` sets the
actor as a **lazy object** (resolved when the first `LogEntry` is written, by which time DRF has set
`request.user`), plus the client IP and a correlation id:

```python
class AuditActorMiddleware:
    def __call__(self, request):
        set_cid(request)                                            # X-Correlation-ID → LogEntry.cid
        actor = SimpleLazyObject(lambda: self._resolve_actor(request))
        with set_actor(actor=actor, remote_addr=RequestUtils.get_client_ip(request)):
            return self.get_response(request)
```

A test in the scaffold proves a token-authenticated `PATCH` produces a `LogEntry` whose `actor` is
the token's user. Writes outside requests (Celery tasks, management commands) have no actor unless
you wrap them: `with set_actor(user): …`.

---

## 3. Registering models

Register in the app's `AppConfig.ready()` (keeps `models.py` import-light and avoids cycles):

```python
class OrdersConfig(AppConfig):
    name = "apps.orders"
    label = "orders"

    def ready(self) -> None:
        from auditlog.registry import auditlog

        from .models import Order, OrderLine

        auditlog.register(Order, exclude_fields=["modified_on"])
        auditlog.register(OrderLine, exclude_fields=["modified_on"])
```

- **What to register:** every model that holds business data or controls access — users, tokens,
  organizations, roles, memberships, invites, and the project's domain models. Skip high-churn
  technical tables (caches, counters, sessions).
- **Per-object history:** add `history = AuditlogHistoryField()` (from `auditlog.models`) to a model
  to get `obj.history.all()`; it complements, not replaces, `register()`. Without it use
  `LogEntry.objects.get_for_object(obj)`.
- **Many-to-many:** pass `m2m_fields={"tags"}` to record relation changes.
- **Noise control:** always exclude `modified_on` (it changes on every save); exclude bookkeeping
  fields that change on reads (e.g. `Token.last_used_on`) — an update touching only excluded fields
  writes no entry.

---

## 4. Excluding and masking sensitive fields

Secrets must never land in `LogEntry.changes`:

| Model | Exclude |
|-------|---------|
| `User` | `password`, `last_login` (+ `modified_on`) |
| `Token` / API keys | `key_hash`, `last_used_on`, `last_ip`, `user_agent`, `expires_on` |
| Integration credentials | the encrypted secret columns (exclude — never mask-and-keep) |

For fields whose *change* matters but whose value is sensitive (e.g. a webhook URL with an embedded
key, an admin-editable Option), use `mask_fields=["value"]` — auditlog records that it changed with
the value partially masked. Review `exclude_fields`/`mask_fields` whenever a model gains a field.

---

## 5. Recording security events

`SecurityEvent.record()` is the only write path. Call it **at the point of the event**, pass the
request (actor, tenant, IP and user agent are derived from it), and put non-secret context in
keyword metadata:

```python
SecurityEvent.record(SecurityEvent.Type.LOGIN_FAILED, request=request, email=email)
SecurityEvent.record(SecurityEvent.Type.LOGIN_SUCCEEDED, request=request, actor=user)
SecurityEvent.record(
    SecurityEvent.Type.ROLE_CHANGED, request=request,
    member_id=str(member.pk), from_role=previous, to_role=member.role.name,
)
```

**Event catalogue** (`SecurityEvent.Type`) and where each is emitted:

| Event | Emitted by |
|-------|-----------|
| `USER_REGISTERED`, `LOGIN_SUCCEEDED`, `LOGIN_FAILED`, `LOGOUT` | accounts views |
| `TOKEN_ISSUED`, `TOKEN_REVOKED` | API-key / personal-token management (login tokens are covered by login/logout) |
| `PASSWORD_RESET_REQUESTED`, `PASSWORD_CHANGED` | password reset views (and any change-password endpoint) |
| `ROLE_CHANGED` | member role changes (multi) / `User.role` changes (single) / role permission edits |
| `MEMBER_INVITED`, `INVITE_ACCEPTED`, `MEMBER_REMOVED` | organization views |
| `DATA_EXPORTED` | every export/download-all endpoint or task |
| `HARD_DELETED` | any irreversible delete of business data (record *before* deleting: ids, counts) |
| `INTEGRATION_CONNECTED`, `INTEGRATION_DISCONNECTED` | OAuth/integration flows |

Add project-specific types to the `TextChoices` (and run `makemigrations`) rather than overloading
metadata. **Metadata rules:** ids, emails, role names, counts — never passwords, tokens, OTPs, reset
links, or document contents.

---

## 6. Immutability

Audit evidence is worthless if it can be edited. Enforce append-only at every layer:

- **Model:** `SecurityEvent.save()` refuses updates, `delete()` raises `ImmutableRecordError`.
- **QuerySet:** `SecurityEventQuerySet.update()` / `.delete()` raise; the only deletion path is
  `purge_older_than(cutoff)`, used by the retention task.
- **Admin:** `SecurityEvent` and auditlog's `LogEntry` are registered with a `ReadOnlyAdminMixin`
  (no add/change/delete; `LogEntry` is re-registered to forbid deletes too).
- **API:** never expose update/delete endpoints for audit data. Read access, if any, is an
  `AdminOnlyView` (or tenant-admin-scoped view filtering by `organization_id`) — and reading/exporting
  the trail is itself a `DATA_EXPORTED` event.
- **Database (recommended for production):** run the app with a DB role that has no `UPDATE`/`DELETE`
  on `core_securityevent` and `auditlog_logentry`, and run retention under a separate role.

---

## 7. Retention

Keep audit data at least as long as your SOC 2 observation window plus a margin —
`AUDIT_RETENTION_DAYS` (default **400**). The daily beat task `apps.core.tasks.purge_audit_logs`
(queue `maintenance`) deletes older `SecurityEvent` rows via `purge_older_than` and older
`LogEntry` rows. For ad-hoc maintenance auditlog also ships a command:

```bash
python app/manage.py auditlogflush --before-date 2025-01-01 --yes
```

If policy requires longer retention than the primary DB should hold, export aged rows to immutable
object storage (write-once bucket) before purging.

---

## 8. SOC 2 mapping

| Trust Services Criterion | Evidence from this design |
|--------------------------|---------------------------|
| **CC6.1** logical access controls | Token auth, RBAC (`HasOrgPermission` / `HasRole`), tenant isolation tests; `LOGIN_*` events |
| **CC6.2 / CC6.3** provisioning, modification, removal of access | `USER_REGISTERED`, `MEMBER_INVITED`, `INVITE_ACCEPTED`, `ROLE_CHANGED`, `MEMBER_REMOVED`, `TOKEN_REVOKED`; auditlog diffs on users/roles/memberships |
| **CC6.6 / CC6.7** boundary & data transmission | `INTEGRATION_*` events, `DATA_EXPORTED` |
| **CC7.2** monitoring for anomalies | `LOGIN_FAILED` bursts, off-hours `DATA_EXPORTED`, `HARD_DELETED` — alert on these |
| **CC7.3 / CC7.4** incident evaluation & response | Correlated trail: actor, IP, correlation id, timestamps across both layers |
| **CC8.1** change management | auditlog field-level history of configuration/business records (Options changes masked) |

Auditors ask for *samples*: make sure you can answer "show every access change for user X in
period Y" with one admin filter or query.

---

## 9. Checklist

- [ ] `auditlog` installed before `apps.core`; `AuditActorMiddleware` in `MIDDLEWARE`.
- [ ] Every business/access model registered in its `AppConfig.ready()` with sensitive fields
      excluded (or masked) and `modified_on` excluded.
- [ ] Every security-relevant action calls `SecurityEvent.record(...)` with non-secret metadata.
- [ ] No update/delete path for audit data (model, queryset, admin, API); retention via the task only.
- [ ] `AUDIT_RETENTION_DAYS` set per policy; `purge_audit_logs` scheduled on the `maintenance` queue.
- [ ] Tests cover: actor attribution under token auth, a failed-login event without the password,
      append-only guards.
