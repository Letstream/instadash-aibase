---
name: database-optimizer
description: Use automatically when adding or changing Django model fields, indexes, constraints or migrations, when writing QuerySets that filter, sort or aggregate over large or tenant-scoped tables, when an endpoint or report is slow, and when reviewing N+1 or query-count problems (PostgreSQL 17). Optimizes database queries and improves performance across PostgreSQL and MySQL systems. Use when investigating slow queries, analyzing execution plans, or optimizing database performance. Invoke for index design, query rewrites, configuration tuning, partitioning strategies, lock contention resolution.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.1"
  domain: infrastructure
  triggers: database optimization, slow query, query performance, database tuning, index optimization, execution plan, EXPLAIN ANALYZE, database performance, PostgreSQL optimization, MySQL optimization
  role: specialist
  scope: optimization
  output-format: analysis-and-code
  related-skills: devops-engineer, postgres-pro, graphql-architect
---

# Database Optimizer

<!-- instadash: begin -->
## Instadash stack mapping (overrides the generic examples below)

The examples in this skill are raw SQL for PostgreSQL **and** MySQL, applied directly to a server.
In Instadash projects (PostgreSQL 17, Django ORM, schema only via migrations) the **canonical
decisions** (`docs/architecture-guidelines/README.md`), the backend guideline pages and the project
`DOCS.md` win on any conflict:

| Upstream advice | Instadash equivalent |
|---|---|
| MySQL sections and `references/mysql-tuning.md` | Not applicable — PostgreSQL 17 only. Ignore MySQL advice. |
| Apply `CREATE INDEX [CONCURRENTLY] …` / `INCLUDE` / partial / expression / GIN indexes directly as SQL | Declare indexes on the model's `Meta.indexes` — `models.Index(fields=[…], include=[…], condition=Q(…), name=…)`, expression indexes (`models.Index(Lower("email"), name=…)`), `GinIndex` / `OpClass` from `django.contrib.postgres` — then generate the migration with `makemigrations <app>`. Never hand-write a migration or run DDL outside migrations. |
| "Create indexes with `CONCURRENTLY` to avoid table locks" | Plain `AddIndex` is the default. For a large, live table, switching the generated migration to `AddIndexConcurrently` with `atomic = False` is an explicit, reviewed decision — propose it, don't do it silently. |
| Partial index `WHERE created_at > NOW() - INTERVAL '30 days'` (`references/index-strategies.md`) | Invalid in PostgreSQL (index predicates must be immutable) — never use a moving time window in `condition`; use a status/flag predicate instead. |
| Index design by selectivity only | Tenant tables are always filtered by `organization` via `visible_to(user, org)`: composite indexes lead with it (`models.Index(fields=["organization", "-created_on"])`). `TimeStampedModel.created_on` is already indexed — don't duplicate it. |
| `ALTER SYSTEM SET …`, `postgresql.conf` tuning for a "16GB RAM server", `max_connections` (`references/postgresql-tuning.md`) | Server parameters are infra, not app code: `infra/` compose (`postgres:17-alpine`, e.g. `command: postgres -c …`) or the managed DB's parameter group. Recommend values with evidence; don't apply them from the app. App side: `CONN_MAX_AGE=0` (ASGI) + a pooler such as pgbouncer, `CONN_HEALTH_CHECKS=True`; per-connection `statement_timeout` via `DATABASES["OPTIONS"]` only as a project decision. |
| `CREATE EXTENSION pg_stat_statements / pg_trgm / pg_buffercache` | `pg_stat_statements` needs `shared_preload_libraries` → infra config. App-used extensions (`pg_trgm`, …) via `django.contrib.postgres.operations` (`TrigramExtension`, `CreateExtension`) in a migration created with `makemigrations --empty <app>`. |
| Maintenance/tuning commands: `pg_stat_statements_reset()`, `pg_stat_reset()`, `VACUUM FULL`, `REINDEX`, dropping partitions, `SET enable_seqscan = off`, `synchronous_commit = 'off'` | Local/dev database only unless the user explicitly approves running them against a shared or production DB. Never disable `synchronous_commit` (durability of business data and the audit trail). |
| "Run `EXPLAIN ANALYZE`" on raw SQL | `EXPLAIN ANALYZE` **executes** the statement. From Django use `queryset.explain(analyze=True, buffers=True)` on SELECTs; wrap any DML analysis in a transaction that is rolled back. Catch N+1 in tests with pytest-django's `django_assert_num_queries` / `CaptureQueriesContext`. |
| Query rewrites in SQL (EXISTS instead of IN, window functions, CTEs, subqueries) | Express them in the ORM: `Exists(OuterRef(…))`, `Subquery`, `Window`, `annotate()/aggregate()`, `select_related`/`prefetch_related`, `only()/defer()`. Raw SQL only when the ORM can't, and only as `cursor.execute(sql, params)` — never string-built. Put reusable query logic on custom QuerySets. |
| Keyset pagination instead of `OFFSET` | `StandardPagination` (limit/offset) is the global default. For very large or infinite lists, switch that endpoint to DRF `CursorPagination` ordered by (`created_on`, `id`) — a per-view decision. |
| `LIKE '%term%'` → full-text/trigram indexes | DRF `search_fields` generate `icontains`: back hot search columns with a trigram `GinIndex(opclasses=["gin_trgm_ops"])` or use `SearchVector`/`SearchQuery` with a GIN index. |
| Native table partitioning | Not managed by Django migrations; it's an architecture decision (record it in `DOCS.md`). Exhaust indexes, query fixes and archival/retention first. |
| Monitoring queries over `pg_stat_activity` / `pg_stat_statements` (query text, `client_addr`) and "Automate alerts (Prometheus, Grafana, Datadog)" | Output can contain PII/secrets inside query text — don't paste it into docs, tickets or logs. Monitoring stack is a project decision; the baseline is Sentry + the `/api/health/` endpoint. |
<!-- instadash: end -->

