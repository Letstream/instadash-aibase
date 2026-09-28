<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Tenancy (Single- and Multi-Tenant)

> In a multi-tenant project every domain object belongs to a tenant (an **Organization**), and no
> user may ever read or write another tenant's data. This is the **#1 leak vector** in a SaaS
> backend — the boundary is server-side and mandatory. This doc defines the single- vs multi-tenant
> choice, the standard tenancy model, how the active tenant is resolved per request, how querysets
> are scoped, and how role-based permissions are enforced. Runnable code:
> [scaffold/organization](../../bootstrap/scaffold/backend/organization.md). See
> [accounts-and-auth](accounts-and-auth.md), [testing](testing.md), [security](../../security.md).

---

## 0. Single-tenant vs multi-tenant

Every project picks **one** mode at Bootstrap. The choice is recorded in the project's `DOCS.md`
and in the environment as `TENANCY_MODE=multi|single`. Switching later is a migration project, so
decide deliberately: "could two independent customers ever share this deployment?" → multi.

| | **Multi-tenant** (`TENANCY_MODE=multi`) | **Single-tenant** (`TENANCY_MODE=single`) |
|---|---|---|
| Who uses it | Many customer organizations share one deployment | One organization (internal tool, dedicated deployment) |
| Tables | `Organization`, `OrganizationUser` (membership join), `OrganizationRole` (permission codes), `OrganizationInvite` — the `organization` app | **None** — the `organization` app is not installed |
| Tenant models | Extend abstract `OrgScopedModel(TimeStampedModel)` | Extend `TimeStampedModel` / `UUIDTimeStampedModel` |
| Tenant resolution | `X-Organization-Id` header → `TenantMiddleware` → `request.organization` | none (`request.organization` is absent) |
| Authorization | `HasOrgPermission` + per-view `org_permissions = ["order:read"]` | `HasRole` + per-view `min_role = "admin"` |
| Roles | Per-membership `OrganizationRole.permissions` (codes, `"*"`) | `User.role`: **owner > admin > member > guest** |

**How the code switches.** `core/views.py` builds `AuthenticatedView.permission_classes` as
`[IsAuthenticated, HasOrgPermission]` in multi mode and `[IsAuthenticated, HasRole]` in single
mode; `base.py` only installs `apps.organization` and `TenantMiddleware` in multi mode; the root
URLconf only mounts `/api/organization/` in multi mode. Everything else (accounts, core, envelope,
audit) is identical.

**Single-tenant rules**
- `User.role` (`owner`/`admin`/`member`/`guest`, default `member`) is the only authorization input.
  `user.has_role("admin")` is true for admin and owner (superusers always pass).
- `HasOrgPermission` is **replaced**, not degraded: views declare `min_role` instead of
  `org_permissions`. A view without `min_role` is open to any authenticated user, exactly like a
  view without `org_permissions` in multi mode — so **declare `min_role` on every data view**.
  Use `HasRole("owner")` inline for one-off stricter checks.
- Role changes are security events (`SecurityEvent.Type.ROLE_CHANGED`) and only an `owner` (or
  superuser) may grant `owner`/`admin`.
- The user payload exposes `permissions` expanded from the role (`ROLE_PERMISSIONS` in
  `accounts/models.py`, `owner` → `["*"]`) so the frontend can gate UI; keep that map consistent
  with the `min_role` each view enforces.
- `User.role` exists in multi mode too but is ignored there — never read it for tenant decisions.

Everything below applies to **multi-tenant** projects.

---

## 1. The tenancy data model

Four models express tenancy. The key decision: **roles live on the membership row, never as a
field/FK on `User`** — this keeps the system multi-org from day one.

```python
class Organization(UUIDTimeStampedModel):
    name = models.CharField(max_length=150)
    owner = models.ForeignKey(                       # FK: one user may own MANY orgs
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_organizations"
    )
    objects = OrganizationQuerySet.as_manager()      # accessible_to(user), get_for_member(user, id)

class OrganizationRole(UUIDTimeStampedModel):
    name = models.CharField(max_length=64)
    role_type = models.CharField(max_length=16, choices=RoleType.choices)   # admin | user
    permissions = models.JSONField(default=list)     # ["order:read", "order:create"] or ["*"]
    organization = models.ForeignKey(Organization, null=True, on_delete=models.CASCADE,
                                     related_name="roles")   # NULL = global default role
    is_active = models.BooleanField(default=True)
    # unique (organization, name) + unique name among global roles

class OrganizationUser(OrgScopedModel):             # the MEMBERSHIP join model
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.ForeignKey(OrganizationRole, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    # unique (organization, user)

class OrganizationInvite(OrgScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    role = models.ForeignKey(OrganizationRole, on_delete=models.PROTECT)
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    expires_on = models.DateTimeField()              # default now + 7 days
    # unique (organization, email)
```

