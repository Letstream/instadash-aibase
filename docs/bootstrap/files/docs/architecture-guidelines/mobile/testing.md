<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Mobile Testing

> **`flutter_test` + `mocktail` for everything unit-testable; widget tests for generic widgets
> and forms; the running app on an emulator/simulator for flows and visuals.** `integration_test`
> suites only when the user asks for them. ~60 example tests ship with the
> [mobile scaffold](../../bootstrap/scaffold/mobile/README.md).

---

## 1. Stack

| Tool | Role |
|---|---|
| `flutter_test` | runner, `test` / `group` / `testWidgets`, matchers, `WidgetTester`, fake async |
| `mocktail` | mocks/stubs without codegen (`class MockX extends Mock implements X {}`) |
| Fakes | `MemoryTokenStore`, `SharedPreferences.setMockInitialValues`, a fake Dio `HttpClientAdapter` |
| `flutter test --coverage` | `coverage/lcov.info` |

No real network, no real plugins in unit/widget tests: inject fakes through constructors (that is
why nothing is a singleton).

## 2. Layout & commands

- `test/` mirrors `lib/`: `lib/core/api/api_error.dart` → `test/core/api/api_error_test.dart`.
  Files end in `_test.dart`.
- `test/helpers/`: `factories.dart` (JSON builders `userJson({...overrides})`, `testConfig()`),
  `mocks.dart` (shared mocktail classes), `pump_app.dart` (`tester.pumpApp(widget, providers:,
  themeMode:)` wraps theme + localizations).
- Tests are analyzed and formatted like app code.

```bash
flutter test                         # CI + before "done"
flutter test test/core               # a folder while developing
flutter test --coverage              # writes coverage/lcov.info
```

**Coverage** target: **80 % lines** on the unit-testable layers — `lib/core/{api,data,models,auth,config,storage,settings}`,
`lib/features/*/{data,state}`, `lib/app/router/route_guard.dart`, and `lib/core/widgets/resource_list/list_controller.dart`.
Screens and platform glue are covered by widget tests where they hold logic and by device QA.

## 3. What to test

| Unit | Test | Technique |
|---|---|---|
| `AppConfig` | defaults, tenancy parse errors, https outside dev | `AppConfig.parse(...)` |
| Endpoints | param filling, encoding, count mismatch | plain calls |
| `ApiError` | envelope / DRF shapes, field errors, network (status 0) | `ApiError.fromResponse`, `fromDioException` |
| Interceptors | headers (token, tenant only in multi, tz; none to foreign origins), envelope unwrap, `status:false` on 2xx, 401/403 hooks, DRF list params | real `createDio` + fake `HttpClientAdapter` |
| **Models** | `fromJson` maps every field + defaults for missing ones + throws on missing id; `toJson` writable fields; getters | factories |
| **Repositories** | right path/method/params, DTO → models, both list shapes, list-only fails on detail | `MockApiClient` + `when(...)` |
| **Controllers** | every action and state transition, error paths, persistence, RBAC (`single` / `all` / `any`, owner, `*`), single-tenant mode | mocked repositories, `MemoryTokenStore`, mock prefs |
| Route guard | each branch: splash, login + `next`, guest bounce, open-redirect rejection, org selector, permission gate, single-tenant | `RouteGuard` + a tiny `FakeSession` |
| Generic widgets | render per parameter, callbacks, both themes | `tester.pumpApp` |
| Forms | client validation blocks the call; backend field errors shown under inputs; banner for non-field errors | mocked controller via `ChangeNotifierProvider.value` |

Keep tests about **behaviour**, not widget-tree snapshots. Every bug fix gets a regression test.
Golden tests are optional (fonts differ across machines — pin a font and run goldens in one CI
image if a project adopts them).

## 4. Patterns

```dart
// Repository with a mocked client — no network
final client = MockApiClient();
when(() => client.get<Object?>('orders/', query: any(named: 'query')))
    .thenAnswer((_) async => {'count': 1, 'results': [orderJson()]});
final page = await OrderRepository(client).list();
expect(page.items.single, isA<Order>());
```

```dart
// Controller with mocked repositories + in-memory storage
SharedPreferences.setMockInitialValues({'app.installed': true});
final credentials = SessionCredentials(tokenStore: MemoryTokenStore('tok'), preferences: await AppPreferences.load());
await credentials.load();
final session = SessionController(config: testConfig(), credentials: credentials,
    authRepository: auth, organizationRepository: organizations);
when(() => auth.me()).thenThrow(const ApiError(status: 401, message: 'expired'));
await session.restore();
expect(session.status, SessionStatus.unauthenticated);
```

```dart
// Widget with a mocked controller
await tester.pumpApp(const LoginScreen(),
    providers: [ChangeNotifierProvider<SessionController>.value(value: mockSession)]);
await tester.tap(find.byType(FilledButton));
await tester.pumpAndSettle();
expect(find.text('This field is required.'), findsNWidgets(2));
```

- `registerFallbackValue(...)` for custom types used with `any()`.
- Use `pumpAndSettle()` after taps/async work; `pumpEventQueue()` for pure futures.
- Provide `Listenable` objects with `ChangeNotifierProvider.value` (plain `Provider.value` rejects
  them in debug).

## 5. Device QA (flows and visuals)

Unit/widget tests don't replace running the app. Before "done" on UI work:

```bash
flutter emulators --launch <id>      # or open the iOS Simulator
nohup flutter run --dart-define-from-file=config/dev.json > .flutter-run.log 2>&1 &
tail -n 40 .flutter-run.log          # never run it in the foreground
flutter screenshot -o shots/<journey>-light.png
```

Walk the journeys from `DOCS.md`: launch (splash) → login → (multi-tenant) choose organisation →
home → the changed screen → create/edit → settings → sign out. Check **light and dark**, a large
text scale on key screens, offline behaviour (airplane mode → error view with retry, not a
logout), and the log for exceptions/overflow warnings. Save screenshots under `shots/`.

`integration_test` (driving the app on a device in CI) is added only on request; when it is,
tests live in `integration_test/` and run against a seeded dev backend.

## 6. Definition of done (mobile)

`dart format --set-exit-if-changed lib test` · `flutter analyze --fatal-infos` · `flutter test`
all green; new logic has tests; the flow was observed on an emulator/simulator in both themes.
