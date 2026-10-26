---
name: test-master
description: Use automatically whenever writing or changing code in this project that needs tests (backend pytest + pytest-django, frontend Vitest), when fixing a bug (regression test first), and whenever tests, coverage thresholds or type-checked specs fail. Generates test files, creates mocking strategies, analyzes code coverage, designs test architectures, and produces test plans and defect reports across functional, performance, and security testing disciplines. Use when writing unit tests, integration tests, or E2E tests; creating test strategies or automation frameworks; analyzing coverage gaps; performance testing with k6 or Artillery; security testing with OWASP methods; debugging flaky tests; or working on QA, regression, test automation, quality gates, shift-left testing, or test maintenance.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.1"
  domain: quality
  triggers: test, testing, QA, unit test, integration test, E2E, coverage, performance test, security test, regression, test strategy, test automation, test framework, quality metrics, defect, exploratory, usability, accessibility, localization, manual testing, shift-left, quality gate, flaky test, test maintenance
  role: specialist
  scope: testing
  output-format: report
  related-skills: fullstack-guardian, playwright-expert, devops-engineer, debugging-wizard, code-reviewer, feature-forge
---

# Test Master

<!-- instadash: begin -->
## Instadash stack mapping (overrides the generic examples below)

In Instadash projects the **canonical decisions** (`docs/architecture-guidelines/README.md`), the
project docs (`DOCS.md`, `docs/architecture-guidelines/backend/testing.md`,
`docs/architecture-guidelines/frontend/testing.md`, `docs/qa.md`) and the
**`frontend-design-guidelines` skill** win on any conflict with this skill or its references.

| Upstream advice | Instadash equivalent |
|---|---|
| Jest (`jest.fn`, `jest.mock`, `jest.Mocked`) | Frontend: **Vitest** (`vi.fn`, `vi.mock`, globals off — import from `vitest`) + `@vue/test-utils` + `@pinia/testing` + jsdom. Specs in a `__tests__/` folder next to the unit (`src/**/__tests__/*.spec.ts`), DTO builders in `src/test/factories.ts`. |
| Supertest / `httpx.AsyncClient` / FastAPI-style 422, `db.query('DELETE FROM users')` | Backend: **pytest + pytest-django** (+ pytest-mock, `ddf`), DRF `APIClient` via the `conftest.py` fixtures (`auth_client`, `org_client`, `auth_client_factory`); real PostgreSQL test DB managed by pytest-django (`django_db` mark, no manual cleanup). Validation errors are **400** with the envelope `{status:false, err_cd, err_msg, error}` — assert `err_cd`, not just the status. `tests/` package per app. |
| Mock repositories / fake API clients generally | Backend: real DB objects for our own models; mock only boundaries (email/HTTP providers, `.delay`) where the name is looked up. Frontend: fake `ApiClient` injected into resources, or `vi.mock("@/api/resources")` for stores — never real HTTP. |
| Playwright/Cypress E2E, cross-browser matrix, `/api/test/seed` endpoints, Screenplay/page objects, sharded CI (`references/e2e-testing.md`, `automation-frameworks.md`, a11y via Playwright + axe) | **Do not add Playwright/Cypress.** Browser flows and visuals (light + dark, console, network) are verified by driving the running app in Chrome via **Chrome DevTools MCP** during QA (`docs/qa.md`), screenshots in `shots/`. No test-only seed endpoints in the app. |
| `Authorization: Bearer <jwt>`, expired/tampered-JWT tests | `Authorization: Token <t>` (opaque DB token): test missing/invalid/revoked/expired tokens → 401, plus `X-Organization-Id` of a foreign org → 403. |
| IDOR "other user's resources" check | **Mandatory cross-tenant isolation test for every tenant model and endpoint** (queryset level *and* API level: list never leaks, foreign detail/update → 403/404), plus RBAC permission-code tests. |
| Coverage ">80%" generic | Backend `fail_under = 80` (`make test`); frontend thresholds lines/functions/statements **80 %**, branches **75 %** on the unit-testable layers (`npm run test:coverage`). Don't lower the bar — add tests. |
| "If you wrote code before a failing test, delete it and start over" (TDD iron laws) | Write the test first where practical and **always** start a bug fix with a failing regression test; never delete user-written code to satisfy TDD — add the missing tests instead. |
| Flaky tests: "add retry or stabilization logic" | Fix the root cause (ordering, time, async, shared state); no retries in unit tests. Use `vi.useFakeTimers()` / pytest-django `settings`, no sleeping or network. |
| k6/Artillery load tests with hardcoded credentials | Optional and out of the default suite; if a project adds them, record it in `DOCS.md` §8 and read credentials from env, never commit them. |
| Security tests: SQLi → 400, XSS stripped | ORM prevents SQLi (assert no 500/leak rather than a specific 400); rich text is sanitised server-side with `nh3`; frontend never uses `v-html` with API data. See the `secure-code-guardian` skill. |
| GitHub Actions / generic CI | Local == CI: `make lint`, `make check`, `make test` (backend) and `npm run lint`, `npm run type-check`, `npm run test:coverage` (frontend). |
<!-- instadash: end -->

