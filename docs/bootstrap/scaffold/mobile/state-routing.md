# Mobile scaffold — session, routing & screens

> Part of the [mobile scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the mobile repo root (`mobile/`).

`SessionController` (auth + tenancy + RBAC), the go_router setup with one pure `RouteGuard` and
default-deny `routePolicies`, and the starter screens: splash (restore + offline retry), login,
organisation selector (multi-tenant), home, settings (theme, sign out), 404/403. Rules in
[state-and-navigation](../../../architecture-guidelines/mobile/state-and-navigation.md).

Adding a feature route: a path in `AppRoutes`, a `GoRoute` in `createRouter`, and — when it
needs a permission — a `routePolicies` entry, e.g.
`'/orders': RoutePolicy(permission: PermissionQuery.single('order:read'))`.

### `lib/features/auth/state/session_controller.dart`

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

import 'package:<project_slug>/core/api/api_error.dart';
import 'package:<project_slug>/core/auth/permissions.dart';
import 'package:<project_slug>/core/auth/session_credentials.dart';
import 'package:<project_slug>/core/config/app_config.dart';
import 'package:<project_slug>/core/models/organization.dart';
import 'package:<project_slug>/core/models/user.dart';
import 'package:<project_slug>/features/auth/data/auth_repository.dart';
import 'package:<project_slug>/features/organizations/data/organization_repository.dart';
import 'package:flutter/foundation.dart';

enum SessionStatus { unknown, unauthenticated, authenticated }

/// What the route guard needs from the session (lets tests use a tiny fake).
abstract interface class SessionView implements Listenable {
  SessionStatus get status;

  /// Multi-tenant and no valid organisation selected yet.
  bool get needsOrganization;

  bool hasPermission(PermissionQuery? query);
}

/// Session, tenancy and RBAC state: token, user, organisations, current organisation.
///
/// In single-tenant mode organisations are never loaded and permissions come from the user.
class SessionController extends ChangeNotifier implements SessionView {
  SessionController({
    required this._config,
    required this._credentials,
    required this._authRepository,
    required this._organizationRepository,
  });

  final AppConfig _config;
  final SessionCredentials _credentials;
  final AuthRepository _authRepository;
  final OrganizationRepository _organizationRepository;

  SessionStatus _status = SessionStatus.unknown;
  User? _user;
  List<Organization> _organizations = const [];
  ApiError? _restoreError;

  @override
  SessionStatus get status => _status;
  User? get user => _user;
  List<Organization> get organizations => _organizations;
  bool get isAuthenticated => _status == SessionStatus.authenticated;

  /// Set when restoring failed for a reason other than 401 (e.g. offline) — splash offers retry.
  ApiError? get restoreError => _restoreError;

  Organization? get currentOrganization {
    final id = _credentials.organizationId;
    for (final org in _organizations) {
      if (org.id == id) return org;
    }
    return null;
  }

  @override
  bool get needsOrganization => _config.isMultiTenant && currentOrganization == null;

  /// Permission codes in the active scope (current org, or the user in single-tenant).
  List<String> get permissions => _config.isMultiTenant
      ? (currentOrganization?.permissions ?? const [])
      : (_user?.permissions ?? const []);

  bool get isOwner => _config.isMultiTenant
      ? (currentOrganization?.isOwner ?? false)
      : _user?.role == UserRole.owner;

  @override
  bool hasPermission(PermissionQuery? query) =>
      hasPermissions(permissions, query, isOwner: isOwner);

  /// Restores the session from the stored token on app start.
  Future<void> restore() async {
    _restoreError = null;
    if (!_credentials.hasToken) {
      _setStatus(SessionStatus.unauthenticated);
      return;
    }
    try {
      _user = await _authRepository.me();
      if (_config.isMultiTenant) await loadOrganizations(notify: false);
      _setStatus(SessionStatus.authenticated);
    } on ApiError catch (error) {
      if (error.isUnauthorized) {
        await _clear();
      } else {
        // Keep the token: a flaky network must not log the user out.
        _restoreError = error;
        _setStatus(SessionStatus.unknown);
      }
    }
  }

  /// Throws [ApiError] (field errors for the form) on failure.
  Future<void> login({required String email, required String password}) async {
    final result = await _authRepository.login(email: email, password: password);
    await _credentials.setToken(result.token);
    _user = result.user;
    if (_config.isMultiTenant) await loadOrganizations(notify: false);
    _setStatus(SessionStatus.authenticated);
  }

  Future<void> loadOrganizations({bool notify = true}) async {
    _organizations = await _organizationRepository.mine();
    if (currentOrganization == null) {
      final only = _organizations.length == 1 ? _organizations.first : null;
      await _credentials.setOrganizationId(only?.id);
    }
    if (notify) notifyListeners();
  }

  /// Switches tenant. Returns false when the user is not a member (never trust the caller).
  Future<bool> selectOrganization(String id) async {
    if (!_organizations.any((org) => org.id == id)) return false;
    await _credentials.setOrganizationId(id);
    notifyListeners();
    return true;
  }

  Future<void> logout() async {
    try {
      if (_credentials.hasToken) await _authRepository.logout();
    } on ApiError {
      // The token is dropped locally either way.
    } finally {
      await _clear();
    }
  }

  /// Wired to the http 401 hook: any 401 ends the session (there is no refresh flow).
  void handleUnauthorized(ApiError error) {
    if (_status == SessionStatus.authenticated) unawaited(_clear());
  }

  Future<void> _clear() async {
    await _credentials.clear();
    _user = null;
    _organizations = const [];
    _setStatus(SessionStatus.unauthenticated);
  }

  void _setStatus(SessionStatus status) {
    _status = status;
    notifyListeners();
  }
}
```

### `lib/app/router/app_routes.dart`

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

import 'package:<project_slug>/core/auth/permissions.dart';

/// Route paths, declared once. Screens navigate with `context.go(AppRoutes.settings)`.
abstract final class AppRoutes {
  static const splash = '/splash';
  static const login = '/login';
  static const selectOrganization = '/select-organization';
  static const home = '/';
  static const settings = '/settings';
  static const notAuthorized = '/not-authorized';
}

/// Access rules of a route. The default is **deny**: signed in, organisation selected (in
/// multi-tenant mode), no extra permission. Only an explicit `isPublic` opens a route.
class RoutePolicy {
  const RoutePolicy({
    this.isPublic = false,
    this.guestOnly = false,
    this.requiresOrganization = true,
    this.permission,
  });

  final bool isPublic;

  /// Signed-in users are bounced away (login).
  final bool guestOnly;
  final bool requiresOrganization;
  final PermissionQuery? permission;
}

/// Policies keyed by route pattern (`GoRouterState.fullPath`, e.g. `/orders/:id`).
/// Add an entry for every route that differs from the default.
const routePolicies = <String, RoutePolicy>{
  AppRoutes.splash: RoutePolicy(isPublic: true, requiresOrganization: false),
  AppRoutes.login: RoutePolicy(isPublic: true, guestOnly: true, requiresOrganization: false),
  AppRoutes.selectOrganization: RoutePolicy(requiresOrganization: false),
  AppRoutes.notAuthorized: RoutePolicy(requiresOrganization: false),
  AppRoutes.settings: RoutePolicy(requiresOrganization: false),
};
```

### `lib/app/router/route_guard.dart`

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

import 'package:<project_slug>/app/router/app_routes.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';

/// Returns [value] when it is a same-app relative path, else null (no open redirects).
String? safeNext(String? value) {
  if (value == null || !value.startsWith('/') || value.startsWith('//')) return null;
  if (value.contains('://') || value.contains(r'\')) return null;
  return value;
}

/// The single navigation gate: session → tenant → permission. Pure (no Flutter), so it is
/// unit-tested directly.
class RouteGuard {
  RouteGuard({required this.session, required this.isMultiTenant, this.policies = routePolicies});

  final SessionView session;
  final bool isMultiTenant;
  final Map<String, RoutePolicy> policies;

  /// [routePattern] is the matched pattern (`/orders/:id`), [location] the real URI.
  String? redirect({required String? routePattern, required Uri location}) {
    final path = location.path;
    final policy = policies[routePattern ?? path] ?? const RoutePolicy();
    final next = safeNext(location.queryParameters['next']);

    switch (session.status) {
      case SessionStatus.unknown:
        return path == AppRoutes.splash ? null : _withNext(AppRoutes.splash, location);
      case SessionStatus.unauthenticated:
        if (policy.isPublic && path != AppRoutes.splash) return null;
        return _withNext(AppRoutes.login, location);
      case SessionStatus.authenticated:
        if (path == AppRoutes.splash || policy.guestOnly) return next ?? AppRoutes.home;
        if (!isMultiTenant && path == AppRoutes.selectOrganization) return AppRoutes.home;
        if (policy.requiresOrganization && session.needsOrganization) {
          return _withNext(AppRoutes.selectOrganization, location);
        }
        if (!session.hasPermission(policy.permission)) return AppRoutes.notAuthorized;
        return null;
    }
  }

  /// `/login?next=<where the user was going>`; gate screens pass their own `next` through.
  String _withNext(String target, Uri location) {
    final isGate = const {
      AppRoutes.splash,
      AppRoutes.login,
      AppRoutes.selectOrganization,
    }.contains(location.path);
    final next = isGate ? safeNext(location.queryParameters['next']) : location.toString();
    if (next == null || next == AppRoutes.home) return target;
    return Uri(path: target, queryParameters: {'next': next}).toString();
  }
}
```

### `lib/app/router/app_router.dart`

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

import 'package:<project_slug>/app/router/app_routes.dart';
import 'package:<project_slug>/app/router/route_guard.dart';
import 'package:<project_slug>/core/config/app_config.dart';
import 'package:<project_slug>/features/auth/screens/login_screen.dart';
import 'package:<project_slug>/features/auth/screens/splash_screen.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:<project_slug>/features/errors/screens/status_screen.dart';
import 'package:<project_slug>/features/home/screens/home_screen.dart';
import 'package:<project_slug>/features/organizations/screens/select_organization_screen.dart';
import 'package:<project_slug>/features/settings/screens/settings_screen.dart';
import 'package:go_router/go_router.dart';

/// The app's single router. Re-evaluates the guard whenever the session changes.
GoRouter createRouter({required SessionController session, required AppConfig config}) {
  final guard = RouteGuard(session: session, isMultiTenant: config.isMultiTenant);
  return GoRouter(
    initialLocation: AppRoutes.home,
    refreshListenable: session,
    redirect: (context, state) => guard.redirect(routePattern: state.fullPath, location: state.uri),
    errorBuilder: (context, state) => const StatusScreen.notFound(),
    routes: [
      GoRoute(path: AppRoutes.splash, builder: (context, state) => const SplashScreen()),
      GoRoute(path: AppRoutes.login, builder: (context, state) => const LoginScreen()),
      GoRoute(
        path: AppRoutes.selectOrganization,
        builder: (context, state) =>
            SelectOrganizationScreen(next: safeNext(state.uri.queryParameters['next'])),
      ),
      GoRoute(path: AppRoutes.home, builder: (context, state) => const HomeScreen()),
      GoRoute(path: AppRoutes.settings, builder: (context, state) => const SettingsScreen()),
      GoRoute(
        path: AppRoutes.notAuthorized,
        builder: (context, state) => const StatusScreen.notAuthorized(),
      ),
    ],
  );
}
```

### `lib/features/auth/screens/splash_screen.dart`

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

import 'package:<project_slug>/core/widgets/error_view.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Shown while the stored session is restored; offers a retry when that fails offline.
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final error = session.restoreError;
    return Scaffold(
      body: SafeArea(
        child: error == null
            ? const Center(child: CircularProgressIndicator())
            : ErrorView(error: error, onRetry: session.restore),
      ),
    );
  }
}
```

### `lib/features/auth/screens/login_screen.dart`

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

import 'package:<project_slug>/core/api/api_error.dart';
import 'package:<project_slug>/core/i18n/l10n.dart';
import 'package:<project_slug>/core/theme/app_colors.dart';
import 'package:<project_slug>/core/theme/app_tokens.dart';
import 'package:<project_slug>/core/widgets/app_text_field.dart';
import 'package:<project_slug>/core/widgets/error_view.dart';
import 'package:<project_slug>/core/widgets/loading_button.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Email + password sign-in. Navigation after success is done by the route guard.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  Object? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  String? _required(String? value) =>
      value == null || value.trim().isEmpty ? context.l10n.validationRequired : null;

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() => _error = null);
    try {
      await context.read<SessionController>().login(
        email: _email.text.trim(),
        password: _password.text,
      );
    } on ApiError catch (error) {
      if (mounted) setState(() => _error = error);
    }
  }

  /// Non-field errors (wrong credentials, throttling, offline) render as a banner.
  String? _bannerMessage() {
    final error = _error;
    if (error == null) return null;
    if (error is ApiError && error.fieldErrors.keys.any({'email', 'password'}.contains)) {
      return error.firstError('non_field_errors');
    }
    return errorMessage(context, error);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final apiError = _error is ApiError ? _error! as ApiError : null;
    final banner = _bannerMessage();
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: AppSizes.maxContentWidth),
              child: Form(
                key: _formKey,
                child: AutofillGroup(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(l10n.loginTitle, style: context.textTheme.headlineMedium),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        l10n.loginSubtitle,
                        style: context.textTheme.bodyLarge?.copyWith(
                          color: context.colors.textMuted,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xl),
                      if (banner != null) ...[
                        Text(banner, style: TextStyle(color: context.colorScheme.error)),
                        const SizedBox(height: AppSpacing.md),
                      ],
                      AppTextField(
                        name: 'email',
                        label: l10n.fieldEmail,
                        controller: _email,
                        apiError: apiError,
                        validator: _required,
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.next,
                        autofillHints: const [AutofillHints.email],
                      ),
                      const SizedBox(height: AppSpacing.md),
                      AppTextField(
                        name: 'password',
                        label: l10n.fieldPassword,
                        controller: _password,
                        apiError: apiError,
                        validator: _required,
                        obscureText: true,
                        textInputAction: TextInputAction.done,
                        autofillHints: const [AutofillHints.password],
                        onSubmitted: (_) => _submit(),
                      ),
                      const SizedBox(height: AppSpacing.xl),
                      LoadingButton(label: l10n.actionSignIn, onPressed: _submit),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
```

### `lib/features/organizations/screens/select_organization_screen.dart`

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

import 'package:<project_slug>/app/router/app_routes.dart';
import 'package:<project_slug>/core/i18n/l10n.dart';
import 'package:<project_slug>/core/models/organization.dart';
import 'package:<project_slug>/core/widgets/empty_state.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

/// Multi-tenant only: pick the organisation every request is scoped to.
class SelectOrganizationScreen extends StatelessWidget {
  const SelectOrganizationScreen({super.key, this.next});

  /// Where to continue after choosing (already validated by `safeNext`).
  final String? next;

  Future<void> _select(BuildContext context, Organization organization) async {
    final session = context.read<SessionController>();
    final router = GoRouter.of(context);
    if (await session.selectOrganization(organization.id)) router.go(next ?? AppRoutes.home);
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final current = session.currentOrganization;
    final organizations = session.organizations;
    return Scaffold(
      appBar: AppBar(title: Text(context.l10n.selectOrganizationTitle)),
      body: RefreshIndicator(
        onRefresh: session.loadOrganizations,
        child: organizations.isEmpty
            ? ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  EmptyState(
                    icon: Icons.apartment_outlined,
                    title: context.l10n.selectOrganizationEmpty,
                  ),
                ],
              )
            : ListView.builder(
                physics: const AlwaysScrollableScrollPhysics(),
                itemCount: organizations.length,
                itemBuilder: (context, index) {
                  final organization = organizations[index];
                  return ListTile(
                    key: ValueKey(organization.id),
                    leading: const Icon(Icons.apartment_outlined),
                    title: Text(organization.name),
                    subtitle: organization.roleName == null ? null : Text(organization.roleName!),
                    trailing: organization.id == current?.id ? const Icon(Icons.check) : null,
                    onTap: () => _select(context, organization),
                  );
                },
              ),
      ),
    );
  }
}
```

### `lib/features/home/screens/home_screen.dart`

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

import 'package:<project_slug>/app/router/app_routes.dart';
import 'package:<project_slug>/core/config/app_config.dart';
import 'package:<project_slug>/core/i18n/l10n.dart';
import 'package:<project_slug>/core/theme/app_colors.dart';
import 'package:<project_slug>/core/theme/app_tokens.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

/// Landing screen after sign-in: who am I, which organisation, where to go next.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final config = context.read<AppConfig>();
    final session = context.watch<SessionController>();
    final organization = session.currentOrganization;
    return Scaffold(
      appBar: AppBar(
        title: Text(config.appName),
        actions: [
          IconButton(
            tooltip: l10n.settingsTitle,
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => context.push(AppRoutes.settings),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          children: [
            Text(
              l10n.homeGreeting(session.user?.fullName ?? ''),
              style: context.textTheme.headlineSmall,
            ),
            if (config.isMultiTenant && organization != null) ...[
              const SizedBox(height: AppSpacing.lg),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.apartment_outlined),
                  title: Text(organization.name),
                  subtitle: Text(l10n.homeOrganization),
                  trailing: TextButton(
                    onPressed: () => context.push(AppRoutes.selectOrganization),
                    child: Text(l10n.homeSwitchOrganization),
                  ),
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.xxl),
            Text(
              l10n.copyright(DateTime.now().year, config.legalEntityName),
              style: context.textTheme.bodySmall?.copyWith(color: context.colors.textMuted),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
```

