<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Mobile UI & Theming

> Tokens, light/dark themes, the generic widgets, forms, dialogs, lists, accessibility and i18n.
> Web analogue: [frontend shared-components](../frontend/shared-components.md) and the token
> pipeline in [frontend project-structure §7](../frontend/project-structure.md#7-theming--design-tokens).
> Code: [mobile scaffold — core](../../bootstrap/scaffold/mobile/core.md) and
> [widgets](../../bootstrap/scaffold/mobile/widgets.md).

---

## 1. Token pipeline (one source of colour)

```
AppPalette (brand hex)  →  ColorScheme.fromSeed (light / dark)  →  ThemeData + AppColors extension  →  widgets
AppSpacing · AppRadii · AppSizes (numbers)                        ↗
```

- `lib/core/theme/app_tokens.dart` — `AppPalette` (brand seed + success/warning/danger), the
  spacing scale (`xs 4 · sm 8 · md 12 · lg 16 · xl 24 · xxl 32`), radii and sizes (48 dp min tap
  target, max content width). **The only file with raw `Color(0x…)` values.** Pick the brand at
  Bootstrap by editing `AppPalette.brand`.
- `AppTheme.light()` / `AppTheme.dark()` build Material 3 `ThemeData` from the seed and set
  **component defaults** once (buttons, inputs, cards, dialogs, snackbars, app bar). Widgets use
  those defaults instead of restyling.
- `AppColors` (`ThemeExtension`) adds semantic colours `ColorScheme` lacks (`success`, `warning`,
  `textMuted`, `border`), derived per brightness. Read via `context.colors.success`;
  `context.colorScheme` / `context.textTheme` for the rest.
- New semantic colour or size → add a token/extension field, never a literal in a widget.

**Banned in widgets:** `Color(0x…)`, `Colors.<palette>` (`Colors.grey`, `Colors.blue` — `Colors.white`
/ `transparent` only inside the theme), magic numbers for padding/radius/font size
(`EdgeInsets.all(13)`), `TextStyle(fontSize: …)` from scratch — derive from `context.textTheme`.

## 2. Light + dark are both first-class

- `MaterialApp.router(theme: AppTheme.light(), darkTheme: AppTheme.dark(), themeMode: settings.themeMode)`;
  the user picks System / Light / Dark in Settings (persisted by `SettingsController`).
- Every screen is checked in both themes (widget tests pump both where colour logic exists; QA
  screenshots both).
- Status bar / nav bar icons follow the theme via `AppBarTheme` — no per-screen
  `SystemChrome` calls.

## 3. Generic widgets — use them first

| Widget | Use for |
|---|---|
| `EmptyState(icon, title, message?, action?)` | empty lists, placeholders, 404/403 bodies |
| `ErrorView(error, onRetry)` + `errorMessage(context, error)` | any failed load; localized copy for offline/5xx, backend message otherwise |
| `LoadingButton(label, onPressed: Future Function())` | every primary async action (shows spinner, blocks double taps) |
| `AppTextField(name, label, controller, apiError)` | form inputs; shows `apiError.firstError(name)` |
| `showConfirmDialog(...)` → `Future<bool>` | every confirm / destructive action (cancel first, primary last) |
| `showAppSnackBar(context, msg, isError:)` | transient feedback |
| `ResourceListView<T>(controller: ListController<T>, itemBuilder)` | any paged list: first-load spinner, pull-to-refresh, infinite scroll, empty + error states |
| `StatusScreen.notFound()` / `.notAuthorized()` | router error / permission pages |

- Before writing a new small piece (badge, avatar, status chip, section header), check
  `lib/core/widgets/`. Extend an existing widget with an optional parameter rather than forking it.
- Promote a feature widget to `core/widgets/` the second time another feature needs it; it must
  then be domain-agnostic (config/builder-driven, no feature imports).
- Status indicators use one `StatusChip` (create it once, token colours) — not ad-hoc containers.

## 4. Widget rules

- `StatelessWidget` by default; `const` constructors and `const` instances everywhere possible.
- **Extract widgets as classes**, not `Widget _buildX()` helper methods (classes get their own
  element, rebuild independently and are testable).
- `build()` is pure and cheap: no I/O, no object creation that should live in state, no
  `Future`s started from `build`. Kick off loads in `initState` / the controller.
- Lists: `ListView.builder` / slivers for anything unbounded; `key: ValueKey(item.id)` on items
  that can reorder or be removed.
- Layout: `SafeArea` on every screen body; constrain readable content width
  (`AppSizes.maxContentWidth`) so tablets look right; `LayoutBuilder` breakpoints when a screen
  needs two panes.
- Images from the network use a cache (add `cached_network_image` when the first one appears) and
  explicit sizes; heavy CPU work goes to `compute()`/isolates.
- Dispose every controller, subscription, animation and `TextEditingController` you create.

## 5. Sectioned screens & data flow

- A screen with several independent cards loads each section on its own (own controller or
  `FutureBuilder`-free controller state) with its own loading placeholder — never block the whole
  page on one request.
- After a successful save: refresh the affected section from the API (don't trust optimistic
  local state as truth), then show a snackbar.
- Pull-to-refresh on every data screen.

## 6. Accessibility

- Tap targets ≥ 48 dp (theme sets button minimum sizes). Icon-only buttons have a `tooltip`
  (also the screen-reader label).
- Text scales: never fix heights around text; test at 200 % text scale for key screens.
- Contrast comes from the seeded scheme — don't lower it with opacity on text.
- `Semantics` labels for custom-painted or gesture-only widgets; decorative images
  `excludeFromSemantics: true`.

## 7. i18n

- ARB files in `lib/l10n/` (`app_en.arb` is the template; add `app_<lang>.arb` per language);
  `flutter pub get` / `flutter run` regenerate `app_localizations*.dart` (committed, never edited).
- Use `context.l10n.keyName` — **no user-facing string literals** in widgets, dialogs, snackbars or
  validators. Placeholders are typed (`"homeGreeting": "Hello, {name}"` + `@homeGreeting`).
- Keys are `lowerCamelCase`, grouped by prefix (`action…`, `field…`, `error…`, `<feature>…`).
  Reuse `action*` keys for common verbs.
- Dates/numbers/currency via `intl` (`DateFormat.yMMMd(locale)`, `NumberFormat`), never string
  concatenation. The copyright line is `© <year> <legal entity>` from config.
- Controllers don't produce copy: they expose `ApiError`/enums; widgets map them to strings.
- Language choice (optional) is `SettingsController.setLocale`; `null` follows the device.
