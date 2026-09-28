# Mobile scaffold — app core

> Part of the [mobile scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the mobile repo root (`mobile/`).

Entry point, composition root, root widget, build config, theme tokens, i18n, preferences and
settings, plus the shared test helpers. The data layer is in [data-layer.md](data-layer.md), the
session + router + screens in [state-routing.md](state-routing.md), generic widgets in
[widgets.md](widgets.md).

### `lib/main.dart`

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'dart:async';

import 'package:<project_slug>/app/app.dart';
import 'package:<project_slug>/app/dependencies.dart';
import 'package:flutter/widgets.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final dependencies = await AppDependencies.create();
  unawaited(dependencies.session.restore());
  runApp(App(dependencies: dependencies));
}
```

### `lib/app/dependencies.dart`

The composition root — the only place long-lived objects are constructed. Optional integrations (crash reporting, analytics, push) are added here behind config flags.

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/core/api/api_client.dart';
import 'package:<project_slug>/core/api/interceptors.dart';
import 'package:<project_slug>/core/auth/session_credentials.dart';
import 'package:<project_slug>/core/config/app_config.dart';
import 'package:<project_slug>/core/settings/settings_controller.dart';
import 'package:<project_slug>/core/storage/app_preferences.dart';
import 'package:<project_slug>/core/storage/token_store.dart';
import 'package:<project_slug>/features/auth/data/auth_repository.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:<project_slug>/features/organizations/data/organization_repository.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_timezone/flutter_timezone.dart';

/// Composition root: builds every long-lived object once, in dependency order, and wires the
/// http hooks to the session. Nothing else calls these constructors in app code.
class AppDependencies {
  AppDependencies({
    required this.config,
    required this.preferences,
    required this.credentials,
    required this.apiClient,
    required this.authRepository,
    required this.organizationRepository,
    required this.session,
    required this.settings,
  });

  static Future<AppDependencies> create({AppConfig? config, TokenStore? tokenStore}) async {
    final appConfig = config ?? AppConfig.fromEnvironment();
    final preferences = await AppPreferences.load();
    final credentials = SessionCredentials(
      tokenStore: tokenStore ?? SecureTokenStore(),
      preferences: preferences,
    );
    await credentials.load();
    final timezone = await _deviceTimezone();
    final hooks = HttpHooks();
    final apiClient = ApiClient(
      createDio(
        config: appConfig,
        credentials: credentials,
        hooks: hooks,
        timezone: () => timezone,
      ),
    );
    final authRepository = AuthRepository(apiClient);
    final organizationRepository = OrganizationRepository(apiClient);
    final session = SessionController(
      config: appConfig,
      credentials: credentials,
      authRepository: authRepository,
      organizationRepository: organizationRepository,
    );
    hooks.onUnauthorized = session.handleUnauthorized;
    return AppDependencies(
      config: appConfig,
      preferences: preferences,
      credentials: credentials,
      apiClient: apiClient,
      authRepository: authRepository,
      organizationRepository: organizationRepository,
      session: session,
      settings: SettingsController(preferences),
    );
  }

  final AppConfig config;
  final AppPreferences preferences;
  final SessionCredentials credentials;
  final ApiClient apiClient;
  final AuthRepository authRepository;
  final OrganizationRepository organizationRepository;
  final SessionController session;
  final SettingsController settings;

  /// IANA zone name for `X-User-Tz` (falls back to UTC).
  static Future<String> _deviceTimezone() async {
    try {
      return (await FlutterTimezone.getLocalTimezone()).identifier;
    } catch (error) {
      debugPrint('Timezone lookup failed: $error');
      return 'UTC';
    }
  }
}
```

### `lib/app/app.dart`

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/app/dependencies.dart';
import 'package:<project_slug>/app/router/app_router.dart';
import 'package:<project_slug>/core/api/api_client.dart';
import 'package:<project_slug>/core/config/app_config.dart';
import 'package:<project_slug>/core/i18n/l10n.dart';
import 'package:<project_slug>/core/settings/settings_controller.dart';
import 'package:<project_slug>/core/theme/app_theme.dart';
import 'package:<project_slug>/features/auth/data/auth_repository.dart';
import 'package:<project_slug>/features/organizations/data/organization_repository.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

/// Root widget: provides the dependencies, builds the router once, applies theme + locale.
class App extends StatefulWidget {
  const App({super.key, required this.dependencies});

  final AppDependencies dependencies;

  @override
  State<App> createState() => _AppState();
}