### `lib/features/settings/screens/settings_screen.dart`

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
import 'package:<project_slug>/core/settings/settings_controller.dart';
import 'package:<project_slug>/core/theme/app_tokens.dart';
import 'package:<project_slug>/core/widgets/app_dialogs.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Appearance and sign-out.
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  Future<void> _signOut(BuildContext context) async {
    final l10n = context.l10n;
    final session = context.read<SessionController>();
    final confirmed = await showConfirmDialog(
      context,
      title: l10n.signOutConfirmTitle,
      message: l10n.signOutConfirmBody,
      confirmLabel: l10n.actionSignOut,
      destructive: true,
    );
    if (confirmed) await session.logout();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final settings = context.watch<SettingsController>();
    return Scaffold(
      appBar: AppBar(title: Text(l10n.settingsTitle)),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          Text(l10n.settingsTheme, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: AppSpacing.sm),
          SegmentedButton<ThemeMode>(
            segments: [
              ButtonSegment(value: ThemeMode.system, label: Text(l10n.themeSystem)),
              ButtonSegment(value: ThemeMode.light, label: Text(l10n.themeLight)),
              ButtonSegment(value: ThemeMode.dark, label: Text(l10n.themeDark)),
            ],
            selected: {settings.themeMode},
            onSelectionChanged: (selection) => settings.setThemeMode(selection.first),
          ),
          const SizedBox(height: AppSpacing.xl),
          OutlinedButton.icon(
            onPressed: () => _signOut(context),
            icon: const Icon(Icons.logout),
            label: Text(l10n.actionSignOut),
          ),
        ],
      ),
    );
  }
}
```

### `lib/features/errors/screens/status_screen.dart`

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

import 'package:<project_slug>/app/router/app_routes.dart';
import 'package:<project_slug>/core/i18n/l10n.dart';
import 'package:<project_slug>/core/widgets/empty_state.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

enum _StatusKind { notFound, notAuthorized }

/// Full-screen 404 / 403 state with a way back home.
class StatusScreen extends StatelessWidget {
  const StatusScreen.notFound({super.key}) : _kind = _StatusKind.notFound;

  const StatusScreen.notAuthorized({super.key}) : _kind = _StatusKind.notAuthorized;

  final _StatusKind _kind;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final (icon, title, body) = switch (_kind) {
      _StatusKind.notFound => (Icons.explore_off_outlined, l10n.notFoundTitle, l10n.notFoundBody),
      _StatusKind.notAuthorized => (
        Icons.lock_outline,
        l10n.notAuthorizedTitle,
        l10n.notAuthorizedBody,
      ),
    };
    return Scaffold(
      body: SafeArea(
        child: EmptyState(
          icon: icon,
          title: title,
          message: body,
          action: FilledButton(
            onPressed: () => context.go(AppRoutes.home),
            child: Text(l10n.actionBackHome),
          ),
        ),
      ),
    );
  }
}
```

