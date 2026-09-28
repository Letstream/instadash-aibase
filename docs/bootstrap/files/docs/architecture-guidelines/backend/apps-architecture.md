<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Apps Architecture & Backend Conventions

> How every backend app is built and how the shared foundation (`core`) provides the base
> classes each app reuses. The two governing principles are **fat models / thin views** and a
> **uniform response envelope**. This doc is the "how to build a feature app" view; for the full
> contract of the shared foundation (parsers, serializer fields, the Options registry, limiters,
> utils) see [core-app-reference](core-app-reference.md). Runnable code:
> [scaffold/core](../../bootstrap/scaffold/backend/core.md). See also [project-structure](project-structure.md),
> [multi-tenancy](multi-tenancy.md), [accounts-and-auth](accounts-and-auth.md), [testing](testing.md).

---

## 1. Standard app layout (one concern per app)

```
apps/<app>/
  models.py              # domain models — FAT: validation, side-effects, factory classmethods
  serializers.py         # DRF ModelSerializers (+ nested and Lite variants)
  views.py               # THIN views on the core base classes + DRF generics
  urls.py                # app_name + explicit path() list
  admin.py               # admin registration
  apps.py                # AppConfig; ready() wires signals + auditlog registration
  utils.py               # optional: app-specific helper classes (namespaced, static/classmethods)
  signals.py             # optional: receivers, connected in ready()
  tasks.py               # optional: Celery @shared_task
  constants.py           # optional: choices, enums, string constants
  permission_constants.py# optional (multi-tenant): this app's "resource:action" codes
  api_errors.py          # optional: this app's namespaced error codes (+ exception classes)
  public/                # optional: unauthenticated endpoints for this domain
  migrations/  tests/
```

**Conventions**
- Business logic lives on **models** (instance/class methods), **custom QuerySets/managers**
  (`Order.objects.visible_to(user, org)`), and **per-app helper classes** — not in views. A
  dedicated `services.py` is optional; reach for it only for genuinely multi-step orchestration
  that doesn't belong on one model.
- Prefer **namespaced utility classes** (`class LinkValidationUtils: @staticmethod def …`) over
  loose module functions — it keeps helpers discoverable and grouped by concern.
- Do not run `makemigrations` from a subagent/parallel worker; a single owner runs migrations
  centrally in dependency order.

---

## 2. Base models (`apps/core/models.py`)

**Every model extends `TimeStampedModel`** — directly, via `UUIDTimeStampedModel`, or via
another abstract base that itself subclasses `TimeStampedModel` (e.g. `OrgScopedModel`). Keep the
shared bases tiny and composable; add small **abstract mixins** per feature as needed.

```python
class TimeStampedModel(models.Model):
    """`created_on` / `modified_on` — EVERY model extends this (directly or via a base)."""

    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_on = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Keep `modified_on` fresh even on partial `update_fields` saves."""
        update_fields = kwargs.get("update_fields")
        if update_fields and "modified_on" not in update_fields:
            kwargs["update_fields"] = [*update_fields, "modified_on"]
        super().save(*args, **kwargs)


class UUIDTimeStampedModel(TimeStampedModel):
    """TimeStampedModel with a non-enumerable UUID primary key (URL-facing resources)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
```

**Rules**
- **User-facing resources** whose PK appears in URLs use `UUIDTimeStampedModel` (non-enumerable,
  `<uuid:pk>` routes). Internal/lookup rows can keep the default integer PK.