class _AppState extends State<App> {
  late final GoRouter _router = createRouter(
    session: widget.dependencies.session,
    config: widget.dependencies.config,
  );

  @override
  void dispose() {
    _router.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final deps = widget.dependencies;
    return MultiProvider(
      providers: [
        Provider<AppConfig>.value(value: deps.config),
        Provider<ApiClient>.value(value: deps.apiClient),
        Provider<AuthRepository>.value(value: deps.authRepository),
        Provider<OrganizationRepository>.value(value: deps.organizationRepository),
        ChangeNotifierProvider.value(value: deps.session),
        ChangeNotifierProvider.value(value: deps.settings),
      ],
      child: Consumer<SettingsController>(
        builder: (context, settings, _) => MaterialApp.router(
          onGenerateTitle: (_) => deps.config.appName,
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light(),
          darkTheme: AppTheme.dark(),
          themeMode: settings.themeMode,
          locale: settings.locale,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          routerConfig: _router,
        ),
      ),
    );
  }
}
```

### `lib/core/config/app_config.dart`

`TENANCY_MODE` must match the backend's choice in `DOCS.md`. Invalid config fails at startup.

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

/// Build-time configuration, read once from `--dart-define` / `--dart-define-from-file`.
///
/// Every value here is compiled into the app binary and is therefore **public**. Never pass a
/// secret through a dart-define.
library;

/// Whether the backend uses organisations (`X-Organization-Id`) or a single tenant.
enum TenancyMode {
  multi,
  single;

  /// Parses `TENANCY_MODE`; empty means multi-tenant, anything unknown is a startup error.
  static TenancyMode parse(String value) => switch (value) {
    '' || 'multi' => TenancyMode.multi,
    'single' => TenancyMode.single,
    _ => throw ConfigError('Invalid TENANCY_MODE "$value" (expected "multi" or "single").'),
  };
}

/// Deployment environment the build targets.
enum AppEnvironment {
  dev,
  staging,
  prod;

  static AppEnvironment parse(String value) => switch (value) {
    '' || 'dev' => AppEnvironment.dev,
    'staging' => AppEnvironment.staging,
    'prod' => AppEnvironment.prod,
    _ => throw ConfigError('Invalid APP_ENV "$value" (expected dev, staging or prod).'),
  };
}

/// Raised when the build configuration is missing or invalid.
class ConfigError extends Error {
  ConfigError(this.message);

  final String message;

  @override
  String toString() => 'ConfigError: $message';
}

/// Validated, immutable app configuration.
class AppConfig {
  const AppConfig({
    required this.environment,
    required this.appName,
    required this.legalEntityName,
    required this.apiBaseUrl,
    required this.tenancyMode,
  });

  /// Parses raw values; used by [AppConfig.fromEnvironment] and by tests.
  factory AppConfig.parse({
    String environment = '',
    String appName = '',
    String legalEntityName = '',
    String apiBaseUrl = '',
    String tenancyMode = '',
  }) {
    final env = AppEnvironment.parse(environment);
    return AppConfig(
      environment: env,
      appName: appName.isEmpty ? 'App' : appName,
      legalEntityName: legalEntityName.isEmpty ? appName : legalEntityName,
      apiBaseUrl: _parseApiBaseUrl(apiBaseUrl, env),
      tenancyMode: TenancyMode.parse(tenancyMode),
    );
  }

  /// Reads the compile-time defines (`flutter run --dart-define-from-file=config/dev.json`).
  factory AppConfig.fromEnvironment() => AppConfig.parse(
    environment: const String.fromEnvironment('APP_ENV'),
    appName: const String.fromEnvironment('APP_NAME'),
    legalEntityName: const String.fromEnvironment('LEGAL_ENTITY_NAME'),
    apiBaseUrl: const String.fromEnvironment('API_BASE_URL'),
    tenancyMode: const String.fromEnvironment('TENANCY_MODE'),
  );

  final AppEnvironment environment;
  final String appName;
  final String legalEntityName;

  /// Absolute API root ending in `/` (e.g. `https://api.example.com/api/`).
  final String apiBaseUrl;
  final TenancyMode tenancyMode;

  /// True when the project uses organisations + the `X-Organization-Id` header.
  bool get isMultiTenant => tenancyMode == TenancyMode.multi;

  bool get isProduction => environment == AppEnvironment.prod;

  static String _parseApiBaseUrl(String value, AppEnvironment env) {
    final uri = Uri.tryParse(value);
    if (value.isEmpty || uri == null || !uri.hasScheme || uri.host.isEmpty) {
      throw ConfigError(
        'API_BASE_URL is missing or invalid. Run with --dart-define-from-file=config/<env>.json.',
      );
    }
    if (env != AppEnvironment.dev && uri.scheme != 'https') {
      throw ConfigError('API_BASE_URL must use https outside dev.');
    }
    return value.endsWith('/') ? value : '$value/';
  }
}
```

### `lib/core/theme/app_tokens.dart`

The only file with raw colour values. Pick the brand at Bootstrap by changing `AppPalette.brand`.

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:flutter/material.dart';

/// Brand palette — the ONLY place raw colour values appear. Pick the brand at Bootstrap by
/// changing these; everything else derives from them via the [ColorScheme] and [AppColors].
abstract final class AppPalette {
  static const brand = Color(0xFF6366F1);
  static const success = Color(0xFF16A34A);
  static const warning = Color(0xFFD97706);
  static const danger = Color(0xFFDC2626);
}

/// Spacing scale — every gap, padding and margin uses one of these.
abstract final class AppSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;
}

/// Corner radii.
abstract final class AppRadii {
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 20;
}

/// Layout sizes.
abstract final class AppSizes {
  /// Minimum touch target (Material + Apple HIG).
  static const double minTapTarget = 48;
  static const double maxContentWidth = 560;
  static const double iconLg = 56;
}
```