### `test/features/auth/session_controller_test.dart`

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

import 'package:<project_slug>/core/api/api_error.dart';
import 'package:<project_slug>/core/auth/permissions.dart';
import 'package:<project_slug>/core/auth/session_credentials.dart';
import 'package:<project_slug>/core/models/organization.dart';
import 'package:<project_slug>/core/models/user.dart';
import 'package:<project_slug>/core/storage/app_preferences.dart';
import 'package:<project_slug>/core/storage/token_store.dart';
import 'package:<project_slug>/features/auth/data/auth_repository.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../helpers/factories.dart';
import '../../helpers/mocks.dart';

void main() {
  late MockAuthRepository auth;
  late MockOrganizationRepository organizations;
  late MemoryTokenStore tokenStore;
  late SessionCredentials credentials;

  final user = User.fromJson(userJson());
  final acme = Organization.fromJson(organizationJson());
  final globex = Organization.fromJson(organizationJson({'id': 'org-2', 'name': 'Globex'}));

  Future<SessionController> build({String? token, String tenancyMode = 'multi'}) async {
    SharedPreferences.setMockInitialValues({'app.installed': true});
    tokenStore = MemoryTokenStore(token);
    credentials = SessionCredentials(
      tokenStore: tokenStore,
      preferences: await AppPreferences.load(),
    );
    await credentials.load();
    return SessionController(
      config: testConfig(tenancyMode: tenancyMode),
      credentials: credentials,
      authRepository: auth,
      organizationRepository: organizations,
    );
  }

  setUp(() {
    auth = MockAuthRepository();
    organizations = MockOrganizationRepository();
    when(() => organizations.mine()).thenAnswer((_) async => [acme]);
  });

  group('restore', () {
    test('without a token → unauthenticated, no API calls', () async {
      final session = await build();
      await session.restore();
      expect(session.status, SessionStatus.unauthenticated);
      verifyNever(() => auth.me());
    });

    test('with a token → loads user + orgs and auto-selects a single org', () async {
      when(() => auth.me()).thenAnswer((_) async => user);
      final session = await build(token: 'tok');
      await session.restore();
      expect(session.status, SessionStatus.authenticated);
      expect(session.currentOrganization?.id, 'org-1');
      expect(session.needsOrganization, isFalse);
    });

    test('a 401 clears the stored token', () async {
      when(() => auth.me()).thenThrow(const ApiError(status: 401, message: 'expired'));
      final session = await build(token: 'tok');
      await session.restore();
      expect(session.status, SessionStatus.unauthenticated);
      expect(tokenStore.token, isNull);
    });

    test('a network error keeps the token and exposes restoreError', () async {
      when(() => auth.me()).thenThrow(const ApiError(status: 0, message: 'offline'));
      final session = await build(token: 'tok');
      await session.restore();
      expect(session.status, SessionStatus.unknown);
      expect(session.restoreError?.isNetworkError, isTrue);
      expect(tokenStore.token, 'tok');
    });

    test('a first launch after reinstall drops keychain leftovers', () async {
      SharedPreferences.setMockInitialValues({});
      final store = MemoryTokenStore('stale');
      final fresh = SessionCredentials(tokenStore: store, preferences: await AppPreferences.load());
      await fresh.load();
      expect(fresh.hasToken, isFalse);
      expect(store.token, isNull);
    });
  });

  group('login / logout', () {
    test('login stores the token and authenticates', () async {
      when(
        () => auth.login(email: 'ada@example.com', password: 'pw'),
      ).thenAnswer((_) async => LoginResult(token: 'new', user: user));
      final session = await build();
      await session.login(email: 'ada@example.com', password: 'pw');
      expect(session.isAuthenticated, isTrue);
      expect(tokenStore.token, 'new');
    });

    test('login errors propagate for the form', () async {
      when(
        () => auth.login(
          email: any(named: 'email'),
          password: any(named: 'password'),
        ),
      ).thenThrow(const ApiError(status: 400, message: 'bad'));
      final session = await build();
      await expectLater(session.login(email: 'a@b.c', password: 'x'), throwsA(isA<ApiError>()));
      expect(session.isAuthenticated, isFalse);
    });

    test('logout clears locally even when the API call fails', () async {
      when(() => auth.me()).thenAnswer((_) async => user);
      when(() => auth.logout()).thenThrow(const ApiError(status: 0, message: 'offline'));
      final session = await build(token: 'tok');
      await session.restore();
      await session.logout();
      expect(session.status, SessionStatus.unauthenticated);
      expect(tokenStore.token, isNull);
      expect(credentials.organizationId, isNull);
    });

    test('handleUnauthorized ends an active session', () async {
      when(() => auth.me()).thenAnswer((_) async => user);
      final session = await build(token: 'tok');
      await session.restore();
      session.handleUnauthorized(const ApiError(status: 401, message: 'expired'));
      await pumpEventQueue();
      expect(session.status, SessionStatus.unauthenticated);
    });
  });

  group('tenancy + RBAC', () {
    test('several orgs → needs a choice; only member orgs can be selected', () async {
      when(() => organizations.mine()).thenAnswer((_) async => [acme, globex]);
      when(() => auth.me()).thenAnswer((_) async => user);
      final session = await build(token: 'tok');
      await session.restore();
      expect(session.needsOrganization, isTrue);
      expect(await session.selectOrganization('foreign'), isFalse);
      expect(await session.selectOrganization('org-2'), isTrue);
      expect(session.currentOrganization?.name, 'Globex');
      expect(credentials.organizationId, 'org-2');
    });

    test('permissions come from the current org', () async {
      when(() => auth.me()).thenAnswer((_) async => user);
      final session = await build(token: 'tok');
      await session.restore();
      expect(session.hasPermission(const PermissionQuery.single('order:read')), isTrue);
      expect(session.hasPermission(const PermissionQuery.single('order:write')), isFalse);
    });

    test('single-tenant: no org calls, permissions come from the user', () async {
      final admin = User.fromJson(
        userJson({
          'role': 'owner',
          'permissions': ['x'],
        }),
      );
      when(() => auth.me()).thenAnswer((_) async => admin);
      final session = await build(token: 'tok', tenancyMode: 'single');
      await session.restore();
      verifyNever(() => organizations.mine());
      expect(session.needsOrganization, isFalse);
      expect(session.isOwner, isTrue);
      expect(session.hasPermission(const PermissionQuery.single('anything')), isTrue);
    });
  });
}
```

### `test/app/route_guard_test.dart`

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

import 'package:<project_slug>/app/router/app_routes.dart';
import 'package:<project_slug>/app/router/route_guard.dart';
import 'package:<project_slug>/core/auth/permissions.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeSession extends ChangeNotifier implements SessionView {
  FakeSession({this.status = SessionStatus.authenticated, this.needsOrganization = false});

  @override
  SessionStatus status;

  @override
  bool needsOrganization;

  Set<String> granted = {};

  @override
  bool hasPermission(PermissionQuery? query) => hasPermissions(granted.toList(), query);
}

void main() {
  const ordersPolicy = RoutePolicy(permission: PermissionQuery.single('order:read'));
  final policies = {...routePolicies, '/orders': ordersPolicy};

  String? go(FakeSession session, String location, {bool multi = true}) => RouteGuard(
    session: session,
    isMultiTenant: multi,
    policies: policies,
  ).redirect(routePattern: Uri.parse(location).path, location: Uri.parse(location));

  test('unknown session waits on the splash, keeping the destination', () {
    final session = FakeSession(status: SessionStatus.unknown);
    expect(go(session, '/orders'), '/splash?next=%2Forders');
    expect(go(session, '/splash?next=/orders'), isNull);
  });

  test('anonymous users go to login with next; public routes stay open', () {
    final session = FakeSession(status: SessionStatus.unauthenticated);
    expect(go(session, '/orders'), '/login?next=%2Forders');
    expect(go(session, '/splash?next=/orders'), '/login?next=%2Forders');
    expect(go(session, '/'), AppRoutes.login);
    expect(go(session, '/login'), isNull);
  });

  test('signed-in users leave guest-only screens for next or home', () {
    final session = FakeSession();
    expect(go(session, '/login?next=/settings'), '/settings');
    expect(go(session, '/login'), AppRoutes.home);
    expect(go(session, '/splash'), AppRoutes.home);
  });

  test('rejects open redirects in next', () {
    final session = FakeSession();
    expect(go(session, '/login?next=//evil.com'), AppRoutes.home);
    expect(go(session, '/login?next=https://evil.com'), AppRoutes.home);
    expect(safeNext('/orders?page=2'), '/orders?page=2');
  });

  test('multi-tenant: no organisation → selector, carrying next', () {
    final session = FakeSession(needsOrganization: true);
    expect(go(session, '/'), AppRoutes.selectOrganization);
    expect(go(session, '/settings'), isNull);
    session.granted = {'order:read'};
    expect(go(session, '/orders'), '/select-organization?next=%2Forders');
    expect(go(session, '/select-organization'), isNull);
  });

  test('single-tenant never shows the selector', () {
    final session = FakeSession();
    expect(go(session, '/select-organization', multi: false), AppRoutes.home);
  });

  test('permission gate', () {
    final session = FakeSession();
    expect(go(session, '/orders'), AppRoutes.notAuthorized);
    session.granted = {'order:read'};
    expect(go(session, '/orders'), isNull);
  });
}
```

