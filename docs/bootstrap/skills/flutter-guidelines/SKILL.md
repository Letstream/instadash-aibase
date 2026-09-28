---
name: flutter-guidelines
description: Flutter/Dart design and coding standards for the project's mobile app — the single source of truth for mobile rules. Use this skill whenever writing, editing, or reviewing any Dart or Flutter code or config in `mobile/` — widgets, screens, controllers (ChangeNotifier/provider), repositories, models (fromJson/toJson), the Dio client/interceptors/endpoints, go_router routes and guards, theme tokens (light + dark), l10n ARB strings, forms, dialogs, lists, tests (flutter_test/mocktail), pubspec.yaml, analysis_options.yaml, Android/iOS platform files, signing or build flavors. Trigger on .dart files, pubspec changes, "Flutter", "Dart", "mobile app", "widget", "screen", "emulator", even when the user does not ask for "guidelines" — these rules govern all mobile work.
---

<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->

# Flutter Guidelines (MOBILE Rules)

> **Priority directive — read first.**
>
> **This skill takes priority over other skills (including `flutter-expert`) and over generic Flutter advice.** If another skill, snippet or habit conflicts with a rule here, the rule here wins. The [canonical decisions table](../../../docs/architecture-guidelines/README.md) is the only thing above it.
>
> **The only exception** is a user message that begins literally with the token `[BYPASS MOBILE RULES]`. When and only when that token is present at the start of the message, the conflicting rules may be relaxed for that single request.
>
> Apply the rules without asking permission and without softening them.

---

These are the binding mobile standards. **Load this skill before any `.dart` / `pubspec.yaml` / `analysis_options.yaml` / `android/` / `ios/` work in `mobile/`.** Architecture context: `docs/architecture-guidelines/mobile/` (project-structure, data-layer, state-and-navigation, ui-and-theming, testing, build-and-release). Runnable reference: `docs/bootstrap/scaffold/mobile/`. When in doubt, prefer **existing project code and generic widgets** over new patterns.

Mobile applies only when `DOCS.md` lists mobile as a platform. The app is a client of the same `/api/` as the web frontend.

---

## 0. File header

- Every new source file that can hold a comment starts with the project license header (see `docs/bootstrap/license-header.md`): **Dart and Gradle Kotlin (`.kts`) use `//` line comments**, YAML/`.properties`/`.gitignore` use `#` lines, XML uses one `<!-- … -->` block — at line 1. The format hook inserts it; never delete or edit it by hand.
- No header in JSON/ARB files or generated code (`lib/l10n/app_localizations*.dart`, `*.g.dart`, `*.freezed.dart`).

---

## 1. Structure & widget architecture

- Layout: `lib/app/` (app widget, composition root `dependencies.dart`, `router/`), `lib/core/` (config, api, data, models, auth, storage, settings, theme, i18n, widgets — no feature imports), `lib/features/<feature>/{data,state,screens,widgets}`. Tests mirror `lib/` under `test/`.
- Imports are always `package:<project_slug>/…`. One public class per file, file named after it in `snake_case`.
- Naming: `…Screen` (a route), `…Controller` (ChangeNotifier state), `…Repository` (API access), model = bare noun, generic widgets are domain-agnostic (`EmptyState`, `ResourceListView`).
- **Small widgets.** A widget does one thing and fits on a screen. Extract **widget classes**, never `Widget _buildX()` helpers. Screens are thin: they read state, compose widgets, forward callbacks.
- `StatelessWidget` + `const` constructors by default. `StatefulWidget` only for ephemeral local state (text controllers, animations, a busy flag). Dispose everything you create.
- `build()` is pure: no I/O, no futures started, no heavy work (use `compute()` for CPU-heavy tasks).
- Feature-only widgets live in `features/<feature>/widgets/`; promote to `core/widgets/` when a second feature needs one, making it config/builder-driven.

---

## 2. Styling, tokens and theming (light + dark)