Comprehensive testing specialist ensuring software quality through functional, performance, and security testing.

## Core Workflow

1. **Define scope** — Identify what to test and which testing types apply
2. **Create strategy** — Plan the test approach across functional, performance, and security perspectives
3. **Write tests** — Implement tests with proper assertions (see example below)
4. **Execute** — Run tests and collect results
   - If tests fail: classify the failure (assertion error vs. environment/flakiness), fix root cause, re-run
   - If tests are flaky: isolate ordering dependencies, check async handling, add retry or stabilization logic
5. **Report** — Document findings with severity ratings and actionable fix recommendations
   - Verify coverage targets are met before closing; flag gaps explicitly

## Quick-Start Example

A minimal Jest unit test illustrating the key patterns this skill enforces:

```js
// ✅ Good: meaningful description, specific assertion, isolated dependency
describe('calculateDiscount', () => {
  it('applies 10% discount for premium users', () => {
    const result = calculateDiscount({ price: 100, userTier: 'premium' });
    expect(result).toBe(90); // specific outcome, not just truthy
  });

  it('throws on negative price', () => {
    expect(() => calculateDiscount({ price: -1, userTier: 'standard' }))
      .toThrow('Price must be non-negative');
  });
});
```

Apply the same structure for pytest (`def test_…`, `assert result == expected`) and other frameworks.

## Reference Guide

Load detailed guidance based on context:

<!-- TDD Iron Laws and Testing Anti-Patterns adapted from obra/superpowers by Jesse Vincent (@obra), MIT License -->

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Unit Testing | `references/unit-testing.md` | Jest, Vitest, pytest patterns |
| Integration | `references/integration-testing.md` | API testing, Supertest |
| E2E | `references/e2e-testing.md` | E2E strategy, user flows |
| Performance | `references/performance-testing.md` | k6, load testing |
| Security | `references/security-testing.md` | Security test checklist |
| Reports | `references/test-reports.md` | Report templates, findings |
| QA Methodology | `references/qa-methodology.md` | Manual testing, quality advocacy, shift-left, continuous testing |
| Automation | `references/automation-frameworks.md` | Framework patterns, scaling, maintenance, team enablement |
| TDD Iron Laws | `references/tdd-iron-laws.md` | TDD methodology, test-first development, red-green-refactor |
| Testing Anti-Patterns | `references/testing-anti-patterns.md` | Test review, mock issues, test quality problems |

## Constraints

**MUST DO**
- Test happy paths AND error/edge cases (e.g., empty input, null, boundary values)
- Mock external dependencies — never call real APIs or databases in unit tests
- Use meaningful `it('…')` descriptions that read as plain-English specifications
- Assert specific outcomes (`expect(result).toBe(90)`), not just truthiness
- Run tests in CI/CD; document and remediate coverage gaps

**MUST NOT**
- Skip error-path testing (e.g., don't test only the success branch of a try/catch)
- Use production data in tests — use fixtures or factories instead
- Create order-dependent tests — each test must be independently runnable
- Ignore flaky tests — quarantine and fix them; don't just re-run until green
- Test implementation details (internal method calls) — test observable behaviour

## Output Templates

When creating test plans, provide:
1. Test scope and approach
2. Test cases with expected outcomes
3. Coverage analysis
4. Findings with severity (Critical/High/Medium/Low)
5. Specific fix recommendations

[Documentation](https://jeffallan.github.io/claude-skills/skills/quality/test-master/)
