---
name: flutter-expert
description: Use automatically whenever writing, reviewing or debugging Flutter/Dart code in this project's mobile app (`mobile/`, .dart files, pubspec.yaml, Android/iOS platform code) — alongside the flutter-guidelines skill, which wins on any conflict. Use when building cross-platform applications with Flutter 3+ and Dart. Invoke for widget development, state management, GoRouter navigation, platform-specific implementations, performance optimization, jank and rebuild issues.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.0"
  domain: frontend
  triggers: Flutter, Dart, widget, Riverpod, Bloc, GoRouter, cross-platform
  role: specialist
  scope: implementation
  output-format: code
  related-skills: react-native-expert, test-master, fullstack-guardian
---

# Flutter Expert

<!-- instadash: begin -->
## Instadash stack mapping (overrides the generic advice below)

In Instadash projects the **`flutter-guidelines` skill** and `docs/architecture-guidelines/mobile/`
are binding; the [canonical decisions](../../../docs/architecture-guidelines/README.md) win over
both. Where this skill (or its `references/`) disagrees, apply the right-hand column:

| Upstream advice | Instadash equivalent |
|---|---|
| Riverpod providers / `ConsumerWidget` / `StateNotifier`; Bloc/Cubit (`references/riverpod-state.md`, `bloc-state.md`) | `provider` + **`ChangeNotifier` controllers**, constructor-injected and built in the composition root `AppDependencies`; `context.watch`/`select`/`read`. Riverpod/Bloc only if `DOCS.md` records that decision. The *principles* still apply: immutable models, small focused controllers, no context/UI in state, test every controller. |
| "Use Consumer/ConsumerWidget, not StatefulWidget" | App/feature state in controllers; `StatefulWidget` is correct for ephemeral widget state (text controllers, animations, busy flags). |
| `routes/app_router.dart`, ad-hoc `redirect` checking login | `lib/app/router/`: paths in `AppRoutes`, default-deny `routePolicies`, the pure `RouteGuard` (session → tenant → permission), `refreshListenable: session`, `next` via `safeNext()`. |
| `context.push(..., extra: {...})` for data | Ids in the path; the destination loads by id. |
| `shared/services/api_service.dart`, any HTTP client | The ONE Dio instance (`createDio` + `SessionInterceptor` + `EnvelopeInterceptor`) → `ApiClient` → a repository per domain (`BaseRepository<T>`) → models. `Authorization: Token <t>` (no refresh; 401 = logout), `X-Organization-Id` (multi-tenant), `X-User-Tz`, envelope unwrap, `ApiError`. |
| `freezed` / `json_serializable` / `build_runner` | Hand-written immutable models with `fromJson` (via `Json` readers) + `toJson`; codegen only as a recorded project decision. |
| `data/domain/presentation` + use cases per feature | `lib/features/<feature>/{data,state,screens,widgets}` + shared `lib/core/`; no use-case layer unless a feature's logic genuinely needs it. |
| `hive_flutter` / `shared_preferences` for storage | Token in `flutter_secure_storage` (`SecureTokenStore`); `AppPreferences` (SharedPreferences) for non-secret UI state only. No local DB by default. |
| `core/constants/colors.dart`, `text_styles.dart` | `lib/core/theme/app_tokens.dart` (only place with raw colours) → `ColorScheme.fromSeed` → `AppTheme.light()/dark()` + `AppColors` extension; light + dark first-class. |
| `strings.dart` constants | `flutter gen-l10n` ARB files, `context.l10n.key`. |
| `flutter_lints: ^4` defaults | The scaffold's `analysis_options.yaml` (strict analyzer + extra lints), `dart format` page width 100, `flutter analyze --fatal-infos`. |
| `flutter_hooks` (`references/widget-patterns.md`) | Not used — `StatefulWidget` for local state. |
| Integration tests in the workflow | `flutter_test` + `mocktail` unit/widget tests; `integration_test` only when the user asks; flows verified on an emulator/simulator. |
| `flutter test --coverage` "before merging" | Same, plus the full gate: `dart format --set-exit-if-changed lib test` · `flutter analyze --fatal-infos` · `flutter test`. |

Everything else here (const widgets, keys for lists, `ListView.builder`, `RepaintBoundary`,
`compute()`, selective rebuilds, DevTools profiling, platform awareness) applies as written.
<!-- instadash: end -->

Senior mobile engineer building high-performance cross-platform applications with Flutter 3 and Dart.

## When to Use This Skill