### `lib/core/theme/app_colors.dart`

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/core/theme/app_tokens.dart';
import 'package:flutter/material.dart';

/// App semantic colours not covered by [ColorScheme], light + dark, as a [ThemeExtension].
/// Read them with `context.colors.success`.
@immutable
class AppColors extends ThemeExtension<AppColors> {
  const AppColors({
    required this.success,
    required this.onSuccess,
    required this.warning,
    required this.onWarning,
    required this.textMuted,
    required this.border,
  });

  factory AppColors.from(ColorScheme scheme) => AppColors(
    success: AppPalette.success,
    onSuccess: Colors.white,
    warning: AppPalette.warning,
    onWarning: Colors.white,
    textMuted: scheme.onSurfaceVariant,
    border: scheme.outlineVariant,
  );

  final Color success;
  final Color onSuccess;
  final Color warning;
  final Color onWarning;
  final Color textMuted;
  final Color border;

  @override
  AppColors copyWith({
    Color? success,
    Color? onSuccess,
    Color? warning,
    Color? onWarning,
    Color? textMuted,
    Color? border,
  }) => AppColors(
    success: success ?? this.success,
    onSuccess: onSuccess ?? this.onSuccess,
    warning: warning ?? this.warning,
    onWarning: onWarning ?? this.onWarning,
    textMuted: textMuted ?? this.textMuted,
    border: border ?? this.border,
  );