- `owner` is a **ForeignKey**, not one-to-one: a user can create/own several organizations.
  `PROTECT` forces an explicit ownership transfer before a user can be deleted.
- Global default roles ("Admin" = `["*"]`, "Member" = read codes) are seeded idempotently after
  every `migrate` (`OrganizationRole.ensure_defaults()` on `post_migrate`). Tenants may add their
  own roles; list both with `OrganizationRole.objects.available_to(org)`.
- Self-serve sign-up creates the user's first organization via the `accounts.signals.user_registered`
  signal (accounts never imports tenancy).

**Effective access lives on the org (fat model):**

```python
def get_permissions(self, user) -> list[str]:
    if self.is_owner(user):
        return ["*"]
    membership = self.get_membership(user)          # active membership, cached per instance
    if membership is None or not membership.role.is_active:
        return []
    return list(membership.role.permissions or [])

def has_permission(self, user, code) -> bool:
    granted = self.get_permissions(user)
    return "*" in granted or code in granted
```

`org.has_member(user)` (owner or active member) and `org.describe_for(user)` (payload for
my-orgs) complete the API.

---

## 2. Resolving the active tenant per request (header-based)

The client sends the active tenant id in the **`X-Organization-Id`** header. `TenantMiddleware`
attaches `request.organization`, validated against membership. **Never trust a client-supplied
tenant id** without that check.

```python
class TenantMiddleware:
    HEADER = "X-Organization-Id"

    def __call__(self, request):
        org_id = request.headers.get(self.HEADER)
        request.organization = SimpleLazyObject(lambda: self._resolve(request, org_id))
        return self.get_response(request)

    @staticmethod
    def _resolve(request, org_id):
        if not org_id:
            return None
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        return Organization.objects.get_for_member(user, org_id)   # else PermissionDenied → 403
```

- **Why lazy:** DRF authenticates the `Authorization: Token …` header *inside the view*, after all
  middleware ran. The lazy object resolves on first access, when `request.user` is the token user.
  Consequence: test it by **truthiness** (`if not request.organization`), never `is None`.
- A header naming an org the caller can't access → `PermissionDenied` → **403** envelope (never a
  404 that would confirm the org exists).
- The header is in `CORS_ALLOW_HEADERS`.
- **Org switching is stateless** — the client sends a different header value per request.
  `GET /api/organization/my-orgs/` lists switchable tenants (owned + active memberships) with each
  tenant's role + permissions, so the front end can gate UI immediately after login.
- An API-key auth path (machine-to-machine), if a project adds one, sets `request.organization`
  directly from the key's tenant.

---

## 3. Scoping querysets to the tenant (`OrgScopedModel`)

There is **one** enforcement style: every tenant-owned model extends the abstract
`OrgScopedModel`, whose manager makes the scope explicit at every call site.

```python
class OrgScopedQuerySet(models.QuerySet):
    def for_org(self, organization):              # org already validated (request.organization)
        if not organization:
            return self.none()
        return self.filter(organization=organization)

    def visible_to(self, user, organization):     # also re-checks membership
        if not organization or not (user and user.is_authenticated):
            return self.none()
        if not (user.is_superuser or organization.has_member(user)):
            return self.none()
        return self.for_org(organization)


class OrgScopedModel(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                     related_name="%(app_label)s_%(class)s_set")
    objects = OrgScopedQuerySet.as_manager()

    class Meta:
        abstract = True

    def is_accessible_by(self, user) -> bool:     # object-level check for writes / cross-links
        return bool(user and user.is_authenticated) and (
            user.is_superuser or self.organization.has_member(user)
        )
```

Usage:

```python
class Order(OrgScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ...

def get_queryset(self):                                    # every read path
    return Order.objects.visible_to(self.request.user, self.request.organization)

serializer.save(organization=self.request.organization)    # every create
```

