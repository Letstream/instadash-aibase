<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# SOC 2 Readiness — control mapping

> Projects built from this base implement the **technical controls** a SOC 2 (Trust Services
> Criteria) audit expects. This maps each control to where it lives. Certification also needs
> organisation-level process evidence (policies, vendor reviews, pen tests) owned by the legal
> entity in [`DOCS.md`](../DOCS.md) — out of scope for code but listed below. See [security](./security.md).

## Security (Common Criteria)

| Control | Implementation |
|---|---|
| **Logical access / RBAC** | Multi-tenant: `OrganizationRole` permission codes checked by `HasOrgPermission` per view. Single-tenant: user `role` + `HasRole`. Least privilege per endpoint. [multi-tenancy](./architecture-guidelines/backend/multi-tenancy.md) |
| **Tenant isolation** | Tenant data extends `OrgScopedModel`; querysets via `visible_to(user, org)`; object-level `is_accessible_by`; tenant header validated server-side; cross-tenant isolation test per model. |
| **Authentication** | Hashed, expiring, revocable DB tokens; Django password hashing + validators; server-side Google ID-token verification; throttled auth endpoints. [accounts-and-auth](./architecture-guidelines/backend/accounts-and-auth.md) |
| **Encryption in transit** | Prod: HSTS, `SECURE_PROXY_SSL_HEADER`, secure cookies, TLS terminated at the ingress. |
| **Encryption at rest** | Integration secrets via a Fernet `SecretBox` in core. DB/disk/bucket encryption is a deployment control. |
| **Audit logging** | `django-auditlog`: model change history with actor (`AuditActorMiddleware`); append-only `core.SecurityEvent` for security events (login success/failure, logout, token issue/revoke, role/permission change, invite, export, hard delete, integration connect). Read-only; no update/delete API; retention via a periodic flush. [audit-logging](./architecture-guidelines/backend/audit-logging.md) |
| **Change management** | Git (separate `backend`/`frontend`/`infra` repos), reviewed merges, CI lint + tests, command-generated migrations, docs updated per change (`handoff.md`). |
| **Vulnerability management** | `nh3` sanitisation, ORM-only queries, webhook signature checks, lockfiles (Poetry/npm), dependency audits, `/security-review` in QA. |
| **Monitoring** | `/api/health/` (DB + Redis + broker), structured logs, optional Sentry (`send_default_pii=False`). |

## Availability
- Health checks, Celery for async/retryable work (one worker per queue), stateless token auth,
  horizontally scalable web tier. Backups and DR are deployment controls (document them in `infra/`).

## Confidentiality
- Private per-tenant object storage + presigned URLs; secrets only in `.env` / encrypted columns;
  no secrets in logs or docs; CORS allowlist in prod.

## Processing integrity
- Server-side validation (DRF serializers), DB constraints (unique, FKs), atomic transactions for
  multi-row operations, idempotent tasks and webhook processing (dedupe by external id).

## Privacy
- Minimal PII; `send_default_pii=False`; per-user data export and erasure (hard delete, audit-logged)
  when the product handles personal data. Retention/consent policy is an organisation control.

## Not code (organisation process evidence still required)
Security policies, risk assessment, vendor management, background checks, incident response and
BCP/DR runbooks, access reviews, and an independent audit.
