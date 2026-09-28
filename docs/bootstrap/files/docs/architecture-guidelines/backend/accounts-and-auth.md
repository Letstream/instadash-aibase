<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Accounts & Authentication

> The `accounts` app owns identity: the custom `User` model, opaque token authentication, and the
> credential flows (registration, login, logout, password reset, optional activation / social
> login). Keep identity in one app; keep tenancy/roles in the [multi-tenancy](multi-tenancy.md)
> app. Runnable code: [scaffold/accounts](../../bootstrap/scaffold/backend/accounts.md). See also
> [audit-logging](audit-logging.md), [security](../../security.md).

---

## 1. Custom User model — always, from day one

Start every project with a **custom user model** so you never face the painful mid-project swap.
Use `AbstractBaseUser + PermissionsMixin` (plus `TimeStampedModel`, like every model) with **email
as the login identity** and a custom manager. `AUTH_USER_MODEL = "accounts.User"` is set in
`base.py` before the first migration.

```python
class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)                    # None → unusable password
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra): ...
    def create_superuser(self, email, password=None, **extra): ...   # staff + superuser + role=owner

    def get_by_natural_key(self, username):            # case-insensitive login
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})


class User(TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):                    # single-tenant projects only
        OWNER = "owner"; ADMIN = "admin"; MEMBER = "member"; GUEST = "guest"

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    email_confirmed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()
    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []
```

**Fat user model.** Identity helpers live on the model so callers ask the object, not a service:
`user.has_role(min_role)` (single-tenant hierarchy `owner > admin > member > guest`),
`user.issue_token(request)`, `user.revoke_all_tokens()`, `user.get_login_payload(request)` (issues a
token + serialized user). Tenancy questions go to the org (`org.has_permission(user, code)`), not the
user — see [multi-tenancy](multi-tenancy.md).

- `role` is used **only** when `TENANCY_MODE=single`; multi-tenant roles live on memberships.
- The user payload (login, register, `me`) includes `permissions: string[]` from
  `user.get_permissions()`: superuser → `["*"]`; single-tenant → the role's expansion from
  `ROLE_PERMISSIONS` (`owner` → `["*"]`, then admin/member/guest code lists the project extends);
  multi-tenant → `[]` (per-org `role` + `permissions` come from `GET /api/organization/my-orgs/`).
  The frontend gates UI on these codes; the backend still enforces on every request.
- Users can't change their own `email` or `role` through `/api/accounts/me/` (read-only fields).

---

## 2. Token authentication (opaque, hashed, DB-backed)

API authentication uses **opaque DB-backed tokens** sent as **`Authorization: Token <token>`**.
**No JWTs for session auth** — tokens must be revocable instantly (logout, password reset,
suspension) without a blacklist. The rule that matters: **store only the hash; return the plaintext
to the client exactly once.**

```python
class Token(TimeStampedModel):
    key_hash = models.CharField(max_length=64, unique=True, editable=False)   # SHA-256 hex
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_tokens")
    expires_on = models.DateTimeField()
    last_used_on = models.DateTimeField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    revoked_on = models.DateTimeField(null=True, blank=True)

    objects = TokenQuerySet.as_manager()                # .active(), .stale(grace)

    @classmethod
    def issue(cls, user, *, request=None, ttl=None) -> tuple[str, "Token"]:
        raw = secrets.token_urlsafe(32)                 # 256 bits of entropy
        token = cls.objects.create(user=user, key_hash=cls.hash_key(raw),
                                   expires_on=timezone.now() + (ttl or settings.AUTH_TOKEN_TTL), ...)
        return raw, token                               # plaintext leaves the server once

    @staticmethod
    def hash_key(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()
```

- **Authentication class** (`apps.accounts.authentication.TokenAuthentication`): hash the presented
  key, look up an **active** row (not revoked, not expired), reject suspended users, `touch()` it,
  return `(user, token)`. Its `authenticate_header()` returns `"Token"` so DRF answers **401** (not
  403) for missing/invalid credentials.
- **Sliding expiry**: `touch()` extends `expires_on` and records `last_used_on`/`last_ip`, written at
  most once a minute. TTL from `AUTH_TOKEN_TTL_DAYS` (default 30).
- **Logout revokes** the presented token (`revoked_on`); **password reset revokes all** of the
  user's tokens. A daily task purges tokens expired/revoked for more than 30 days.
- The token hash is excluded from the audit log and never rendered (`__str__`, admin).
- **Signed links** (email verification, one-off downloads) use Django's `signing` /
  `default_token_generator` — not JWT. JWT is acceptable only when a third party requires it, and
  never as the session mechanism.

