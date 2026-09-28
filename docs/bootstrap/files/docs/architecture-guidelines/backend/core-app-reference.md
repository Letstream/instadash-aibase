<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Core App Reference

> The exhaustive contract of the shared `core` app — the foundation every feature app builds on.
> [apps-architecture](apps-architecture.md) shows how to *use* these when building a feature; this
> doc is the *reference* for what `core` actually ships and how each piece behaves. The exact code
> is in [scaffold/core](../../bootstrap/scaffold/backend/core.md). `core` holds **no domain models** — only
> cross-cutting base classes, the audit trail, and utilities.

Contents: base models · base views · custom parsers · response renderer · exceptions & error codes
· reusable serializer fields · permissions · the Options registry · rate limiters · utility
namespaces · middleware & Instadash lineage · admin · what core does *not* ship.

---

## 1. Base models (`core/models.py`)

Two abstract bases — full detail in [apps-architecture](apps-architecture.md) §2:

- `TimeStampedModel` — `created_on` / `modified_on`, with a `save()` override that keeps
  `modified_on` fresh even on partial `update_fields` saves. **Every model extends it.**
- `UUIDTimeStampedModel(TimeStampedModel)` — adds a UUID primary key for URL-facing resources.

Other shared bases subclass `TimeStampedModel` and stay abstract — notably the tenant base
`OrgScopedModel`, which lives with tenancy in the `organization` app
([multi-tenancy](multi-tenancy.md) §3). Cross-cutting fields become small **abstract mixins**.

`core` also owns two concrete, cross-cutting tables:
- `Options` — the dynamic-settings store behind the Options registry (§8).
- `SecurityEvent` — the **append-only** security/audit trail (logins, token revocation, role
  changes, invites, exports, hard deletes, integration connects). `SecurityEvent.record(...)` is the
  one way to write it; updates and deletes raise. See [audit-logging](audit-logging.md).

---

## 2. Base API views (`core/views.py`)

A three-tier `APIView` hierarchy expressing the auth tier by class. Feature views compose one with
a DRF `generics.*`/`viewsets.*` mixin.

```
APIView
 └─ AnonymousView          # AllowAny; custom parsers; LetstreamAPIRenderer; exception aliases
     └─ AuthenticatedView  # [IsAuthenticated, HasOrgPermission]   ← the 90% case
         └─ AdminOnlyView  # [IsAuthenticated, IsAdmin]
```

`AuthenticatedView` picks its tenant permission from `settings.TENANCY_MODE`: `HasOrgPermission`
(multi-tenant) or `HasRole` (single-tenant). `AnonymousView` is where the shared machinery lives
(parsers, renderer swap, `self.NotFoundError` & friends) — see [apps-architecture](apps-architecture.md) §3.

`core/views.py` also defines:
- the Django error-handler views (`bad_request`, `permission_denied`, `page_not_found`,
  `server_error`) wired as `handler400/403/404/500` in the root URLconf, plus a `prepare_response(...)`
  helper that builds the **same envelope** for non-DRF responses — so even a raw 404 or 500
  returns the standard shape;
- `HealthView` — `GET /api/health/`: checks the database and cache, returns 200 (or 503) in the
  envelope, never leaks error details, skips authentication and throttling. Load balancers and
  compose health checks use it.

**Choosing a tier:** `class OrderListView(AuthenticatedView, generics.ListAPIView): …`. Use
`AnonymousView` for public endpoints, `AdminOnlyView` for platform-superuser tools.

---

## 3. Custom parsers (`core/parsers.py`)

Front ends routinely send the strings `"null"`, `"undefined"`, or `""` for cleared fields —
especially through `multipart/form-data`, where everything is a string. Custom parsers normalize
these to real `None` **at the boundary** so serializers and models never special-case them.

```python
class APIFormParser(FormParser):
    def parse(self, stream, media_type=None, parser_context=None):
        return coerce_empties(super().parse(stream, media_type, parser_context))

class APIMultiPartParser(MultiPartParser):
    def parse(self, stream, media_type=None, parser_context=None):
        result = super().parse(stream, media_type, parser_context)
        coerce_empties(result.data)          # files untouched
        return result
```

- `QueryDict` is immutable by default; `coerce_empties` flips `_mutable`, rewrites, and restores it.
- JSON bodies already carry real `null`, so `JSONParser` needs no wrapper — it stays first in the list.
- Registered both on the base view and in `DEFAULT_PARSER_CLASSES`. **Don't** re-implement
  "if value == 'null'" checks in serializers — that's the parser's job.

---

## 4. Response renderer (the envelope)

`LetstreamAPIRenderer` (`core/api_renderers.py`) wraps **every** response:
success `{status: true, data, version}`, error `{status: false, err_cd, err_msg, error, version}`.
Full detail and rules in [apps-architecture](apps-architecture.md) §4. Views return a plain DRF
`Response(payload)`; the renderer wraps it — never assemble the envelope by hand.