**Rules:** **every** queryset returning tenant data goes through `for_org`/`visible_to` (never a
bare `.objects.all()` / `.get(pk=…)`), **every** write verifies the object belongs to the caller's
tenant (`obj.is_accessible_by(user)` or fetch through the scoped queryset), and cross-links between
two tenant objects re-check both ends share the same tenant (narrow related-field querysets in the
serializer). Override the inherited `organization` field only to set a nicer `related_name`.

---

## 4. Declarative RBAC — permission codes on the view

Authorization is declarative: a view declares the permission codes it needs; one permission class
checks them against the caller's role in the request tenant.

```python
class HasOrgPermission(BasePermission):
    def has_permission(self, request, view):
        codes = getattr(view, "org_permissions", None)
        if codes is None:
            return True                                   # view opts out of tenant checks
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:                             # platform superuser bypass
            return True
        if not codes or "*" in codes:
            return True
        organization = getattr(request, "organization", None)
        if not organization:                              # no/invalid header → deny
            return False
        return all(organization.has_permission(user, code) for code in codes)   # owner → "*"
```

- Codes are **`"resource:action"`** string constants in a per-app registry
  (`permission_constants.py`): `"order:read"`, `"order:create"`, `"user:manage"`,
  `"billing:manage"`.
- A view declares them statically (`org_permissions = [perms.ORDER_READ]`) or **per HTTP verb**
  inside `check_permissions()` (see [apps-architecture](apps-architecture.md) §7).
- **Bypass hierarchy:** platform superuser → org owner (`"*"`) → role-permission check.
- Endpoints that manage the tenant itself (members, invites, roles) are gated by `user:manage` /
  `user:read` and additionally refuse to act on the caller's own membership.

---

## 5. Invitations, roles, and org lifecycle

- **Invite** (`POST /api/organization/invites/`, `user:manage`): validate not-the-owner /
  not-already-a-member / no pending invite, create an `OrganizationInvite` (7-day expiry), enqueue
  the email with an accept URL (`{FRONTEND_URL}/invite/{id}`), record `MEMBER_INVITED`.
- **Public invite preview** (`GET /api/organization/invites/<id>/public/`): **anonymous**, so an
  invitee can see the org name + inviter before signing up. Unexpired invites only.
- **Accept** (`POST /api/organization/invites/<id>/accept/`): the authenticated user's email must match
  the invite; `OrganizationUser.update_or_create(...)`, delete the invite, record `INVITE_ACCEPTED`.
- **Manage members** (`PATCH`/`DELETE /api/organization/members/<id>/`, `user:manage`): change role
  (`ROLE_CHANGED`), remove (`MEMBER_REMOVED`). Suspend/resend/revoke follow the same pattern.
- **Create another org** (`POST /api/organization/`): the caller becomes its owner.

All of these are security events — see [audit-logging](audit-logging.md).

---

## 6. Tenant-scoped subscriptions & quotas

Tie plans and quotas to the tenant, not the user. Put the linkage on the org model
(`org.get_subscription()`, `org.can_do(addon)`, `org.ensure_can_do(addon)`) backed by
Redis-cached usage/entitlement helpers. Reuse the same tenant plan in **both** the rate limiter
and a `@subscription_limiter(addon_code)` decorator applied to resource-creating endpoints, so
throttling and quota both derive from tenancy. Team size is itself a quota (seats vs. active
members + pending invites).

---

## 7. Public vs. authenticated surface

Keep the **public, unauthenticated** surface small and explicit: the health check, invite
previews, and any anonymous, tenant-agnostic endpoints (in a dedicated `portal`-style app when
there are several). The authenticated, tenant-scoped API lives in the feature apps behind the
`X-Organization-Id` header. This clean split makes the tenancy boundary obvious.

---

## Tenancy checklist (every change)

1. Mode is known (`DOCS.md` / `TENANCY_MODE`); single-tenant views declare `min_role`.
2. New tenant model extends `OrgScopedModel` and is scoped (`for_org` / `visible_to`) in **every** read path.
3. Writes stamp `organization=request.organization` and verify object access (`is_accessible_by`).
4. Active tenant comes **only** from the validated `X-Organization-Id` → `request.organization`.
5. Endpoints declare `org_permissions`; codes exist in the app's `permission_constants.py`.
6. Cross-tenant links re-check both ends share a tenant (narrow related-field querysets).
7. **A test proves user A cannot see or modify org B's rows** for the new model ([testing](testing.md)).
8. Quotas/limits read from the tenant's plan.