---

## 3. Authentication classes

`REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` lists the ways a request can authenticate; DRF
tries each in order:

1. **User-token auth** — `TokenAuthentication` above (the primary, and in the scaffold the only, path).
2. **API-key auth** *(add when needed)* — `Authorization: ApiKey <key>` for machine-to-machine;
   store the key hashed, resolve a **tenant-scoped** key, and set `request.organization` directly.
3. **Impersonation** *(add when needed, admin-only)* — a hashed shared secret + `X-User-Id` header
   to act as another user for support; every use is a `SecurityEvent`.

The Django admin uses Django's own **session login** — not a DRF authentication class. Public
endpoints (login, register, password reset, health) set `authentication_classes = []` so a stale
token header can't break them.

---

## 4. Credential flows

All auth endpoints live under `/api/accounts/…` (every API route is under `/api/` — the frontend
proxies and the infra compose forward only `/api/` and `/ws/`):

| Flow | Endpoint | Notes |
|------|----------|-------|
| Register | `POST /api/accounts/register/` | Creates the user (password validators apply), sends `user_registered` (multi-tenant: the org app creates the user's first organization), returns the login payload (201). Gated by the `SIGNUP_ENABLED` Option. |
| Login | `POST /api/accounts/login/` | Email/password → `{token, expires_on, user}`. Bad credentials → 400 `E-C-ACC-0001`; inactive users can't log in. Success and failure are `SecurityEvent`s. |
| Logout | `POST /api/accounts/logout/` | Revokes the presented token → 204. |
| Current user | `GET/PATCH /api/accounts/me/` | Profile read/update (email/role read-only). Multi-tenant clients then call `GET /api/organization/my-orgs/`. |
| Password reset (request) | `POST /api/accounts/password-reset/` | Emails a link `{FRONTEND_URL}/reset-password/<uid>/<token>` (Django's `default_token_generator`, valid `PASSWORD_RESET_TIMEOUT`). **Always 200** (anti-enumeration). |
| Password reset (confirm) | `POST /api/accounts/password-reset/confirm/` | `{uid, token, new_password}` → sets the password, revokes all tokens. Bad link → 400 `E-C-ACC-0003`. |
| Activate *(optional)* | `POST /api/accounts/activate/` | Email confirmation via a signed link or a Redis OTP; flip `email_confirmed`. Add when the product requires verified emails before use. |
| Social login *(optional)* | `POST /api/accounts/oauth/google/` | **Verify the provider ID token server-side** (signature + `aud` + issuer), then get-or-create the user (unusable password) and auto-confirm the email. |
| Check email *(optional)* | `GET /api/accounts/check-email/` | Availability check — throttle it; it inherently reveals existence. |

Reset, activation and invite emails are **enqueued** (`send_email.delay(...)` / the notifications
app), never sent inline — see [background-tasks-and-notifications](background-tasks-and-notifications.md).

**OTP utilities** (only if a project uses OTPs): 6-digit codes in Redis keyed
`otp:{user_id}:{purpose}`, 15-minute TTL, one-time (delete on verify), compared with
`hmac.compare_digest`.

---

## 5. Throttling

Anonymous auth endpoints are throttled with DRF scoped throttles backed by the Redis cache:
`AuthRateThrottle` (`auth`, default `10/min`) on register/login and `PasswordResetRateThrottle`
(`password_reset`, default `5/hour`) on both reset endpoints. Rates come from env
(`THROTTLE_AUTH`, `THROTTLE_PASSWORD_RESET`). Tenant-aware quotas use the core rate limiter pattern
([core-app-reference](core-app-reference.md) §9).

---

## 6. Security checklist for identity

- Passwords hashed with Django's default (PBKDF2) + all four validators; social users get an
  unusable password.
- Tokens: opaque, `secrets.token_urlsafe(32)`, store the SHA-256 only, return plaintext once,
  sliding expiry, revoke on logout / password reset / suspension.
- Anti-enumeration: password reset returns a constant response.
- Social login: verify the provider's ID token **server-side**; never trust a client-decoded profile.
- Record `USER_REGISTERED`, `LOGIN_SUCCEEDED`, `LOGIN_FAILED`, `LOGOUT`, `PASSWORD_RESET_REQUESTED`,
  `PASSWORD_CHANGED` (and `TOKEN_ISSUED`/`TOKEN_REVOKED` for API keys) as `SecurityEvent`s —
  [audit-logging](audit-logging.md).
- Never log tokens, OTPs, reset links or passwords; keep them out of error envelopes and audit
  metadata. `User.password` and `Token.key_hash` are excluded from auditlog.
