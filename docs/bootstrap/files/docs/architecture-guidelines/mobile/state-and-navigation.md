<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Mobile State & Navigation

> Controllers, the session/tenancy/RBAC state, and go_router with one guard. The web analogue is
> Pinia stores + vue-router guards ([frontend project-structure §4–5](../frontend/project-structure.md#4-state-management-pinia)).
> Code: [mobile scaffold — state & routing](../../bootstrap/scaffold/mobile/state-routing.md).

---

## 1. State management: `provider` + `ChangeNotifier` controllers

- **App/feature state** lives in a `…Controller extends ChangeNotifier` — the Dart counterpart of
  a Pinia setup store: private fields, public getters, async action methods that call
  repositories and `notifyListeners()`.
- **Ephemeral widget state** (text controllers, a toggle, an animation, a form's error) stays in a
  `StatefulWidget`. Never put app-wide state in `setState`.
- Controllers are **constructor-injected** (repositories, config, other controllers) — no
  singletons, no `static instance`, no service locator. That is what makes them unit-testable
  with fakes.
- Controllers never import Flutter UI (`BuildContext`, `Navigator`, `ScaffoldMessenger`): they
  expose state + `ApiError`; the widget decides what to show and where to go.
- One controller per concern. Split before it passes ~300 lines or mixes two domains.
- Immutable models inside controllers; replace lists (`_items = [..._items, x]`), don't mutate
  them in place.

### Scope

| Scope | Where it's created | Example |
|---|---|---|
| App-wide | `AppDependencies.create()` → provided in `App` via `ChangeNotifierProvider.value` | `SessionController`, `SettingsController` |
| Feature/screen | `ChangeNotifierProvider(create: …)` at the feature's route (disposed with it) | `OrderListController` built from `context.read<ApiClient>()` |
| Widget-local | `StatefulWidget` | form field controllers, `_busy` flags |

### Consuming

```dart
final session = context.watch<SessionController>();          // rebuild on change (build only)
final name = context.select<SessionController, String?>(      // rebuild only when this changes
  (s) => s.user?.fullName,
);
context.read<SessionController>().logout();                    // in callbacks — never watch there
```

- Capture `context.read<…>()`, `GoRouter.of(context)` and `ScaffoldMessenger.of(context)` **before**
  an `await`; after it, check `mounted` / `context.mounted` (lint
  `use_build_context_synchronously`).
- `ListenableBuilder` for a controller you hold directly (e.g. passed to a generic widget).

## 2. The session controller (auth + tenancy + RBAC)

`SessionController` is the single source of truth for who is signed in:

| Member | Purpose |
|---|---|
| `status` | `unknown` (restoring) · `unauthenticated` · `authenticated` — drives the router |
| `user`, `organizations`, `currentOrganization` | loaded on login/restore |
| `restoreError` | restore failed for a non-401 reason (offline) → splash shows retry, token kept |
| `needsOrganization` | multi-tenant and no valid org selected |
| `permissions`, `isOwner`, `hasPermission(PermissionQuery?)` | RBAC for routes, menus, buttons |
| `restore()`, `login()`, `loadOrganizations()`, `selectOrganization(id)`, `logout()` | actions |
| `handleUnauthorized(error)` | wired to the http 401 hook — clears the session |

`PermissionQuery.single('order:read')`, `.all([...])` (AND), `.any([...])` (OR) — the same
uniform query as the web `hasPermission`, evaluated by the pure `hasPermissions()`.

Other controllers that hold per-user data listen for the session leaving `authenticated` and
reset themselves (or are feature-scoped so they die with their route).

## 3. Navigation: go_router + one guard

- One `GoRouter`, created once in `App`'s state, `refreshListenable: session` so every session
  change re-runs the guard (login, logout, 401, org switch).
- Paths live in `AppRoutes`; navigate with `context.go(AppRoutes.x)` (replace) or
  `context.push(...)` (stack, back button). Never build path strings inline.
- **Route policies** (`routePolicies` in `app_routes.dart`) are the mobile `route.meta`:
  `isPublic`, `guestOnly`, `requiresOrganization`, `permission`. The default is **deny**
  (signed-in + org + no extra permission) — only `isPublic: true` opens a route.
- `RouteGuard.redirect(routePattern, location)` is pure Dart (unit-tested): 

  1. `unknown` → `/splash?next=…` (splash shows progress / retry)
  2. `unauthenticated` → public routes pass, everything else `/login?next=…`
  3. `authenticated` on splash / guest-only → `next` or home
  4. multi-tenant + `requiresOrganization` + no org → `/select-organization?next=…`
  5. permission fails → `/not-authorized`

- `next` is accepted only through `safeNext()` (same-app relative path; no `//`, no scheme).
- `errorBuilder` renders the 404 screen. Screens never push login themselves — they change
  session state and let the guard route.
- Nested navigation (bottom tabs) uses `StatefulShellRoute.indexedStack`; each branch keeps its
  own stack. Add it when the project has ≥ 2 top-level sections.
- Pass ids in the path (`/orders/:id`), never whole objects via `extra` (breaks deep links and
  restoration); the screen loads by id.

## 4. Deep links (optional)

- App Links (Android) / Universal Links (iOS) map 1:1 to go_router paths; go_router handles them
  when Flutter deep linking is enabled. The guard applies unchanged (anonymous → login → back to
  the link via `next`).
- Hosting `assetlinks.json` / `apple-app-site-association` belongs to the web frontend/infra;
  record the domains in `DOCS.md`.
- Links carrying ids for another tenant must resolve through `selectOrganization` — never switch
  tenant silently on an unverified id.

## 5. Forms

- `Form` + `GlobalKey<FormState>` for client-side validation (required, format) — UX only; the
  server validates again.
- Submit via a controller/session action; catch `ApiError` into widget state; render
  `error.firstError('<field>')` under each input (`AppTextField(apiError: …)`) and non-field
  errors (`non_field_errors` / `message`) in a banner above the form.
- The primary button is `LoadingButton` (disables itself while the future runs — no double
  submit).
- Dirty-state leave guard (`PopScope(canPop: !isDirty)` + confirm dialog) on long forms.
