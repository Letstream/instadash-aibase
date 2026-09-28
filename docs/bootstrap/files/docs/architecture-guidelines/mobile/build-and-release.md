<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Mobile Build & Release

> Environments, signing, versioning, store builds, CI and optional integrations. Security rules
> from `docs/security.md` apply unchanged: **no secret in code, git, logs — or the app binary.**
> Config files and Gradle signing are in the [mobile scaffold — project](../../bootstrap/scaffold/mobile/project.md).

---

## 1. Environments via dart-define files

One file per environment, passed at build/run time:

```bash
flutter run   --dart-define-from-file=config/dev.json
flutter build appbundle --release --dart-define-from-file=config/prod.json
```

| Key | Example | Notes |
|---|---|---|
| `APP_ENV` | `dev` \| `staging` \| `prod` | non-dev requires an `https` API URL |
| `API_BASE_URL` | `https://api.example.com/api/` | Android emulator → host: `http://10.0.2.2:<BACKEND_PORT>/api/`; iOS simulator: `http://localhost:<BACKEND_PORT>/api/`; physical device: the machine's LAN IP or the https dev URL |
| `TENANCY_MODE` | `multi` \| `single` | must match the backend (`DOCS.md`) |
| `APP_NAME`, `LEGAL_ENTITY_NAME` | from `DOCS.md` §1 | shown in the app bar / copyright |
| optional (`SENTRY_DSN`, …) | empty = feature off | see §7 |

- `config/example.json` is tracked (placeholders); `config/dev|staging|prod.json` are gitignored
  and created from it (locally by the developer, in CI from pipeline variables).
- Every value is **compiled into the binary and extractable** — they are public identifiers only.
  Anything secret (API secrets, signing passwords, service-account keys) never enters a
  dart-define; if the app needs a privileged call, the backend makes it.
- `AppConfig.fromEnvironment()` validates at startup and throws `ConfigError` — a misconfigured
  build fails immediately instead of silently pointing at the wrong API. Never add hardcoded
  fallback hostnames.
- Cleartext `http://` works only in debug on Android (debug manifest `usesCleartextTraffic`);
  iOS ATS may need `NSAllowsLocalNetworking` for local dev hosts. Release builds are https-only.

## 2. Native flavors (optional)

Dart-define files are enough when one installed app per device is fine. Add **flavors** only when
the project needs side-by-side installs or per-env app names/icons/Firebase projects:

- Android: `productFlavors { create("dev") { dimension = "env"; applicationIdSuffix = ".dev" } … }`
  in `android/app/build.gradle.kts`.
- iOS: one scheme + build configurations per flavor (`Debug-dev`, `Release-dev`, …) with an
  `.xcconfig` for bundle id suffix / display name.
- Build with both: `flutter build apk --flavor dev --dart-define-from-file=config/dev.json`.
- Record the flavor matrix in `DOCS.md`; CI builds each store flavor explicitly.

## 3. Signing — secrets outside git

**Android**
- Generate the **upload** keystore once (`keytool -genkey -v -keystore upload-keystore.jks
  -keyalg RSA -keysize 2048 -validity 10000 -alias upload`), store the file + passwords in the
  team secret store / CI secrets. Enable **Play App Signing** (Google holds the app-signing key; a
  lost upload key can be reset).
- `android/key.properties` (from `key.properties.example`) points at the keystore; **both are
  gitignored** (`/android/key.properties`, `*.jks`, `*.keystore`). CI writes them from secrets
  (base64-decoded keystore) before building and deletes them after.
- `build.gradle.kts` signs release builds with it when present; without it a local release build
  is debug-signed (runnable, not uploadable).
- API keys that must be in the manifest (e.g. Maps) come from `local.properties` / `-P` Gradle
  properties or CI variables via `manifestPlaceholders` — never a hardcoded fallback — and are
  restricted in the provider console to the app id + signing SHA.

**iOS**
- Local: Xcode automatic signing with the team account. CI: an App Store Connect API key (`.p8`)
  and/or a certificate repository (e.g. fastlane match) — `.p8`, `.p12`, `.mobileprovision` never
  in git.
- The Team ID and bundle id in `project.pbxproj` are not secrets and are committed.