  @override
  AppColors lerp(AppColors? other, double t) {
    if (other == null) return this;
    return AppColors(
      success: Color.lerp(success, other.success, t)!,
      onSuccess: Color.lerp(onSuccess, other.onSuccess, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      onWarning: Color.lerp(onWarning, other.onWarning, t)!,
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
      border: Color.lerp(border, other.border, t)!,
    );
  }
}

extension AppThemeContext on BuildContext {
  ColorScheme get colorScheme => Theme.of(this).colorScheme;
  TextTheme get textTheme => Theme.of(this).textTheme;
  AppColors get colors => Theme.of(this).extension<AppColors>()!;
}
```

### `lib/core/theme/app_theme.dart`

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/core/theme/app_colors.dart';
import 'package:<project_slug>/core/theme/app_tokens.dart';
import 'package:flutter/material.dart';

/// Light and dark [ThemeData] built from the tokens. Component defaults live here so widgets
/// never restyle buttons, inputs or cards one by one.
abstract final class AppTheme {
  static ThemeData light() => _build(Brightness.light);

  static ThemeData dark() => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppPalette.brand,
      brightness: brightness,
      error: AppPalette.danger,
    );
    final rounded = RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppRadii.md));
    const minSize = Size(AppSizes.minTapTarget, AppSizes.minTapTarget);
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      extensions: [AppColors.from(scheme)],
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        color: scheme.surfaceContainerLow,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadii.lg),
          side: BorderSide(color: scheme.outlineVariant),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHighest,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadii.md),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.md,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: minSize, shape: rounded),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(minimumSize: minSize, shape: rounded),
      ),
      textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(minimumSize: minSize)),
      snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
      dialogTheme: DialogThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppRadii.lg)),
      ),
    );
  }
}
```

### `lib/core/i18n/l10n.dart`

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/l10n/app_localizations.dart';
import 'package:flutter/widgets.dart';

export 'package:<project_slug>/l10n/app_localizations.dart';

/// `context.l10n.actionSave` — shorthand for the generated localizations.
extension L10nContext on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this);
}
```

### `lib/l10n/app_en.arb`

Template ARB (JSON — no header). Add `app_<lang>.arb` files for more languages.

```json
{
  "@@locale": "en",
  "actionCancel": "Cancel",
  "actionConfirm": "Confirm",
  "actionRetry": "Try again",
  "actionSave": "Save",
  "actionSignIn": "Sign in",
  "actionSignOut": "Sign out",
  "actionBackHome": "Back to home",
  "fieldEmail": "Email",
  "fieldPassword": "Password",
  "validationRequired": "This field is required.",
  "errorNetwork": "You appear to be offline. Check your connection and try again.",
  "errorGeneric": "Something went wrong. Please try again.",
  "loginTitle": "Welcome back",
  "loginSubtitle": "Sign in to continue",
  "selectOrganizationTitle": "Choose an organisation",
  "selectOrganizationEmpty": "You are not a member of any organisation yet.",
  "homeGreeting": "Hello, {name}",
  "@homeGreeting": {
    "placeholders": {
      "name": {
        "type": "String"
      }
    }
  },
  "homeOrganization": "Organisation",
  "homeSwitchOrganization": "Switch organisation",
  "settingsTitle": "Settings",
  "settingsTheme": "Appearance",
  "themeSystem": "System",
  "themeLight": "Light",
  "themeDark": "Dark",
  "signOutConfirmTitle": "Sign out?",
  "signOutConfirmBody": "You will need to sign in again to use the app.",
  "notAuthorizedTitle": "Not authorised",
  "notAuthorizedBody": "You do not have permission to open this screen.",
  "notFoundTitle": "Page not found",
  "notFoundBody": "The screen you tried to open does not exist.",
  "emptyTitle": "Nothing here yet",
  "copyright": "© {year} {entity}",
  "@copyright": {
    "placeholders": {
      "year": {
        "type": "int"
      },
      "entity": {
        "type": "String"
      }
    }
  }
}
```

### `lib/core/storage/app_preferences.dart`

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Namespaced, typed wrapper over SharedPreferences for **non-secret** UI state only
/// (theme, locale, current organisation). Tokens go to `TokenStore`.
class AppPreferences {
  AppPreferences(this._prefs);

  static Future<AppPreferences> load() async =>
      AppPreferences(await SharedPreferences.getInstance());

  static const _prefix = 'app.';
  static const _themeMode = '${_prefix}theme_mode';
  static const _locale = '${_prefix}locale';
  static const _organizationId = '${_prefix}organization_id';
  static const _installed = '${_prefix}installed';

  final SharedPreferences _prefs;

  ThemeMode get themeMode =>
      ThemeMode.values.asNameMap()[_prefs.getString(_themeMode)] ?? ThemeMode.system;

  Future<void> setThemeMode(ThemeMode mode) => _prefs.setString(_themeMode, mode.name);

  /// `null` = follow the device language.
  String? get localeCode => _prefs.getString(_locale);

  Future<void> setLocaleCode(String? code) =>
      code == null ? _prefs.remove(_locale) : _prefs.setString(_locale, code);

  String? get organizationId => _prefs.getString(_organizationId);

  Future<void> setOrganizationId(String? id) =>
      id == null ? _prefs.remove(_organizationId) : _prefs.setString(_organizationId, id);

  /// False on the first launch after (re)install — used to drop keychain leftovers on iOS.
  bool get isInstalled => _prefs.getBool(_installed) ?? false;

  Future<void> markInstalled() => _prefs.setBool(_installed, true);
}
```

### `lib/core/settings/settings_controller.dart`

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/core/storage/app_preferences.dart';
import 'package:flutter/material.dart';

/// Appearance + language preferences (System / Light / Dark, device or chosen locale).
class SettingsController extends ChangeNotifier {
  SettingsController(this._preferences)
    : _themeMode = _preferences.themeMode,
      _locale = _preferences.localeCode == null ? null : Locale(_preferences.localeCode!);

  final AppPreferences _preferences;
  ThemeMode _themeMode;
  Locale? _locale;

  ThemeMode get themeMode => _themeMode;

  /// `null` = follow the device locale.
  Locale? get locale => _locale;

  Future<void> setThemeMode(ThemeMode mode) async {
    if (mode == _themeMode) return;
    _themeMode = mode;
    notifyListeners();
    await _preferences.setThemeMode(mode);
  }

