<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Mobile Project Structure

> Layout, bootstrap and tooling of the Flutter app. Data access is in [data-layer](data-layer.md),
> state and routing in [state-and-navigation](state-and-navigation.md), widgets and theming in
> [ui-and-theming](ui-and-theming.md). Coding rules: the `flutter-guidelines` skill. Runnable
> reference: the [mobile scaffold](../../bootstrap/scaffold/mobile/README.md).

---

## 1. Directory layout

```
mobile/                               # its own git repo (flutter create … mobile)
├── lib/
│   ├── main.dart                     # ensureInitialized → AppDependencies.create() → restore → runApp
│   ├── app/
│   │   ├── app.dart                  # MultiProvider + MaterialApp.router (theme, locale, router)
│   │   ├── dependencies.dart         # composition root: builds every long-lived object once
│   │   └── router/                   # app_routes.dart (paths + policies), route_guard.dart, app_router.dart
│   ├── core/                         # cross-feature infrastructure — no feature imports
│   │   ├── config/app_config.dart    # dart-define config (env, API base, tenancy)
│   │   ├── api/                      # endpoints.dart, api_client.dart, interceptors.dart, api_error.dart, page_result.dart
│   │   ├── data/base_repository.dart # BaseRepository<T>, ResourcePaths, ListableRepository
│   │   ├── models/                   # json.dart (JsonMap, Json readers, BaseModel), user.dart, organization.dart
│   │   ├── auth/                     # permissions.dart (PermissionQuery), session_credentials.dart
│   │   ├── storage/                  # token_store.dart (secure), app_preferences.dart (non-secret)
│   │   ├── settings/                 # settings_controller.dart (theme mode, locale)
│   │   ├── theme/                    # app_tokens.dart, app_colors.dart, app_theme.dart
│   │   ├── i18n/l10n.dart            # context.l10n
│   │   └── widgets/                  # generic widgets (EmptyState, ErrorView, …, resource_list/)
│   ├── features/<feature>/           # one folder per domain
│   │   ├── data/                     # <feature>_repository.dart (+ feature-only models/)
│   │   ├── state/                    # <feature>_controller.dart (ChangeNotifier)
│   │   ├── screens/                  # <name>_screen.dart (one route each)
│   │   └── widgets/                  # widgets used only by this feature
│   └── l10n/                         # app_en.arb (+ app_<lang>.arb) and generated app_localizations*.dart
├── test/                             # mirrors lib/ (…_test.dart) + helpers/ (factories, mocks, pumpApp)
├── config/                           # example.json (tracked) + dev/staging/prod.json (gitignored)
├── android/  ios/                    # platform projects (flutter create); signing via key.properties
├── pubspec.yaml  pubspec.lock  analysis_options.yaml  l10n.yaml  .gitignore
```

**Conventions**
- Imports are always `package:<project_slug>/…` (lint `always_use_package_imports`); tests import
  helpers relatively.
- File names `snake_case.dart`; one public class per file, named after the file
  (`order_repository.dart` → `OrderRepository`). Suffixes: `…Screen` (routed page), `…Controller`
  (ChangeNotifier state), `…Repository` (API access), model = bare noun (`Order`).
- **Dependency direction:** `features/*` → `core/*`; `app/` wires both. `core/` never imports a
  feature; features never import each other's internals — shared pieces move to `core/`.
  (Exception kept on purpose: auth + organisations are features but the session is app-wide.)
- A feature grows sub-folders only when it needs them; a single-screen feature can be `screens/`
  only.
- Every source file that can hold a comment starts with the project license header (Dart and
  Gradle Kotlin: `//` lines; YAML/properties: `#` lines; XML: `<!-- -->`). JSON/ARB files and
  generated `lib/l10n/app_localizations*.dart` have none.

---

## 2. Bootstrap sequence