Never commit: keystores, `key.properties`, certificates, provisioning profiles, service-account
JSON, `.env` files. `google-services.json` / `GoogleService-Info.plist` are gitignored by default
and injected per environment by CI (they are identifiers, but environment-specific).

## 4. Versioning

- `pubspec.yaml` `version: <major>.<minor>.<patch>+<build>` → Android `versionName`/`versionCode`,
  iOS `CFBundleShortVersionString`/`CFBundleVersion`.
- Marketing version follows semver for user-visible changes; the **build number increases on
  every store upload** (CI passes `--build-number=$CI_RUN_NUMBER` or bumps it in the release
  commit). Stores reject a reused build number.
- Tag releases in the mobile repo (`v1.4.0`) and keep a `CHANGELOG.md` entry per release.
- If the backend changes an endpoint's contract, keep the old shape until the minimum supported
  app version no longer uses it (mobile users update late). Record the minimum version in
  `DOCS.md`; an optional backend "min app version" check can prompt updates.

## 5. Store builds

```bash
# Android App Bundle (Play)
flutter build appbundle --release --dart-define-from-file=config/prod.json \
  --obfuscate --split-debug-info=build/symbols/android

# iOS (App Store / TestFlight)
flutter build ipa --release --dart-define-from-file=config/prod.json \
  --obfuscate --split-debug-info=build/symbols/ios
```

- Keep `build/symbols/…` as CI artifacts (needed to de-obfuscate crash reports); never commit
  them (`app.*.symbols` is ignored).
- Before a store submission: bump version/build, run the full gate, QA the release build on a
  real device in both themes, check permissions strings (`Info.plist` usage descriptions only for
  features actually used) and the privacy declarations (data safety / App Privacy / ATT).

## 6. CI

Same commands as local, pinned Flutter version (record it in `DOCS.md`):

```yaml
# sketch — adapt to the project's CI
steps:
  - uses: actions/checkout@v4
  - uses: subosito/flutter-action@v2
    with: { flutter-version: "<pinned>", channel: stable, cache: true }
  - run: flutter pub get
  - run: dart format --set-exit-if-changed lib test
  - run: flutter analyze --fatal-infos
  - run: flutter test --coverage
  # release jobs only (tags / main), secrets from the CI secret store:
  - run: echo "$CONFIG_PROD_JSON" > config/prod.json
  - run: echo "$ANDROID_KEYSTORE_B64" | base64 -d > android/upload-keystore.jks
  - run: printf '%s\n' "storePassword=$KS_PASS" "keyPassword=$KEY_PASS" "keyAlias=upload" "storeFile=../upload-keystore.jks" > android/key.properties
  - run: flutter build appbundle --release --dart-define-from-file=config/prod.json --build-number=${{ github.run_number }}
```

- PR pipeline: format + analyze + test (no secrets available to PRs from forks).
- Release pipeline: builds, uploads symbols, publishes to an internal track / TestFlight; promotion
  to production is a manual step.

## 7. Optional integrations

None ship in the base scaffold. When a project adds one:

| Integration | Rules |
|---|---|
| Crash reporting (Sentry / Crashlytics) | DSN/config via dart-define (empty ⇒ off); `sendDefaultPii = false`; release = `<app>@<version>+<build>`; environment = `APP_ENV`; upload symbols from CI. Wrap `runApp` only when enabled. |
| Analytics | Behind a consent gate (GDPR/UK in-region users opt in; iOS **ATT** prompt before any tracking); screen names from route paths via a `NavigatorObserver`; never send PII or free text. |
| Push (FCM/APNs) | Register the device token with a backend endpoint (user + org scoped) **after** login; unregister on logout; tapping a notification navigates with `context.go(path)` through the normal guard. |
| Deep links | See [state-and-navigation §4](state-and-navigation.md#4-deep-links-optional). |
| In-app updates / ads / home widgets | Separate service each, platform-guarded inside the service, initialised post-first-frame, failures never block startup. |

Each integration is one service class in `lib/core/services/` with an interface and a no-op
implementation, created in `AppDependencies.create()` behind its flag, so tests and disabled
builds use the no-op. Platform config files that enable a plugin (e.g. `google-services.json`)
are applied conditionally in Gradle (`if (file("google-services.json").exists())`) so the app still
builds without them.
