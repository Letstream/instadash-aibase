<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Frontend Testing

> **Vitest for everything unit-testable; Chrome DevTools MCP for browser flows and visuals.** No
> Playwright/Cypress suite. The runnable setup and ~80 example specs are in the
> [frontend scaffold](../../bootstrap/scaffold/frontend/README.md). See also
> [project-structure](project-structure.md) and the `frontend-design-guidelines` skill.

---

## 1. Stack

| Tool | Role |
|------|------|
| **Vitest** (`vitest.config.ts` reuses `vite.config.ts`) | runner, assertions, mocks (`vi`), fake timers, v8 coverage |
| **jsdom** | DOM environment (`test.environment: "jsdom"`) |
| **@vue/test-utils** | `mount`, `flushPromises`, global plugins |
| **@pinia/testing** | `createTestingPinia` for component tests (actions stubbed) |
| `vi.mock` / fake `ApiClient` | HTTP is never real: mock the resource module, inject a fake client, or spy on `api.get`. `msw` is an acceptable alternative for request-level tests. |

Globals are **off** — import `describe/it/expect/vi` from `vitest` explicitly (and pass
`createSpy: vi.fn` to `createTestingPinia`).

`src/test/setup.ts` installs PrimeVue (`unstyled: true`), vue-i18n and the tooltip directive for
every mounted component and clears `localStorage` after each test. `src/test/factories.ts` holds
DTO builders (`userDto()`, `organizationDto()`) — override only what a test cares about.

## 2. Layout & commands

- Specs live in a **`__tests__/` folder next to the unit**: `src/models/__tests__/User.spec.ts`,
  `src/components/GenericList/__tests__/FormatCell.spec.ts`. Vitest `include`:
  `src/**/__tests__/**/*.spec.ts`. (One convention only — no co-located `*.spec.ts` beside sources.)
- Specs are type-checked (`tsconfig.vitest.json`, part of `npm run type-check`) and linted.

```bash
npm run test            # vitest run (CI + before "done")
npm run test:watch      # while developing
npm run test:coverage   # v8 coverage with thresholds
```

**Coverage** is measured on the unit-testable layers only — `src/api`, `src/config`,
`src/models`, `src/stores`, `src/utils`, `src/composables`, `src/router/guards.ts`, and shells'
`helpers/` + `composables/` — with thresholds **lines/functions/statements 80 %, branches 75 %**.
A PR that drops below fails. Views/layouts are covered by QA in Chrome instead.

## 3. What to test (everything unit-testable)

| Unit | Test | Technique |
|------|------|-----------|
| Utils / formatters | pure input → output, edge cases (null, junk, locale) | plain calls; `vi.useFakeTimers()` for debounce |
| **Model classes** | `fromJson` maps every field (+ defaults for missing ones), `toJson` round-trip of writable fields, getters/methods (`fullName`, `can()`, `hasRoleAtLeast`) | plain calls with factories |
| **API resources** | right path/method/params, DTO → model instances, both list shapes, list-only resources fail loudly on detail calls | construct with a **fake `ApiClient`** (constructor injection) |
| http layer | header injection (token, tenant, tz; none for foreign origins), envelope unwrap, `ApiError` parsing, 401/403 hooks fire | call the exported interceptor functions directly |
| **Pinia stores** | actions (login/logout/ensureSession/selectOrganization), persistence, **RBAC getters** (`hasPermission` with string / AND array / `{keys, operator}`, owner, `"*"`) | real `createPinia()` + `vi.mock("@/api/resources")` |
| Tenancy toggle | single-tenant behaviour (no org calls, user permissions) | `vi.mock("@/config/app")` returning `new AppConfig({ VITE_TENANCY_MODE: "single" })` |
| Composables | state transitions, URL sync, debounce, race handling, errors | mount a tiny host component with a **memory-history router** |
| Router guards | public, anonymous → login `?next`, guest-only bounce, tenant validation, permission gate, `safeNext` | call `authGuard(to)` with a fake `RouteLocationNormalized` |
| Small components | rendering per prop/type, emitted events, store calls | `mount` (+ `createTestingPinia` when a store is involved) |

Keep specs about **behaviour**, not markup snapshots. Every bug fix gets a regression spec.

## 4. Patterns

```ts
// Resource with a fake client — no module mocking, no network
const client = { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() };
client.get.mockResolvedValue({ results: [orderDto()], count: 1 });
const page = await new OrderResource(client as unknown as ApiClient).list({ search: "a" });
expect(client.get).toHaveBeenCalledWith("orders/list/", { search: "a" });
expect(page.items[0]).toBeInstanceOf(Order);
```

```ts
// Store with mocked resource singletons
vi.mock("@/api/resources", () => ({
    authResource: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
    organizationResource: { mine: vi.fn() },
}));
beforeEach(() => setActivePinia(createPinia()));
```

```ts
// Component with a stubbed store
const wrapper = mount(ThemeToggle, {
    global: { plugins: [createTestingPinia({ createSpy: vi.fn, initialState: { app: { theme: "dark" } } })] },
});
await wrapper.find("button").trigger("click");
expect(useAppStore().toggleTheme).toHaveBeenCalledOnce();
```

## 5. Browser flows (QA, not unit tests)

End-to-end journeys and visuals are verified by **driving the running app in Chrome via Chrome
DevTools MCP** (see `docs/qa.md`): log in → (multi-tenant) choose an organisation → key screens →
create/edit → sign out; check **light and dark**, the console (no errors), and network (no
unexpected 4xx/5xx). Save screenshots under `shots/`. This replaces a Playwright suite.

## 6. Definition of done (frontend)

`npm run lint` · `npm run type-check` · `npm run test:coverage` (thresholds met) all green, new
logic has specs, and the flow was observed in Chrome in both themes.