```dart
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final dependencies = await AppDependencies.create();   // config, prefs, secure token, dio, repos, controllers
  unawaited(dependencies.session.restore());             // splash shows while status == unknown
  runApp(App(dependencies: dependencies));
}
```

- `AppDependencies.create()` is the **composition root**: it reads `AppConfig.fromEnvironment()`
  (throws `ConfigError` on a bad build), loads `AppPreferences` and `SessionCredentials`, resolves
  the device IANA timezone, builds the Dio instance, repositories and controllers, and wires
  `HttpHooks.onUnauthorized → session.handleUnauthorized`. Nothing else in app code calls these
  constructors; tests construct objects directly with fakes.
- `App` provides the dependencies (`Provider.value` / `ChangeNotifierProvider.value`) above
  `MaterialApp.router` and creates the router **once** (in `State`, disposed with it).
- Keep `main()` fast: no network before `runApp`. Session restore runs after the first frame
  behind the splash; optional integrations (crash reporting, analytics, push) initialise in
  `AppDependencies.create()` behind their config flags — see [build-and-release](build-and-release.md#7-optional-integrations).

---

## 3. Dependencies policy

Baseline (`pubspec.yaml`): `provider`, `go_router`, `dio`, `flutter_secure_storage`,
`shared_preferences`, `flutter_timezone`, `intl`, `flutter_localizations`; dev: `flutter_lints`,
`mocktail`.

- Add a package only when it removes real code or risk, is maintained (recent release, verified
  publisher, null-safe, supports both platforms), and has a permissive license. Record notable
  additions in `DOCS.md`.
- **One package per job** — one HTTP client (dio; never `http` alongside it), one state approach,
  one router.
- Pin with caret ranges; commit `pubspec.lock` (it is an app). `flutter pub outdated` monthly;
  upgrade deliberately, re-run the full gate.
- Plugins that don't support a platform must be guarded (`kIsWeb`, `Platform.isIOS`) in one
  service class, not at every call site.
- Vendoring/patching a plugin (`dependency_overrides` + `third_party/`) is a last resort; document
  why and the upstream issue.

---

## 4. Formatting & linting

- **Formatter:** `dart format` with `formatter: page_width: 100` in `analysis_options.yaml`
  (Dart 3.7+ "tall" style manages trailing commas — don't fight it).
- **Analyzer:** `include: package:flutter_lints/flutter.yaml` + `strict-casts`, `strict-inference`,
  `strict-raw-types` + extra rules (package imports, `prefer_single_quotes`, `avoid_dynamic_calls`,
  `unawaited_futures`, `use_build_context_synchronously`, `directives_ordering`,
  `prefer_final_locals`, …) — the exact file is in the scaffold.
- The gate — run on every change, identical in CI:
  ```bash
  dart format --set-exit-if-changed lib test
  flutter analyze --fatal-infos
  flutter test
  ```
- Fix findings instead of suppressing them. `// ignore:` needs a same-line reason; never
  `ignore_for_file` in app code.

---

## 5. Weak spots to avoid (seen in real apps)

| Anti-pattern | Instead |
|---|---|
| One 2 000-line `ApiService` with a method per endpoint returning raw `http.Response`, `jsonDecode` in providers | `ApiClient` + a repository per domain returning models |
| Token in SharedPreferences; token-type sniffing (`Bearer` vs `Token`) | `SecureTokenStore`; always `Token <t>` |
| Hardcoded dev hostnames / API keys as fallbacks in code or Gradle | Fail fast on missing config; keys via CI secrets / `local.properties` |
| Every provider global in `main.dart`, each creating its own API service | Composition root + constructor injection; feature controllers created where used |
| Regex-parsed routes in `onGenerateRoute`, no guards | go_router routes + `RouteGuard` policies |
| Hardcoded English error strings in state classes | `ApiError` in state, localized message chosen in the widget |
| `main.dart` doing ads, consent, push, widgets, deep links | Each integration is a service initialised from the composition root, behind a flag |
