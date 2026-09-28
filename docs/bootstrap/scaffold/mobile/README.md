# Mobile Scaffold (Flutter)

> The **reference implementation** of the mobile architecture guidelines, stored as Markdown.
> Every fenced code block under a `### \`path\`` heading is the **exact, complete content** of that
> file, relative to the **mobile repo root** (`mobile/`). An agent bootstrapping the app runs
> `flutter create`, then materialises these blocks verbatim (substituting placeholders), in the
> order below. There is no source code in this base repo — only these documents.
>
> Only for projects whose `DOCS.md` lists **mobile** as a platform. Rationale lives in
> [`../../architecture-guidelines/mobile/`](../../../architecture-guidelines/mobile/README.md) and
> the coding rules in the `flutter-guidelines` skill. If anything disagrees, the
> [canonical decisions table](../../../architecture-guidelines/README.md#canonical-decisions-these-win-over-any-older-wording)
> wins — fix whichever page is wrong.

---

## Files in this scaffold

| Doc | Materialises |
|-----|--------------|
| [project.md](project.md) | `pubspec.yaml`, `analysis_options.yaml`, `l10n.yaml`, `.gitignore`, `config/example.json`, `android/app/build.gradle.kts`, `android/key.properties.example`, Android main + debug manifests |
| [core.md](core.md) | `lib/main.dart`, `lib/app/{app,dependencies}.dart`, `lib/core/config/`, `lib/core/theme/`, `lib/core/i18n/`, `lib/l10n/app_en.arb`, `lib/core/storage/app_preferences.dart`, `lib/core/settings/`, `test/helpers/*` (+ config test) |
| [data-layer.md](data-layer.md) | `lib/core/api/*` (endpoints, Dio + interceptors, `ApiClient`, `ApiError`, `PageResult`), `lib/core/data/base_repository.dart`, `lib/core/models/*`, `lib/core/auth/*`, `lib/core/storage/token_store.dart`, auth + organisation repositories (+ tests) |
| [widgets.md](widgets.md) | `lib/core/widgets/*` — `EmptyState`, `ErrorView`, `LoadingButton`, `AppTextField`, dialogs/snackbar, `ListController` + `ResourceListView` (+ tests) |
| [state-routing.md](state-routing.md) | `SessionController`, `lib/app/router/*` (routes + policies, `RouteGuard`, router), screens (splash, login, organisation selector, home, settings, 404/403) (+ tests) |

## Resulting layout

```
mobile/                               # its own git repo
├── pubspec.yaml  pubspec.lock  analysis_options.yaml  l10n.yaml  .gitignore
├── config/example.json               # + dev/staging/prod.json (gitignored)
├── android/  ios/                    # from flutter create; signing + manifests replaced
├── lib/
│   ├── main.dart
│   ├── app/                          # app.dart, dependencies.dart, router/
│   ├── core/                         # config, api, data, models, auth, storage, settings, theme, i18n, widgets
│   ├── features/                     # auth/, organizations/, home/, settings/, errors/
│   └── l10n/                         # app_en.arb + generated app_localizations*.dart
└── test/                             # mirrors lib/ + helpers/
```

## Placeholders

| Placeholder | Where | Source |
|-------------|-------|--------|
| `<project_slug>` | `pubspec.yaml` `name`, every `package:<project_slug>/…` import, the Android namespace / application id | `DOCS.md` §1 slug in **snake_case** (`my-app` → `my_app`; must be a valid Dart package name) |
| `<org_reverse_domain>` | `flutter create --org`, Android namespace / application id | reverse domain of the legal entity (`com.example`); iOS bundle id is set from it by `flutter create` |
| `<Project name>` | Android `android:label`, iOS `CFBundleDisplayName`, `pubspec.yaml` description, `config/*.json` `APP_NAME` | `DOCS.md` §1 |
| `<Legal entity name>` | `config/*.json` `LEGAL_ENTITY_NAME` | `DOCS.md` §1 |
| `<BACKEND_PORT>` | `config/dev.json` `API_BASE_URL` | `DOCS.md` §4 ports |
| `<Project Name>`, `<YEAR>`, `<Legal Entity Name>` | license header at the top of every file that can hold comments (Dart/Kotlin `//`, YAML/properties `#`, XML `<!-- -->`) | `DOCS.md` §1 (see the bootstrap license-header doc) |

`TENANCY_MODE` (`multi` \| `single`) in `config/*.json` must match the backend's tenancy choice in
`DOCS.md`. `multi` enables organisations, the `X-Organization-Id` header and the organisation
selector; `single` drops them (permissions come from the user).

## Materialisation order

1. Create the app (Flutter stable ≥ 3.44 — `flutter --version`):
   ```bash
   flutter create --org <org_reverse_domain> --project-name <project_slug> \
     --platforms android,ios mobile
   cd mobile && git init
   rm test/widget_test.dart                 # references the demo counter app
   ```
2. Write every file from [project.md](project.md), then [core.md](core.md),
   [data-layer.md](data-layer.md), [widgets.md](widgets.md), [state-routing.md](state-routing.md) —
   verbatim, placeholders substituted (overwrite the generated `pubspec.yaml`,
   `analysis_options.yaml`, `.gitignore`, `lib/main.dart`, `android/app/build.gradle.kts` and the
   two `AndroidManifest.xml` files).
3. Set `CFBundleDisplayName` in `ios/Runner/Info.plist` to `<Project name>`.
4. `cp config/example.json config/dev.json` and fill it from `DOCS.md` (Android emulator →
   `http://10.0.2.2:<BACKEND_PORT>/api/`, iOS simulator → `http://localhost:<BACKEND_PORT>/api/`).
5. Install and verify (keep output capped):

```bash
flutter pub get                                  # also generates lib/l10n/app_localizations*.dart
dart format --set-exit-if-changed lib test       # formatter (page width 100)
flutter analyze --fatal-infos                    # strict analyzer + lints — must be clean
flutter test                                     # ~60 unit + widget tests
flutter build apk --debug --dart-define-from-file=config/dev.json   # platform build sanity
```

6. QA on an emulator/simulator (backend running): 
   `nohup flutter run --dart-define-from-file=config/dev.json > .flutter-run.log 2>&1 &` then
   `tail -n 40 .flutter-run.log`. Splash → login → (multi-tenant) choose organisation → home →
   settings: toggle **light / dark** → sign out → login. Airplane mode on launch → splash shows
   retry (not a logout). Screenshots with `flutter screenshot -o shots/<name>.png`.
7. First commit: `git add -A && git commit -m "chore: mobile scaffold"`.

## Commands

| Command | Does |
|---------|------|
| `flutter run --dart-define-from-file=config/dev.json` | run against the dev backend (background it, log to `.flutter-run.log`) |
| `dart format lib test` / `--set-exit-if-changed` | format / check formatting |
| `flutter analyze --fatal-infos` | analyzer + lints (infos fail too) |
| `flutter test` / `--coverage` | unit + widget tests / with `coverage/lcov.info` |
| `flutter build appbundle --release --dart-define-from-file=config/prod.json --obfuscate --split-debug-info=build/symbols/android` | Play bundle (needs `android/key.properties`) |
| `flutter build ipa --release --dart-define-from-file=config/prod.json --obfuscate --split-debug-info=build/symbols/ios` | App Store build (needs signing set up in Xcode / CI) |

Environments are selected with the dart-define file (`dev` / `staging` / `prod`); native flavors
are optional and added only when side-by-side installs are needed — see
[build-and-release](../../../architecture-guidelines/mobile/build-and-release.md).

## Notes on decisions baked in

- **State:** `provider` + `ChangeNotifier` controllers, built once in `AppDependencies.create()`
  (the composition root) and injected — no singletons, so everything is testable with fakes.
- **Auth** is `Authorization: Token <token>` (opaque DB token) stored in `flutter_secure_storage`.
  No refresh flow: any 401 clears the session and the router shows the login screen. A network
  failure during restore keeps the token and offers a retry.
- **Tenancy:** the selected organisation lives in the session (persisted id, re-validated against
  `my-orgs` on every restore), not in route paths.
- **Backend URLs** in `Endpoints` are relative to `API_BASE_URL` (`…/api/`). Keep the registry in
  sync with the backend URLconf.
- **Signing:** `android/key.properties` + keystore are gitignored and written by CI; without them a
  local release build is debug-signed.
- **License header**: every file that can hold a comment starts with the project license header;
  JSON/ARB files and the generated `lib/l10n/app_localizations*.dart` have none.