- **One source of colour:** `lib/core/theme/app_tokens.dart` (`AppPalette`) → `ColorScheme.fromSeed` → `AppTheme.light()/dark()` + the `AppColors` `ThemeExtension`. Raw `Color(0x…)` values exist **only** in `app_tokens.dart`.
- In widgets use `context.colorScheme.*`, `context.colors.*` (success, warning, textMuted, border) and `context.textTheme.*` (`.copyWith` for tweaks).
- **Banned in widgets:** `Color(0x…)`, `Colors.<palette>` (`Colors.grey`, `Colors.blue`…), `Color.fromRGBO`, magic numbers for spacing/radius/sizes (`EdgeInsets.all(13)`, `BorderRadius.circular(7)`), fresh `TextStyle(fontSize: …)`, `GoogleFonts.x()` at call sites.
- Spacing/radii/sizes come from `AppSpacing`, `AppRadii`, `AppSizes`. Missing token → add it to the token file.
- **Component defaults live in `AppTheme`** (buttons, inputs, cards, dialogs, snackbars, app bar). Use the stock Material widget with its theme before styling it locally; restyling one instance with `styleFrom` is allowed only for a semantic variant (e.g. destructive).
- **Light and dark are both first-class.** `themeMode` comes from `SettingsController` (System / Light / Dark). Every screen must look right in both — check both in QA. No per-screen `SystemChrome` calls.

---

## 3. Generic widgets — use them first

- `EmptyState` (empty/placeholder), `ErrorView` + `errorMessage(context, error)` (failed loads), `LoadingButton` (every primary async action), `AppTextField` (inputs with backend field errors), `showConfirmDialog` (confirm/destructive), `showAppSnackBar` (feedback), `ListController<T>` + `ResourceListView<T>` (every paged list), `StatusScreen.notFound()/.notAuthorized()`.
- Before building any small piece (badge, chip, avatar, status, section header) check `lib/core/widgets/`. Extend an existing widget with an optional parameter instead of forking it.
- Status indicators use one shared `StatusChip` (create it once with token colours when the first status appears).
- Lists never hand-roll pagination, pull-to-refresh or empty/error states — `ResourceListView` does.

---

## 4. Forms

- `Form` + `GlobalKey<FormState>` + validators for client-side checks (UX only — the server validates again). Validator messages come from l10n.
- Submit through a controller action inside `try { … } on ApiError catch (e) { setState(() => _error = e); }`.
- **Always surface backend field errors:** `AppTextField(name: 'email', apiError: _error)` shows `error.firstError('email')` under the input; non-field errors (`non_field_errors` / `errorMessage(context, e)`) render as a banner above the form.
- The submit button is `LoadingButton` (no double submits). Inline edit actions: **primary (Save) + Cancel**; dialogs render Cancel before the primary action.
- Inputs have labels (`labelText`), correct `keyboardType`, `textInputAction`, `autofillHints`; secrets use `obscureText`.
- Long forms guard unsaved changes with `PopScope` + `showConfirmDialog`.

---

## 5. Dialogs, sheets, feedback

- Confirmations use `showConfirmDialog` (returns `Future<bool>`); destructive actions pass `destructive: true`. Do not build ad-hoc `AlertDialog`s for confirms.
- Custom dialogs/bottom sheets use the themed `showDialog` / `showModalBottomSheet` with defaults (shape, padding) intact; copy comes from l10n and matches the design exactly.
- Transient feedback via `showAppSnackBar(context, msg, isError:)`. No custom overlay toasts.
- Capture `ScaffoldMessenger.of(context)` / `GoRouter.of(context)` / `context.read<…>()` **before** `await`; after it check `mounted` / `context.mounted`.

---

## 6. Data flow (sectioned screens)