Senior database optimizer with expertise in performance tuning, query optimization, and scalability across multiple database systems.

## When to Use This Skill

- Analyzing slow queries and execution plans
- Designing optimal index strategies
- Tuning database configuration parameters
- Optimizing schema design and partitioning
- Reducing lock contention and deadlocks
- Improving cache hit rates and memory usage

## Core Workflow

1. **Analyze Performance** — Capture baseline metrics and run `EXPLAIN ANALYZE` before any changes
2. **Identify Bottlenecks** — Find inefficient queries, missing indexes, config issues
3. **Design Solutions** — Create index strategies, query rewrites, schema improvements
4. **Implement Changes** — Apply optimizations incrementally with monitoring; validate each change before proceeding to the next
5. **Validate Results** — Re-run `EXPLAIN ANALYZE`, compare costs, measure wall-clock improvement, document changes

> ⚠️ Always test changes in non-production first. Revert immediately if write performance degrades or replication lag increases.

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Query Optimization | `references/query-optimization.md` | Analyzing slow queries, execution plans |
| Index Strategies | `references/index-strategies.md` | Designing indexes, covering indexes |
| PostgreSQL Tuning | `references/postgresql-tuning.md` | PostgreSQL-specific optimizations |
| MySQL Tuning | `references/mysql-tuning.md` | MySQL-specific optimizations |
| Monitoring & Analysis | `references/monitoring-analysis.md` | Performance metrics, diagnostics |

## Common Operations & Examples

### Identify Top Slow Queries (PostgreSQL)
```sql
-- Requires pg_stat_statements extension
SELECT query,
       calls,
       round(total_exec_time::numeric, 2)  AS total_ms,
       round(mean_exec_time::numeric, 2)   AS mean_ms,
       round(stddev_exec_time::numeric, 2) AS stddev_ms,
       rows
FROM   pg_stat_statements
ORDER  BY mean_exec_time DESC
LIMIT  20;
```

### Capture an Execution Plan
```sql
-- Use BUFFERS to expose cache hit vs. disk read ratio
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT o.id, c.name
FROM   orders o
JOIN   customers c ON c.id = o.customer_id
WHERE  o.status = 'pending'
  AND  o.created_at > now() - interval '7 days';
```

### Reading EXPLAIN Output — Key Patterns to Find

| Pattern | Symptom | Typical Remedy |
|---------|---------|----------------|
| `Seq Scan` on large table | High row estimate, no filter selectivity | Add B-tree index on filter column |
| `Nested Loop` with large outer set | Exponential row growth in inner loop | Consider Hash Join; index inner join key |
| `cost=... rows=1` but actual rows=50000 | Stale statistics | Run `ANALYZE <table>;` |
| `Buffers: hit=10 read=90000` | Low buffer cache hit rate | Increase `shared_buffers`; add covering index |
| `Sort Method: external merge` | Sort spilling to disk | Increase `work_mem` for the session |

### Create a Covering Index
```sql
-- Covers the filter AND the projected columns, eliminating a heap fetch
CREATE INDEX CONCURRENTLY idx_orders_status_created_covering
    ON orders (status, created_at)
    INCLUDE (customer_id, total_amount);
```

### Validate Improvement
```sql
-- Before optimization: save plan & timing
EXPLAIN (ANALYZE, BUFFERS) <query>;   -- note "Execution Time: X ms"

-- After optimization: compare
EXPLAIN (ANALYZE, BUFFERS) <query>;   -- target meaningful reduction in cost & time

-- Confirm index is actually used
SELECT indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM   pg_stat_user_indexes
WHERE  relname = 'orders';
```

### MySQL: Find Slow Queries
```sql
-- Inspect slow query log candidates
SELECT * FROM performance_schema.events_statements_summary_by_digest
ORDER  BY SUM_TIMER_WAIT DESC
LIMIT  20;

-- Execution plan
EXPLAIN FORMAT=JSON
SELECT * FROM orders WHERE status = 'pending' AND created_at > NOW() - INTERVAL 7 DAY;
```

## Constraints

### MUST DO
- Capture `EXPLAIN (ANALYZE, BUFFERS)` output **before** optimizing — this is the baseline
- Measure performance before and after every change
- Create indexes with `CONCURRENTLY` (PostgreSQL) to avoid table locks
- Test in non-production; roll back if write performance or replication lag worsens
- Document all optimization decisions with before/after metrics
- Run `ANALYZE` after bulk data changes to refresh statistics

### MUST NOT DO
- Apply optimizations without a measured baseline
- Create redundant or unused indexes
- Make multiple changes simultaneously (impossible to attribute impact)
- Ignore write amplification caused by new indexes
- Neglect `VACUUM` / statistics maintenance

## Output Templates

When optimizing database performance, provide:
1. Performance analysis with baseline metrics (query time, cost, buffer hit ratio)
2. Identified bottlenecks and root causes (with EXPLAIN evidence)
3. Optimization strategy with specific changes
4. Implementation SQL / config changes
5. Validation queries to measure improvement
6. Monitoring recommendations

[Documentation](https://jeffallan.github.io/claude-skills/skills/infrastructure/database-optimizer/)