- **Tenant-owned models** (multi-tenant projects) extend the abstract
  `OrgScopedModel(TimeStampedModel)` from the tenancy app — it adds the `organization` FK and the
  scoped manager (`for_org(org)`, `visible_to(user, org)`) plus `is_accessible_by(user)`. For a
  UUID key on a tenant model, declare `id = models.UUIDField(primary_key=True, default=uuid.uuid4,
  editable=False)` on the concrete class. See [multi-tenancy §3](multi-tenancy.md#3-scoping-querysets-to-the-tenant-orgscopedmodel).
- Cross-cutting fields become **abstract mixins** (e.g. a `HitsMixin` adding a counter). Compose
  mixins; don't fatten the base. `core` deliberately ships **no** soft-delete or ordering base.
- Register every model that holds business or security-relevant data with **django-auditlog**
  ([audit-logging](audit-logging.md)).

---

## 3. Base API views (`apps/core/views.py`)

A small hierarchy of base `APIView`s expresses the **auth tier** by class; feature views compose
one of them with a DRF `generics.*` mixin.

```
APIView
 └─ AnonymousView          # AllowAny; custom parsers; LetstreamAPIRenderer; nested exceptions
     └─ AuthenticatedView  # [IsAuthenticated, HasOrgPermission]  ← the 90% case
         └─ AdminOnlyView  # [IsAuthenticated, IsAdmin]
```

In a **single-tenant** project `AuthenticatedView` uses `[IsAuthenticated, HasRole]` instead of
`HasOrgPermission` (selected from `settings.TENANCY_MODE`) — see [multi-tenancy §0](multi-tenancy.md#0-single-tenant-vs-multi-tenant).

```python
class AnonymousView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, APIFormParser, APIMultiPartParser]  # "null"/"" → None
    renderer_classes = [LetstreamAPIRenderer, BrowsableAPIRenderer]

    # raise self.NotFoundError() / self.MissingParametersError(fields=["x"]) — no imports
    MissingParametersError = api_exceptions.MissingParametersError
    DataInvalidError = api_exceptions.DataInvalidError
    PermissionDeniedError = api_exceptions.PermissionDeniedError
    NotFoundError = api_exceptions.NotFoundError

    def get_renderers(self):
        # Browsable API in DEBUG only; production always returns the JSON envelope
        if settings.DEBUG:
            return super().get_renderers()
        return [LetstreamAPIRenderer()]


class AuthenticatedView(AnonymousView):
    permission_classes = [IsAuthenticated, HasOrgPermission]  # HasRole when single-tenant


class AdminOnlyView(AuthenticatedView):
    permission_classes = [IsAuthenticated, IsAdmin]
```

**Conventions**
- Choose the auth tier by **base class**, then mix in the DRF generic:
  `class OrderListView(AuthenticatedView, generics.ListAPIView): …`
- **Custom parsers** normalize empty/`"null"`/`"undefined"` strings to `None` (front ends send
  these for cleared fields) so serializers see real nulls — see [core-app-reference](core-app-reference.md) §3.
- **Renderer swap**: the browsable API is dev-only; production is JSON-envelope only.
- **Exception aliases** on the base view point at the module-level classes in
  `core/api_exceptions.py`, so `raise self.NotFoundError()` works without imports and the global
  handler catches them anywhere.
- Set `serializer_class` even on plain `APIView`s (and use `self.serializer_class(...)`) so
  drf-spectacular can describe the endpoint.

---

## 4. The response envelope (never build it by hand)

Every response is wrapped by one `JSONRenderer` subclass: **`LetstreamAPIRenderer`** in
`apps/core/api_renderers.py`. This is the most important cross-cutting contract — the front end
relies on it verbatim.

```jsonc
// success
{ "status": true,  "data": { … }, "version": "2.0.85" }
// error
{ "status": false, "err_cd": "E-C-ORD-0004", "err_msg": "Some data is invalid, please check.",
  "error": { "field": ["message"] }, "version": "2.0.85" }
```

```python
class LetstreamAPIRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        status_code = response.status_code if response is not None else 200
        if status_code == 204:
            return b""
        ok = 200 <= status_code < 300
        envelope = {"status": ok}
        if ok:
            envelope["data"] = data
        else:
            envelope.update(self._error_parts(data, status_code))  # err_cd, err_msg, error
        envelope["version"] = settings.APPLICATION_VERSION
        return super().render(envelope, accepted_media_type, renderer_context)
```

- `status` is a boolean derived from the HTTP status class.
- Payload goes under `data` on success; `err_cd` / `err_msg` / `error` on failure — **never both**.
  A payload's own `err_cd` / `err_msg` win; otherwise they default from the HTTP status.
- `version` comes from the `VERSION` file (`settings.APPLICATION_VERSION`).
- `204 No Content` stays bodiless.
- Views return a plain DRF `Response(payload)`; the renderer wraps it. **Never assemble the
  envelope in view code.** It is also the `DEFAULT_RENDERER_CLASSES` entry, so any DRF view is
  wrapped.

---

## 5. Exceptions & error codes

Register one global exception handler (`REST_FRAMEWORK["EXCEPTION_HANDLER"] =
"apps.core.api_exceptions.api_exception_handler"`) that converts `BaseAPIException` subclasses into
`{err_cd, err_msg, error}`, then lets the renderer fold them into the envelope. Everything else
falls through to DRF's default handler (validation errors → 400 with field errors, auth → 401, …).

```python
class BaseAPIException(APIException):
    err_cd: str = ERR_SERVER_ERROR

    def __init__(self, detail=None, code=None, *, fields=None):
        super().__init__(detail=detail, code=code)
        self.error_fields = list(fields or [])  # → {field: ["This field is required."]}
```

**Namespaced, numbered error codes** are a stable machine contract the front end can switch on.
Each app ships an `api_errors.py` with its codes (and small exception classes carrying them):

```python
APP_BASE = "E-C-ORD-"            # E-<class>-<APP>-
ERR_ORDER_LOCKED = APP_BASE + "0001"


class OrderLockedError(BaseAPIException):
    status_code = 409
    default_detail = "This order is locked."
    err_cd = ERR_ORDER_LOCKED
```

`core` owns the generic codes (`E-C-COR-0001` missing parameters … `0007` throttled). Django's
`handler400/403/404/500` point at core views that emit the **same** envelope, so even non-DRF
errors are consistent.

---

## 6. Serializers & reusable fields

- Use `ModelSerializer` with explicit `fields` + `read_only_fields`. Keep create/update
  **side-effects on the model or a service**, not in the serializer — the serializer validates
  and persists, the model owns behavior.
- Provide a **`Lite<Model>Serializer`** variant for list endpoints; switch on it in
  `get_serializer_class()` via a `?mode=lite` query param.
- Expose computed/nested reads with `SerializerMethodField`.
- Any stored rich text/HTML goes through `apps.core.utils.sanitize_html()` (nh3) before saving.
- Keep a small library of **reusable serializer fields** in `core` and use them everywhere:
  - A **write-by-id / read-as-nested** related field (one field serves both directions):
    ```python
    customer = ForeignSerializerField(
        queryset=Customer.objects.all(),          # narrow to the tenant in __init__
        serializer_class=CustomerLiteSerializer,
    )
    ```
  - `Base64FileField` / `Base64ImageField` accepting data-URI uploads with **mime allowlist +
    size cap**.
- Full field library (incl. `M2MSerializerField`) in [core-app-reference](core-app-reference.md) §6.

---

## 7. The view pattern (the 90% case)

**List** — declarative filtering + tenant-scoped queryset:

```python
class OrderListView(AuthenticatedView, generics.ListAPIView):
    org_permissions  = [perms.ORDER_READ]                 # declarative RBAC (see multi-tenancy)
    serializer_class = serializers.OrderSerializer
    queryset         = Order.objects.none()               # schema only; get_queryset scopes
    search_fields    = ["code", "name"]
    ordering_fields  = ["created_on", "modified_on"]
    ordering         = ["-created_on"]
    filterset_fields = {"status": ["exact"], "folder": ["exact", "isnull"]}

    def get_queryset(self):
        return Order.objects.visible_to(self.request.user, self.request.organization)  # TENANCY
```

**Create** — stamp the tenant on write; let the model do the heavy lifting:

```python
class OrderCreateView(AuthenticatedView):
    org_permissions = [perms.ORDER_CREATE]
    serializer_class = serializers.OrderSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=request.organization)   # stamp tenant on create
        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

- **Vary permission by HTTP verb** when a single endpoint does read + write:
  ```python
  def check_permissions(self, request):
      self.org_permissions = [perms.ORDER_EDIT] if request.method in ("PUT", "PATCH") else [perms.ORDER_READ]
      return super().check_permissions(request)
  ```
- Use DRF **ViewSets** only where you need custom `@action` verbs
  (`POST …/{id}/revoke/`); compose the same base view + `org_permissions`.
- Add domain verbs as `@action` methods rather than overloading generic CRUD.
- After a mutation that other clients should see live, call the realtime helper
  (`broadcast_change(...)`) — only in projects that opted into [realtime](realtime-channels.md).

---

## 8. URL wiring

- Each app defines `app_name` and a flat `urlpatterns` list of **explicit `path()`** entries
  (class-based `.as_view()`), kebab-case segments, `<uuid:pk>` converters, and
  `"<resource>-<action>"` route names.
- Reach for a DRF **router only** to expose ViewSet `@action` endpoints; mix router URLs with
  explicit paths as needed.
- The root URLconf mounts **every** app under `/api/<app>/` with a namespace
  (`/api/accounts/`, `/api/organization/`, `/api/orders/`; plus `/api/health/` and, in `DEBUG`,
  `/api/docs/`). Proxies (Vite dev server, frontend nginx, infra compose) forward only `/api/` and
  `/ws/`. The externally consumed, versioned API gets `/api/v<N>/` (see [project-structure](project-structure.md)).

```python
# apps/orders/urls.py
app_name = "orders"
urlpatterns = [
    path("list/",            views.OrderListView.as_view(),   name="order-list"),
    path("create/",          views.OrderCreateView.as_view(), name="order-create"),
    path("<uuid:pk>/",       views.OrderRUDView.as_view(),    name="order-rud"),
    path("<uuid:pk>/stats/", views.OrderStatsView.as_view(),  name="order-stats"),
]
```

---

## 9. Cross-cutting utilities (`apps/core/`)

Ship a small set of **namespaced helper classes** reused across apps (full reference:
[core-app-reference](core-app-reference.md) §8–§10):

- **Dynamic settings registry** — the DB-backed, cache-fronted, enum-keyed Options store
  (`apps.core.options.Option`) for values an admin must edit at runtime.
- **Decorator-style rate limiter** — a Redis sliding-window `@rate_limiter(feature_code)` keyed
  per tenant (`org_<id>`) or per IP for anonymous callers; returns `429` on breach; increments
  only on 2xx. Limits can resolve from the tenant's plan.
- **Request / HTML / Time / S3 / File** helper classes — client-IP extraction (proxy-aware only
  when configured), `sanitize_html`, timezone conversion, presigned S3 URLs, mime→category.

---

## 10. Admin

Mount the Django admin on an **obfuscated path from env** (`ADMIN_URL`), never the guessable
`/admin/`. When a project needs separate privilege tiers (superuser vs. staff operations), register
models on **custom `AdminSite` instances** mounted on separate obfuscated paths. Audit tables
(`auditlog.LogEntry`, `core.SecurityEvent`) are registered **read-only** — no add/change/delete.
