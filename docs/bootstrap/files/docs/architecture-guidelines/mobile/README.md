<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Mobile Architecture Guidelines (Flutter)

> **Project-agnostic** standards for the optional Flutter app that talks to our Django + DRF
> backend. They mirror the [frontend](../frontend/project-structure.md) patterns — layered data
> access, typed models, generic reusable UI, centralized light/dark tokens, i18n, strict lint,
> unit tests — translated to Dart. The binding coding rules live in the **`flutter-guidelines`
> skill** (`.claude/skills/flutter-guidelines/SKILL.md`); the runnable reference is the
> [mobile scaffold](../../bootstrap/scaffold/mobile/README.md).

## When these apply

Only in projects whose `DOCS.md` lists **mobile** among the platforms (chosen at Bootstrap). The
app lives in its own git repo, `mobile/`, next to `backend/` and `frontend/`. Projects without a
mobile platform ignore this folder. If `DOCS.md` does not mention mobile and the user asks for an
app, run Bootstrap's platform question first — do not improvise a structure.

The mobile app is a **client of the same API** as the web frontend. It never gets its own
backend endpoints for things the web app already does; mobile-only needs (device registration,
app-version checks) are ordinary endpoints under `/api/` and documented in `DOCS.md`.

## Mobile decisions (canonical)

The [canonical decisions table](../README.md#canonical-decisions-these-win-over-any-older-wording)
wins over everything; these rows are its mobile extension.

| Topic | Decision |
|---|---|
| Toolchain | Flutter **stable** (≥ 3.44, Dart ≥ 3.12), Material 3. Targets **Android + iOS**; web/desktop only if `DOCS.md` says so. |
| Repo | Separate `mobile/` git repo, created with `flutter create`, then the scaffold files replace/extend it. Package name = project slug in `snake_case`. |
| State | `provider` + **`ChangeNotifier` controllers** (one per concern), constructor-injected, built once in the composition root `AppDependencies`. No Riverpod/Bloc/GetX unless recorded as a project decision. |
| Navigation | `go_router`, one router, one pure `RouteGuard` (session → tenant → permission), **default-deny** route policies, `refreshListenable` = the session. |
| HTTP | `dio`: **one** instance, `SessionInterceptor` (token, tenant, tz) + `EnvelopeInterceptor` (unwrap / `ApiError`), `ApiClient` facade, `Endpoints` registry. |
| Data layer | `ApiClient` → **repository class per domain** (`BaseRepository<T>`) → **model classes** with `fromJson`/`toJson`. Hand-written serialization via `Json` readers; no codegen by default. |
| Auth | `Authorization: Token <opaque token>`; **no refresh** — any 401 clears the session. Token in **`flutter_secure_storage`** only; SharedPreferences for non-secret UI state. |
| Tenancy | Build-time `TENANCY_MODE` (`multi` \| `single`) matching the backend. Multi: `X-Organization-Id` from the selected org (validated against `my-orgs`), selector screen. Single: none of it. |
| Config | `--dart-define-from-file=config/<env>.json` (`dev` \| `staging` \| `prod`). Every value is public (compiled into the binary); **no secrets in the app**. |
| UI | Generic widgets in `lib/core/widgets/` (EmptyState, ErrorView, LoadingButton, AppTextField, dialogs, `ResourceListView`). Tokens in `lib/core/theme/` — the only place raw colours live. Light + dark first-class. |
| i18n | `flutter gen-l10n` ARB files, `context.l10n.key`; no user-facing literals in widgets. |
| Quality gate | `dart format` (page width 100) · `flutter analyze --fatal-infos` (strict analyzer + extra lints) · `flutter test` — same commands locally and in CI. |
| Tests | `flutter_test` + `mocktail` for every unit-testable piece; widget tests for generic widgets and forms. `integration_test` only when the user asks. |
| Release | Signing material outside git (CI secret store → `android/key.properties`, keystore, iOS certs). Version in `pubspec.yaml`; build number bumps on every store upload. |

## Pages

| Doc | What it covers |
|-----|----------------|
| [project-structure](project-structure.md) | Repo layout (`app/`, `core/`, `features/`), naming, bootstrap sequence, composition root, dependencies policy, lint/format config, license headers. |
| [data-layer](data-layer.md) | Endpoint registry, the Dio instance + interceptors, envelope + `ApiError`, `ApiClient`, repositories, models, token + preferences storage, tenancy headers, pagination. |
| [state-and-navigation](state-and-navigation.md) | Controllers (`ChangeNotifier`), the session/tenancy/RBAC controller, providing and consuming state, go_router + `RouteGuard`, route policies, deep links. |
| [ui-and-theming](ui-and-theming.md) | Tokens, `ThemeData` light/dark, `AppColors` extension, generic widgets, forms + backend errors, dialogs/snackbars, lists, accessibility, i18n. |
| [testing](testing.md) | `flutter_test` + `mocktail`: what to test, layout, fakes, widget tests, coverage, device QA. |
| [build-and-release](build-and-release.md) | Environments via dart-define files, optional native flavors, signing without secrets in git, versioning, store builds, CI, optional integrations (crash reporting, analytics, push). |

## Core principles (same as web)

- **One cohesive concern per file/class**; feature folders own their screens, state and data.
- **Uniform contracts** — one envelope, one error type, one set of generic widgets.
- **Server-side tenancy is the security boundary** — the app only *selects* an org the server
  already confirmed; it never trusts a stored or deep-linked id on its own.
- **Secrets never in code, git or the binary.**
- **Local == CI** — the same format/analyze/test commands.