  Future<void> setLocale(Locale? locale) async {
    _locale = locale;
    notifyListeners();
    await _preferences.setLocaleCode(locale?.languageCode);
  }
}
```

### `test/core/config/app_config_test.dart`

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/core/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('AppConfig.parse', () {
    test('defaults to multi-tenant dev and adds the trailing slash', () {
      final config = AppConfig.parse(apiBaseUrl: 'http://10.0.2.2:8000/api');
      expect(config.isMultiTenant, isTrue);
      expect(config.environment, AppEnvironment.dev);
      expect(config.apiBaseUrl, 'http://10.0.2.2:8000/api/');
      expect(config.appName, 'App');
    });

    test('parses single tenancy and names', () {
      final config = AppConfig.parse(
        apiBaseUrl: 'https://api.test/api/',
        tenancyMode: 'single',
        appName: 'Demo',
      );
      expect(config.tenancyMode, TenancyMode.single);
      expect(config.legalEntityName, 'Demo');
    });

    test('rejects an unknown tenancy mode', () {
      expect(
        () => AppConfig.parse(apiBaseUrl: 'https://api.test/api/', tenancyMode: 'multy'),
        throwsA(isA<ConfigError>()),
      );
    });

    test('requires an API base URL', () {
      expect(AppConfig.parse, throwsA(isA<ConfigError>()));
    });

    test('requires https outside dev', () {
      expect(
        () => AppConfig.parse(environment: 'prod', apiBaseUrl: 'http://api.test/api/'),
        throwsA(isA<ConfigError>()),
      );
      expect(
        AppConfig.parse(environment: 'prod', apiBaseUrl: 'https://api.test/api/').isProduction,
        isTrue,
      );
    });
  });
}
```

### `test/helpers/factories.dart`

JSON builders — override only what a test cares about.

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/core/config/app_config.dart';
import 'package:<project_slug>/core/models/json.dart';

/// DTO builders — override only what a test cares about.
JsonMap userJson([JsonMap overrides = const {}]) => {
  'id': 1,
  'email': 'ada@example.com',
  'first_name': 'Ada',
  'last_name': 'Lovelace',
  'role': 'member',
  'permissions': <String>[],
  'email_confirmed': true,
  'created_on': '2026-01-02T03:04:05Z',
  ...overrides,
};

JsonMap organizationJson([JsonMap overrides = const {}]) => {
  'id': 'org-1',
  'name': 'Acme',
  'is_owner': false,
  'role': 'Member',
  'permissions': <String>['order:read'],
  ...overrides,
};

AppConfig testConfig({String tenancyMode = 'multi'}) => AppConfig.parse(
  appName: 'Test App',
  legalEntityName: 'Test Entity',
  apiBaseUrl: 'https://api.test/api/',
  tenancyMode: tenancyMode,
);
```

### `test/helpers/mocks.dart`

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/core/api/api_client.dart';
import 'package:<project_slug>/features/auth/data/auth_repository.dart';
import 'package:<project_slug>/features/organizations/data/organization_repository.dart';
import 'package:mocktail/mocktail.dart';

class MockApiClient extends Mock implements ApiClient {}

class MockAuthRepository extends Mock implements AuthRepository {}

class MockOrganizationRepository extends Mock implements OrganizationRepository {}
```

### `test/helpers/pump_app.dart`

`tester.pumpApp(widget, providers:, themeMode:)` — theme + localizations for widget tests.

```dart
// <Project Name>
// Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
// Author: <Legal Entity Name>
//
// Built on Instadash AI Base by Letstream
// (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
// Template portions (c) Letstream Ventures Pvt Ltd.
//
// The Instadash AI Base template is provided "AS IS", without warranty of any
// kind, express or implied, including merchantability, fitness for a particular
// purpose and non-infringement, unless covered by an explicit written agreement
// with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
// redistribution of the template, in whole or in part, is prohibited and may
// result in legal action and remedies available under applicable law.

import 'package:<project_slug>/core/i18n/l10n.dart';
import 'package:<project_slug>/core/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:provider/single_child_widget.dart';

extension PumpApp on WidgetTester {
  /// Pumps [child] inside the app theme + localizations (+ optional providers).
  Future<void> pumpApp(
    Widget child, {
    List<SingleChildWidget> providers = const [],
    ThemeMode themeMode = ThemeMode.light,
  }) async {
    final app = MaterialApp(
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: themeMode,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: child,
    );
    await pumpWidget(providers.isEmpty ? app : MultiProvider(providers: providers, child: app));
    await pumpAndSettle();
  }
}
```