---

## 5. Exceptions & error codes (`core/api_exceptions.py`, `core/api_errors.py`)

- `BaseAPIException(APIException)` carries `status_code`, `default_detail` and a namespaced `err_cd`,
  plus an optional keyword-only `fields` list → per-field "required" errors.
- Ready-made subclasses: `MissingParametersError` (400), `DataInvalidError` (400),
  `PermissionDeniedError` (403), `NotFoundError` (404) — aliased on `AnonymousView` for ergonomic
  raising.
- `api_exception_handler` (`REST_FRAMEWORK["EXCEPTION_HANDLER"]`) converts them to
  `{err_cd, err_msg, error}`; everything else goes through DRF's default handler.
- **Namespaced, numbered codes** per app: `E-<class>-<APP>-NNNN` (core: `E-C-COR-0001…0008`,
  accounts: `E-C-ACC-…`). `default_error_for(status)` maps an HTTP status to core's default code +
  message. These are a stable machine contract the front end switches on.

---

## 6. Reusable serializer fields (`core/custom_serializer_fields.py`)

The headline idea: **one field that writes by id and reads as a nested object**, so a serializer
needs one declaration per relation.

```python
class ForeignSerializerField(serializers.RelatedField):
    """Write by id (or {"id": …}); read as a nested object via `serializer_class`."""

    def __init__(self, serializer_class, **kwargs):     # kwargs include queryset=
        self.serializer_class = serializer_class
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        pk = data.get("id") if isinstance(data, dict) else data
        try:
            return self.get_queryset().get(pk=pk)
        except (ObjectDoesNotExist, DjangoValidationError, ValueError, TypeError) as exc:
            raise serializers.ValidationError("Invalid id.") from exc

    def to_representation(self, value):
        return self.serializer_class(value, context=self.context).data


class M2MSerializerField(ForeignSerializerField):   # list of ids/objects in, nested list out
    ...

class Base64FileField(serializers.FileField):       # data-URI upload, mime allowlist + size cap
    ALLOWED_TYPES = frozenset({"application/pdf"})
    MAX_FILE_SIZE_MB = 10

class Base64ImageField(Base64FileField):            # jpeg/png/webp/gif, 5 MB; SVG excluded (script)
    ...
```

**Usage**

```python
class OrderSerializer(serializers.ModelSerializer):
    customer = ForeignSerializerField(queryset=Customer.objects.all(), serializer_class=CustomerLiteSerializer)
    tags     = M2MSerializerField(queryset=Tag.objects.all(), serializer_class=TagLiteSerializer)
    receipt  = Base64FileField(required=False)
```

- **Tenant data:** narrow the field's queryset to the request tenant in the serializer's
  `__init__` (`self.fields["customer"].queryset = Customer.objects.for_org(org)`), otherwise a
  client could link another tenant's object by id.
- Validation (mime allowlist, size cap) lives on the **field**, not the view — see
  [storage-and-media](storage-and-media.md) §7.

---

## 7. Permissions (`core/permissions.py`)

Three reusable permission classes, none of which import tenancy models (they duck-type):

- `IsAdmin` — platform superuser only.
- `HasOrgPermission` (multi-tenant) — reads the view's `org_permissions` and checks each
  `"resource:action"` code with `request.organization.has_permission(user, code)`; bypass order
  superuser → org owner → role codes. A view without `org_permissions` skips the tenant check.
  Full detail in [multi-tenancy](multi-tenancy.md) §4.