- Building cross-platform Flutter applications
- Implementing state management (Riverpod, Bloc)
- Setting up navigation with GoRouter
- Creating custom widgets and animations
- Optimizing Flutter performance
- Platform-specific implementations

## Core Workflow

1. **Setup** — Scaffold project, add dependencies (`flutter pub get`), configure routing
2. **State** — Define Riverpod providers or Bloc/Cubit classes; verify with `flutter analyze`
   - If `flutter analyze` reports issues: fix all lints and warnings before proceeding; re-run until clean
3. **Widgets** — Build reusable, const-optimized components; run `flutter test` after each feature
   - If tests fail: inspect widget tree with Flutter DevTools, fix failing assertions, re-run `flutter test`
4. **Test** — Write widget and integration tests; confirm with `flutter test --coverage`
   - If coverage drops or tests fail: identify untested branches, add targeted tests, re-run before merging
5. **Optimize** — Profile with Flutter DevTools (`flutter run --profile`), eliminate jank, reduce rebuilds
   - If jank persists: check rebuild counts in the Performance overlay, isolate expensive `build()` calls, apply `const` or move state closer to consumers

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Riverpod | `references/riverpod-state.md` | State management, providers, notifiers |
| Bloc | `references/bloc-state.md` | Bloc, Cubit, event-driven state, complex business logic |
| GoRouter | `references/gorouter-navigation.md` | Navigation, routing, deep linking |
| Widgets | `references/widget-patterns.md` | Building UI components, const optimization |
| Structure | `references/project-structure.md` | Setting up project, architecture |
| Performance | `references/performance.md` | Optimization, profiling, jank fixes |

## Code Examples

### Riverpod Provider + ConsumerWidget (correct pattern)

```dart
// provider definition
final counterProvider = StateNotifierProvider<CounterNotifier, int>(
  (ref) => CounterNotifier(),
);

class CounterNotifier extends StateNotifier<int> {
  CounterNotifier() : super(0);
  void increment() => state = state + 1; // new instance, never mutate
}

// consuming widget — use ConsumerWidget, not StatefulWidget
class CounterView extends ConsumerWidget {
  const CounterView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final count = ref.watch(counterProvider);
    return Text('$count');
  }
}
```

### Before / After — State Management

```dart
// ❌ WRONG: app-wide state in setState
class _BadCounterState extends State<BadCounter> {
  int _count = 0;
  void _inc() => setState(() => _count++); // causes full subtree rebuild
}

// ✅ CORRECT: scoped Riverpod consumer
class GoodCounter extends ConsumerWidget {
  const GoodCounter({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final count = ref.watch(counterProvider);
    return IconButton(
      onPressed: () => ref.read(counterProvider.notifier).increment(),
      icon: const Icon(Icons.add), // const on static widgets
    );
  }
}
```

## Constraints

### MUST DO
- Use `const` constructors wherever possible
- Implement proper keys for lists
- Use `Consumer`/`ConsumerWidget` for state (not `StatefulWidget`)
- Follow Material/Cupertino design guidelines
- Profile with DevTools, fix jank
- Test widgets with `flutter_test`

### MUST NOT DO
- Build widgets inside `build()` method
- Mutate state directly (always create new instances)
- Use `setState` for app-wide state
- Skip `const` on static widgets
- Ignore platform-specific behavior
- Block UI thread with heavy computation (use `compute()`)

## Troubleshooting Common Failures

| Symptom | Likely Cause | Recovery |
|---------|-------------|----------|
| `flutter analyze` errors | Unresolved imports, missing `const`, type mismatches | Fix flagged lines; run `flutter pub get` if imports are missing |
| Widget test assertion failures | Widget tree mismatch or async state not settled | Use `tester.pumpAndSettle()` after state changes; verify finder selectors |
| Build fails after adding package | Incompatible dependency version | Run `flutter pub upgrade --major-versions`; check pub.dev compatibility |
| Jank / dropped frames | Expensive `build()` calls, uncached widgets, heavy main-thread work | Use `RepaintBoundary`, move heavy work to `compute()`, add `const` |
| Hot reload not reflecting changes | State held in `StateNotifier` not reset | Use hot restart (`R` in terminal) to reset full app state |

## Output Templates

When implementing Flutter features, provide:
1. Widget code with proper `const` usage
2. Provider/Bloc definitions
3. Route configuration if needed
4. Test file structure

[Documentation](https://jeffallan.github.io/claude-skills/skills/frontend/flutter-expert/)
