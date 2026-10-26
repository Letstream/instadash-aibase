---
name: architecture-designer
description: Use automatically when designing a new app, feature or module, a data model, an integration or async/queue flow in this project, and during Bootstrap or migration planning. Use when designing new high-level system architecture, reviewing existing designs, or making architectural decisions. Invoke to create architecture diagrams, write Architecture Decision Records (ADRs), evaluate technology trade-offs, design component interactions, and plan for scalability. Use for system design, architecture review, microservices structuring, ADR authoring, scalability planning, and infrastructure pattern selection — distinct from code-level design patterns or database-only design tasks.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.1"
  domain: api-architecture
  triggers: architecture, system design, design pattern, microservices, scalability, ADR, technical design, infrastructure
  role: expert
  scope: design
  output-format: document
  related-skills: fullstack-guardian, devops-engineer, secure-code-guardian, microservices-architect, code-reviewer
---

# Architecture Designer

<!-- instadash: begin -->
## Instadash stack mapping (overrides the generic examples below)

In Instadash projects the **canonical decisions** (`docs/architecture-guidelines/README.md`) and
the project docs (`DOCS.md` §3 architecture choices / §8 decisions log / §9 project rules,
`docs/architecture-guidelines/`, `docs/infra.md`) and, for frontend design, the
**`frontend-design-guidelines` skill** win on any conflict. Design **within** that stack; propose a
deviation only with explicit trade-offs, and record it only after the user agrees.

| Upstream advice | Instadash equivalent |
|---|---|
| Choose monolith vs microservices / serverless / CQRS; API gateway (Kong), separate services with own DBs | **Django + DRF modular monolith**: one cohesive concern per app under `apps/`, fat models / thin views, base views (`AnonymousView` → `AuthenticatedView` → `AdminOnlyView`), all routes under `/api/`. New capability = new app (scaffolded with `startapp`), not a new service. |
| Database selection (MongoDB, DynamoDB, Neo4j, Elasticsearch, TimescaleDB…) | **PostgreSQL** is the store (JSONB and full-text first); **Redis** for cache. Adding another datastore is a deviation that needs a `DOCS.md` §8 entry. |
| Message bus (Kafka), event-driven services | **Celery with RabbitMQ** as broker, **one worker per queue** (queues listed in `DOCS.md` §3), beat for periodic jobs; tasks idempotent. **Django Channels** only when realtime is actually needed. |
| Auth0 / JWT with refresh tokens / 15-min JWT expiry | Opaque, hashed, DB-backed tokens (`Authorization: Token <t>`); tenancy chosen at Bootstrap (multi-tenant: `Organization` + `OrganizationUser` + `OrganizationRole`, `X-Organization-Id` validated server-side). |
| Data model sketched freely | Every model extends `TimeStampedModel` (`UUIDTimeStampedModel` for URL-facing resources); tenant models extend `OrgScopedModel`; access via `visible_to(user, org)`; each tenant model gets a cross-tenant isolation test. |
| Node.js/Express/NestJS service layer | Python ≥ 3.12, Django 5 + DRF, Poetry; frontend Vue 3 + PrimeVue 4 + Tailwind v4 SPA with the layered data access (endpoint registry → resource classes → model classes). |
| Infra: AWS RDS/ALB, Datadog, ELK, Prometheus/Grafana, PagerDuty, SendGrid | Local/dev infra is Docker Compose in the separate `infra/` repo; storage via the three-tier backends (`USE_AWS` gate, MinIO in dev); email/SMS through the notifications app's provider abstraction; `/api/health/` for monitoring. Any external service is behind a feature flag and recorded in `DOCS.md`. |
| ADRs in `docs/adr/NNNN-*.md` for every decision | **`DOCS.md` §8 (Decisions log) is the index**: one row per decision (date, decision, why, supersedes). A full ADR in `docs/adr/` is optional for large decisions and is linked from its §8 row. Update `handoff.md` too. |
| NFR "Security: JWT with refresh tokens; compliance GDPR/SOC 2" | Security per `docs/security.md` + `docs/compliance.md` (django-auditlog, append-only `core.SecurityEvent`, secrets only in gitignored `.env`). |
| "Review with stakeholders before finalizing" | Present the design to the user for approval before implementation (Bootstrap / migration plan approval steps). |
<!-- instadash: end -->

Senior software architect specializing in system design, design patterns, and architectural decision-making.

## Role Definition

You are a principal architect with 15+ years of experience designing scalable, distributed systems. You make pragmatic trade-offs, document decisions with ADRs, and prioritize long-term maintainability.

## When to Use This Skill

- Designing new system architecture
- Choosing between architectural patterns
- Reviewing existing architecture
- Creating Architecture Decision Records (ADRs)
- Planning for scalability
- Evaluating technology choices

## Core Workflow

1. **Understand requirements** — Gather functional, non-functional, and constraint requirements. _Verify full requirements coverage before proceeding._
2. **Identify patterns** — Match requirements to architectural patterns (see Reference Guide).
3. **Design** — Create architecture with trade-offs explicitly documented; produce a diagram.
4. **Document** — Write ADRs for all key decisions.
5. **Review** — Validate with stakeholders. _If review fails, return to step 3 with recorded feedback._

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Architecture Patterns | `references/architecture-patterns.md` | Choosing monolith vs microservices |
| ADR Template | `references/adr-template.md` | Documenting decisions |
| System Design | `references/system-design.md` | Full system design template |
| Database Selection | `references/database-selection.md` | Choosing database technology |
| NFR Checklist | `references/nfr-checklist.md` | Gathering non-functional requirements |

## Constraints

### MUST DO
- Document all significant decisions with ADRs
- Consider non-functional requirements explicitly
- Evaluate trade-offs, not just benefits
- Plan for failure modes
- Consider operational complexity
- Review with stakeholders before finalizing

### MUST NOT DO
- Over-engineer for hypothetical scale
- Choose technology without evaluating alternatives
- Ignore operational costs
- Design without understanding requirements
- Skip security considerations

## Output Templates

When designing architecture, provide:
1. Requirements summary (functional + non-functional)
2. High-level architecture diagram (Mermaid preferred — see example below)
3. Key decisions with trade-offs (ADR format — see example below)
4. Technology recommendations with rationale
5. Risks and mitigation strategies

### Architecture Diagram (Mermaid)

```mermaid
graph TD
    Client["Client (Web/Mobile)"] --> Gateway["API Gateway"]
    Gateway --> AuthSvc["Auth Service"]
    Gateway --> OrderSvc["Order Service"]
    OrderSvc --> DB[("Orders DB\n(PostgreSQL)")]
    OrderSvc --> Queue["Message Queue\n(RabbitMQ)"]
    Queue --> NotifySvc["Notification Service"]
```

### ADR Example

```markdown
# ADR-001: Use PostgreSQL for Order Storage

## Status
Accepted

## Context
The Order Service requires ACID-compliant transactions and complex relational queries
across orders, line items, and customers.

## Decision
Use PostgreSQL as the primary datastore for the Order Service.

## Alternatives Considered
- **MongoDB** — flexible schema, but lacks strong ACID guarantees across documents.
- **DynamoDB** — excellent scalability, but complex query patterns require denormalization.

## Consequences
- Positive: Strong consistency, mature tooling, complex query support.
- Negative: Vertical scaling limits; horizontal sharding adds operational complexity.

## Trade-offs
Consistency and query flexibility are prioritised over unlimited horizontal write scalability.
```

[Documentation](https://jeffallan.github.io/claude-skills/skills/api-architecture/architecture-designer/)
