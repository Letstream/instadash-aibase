<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# QA — required before "done"

> The project must **run bug-free** and be **visually verified in Chrome**. Do multiple passes.
> See [AGENTS.md §QA](../AGENTS.md). The journeys to exercise are the project's **core journeys**
> in [`DOCS.md`](../DOCS.md) §6 plus whatever the current task touched.

## 0. Automated gates (run first — cheapest signal)
```bash
cd backend  && make lint && make test                 # black/ruff/codespell + pytest (with coverage)
cd frontend && npm run lint && npm run type-check && npm run test
```
- Backend tests: [backend/testing](./architecture-guidelines/backend/testing.md). Every tenant model
  has a cross-tenant isolation test; every endpoint has happy + error-path tests asserting the envelope.
- Frontend tests (Vitest): [frontend/testing](./architecture-guidelines/frontend/testing.md) —
  models, resources, stores, composables, utils, guards.
- New code without tests is not done.

## 1. Bring the stack up (backgrounded)
```bash
scripts/dev.sh                       # data services check/start + backend + celery + beat + vite
scripts/dev.sh logs                  # tail -n 40 of each — no tracebacks
curl -si localhost:<BACKEND_PORT>/api/health/  # 200, envelope status:true, header X-Letstream-Instadash-Version
```
Backend sanity: `poetry run python app/manage.py check` clean; `migrate --check` shows nothing pending.
Load seed/demo data if the project has a seed command, so screens are populated.

Optionally, before a release: `cd infra && docker compose --profile app up -d --build` and repeat
§2 against the containerised stack ([infra](./infra.md)).

## 2. Driving Chrome (Chrome DevTools MCP)
Tools: `mcp__plugin_chrome-devtools-mcp_chrome-devtools__*` — `new_page`, `navigate_page`,
`take_snapshot` (a11y tree; use its `uid`s), `click`, `fill`, `fill_form`, `press_key`,
`take_screenshot`, `list_console_messages`, `list_network_requests`, `evaluate_script`, `wait_for`,
`resize_page`, `lighthouse_audit`. Skills: `chrome-devtools`, `a11y-debugging`.

Loop:
1. `new_page` → `navigate_page` to `http://localhost:<FRONTEND_PORT>`.
2. `take_snapshot` → act by `uid` (`click` / `fill` / `press_key`).
3. After each step: `list_console_messages` (no errors) and `take_screenshot` → `shots/NN_<journey>.png`.
4. `list_network_requests` — `/api/...` calls return the envelope with `status:true`; auth header is
   `Token …`; multi-tenant calls carry `X-Organization-Id`.
5. Repeat in **light and dark** theme and at a narrow viewport (`resize_page` ~390px).

## 3. Journeys (each must pass, screenshot each)
Baseline (every project):
1. **Auth** — register → log in → log out → log back in; wrong password shows a clean error;
   401 on an expired/revoked token returns to login.
2. **Tenant** (multi-tenant only) — create/switch organisation; data changes with the switch; a
   user without membership gets 403, not data.
3. **Roles** — a lower role can't see/do admin actions (UI hidden **and** API 403).
4. **Empty/error states** — lists with no data, failed requests, validation errors render cleanly.

Then every journey in `DOCS.md` §6 and the flows the current task touched.

## 4. License headers
Run the missing-header check in [license-header.md](./bootstrap/license-header.md#checking) — the list must be empty.

## 5. Reviews & audits
- `/security-review` and `/code-review` on the diff.
- `security-reviewer` skill on the task's diff (static; always) — Critical/High fixed before "done".
- Before a release: `/ship-gate`; `security-reviewer` full pass with a report in
  `docs/security/reviews/`; SOC 2 spot-check against the [compliance](./compliance.md) checklist
  (auditlog wired, RBAC, isolation tests, no secrets committed); `lighthouse_audit` on key pages.

## 6. Record
Update `handoff.md`: each journey ✅ only after observing it work, plus test results and any
console/network errors found. **Never report green on red.**