### `test/features/auth/login_screen_test.dart`

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

import 'package:<project_slug>/core/api/api_error.dart';
import 'package:<project_slug>/features/auth/screens/login_screen.dart';
import 'package:<project_slug>/features/auth/state/session_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:provider/provider.dart';

import '../../helpers/pump_app.dart';

class MockSessionController extends Mock implements SessionController {}

void main() {
  late MockSessionController session;

  setUp(() => session = MockSessionController());

  Future<void> pump(WidgetTester tester) => tester.pumpApp(
    const LoginScreen(),
    providers: [ChangeNotifierProvider<SessionController>.value(value: session)],
  );

  testWidgets('validates required fields before calling the API', (tester) async {
    await pump(tester);
    await tester.tap(find.byType(FilledButton));
    await tester.pumpAndSettle();
    expect(find.text('This field is required.'), findsNWidgets(2));
    verifyNever(
      () => session.login(
        email: any(named: 'email'),
        password: any(named: 'password'),
      ),
    );
  });

  testWidgets('shows backend field errors under the input', (tester) async {
    when(
      () => session.login(
        email: any(named: 'email'),
        password: any(named: 'password'),
      ),
    ).thenThrow(
      const ApiError(
        status: 400,
        message: 'Invalid data.',
        fieldErrors: {
          'email': ['Enter a valid email.'],
        },
      ),
    );
    await pump(tester);
    await tester.enterText(find.byType(TextFormField).first, 'ada@example');
    await tester.enterText(find.byType(TextFormField).last, 'secret');
    await tester.tap(find.byType(FilledButton));
    await tester.pumpAndSettle();
    expect(find.text('Enter a valid email.'), findsOneWidget);
  });

  testWidgets('shows non-field errors as a banner', (tester) async {
    when(
      () => session.login(
        email: any(named: 'email'),
        password: any(named: 'password'),
      ),
    ).thenThrow(const ApiError(status: 400, message: 'Invalid email or password.'));
    await pump(tester);
    await tester.enterText(find.byType(TextFormField).first, 'ada@example.com');
    await tester.enterText(find.byType(TextFormField).last, 'wrong');
    await tester.tap(find.byType(FilledButton));
    await tester.pumpAndSettle();
    expect(find.text('Invalid email or password.'), findsOneWidget);
  });
}
```
