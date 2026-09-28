<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Security

Practices enforced across every project built from this base. See [`AGENTS.md`](../AGENTS.md)
§Security, [conventions](./conventions.md), [compliance](./compliance.md), and the backend pages
[accounts-and-auth](./architecture-guidelines/backend/accounts-and-auth.md),
[multi-tenancy](./architecture-guidelines/backend/multi-tenancy.md),
[audit-logging](./architecture-guidelines/backend/audit-logging.md),
[storage-and-media](./architecture-guidelines/backend/storage-and-media.md).

## Secrets management
- All secrets in **gitignored** `.env` files (`backend/.env`, `infra/.env`); only `.env.example`
  (placeholders) is committed. No credentials/tokens/keys in code, docs (`DOCS.md` records *where*
  a secret lives, never its value), logs, or error output.
- Credentials for local services are collected at [Bootstrap](./bootstrap/interview.md) and written straight
  to `.env`. Generated passwords use `openssl rand`.
- **Integration secrets encrypted at rest** — a Fernet `SecretBox` in core (added when the project
  first stores third-party credentials; key from `FIELD_ENCRYPTION_KEY`). Never stored in plaintext.
- Infra least-privilege: RabbitMQ uses a dedicated per-project user scoped to the project vhost
  (never `guest`); a dedicated DB user per project and environment.

## Tenancy & authorization

The project's mode is recorded in `DOCS.md` §3.

**Multi-tenant** (the #1 leak vector — treat every change as security-relevant):
- Tenant data extends `OrgScopedModel`; every list/detail queryset is filtered by the caller's
  **verified** membership via `Model.objects.visible_to(user, org)`.
- The active tenant comes from the `X-Organization-Id` header and is validated against
  `OrganizationUser` by the tenant middleware — **never** trusted from the client for authorization.
- Authorization is declarative permission codes on views (`org_permissions = ["order:read"]`)
  checked by `HasOrgPermission` against the member's `OrganizationRole`.
- Writes call `obj.is_accessible_by(user)` before mutating; cross-links re-check both ends share
  the tenant.
- Every tenant model has a **cross-tenant isolation test** ([testing](./architecture-guidelines/backend/testing.md)).

**Single-tenant:**
- No org tables; a `role` on the user with the hierarchy `owner > admin > member > guest`, checked
  by `HasRole(<min role>)`. Everything else (object checks, audit) still applies.

## AuthN
- **Opaque, DB-backed tokens** — `Authorization: Token <token>`. Only a **hash** of the token is
  stored; the raw token is shown once at login. Tokens expire, are revocable (logout / password
  change / admin revoke), and issuance/revocation is audit-logged.
- **Passwords**: Django PBKDF2 hashing + validators. Social-login users get unusable passwords.
- **Google Sign-In** (if enabled): the client sends a Google **ID token**; the server verifies the
  signature, `aud == GOOGLE_OAUTH_CLIENT_ID` and the issuer with `google.oauth2.id_token`, then issues
  a normal DB token.
- **Throttling**: DRF scoped throttles on auth endpoints (login / register / password reset /
  social) to blunt brute force. Session auth is for the Django admin only.

## Untrusted input
- **Rich text** HTML is sanitized server-side with **`nh3`** (allowlist) before persisting any
  `*_html` field; the canonical content is structured (JSON) where an editor is used.
- **File uploads**: size cap + mime allowlist; stored under a per-tenant key; filenames sanitized;
  served only via presigned URLs.
- **ORM only** — no string-built SQL.
- **Webhooks**: verify the provider signature (e.g. `X-Hub-Signature-256`) before enqueuing, and
  dedupe by delivery id.

## Storage
- Private media → **private** S3 (`AWS_DEFAULT_ACL=None`), keys prefixed per tenant
  (`private/org/<org_id>/…`). Access via short-lived presigned URLs. No public buckets.
- Dev can point boto3 at local **MinIO** to exercise the same path.

## Audit
- `django-auditlog` records create/update/delete on registered models, with the actor captured by
  `AuditActorMiddleware` (auditlog's own middleware runs before token auth and would miss it).
- Security events (login success/failure, logout, token issue/revoke, role/permission changes,
  invites, exports, hard deletes, integration connects) go to the append-only `core.SecurityEvent`
  via `SecurityEvent.record()`. Sensitive fields (passwords, token hashes, secrets) are never logged.
  Both are read-only in admin and never exposed for update/delete.

## Transport & production
- `DEBUG=False`; HSTS; `SECURE_PROXY_SSL_HEADER`; secure/HTTPOnly cookies; `CONTENT_TYPE_NOSNIFF`.
- CORS: allow-all only in `local`; elsewhere a `CORS_ALLOWED_ORIGINS` allowlist, with
  `X-Organization-Id` in `CORS_ALLOW_HEADERS` for multi-tenant projects.
- No stack traces to clients (the envelope returns a generic 500). Sentry optional with
  `send_default_pii=False`.