- `HasRole` (single-tenant) — compares `User.role` against a minimum (`owner > admin > member >
  guest`). Use as `HasRole` (reads the view's `min_role`) or `HasRole("admin")` inline.

---

## 8. The Options registry — DB-backed, cache-fronted dynamic settings

Configuration that an **admin must change at runtime** (feature switches, default limits, support
addresses) doesn't belong in `.env` — it belongs in a DB-backed, cache-fronted, enum-keyed
**Options registry**. Options are editable live from the admin; `.env` is set at deploy time.

**Storage** — `core.models.Options(TimeStampedModel)` with `key` / `value` / `label`; its `save()` and
`delete()` invalidate the cached value.

**Facade** — `core/options.py`:

```python
class Option:
    CACHE_TTL = 60 * 60

    class Keys(StrEnum):
        SIGNUP_ENABLED = "signup_enabled"
        SUPPORT_EMAIL = "support_email"

    DEFAULTS = {  # key → (default, human label)
        Keys.SIGNUP_ENABLED: ("true", "Allow self-serve registration"),
        Keys.SUPPORT_EMAIL: ("", "Support e-mail shown in outgoing mail"),
    }

    @classmethod
    def get(cls, key) -> str: ...        # cache → DB → default
    @classmethod
    def get_bool(cls, key) -> bool: ...
    @classmethod
    def set(cls, key, value) -> None: ...  # writes DB; the model invalidates the cache
```

**Rules**
- Keys are a **`StrEnum`** (`Option.Keys`) — never bare strings at call sites.
- Reads fall back to `DEFAULTS`, so a fresh environment works without seeding; a seed/`setoption`
  management command is optional.
- Use Options for values operators tune without a deploy. Keep **secrets** and anything
  security-critical in the environment (and credentials of integrations encrypted at rest), not in
  an admin-editable table. Mask Options values in the audit log (`mask_fields=["value"]`) if they
  may hold sensitive data.

---

## 9. Rate & quota limiters

Two decorator-style limiters (add to `core/utils.py` when a project needs them), applied to view
methods:

```python
@rate_limiter(Option.Keys.GENERAL_API_RATELIMIT)     # abuse protection (per minute)
def post(self, request): ...

@subscription_limiter(AddonCode.ORDER)               # plan quota / entitlement
def post(self, request): ...
```

- **`rate_limiter(feature_code)`** — Redis sliding window keyed per identifier (`org_<id>` when
  authenticated, else `anon_<ip>`); acquires a lock, returns **429** on breach, increments usage
  **only on 2xx**; limit resolves from the tenant plan or an Options value; `-1` = unlimited.
- **`subscription_limiter(addon_code)`** — enforces tenant entitlements: `org.ensure_can_do(addon)`
  before the call, usage increment after success. Ties quota to tenancy — see
  [multi-tenancy](multi-tenancy.md) §6.
- For simple per-endpoint brute-force protection (login, password reset) DRF scoped throttles are
  enough — that's what the scaffold's `accounts` app uses.

---

## 10. Utility namespaces (`core/utils.py`)

Cross-cutting helpers as **namespaced classes** (static/class methods) rather than loose functions:

| Namespace | Provides |
|-----------|----------|
| `RequestUtils` | `get_client_ip` (honours `X-Forwarded-For` only when `TRUST_X_FORWARDED_FOR` is set, validates the address), `get_user_agent`, `get_organization` (never raises on a bad tenant header). |
| `HtmlSanitizer` / `sanitize_html()` | nh3 allowlist sanitiser — run on every stored rich-text/HTML field (stored-XSS defence). |
| `TimeUtils` | UTC ↔ local conversion (named tz or `±HH:MM` offset), start/end-of-day-in-UTC. *(add when needed)* |
| `S3Utils` | Presigned S3 upload URLs — see [storage-and-media](storage-and-media.md) §5. *(add when needed)* |
| `SignedLinks` | Short-lived signed links (email verification, downloads) via Django's `signing.TimestampSigner`. JWT only if a third party requires it — never for session auth. *(add when needed)* |
| `FileHandler` | `get_file_type` (mime → category), temp-file helpers. *(add when needed)* |

Raw SQL is allowed only in a dedicated, parameterized helper (e.g. `GenericStats` in `db_utils.py`
against an analytics connection) — never string-built.

---

## 11. Middleware (`core/middleware.py`) & Instadash lineage

- `AuditActorMiddleware` — DRF-aware replacement for auditlog's `AuditlogMiddleware`: sets the
  audit actor lazily so token-authenticated writes are attributed. See [audit-logging](audit-logging.md) §2.
- `InstadashVersionMiddleware` — stamps every response with `X-Letstream-Instadash-Version`.

**Instadash lineage.** Every generated project records which Instadash AI Base version it derives
from: the constant `INSTADASH_BASE_VERSION` in `settings/base.py` (filled from
`docs/bootstrap/VERSION` at bootstrap) and the `InstadashVersionMiddleware` that exposes it as a
response header (placed right after `SecurityMiddleware`). Both are **managed by the bootstrap /
upgrade flow** — don't edit the constant by hand and don't remove the middleware; a test asserts
the header on `/api/health/`.

---

## 12. Admin (`core/admin.py`)

- `Options` is editable in the admin.
- `SecurityEvent` and auditlog's `LogEntry` are registered **read-only** (a `ReadOnlyAdminMixin`
  denies add/change/delete; `LogEntry` is re-registered to also forbid delete).
- The admin itself lives on an obfuscated path (`ADMIN_URL`). Add custom `AdminSite` instances only
  when a project needs separate privilege tiers.

---

## 13. What `core` does NOT ship (don't assume)

Add these deliberately, don't assume they exist:

- A soft-delete base/manager or an `OrderedModel` base — not in core by decision; add a small
  abstract mixin in the feature app that needs it.
- The tenant base model — `OrgScopedModel` lives in the `organization` app (multi-tenant only).
- A crypto/encrypted-field module — add one (e.g. a Fernet `SecretBox` keyed from an env secret)
  when you must store integration credentials at rest.
- Rate/subscription limiters, `TimeUtils`, `S3Utils`, `SignedLinks` — documented patterns, added
  when a project needs them.
- Websocket plumbing — opt-in per project, see [realtime-channels](realtime-channels.md).