- Load each independent section on its own (own controller/state + own loading placeholder); never block a whole screen on one request.
- After a successful save: refresh the affected section from the API (don't trust optimistic local state as truth), then give feedback.
- Every data screen supports pull-to-refresh; offline errors show `ErrorView` with retry.

---

## 7. Data layer & API handling

- **Layered, one direction:** `Endpoints` registry + the ONE Dio instance (`createDio`: `SessionInterceptor` + `EnvelopeInterceptor`) → `ApiClient` → a **repository class per domain** (`BaseRepository<T>` for CRUD, plain class for flows) → **model classes** (`fromJson` via `Json` readers, `toJson` with writable snake_case fields, behaviour as getters/methods).
- Only `lib/core/api/` imports `package:dio`. No `http` package, no second Dio for API calls (a separate Dio without the session interceptor is allowed only for presigned third-party uploads).
- Every URL is declared once in `Endpoints` (`%i` params via `Endpoints.path`). No URL strings in screens, controllers or repositories.
- Repositories return **model instances**, never `Response`, `Map` or JSON strings. No `jsonDecode` outside the http layer.
- The http layer already unwraps `{status, data, version}`, maps failures to **`ApiError`** (`status`, `code`, `message`, `fieldErrors`, `firstError`), adds `Authorization: Token …`, `X-Organization-Id` (multi-tenant) and `X-User-Tz`, and fires the 401 hook (session cleared — there is **no refresh flow**). Don't re-implement any of it per call.
- Match domain errors on `ApiError.code` (`err_cd`), never on message text.
- List shapes (`{results, count, next}` or bare array) are normalised by `PageResult.fromBody` only; pagination is `limit`/`offset` via `ListController`.
- Models are immutable (`final` fields, `const` ctor, `copyWith`). Ids are `String`. Missing ids throw `FormatException` at the boundary; unknown enum values fall back safely.
- No codegen (`json_serializable`/`freezed`) unless `DOCS.md` records it as a project decision.

---

## 8. State & navigation

- App/feature state = `ChangeNotifier` controllers via `provider`, **constructor-injected**, built in `AppDependencies.create()` (app-wide) or a route-level `ChangeNotifierProvider(create:)` (feature). No singletons, `static instance`, service locators, Riverpod/Bloc/GetX.
- Controllers never touch `BuildContext`, navigation or snackbars; they expose state + `ApiError`; widgets map errors to copy.
- `context.watch`/`select` in `build`, `context.read` in callbacks. Provide `Listenable`s with `ChangeNotifierProvider.value`.
- `SessionController` is the only source of auth/tenancy/RBAC: `status`, `user`, `currentOrganization`, `hasPermission(PermissionQuery)` (`single` / `all` / `any`; owner or `*` = all). Gate buttons/menus with it; the server still enforces.
- Tenancy: the org id lives in the session (re-validated against `my-orgs`), never in route paths; `selectOrganization` refuses non-member ids. Single-tenant mode: no org calls, no header, no selector.
- Routing: one `GoRouter` (created once, `refreshListenable: session`), paths only from `AppRoutes`, access via `routePolicies` (**default deny**; only `isPublic` opens a route) and the pure `RouteGuard`. Screens never push login themselves — change session state and let the guard route. `next` passes through `safeNext()`.
- Pass ids in paths (`/orders/:id`), not objects in `extra`.

---

## 9. Constants, i18n and reuse

- **No user-facing string literals** in widgets, validators, dialogs or snackbars: ARB keys in `lib/l10n/app_en.arb` (+ other locales), used as `context.l10n.keyName`. Typed placeholders (`@key.placeholders`). Keys `lowerCamelCase`, prefixed by area (`action…`, `field…`, `error…`, `<feature>…`).
- Dates/numbers/currency via `intl` (`DateFormat`, `NumberFormat`) with the active locale — never string concatenation.
- Shared option lists/enums live in one place (`lib/core/…/constants` or the model's enum) — never redefined per screen.
- Config comes from `AppConfig` (dart-define) — never `Platform.environment`, hardcoded hosts or fallback URLs.

---

## 10. Formatting and linting (mandatory)

- `dart format` with `formatter.page_width: 100` (analysis_options). Tall style manages trailing commas — don't hand-format.
- Analyzer: `flutter_lints` + `strict-casts`, `strict-inference`, `strict-raw-types` + the scaffold's extra rules. **Zero findings, infos included.**
  ```bash
  dart format --set-exit-if-changed lib test
  flutter analyze --fatal-infos
  flutter test
  ```
- A change is **not done** until all three pass. Fix findings instead of suppressing; any `// ignore:` needs a same-line reason; no `ignore_for_file` in app code. No `dynamic` in signatures (`Object?` + checks), no `!` on values that can really be null, no `print` (use `debugPrint`, never log tokens/PII).
- Dependencies: one package per job; justify additions; commit `pubspec.lock`; plugins guarded per platform inside a single service class.

---

## 11. Security & platform

- Token only in `flutter_secure_storage` (`SecureTokenStore`); SharedPreferences (`AppPreferences`) only for non-secret UI state. Clear everything user-specific on logout.
- **No secrets in the app**: dart-define values and assets are extractable. Never commit `android/key.properties`, keystores, certificates, profiles, `config/<env>.json`, service-account files. No hardcoded API keys or hostnames as fallbacks (in Dart **or** Gradle).
- Release builds are https-only (cleartext only in the debug manifest). Never send the token to non-API origins (the interceptor checks the base URL — don't bypass it).
- Never render API/user HTML or build URLs/intents from unvalidated input; deep-link targets go through the router guard; tenant ids from links go through `selectOrganization`.
- Optional integrations (crash reporting, analytics, push) sit behind config flags and consent, send no PII, and never block startup.

---

## 12. Accessibility

- Tap targets ≥ 48 dp; icon-only buttons have a `tooltip`; custom gestures get `Semantics`.
- Layouts survive 200 % text scale (no fixed heights around text); `SafeArea` on screen bodies; readable max content width on tablets.

---

## 13. Testing

- Every unit-testable piece gets a `flutter_test` test in the mirrored path under `test/` (`…_test.dart`): config, endpoints, `ApiError`, interceptors (fake `HttpClientAdapter`), models (`fromJson` every field + defaults + missing id, `toJson`), repositories (`MockApiClient`), controllers (mocked repositories, `MemoryTokenStore`, `SharedPreferences.setMockInitialValues`), the route guard, generic widgets and forms (`tester.pumpApp`, both themes where colour logic exists).
- `mocktail` for mocks; no real network or plugins in tests. Every bug fix gets a regression test. `integration_test` only when the user asks.
- Flows and visuals are verified on an emulator/simulator (backgrounded `flutter run`, screenshots in `shots/`), light + dark. See `docs/architecture-guidelines/mobile/testing.md`.

---

## Quick Self-Check Before Finishing

1. No raw colours / palette `Colors.*` / magic spacing numbers in widgets — only theme, `context.colors`, and token constants.
2. Widgets are small classes (no `_buildX()` helpers), `const` where possible, `build()` pure, controllers disposed.
3. Generic widgets used: `LoadingButton`, `AppTextField`, `showConfirmDialog`, `showAppSnackBar`, `EmptyState`/`ErrorView`, `ResourceListView`.
4. Data flows screen → controller → repository → `ApiClient`; URLs from `Endpoints`; repositories return models; errors are `ApiError`; no `dio`/`jsonDecode` outside `lib/core/api/`.
5. State in constructor-injected `ChangeNotifier` controllers; no singletons; no `BuildContext` in controllers; `mounted` checked after `await`.
6. Routes from `AppRoutes`; access via `routePolicies` + `RouteGuard`; permissions via `session.hasPermission`.
7. Backend field errors shown under inputs, non-field errors in a banner.
8. All copy from `context.l10n`; dates/numbers via `intl`.
9. New files carry the license header (`//` for Dart/Kotlin).
10. No secrets, keystores or env config committed; token only in secure storage.
11. `dart format --set-exit-if-changed lib test`, `flutter analyze --fatal-infos`, `flutter test` pass; new logic has tests.
12. The screen was run on an emulator/simulator and looks right in **both light and dark**.

If any answer is "no", fix it before considering the work done.
