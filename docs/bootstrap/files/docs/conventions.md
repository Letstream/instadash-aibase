<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Backend Conventions (quick reference)

> The one-page summary of how every backend app is built. Details and code live in the
> [architecture guidelines](./architecture-guidelines/README.md) — its **Canonical decisions** table
> wins on any conflict. Mimic the reference apps `apps/core`, `apps/accounts` and (multi-tenant)
> `apps/organization` as materialised from the [backend scaffold](./bootstrap/scaffold/backend/README.md).
> See also [data-model](./data-model.md), [security](./security.md), [AGENTS](../AGENTS.md).

## App layout (one concern per app)
```
apps/<app>/
  models.py        # domain models (fat models: logic + managers here)
  managers.py      # optional custom QuerySets/Managers if large
  serializers.py   # DRF serializers (+ lite variants)
  views.py         # thin views extending core.views.{Anonymous,Authenticated,AdminOnly}View
  urls.py          # exported as `urlpatterns`
  services.py      # optional service classes for multi-step operations
  filters.py       # optional django-filter FilterSets
  admin.py         # Django admin registration
  tasks.py         # optional Celery tasks (routed to a named queue)
  signals.py       # optional; wired in apps.py ready()
  tests/           # pytest: test_models.py, test_views.py, … (mandatory)
```
Create apps with `startapp`; never hand-write `apps.py` or migrations. Don't run `makemigrations`
in a parallel subagent — the lead runs it centrally. Full layout: [apps-architecture](./architecture-guidelines/backend/apps-architecture.md).

## Models
- **Every** model extends `apps.core.models.TimeStampedModel`; URL-facing resources use
  `UUIDTimeStampedModel`. Multi-tenant data extends the abstract `OrgScopedModel` (itself a
  `TimeStampedModel`) → `organization` FK + `objects.visible_to(user, org)` + `is_accessible_by(user)`.
- **Fat models, thin views.** Behaviour on the model (`order.cancel()`), query logic on custom
  QuerySets (`Order.objects.open()`), multi-step workflows in a small service class.
- Register models with `django-auditlog` ([audit-logging](./architecture-guidelines/backend/audit-logging.md)).

## Views & responses
- Pick the auth tier by base class, then mix in a DRF generic/viewset:
  `class OrderListView(AuthenticatedView, generics.ListCreateAPIView)`.
- Return plain `Response(data)`; `LetstreamAPIRenderer` wraps it: success
  `{status:true, data, version}`, error `{status:false, err_cd, err_msg, error, version}`.
  Raise the core API exceptions (`NotFoundError`, `MissingParametersError`,
  `PermissionDeniedError`, …) for clean error envelopes; never build the envelope by hand.
- Multi-tenant: declare `org_permissions = ["order:read", …]`; scope `get_queryset()` with
  `visible_to(request.user, request.organization)`; stamp `organization` on create.
  Single-tenant: `HasRole` instead.
- Details: [apps-architecture](./architecture-guidelines/backend/apps-architecture.md),
  [core-app-reference](./architecture-guidelines/backend/core-app-reference.md),
  [multi-tenancy](./architecture-guidelines/backend/multi-tenancy.md).

## Serializers
- `ModelSerializer`; FKs as ids + a nested "lite" read where the UI needs it.
- Validate in `validate_*`; side effects live in the model/service, not the serializer.
- Timestamps read-only. Reuse the fields in `core/custom_serializer_fields.py`.

## Security (non-negotiable — [security](./security.md))
- Tenant from `X-Organization-Id`, validated server-side; never trust client ids for authz.
- Sanitize rich-text HTML with `apps.core.utils.sanitize_html` (nh3) before storing `*_html`.
- Encrypt stored secrets with a Fernet `SecretBox` in core (add it when first needed).

## Async & realtime
- Celery tasks are idempotent, routed to a named queue, and use retries with backoff —
  [background-tasks-and-notifications](./architecture-guidelines/backend/background-tasks-and-notifications.md).
  A new queue means a new worker in `infra/docker-compose.yml` ([infra](./infra.md)).
- Websockets only when the project needs them — [realtime-channels](./architecture-guidelines/backend/realtime-channels.md).

## URLs
Each app exports `urlpatterns`; the lead includes them under `/api/<app>/` in `app/urls.py`.
Kebab-case resource names (`order-items`). Keep drf-spectacular's schema accurate.

## Tests
Every app ships `tests/`; every tenant model has a cross-tenant isolation test —
[testing](./architecture-guidelines/backend/testing.md).
