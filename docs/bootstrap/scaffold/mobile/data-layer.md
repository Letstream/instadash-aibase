# Mobile scaffold — data layer

> Part of the [mobile scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the mobile repo root (`mobile/`).

Three layers, each depending only on the one below (see
[data-layer guidelines](../../../architecture-guidelines/mobile/data-layer.md)):

1. **Transport** — `Endpoints` (every path once, `%i` params), `createDio` (the ONE Dio instance:
   `SessionInterceptor` adds `Authorization: Token …`, `X-Organization-Id` in multi-tenant mode and
   `X-User-Tz`; `EnvelopeInterceptor` unwraps `{status, data, version}` and turns failures into
   `ApiError`, firing the 401/403 hooks) and `ApiClient`, the typed facade repositories use.
2. **Repositories** — one class per domain, extending `BaseRepository<T>`; CRUD returns models.
3. **Models** — immutable classes with `fromJson` (via the `Json` readers) and `toJson`.

Adding a domain (e.g. orders): add `orderList` / `orderDetail` to `Endpoints`, a
`lib/features/orders/data/order.dart` model and

```dart
class OrderRepository extends BaseRepository<Order> {
  OrderRepository(super.client);

  @override
  ResourcePaths get paths =>
      const ResourcePaths(list: Endpoints.orderList, detail: Endpoints.orderDetail);

  @override
  Order fromJson(JsonMap json) => Order.fromJson(json);
}
```

plus tests for the model and the repository (`MockApiClient`, as below).

### `lib/core/api/endpoints.dart`

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

/// Every backend path, declared once, relative to `AppConfig.apiBaseUrl` (`…/api/`).
///
/// `%i` marks a positional path parameter filled by [Endpoints.path]. Keep this registry in sync
/// with the backend URLconf; screens, controllers and repositories never build URL strings.
abstract final class Endpoints {
  // accounts
  static const login = 'accounts/login/';
  static const logout = 'accounts/logout/';
  static const me = 'accounts/me/';

  // organisations (multi-tenant only)
  static const myOrganizations = 'organization/my-orgs/';
  static const organizationMemberDetail = 'organization/members/%i/';

  /// Fills each `%i` in [template] with the URL-encoded [params], in order.
  static String path(String template, [List<Object> params = const []]) {
    var index = 0;
    final result = template.replaceAllMapped(RegExp('%i'), (_) {
      if (index >= params.length) {
        throw ArgumentError('Missing path parameter ${index + 1} for "$template".');
      }
      return Uri.encodeComponent(params[index++].toString());
    });
    if (index != params.length) {
      throw ArgumentError('Too many path parameters for "$template".');
    }
    return result;
  }
}
```

### `lib/core/api/api_error.dart`

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

import 'package:dio/dio.dart';

/// Field-keyed validation errors (`{'email': ['Enter a valid email.']}`).
typedef FieldErrors = Map<String, List<String>>;

const _envelopeKeys = {'status', 'err_cd', 'err_msg', 'error', 'version', 'detail'};

/// The ONE error type the data layer throws.
///
/// Built from the backend error envelope `{status: false, err_cd, err_msg, error, version}`.
/// `status == 0` means the request never got an HTTP response (offline, timeout, TLS).
class ApiError implements Exception {
  const ApiError({
    required this.status,
    required this.message,
    this.code,
    this.fieldErrors = const {},
    this.body,
  });

  /// Parses an HTTP error response body (envelope or plain DRF shape).
  factory ApiError.fromResponse(int status, Object? body) {
    final envelope = body is Map ? body : const <Object?, Object?>{};
    final code = envelope['err_cd'];
    final errMsg = envelope['err_msg'];
    final detail = envelope['detail'];
    final message = switch ((errMsg, detail)) {
      (final String m, _) when m.isNotEmpty => m,
      (_, final String d) when d.isNotEmpty => d,
      _ => 'Request failed with status $status',
    };
    return ApiError(
      status: status,
      code: code is String ? code : null,
      message: message,
      fieldErrors: normalizeFieldErrors(envelope.containsKey('error') ? envelope['error'] : body),
      body: body,
    );
  }

  /// Maps any [DioException] (or an [ApiError] already attached to it) to an [ApiError].
  factory ApiError.fromDioException(DioException exception) {
    final attached = exception.error;
    if (attached is ApiError) return attached;
    final response = exception.response;
    if (response != null) {
      return ApiError.fromResponse(response.statusCode ?? 0, response.data);
    }
    return ApiError(
      status: 0,
      code: exception.type.name,
      message: exception.message ?? 'Network error',
    );
  }

  /// HTTP status, or 0 for network failures.
  final int status;

  /// Backend error code (`err_cd`, e.g. `E-C-COR-0004`), when present.
  final String? code;

  /// Human-readable backend message (`err_msg`). Screens prefer localized copy for known cases.
  final String message;
  final FieldErrors fieldErrors;
  final Object? body;

  bool get isNetworkError => status == 0;
  bool get isValidationError => status == 400;
  bool get isUnauthorized => status == 401;
  bool get isForbidden => status == 403;
  bool get isNotFound => status == 404;

  /// First message for [field] — what a form renders under the input.
  String? firstError(String field) {
    final messages = fieldErrors[field];
    return messages == null || messages.isEmpty ? null : messages.first;
  }

  /// Normalises DRF / envelope error payloads into `{field: [messages]}`.
  static FieldErrors normalizeFieldErrors(Object? source) {
    if (source is! Map) return const {};
    final errors = <String, List<String>>{};
    for (final entry in source.entries) {
      final field = entry.key;
      if (field is! String || _envelopeKeys.contains(field)) continue;
      final value = entry.value;
      if (value is List) {
        final messages = value.whereType<String>().toList();
        if (messages.isNotEmpty) errors[field] = messages;
      } else if (value is String) {
        errors[field] = [value];
      }
    }
    return errors;
  }

  @override
  String toString() => 'ApiError($status, ${code ?? '-'}): $message';
}
```

### `lib/core/api/interceptors.dart`

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
import 'package:<project_slug>/core/auth/session_credentials.dart';
import 'package:dio/dio.dart';

const authHeader = 'Authorization';
const tenantHeader = 'X-Organization-Id';
const timezoneHeader = 'X-User-Tz';

/// Global reactions to auth failures, wired once in the composition root.
class HttpHooks {
  void Function(ApiError error)? onUnauthorized;
  void Function(ApiError error)? onForbidden;
}

/// Adds `Authorization: Token …`, `X-Organization-Id` (multi-tenant only) and `X-User-Tz` —
/// only to requests for our own API, never to third-party URLs.
class SessionInterceptor extends Interceptor {
  SessionInterceptor({
    required this.credentials,
    required this.apiBaseUrl,
    required this.isMultiTenant,
    required this.timezone,
  });

  final SessionCredentials credentials;
  final String apiBaseUrl;
  final bool isMultiTenant;
  final String Function() timezone;

  bool isApiRequest(Uri uri) => uri.toString().startsWith(apiBaseUrl);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    if (isApiRequest(options.uri)) {
      final token = credentials.token;
      if (token != null) options.headers[authHeader] = 'Token $token';
      final organizationId = credentials.organizationId;
      if (isMultiTenant && organizationId != null) options.headers[tenantHeader] = organizationId;
      options.headers[timezoneHeader] = timezone();
    }
    handler.next(options);
  }
}

/// Unwraps `{status, data, version}` so callers get `data`, and turns every failure into an
/// [ApiError] (attached as `DioException.error`), firing the 401 / 403 hooks.
class EnvelopeInterceptor extends Interceptor {
  EnvelopeInterceptor(this.hooks);

  final HttpHooks hooks;

  static bool isEnvelope(Object? body) =>
      body is Map &&
      body['status'] is bool &&
      (body.containsKey('data') || body['status'] == false);

  @override
  void onResponse(Response<dynamic> response, ResponseInterceptorHandler handler) {
    final body = response.data;
    if (isEnvelope(body)) {
      final envelope = body as Map;
      if (envelope['status'] == false) {
        final error = ApiError.fromResponse(response.statusCode ?? 400, body);
        handler.reject(
          DioException(
            requestOptions: response.requestOptions,
            response: response,
            type: DioExceptionType.badResponse,
            error: error,
          ),
          true,
        );
        return;
      }
      response.data = envelope['data'];
    }
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    final error = ApiError.fromDioException(err);
    if (error.isUnauthorized) {
      hooks.onUnauthorized?.call(error);
    } else if (error.isForbidden) {
      hooks.onForbidden?.call(error);
    }
    handler.next(err.copyWith(error: error));
  }
}
```

### `lib/core/api/api_client.dart`

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
import 'package:<project_slug>/core/api/interceptors.dart';
import 'package:<project_slug>/core/auth/session_credentials.dart';
import 'package:<project_slug>/core/config/app_config.dart';
import 'package:dio/dio.dart';

/// Query parameters; list values serialise DRF-style (`?status=a&status=b`).
typedef QueryParams = Map<String, Object?>;

/// Builds the ONE Dio instance of the app with its interceptors.
Dio createDio({
  required AppConfig config,
  required SessionCredentials credentials,
  required HttpHooks hooks,
  required String Function() timezone,
}) {
  final dio = Dio(
    BaseOptions(
      baseUrl: config.apiBaseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
      headers: {'Accept': 'application/json'},
      listFormat: ListFormat.multi,
    ),
  );
  dio.interceptors.addAll([
    SessionInterceptor(
      credentials: credentials,
      apiBaseUrl: config.apiBaseUrl,
      isMultiTenant: config.isMultiTenant,
      timezone: timezone,
    ),
    EnvelopeInterceptor(hooks),
  ]);
  return dio;
}

/// Typed facade over Dio. Returns the unwrapped payload; throws only [ApiError].
/// Repositories depend on this class, tests fake it.
class ApiClient {
  ApiClient(this._dio);

  final Dio _dio;

  Future<T> get<T>(String path, {QueryParams? query}) =>
      _send(() => _dio.get<Object?>(path, queryParameters: query));

  Future<T> post<T>(String path, {Object? body}) =>
      _send(() => _dio.post<Object?>(path, data: body));

  Future<T> put<T>(String path, {Object? body}) => _send(() => _dio.put<Object?>(path, data: body));

  Future<T> patch<T>(String path, {Object? body}) =>
      _send(() => _dio.patch<Object?>(path, data: body));

  Future<void> delete(String path) => _send<Object?>(() => _dio.delete<Object?>(path));

  Future<T> _send<T>(Future<Response<Object?>> Function() request) async {
    try {
      final response = await request();
      return response.data as T;
    } on DioException catch (exception) {
      throw ApiError.fromDioException(exception);
    }
  }
}
```

### `lib/core/api/page_result.dart`

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

import 'package:<project_slug>/core/models/json.dart';

/// One page of a list endpoint, normalised from either backend list shape.
class PageResult<T> {
  const PageResult({required this.items, required this.count, this.next, this.previous});

  /// Accepts DRF `{results, count, next, previous}` or a bare `[...]` and maps each item.
  factory PageResult.fromBody(Object? body, T Function(JsonMap json) fromJson) {
    if (body is List) {
      final items = body.map((item) => fromJson(Json.map(item))).toList();
      return PageResult(items: items, count: items.length);
    }
    if (body is Map) {
      final raw = body['results'];
      final items = raw is List ? raw.map((item) => fromJson(Json.map(item))).toList() : <T>[];
      final count = body['count'];
      final next = body['next'];
      final previous = body['previous'];
      return PageResult(
        items: items,
        count: count is int ? count : items.length,
        next: next is String ? next : null,
        previous: previous is String ? previous : null,
      );
    }
    return PageResult<T>(items: const [], count: 0);
  }

  final List<T> items;
  final int count;
  final String? next;
  final String? previous;

  bool get hasMore => next != null;
}
```

### `lib/core/data/base_repository.dart`

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
import 'package:<project_slug>/core/api/endpoints.dart';
import 'package:<project_slug>/core/api/page_result.dart';
import 'package:<project_slug>/core/models/json.dart';

/// Paths of a CRUD resource as endpoint templates (`detail` holds one `%i` for the id).
class ResourcePaths {
  const ResourcePaths({required this.list, this.detail, this.create});

  final String list;

  /// Omit for list-only resources; [BaseRepository.get]/`update`/`remove` then throw.
  final String? detail;

  /// Defaults to [list] (DRF router style).
  final String? create;
}

/// What list-driven widgets (`ResourceListView`, pickers) need from a repository.
abstract interface class ListableRepository<T> {
  Future<PageResult<T>> list({QueryParams? query});
}

/// One repository per backend domain. CRUD returns **model instances**; domain calls are extra
/// methods on the subclass.
abstract class BaseRepository<T> implements ListableRepository<T> {
  BaseRepository(this.client);

  final ApiClient client;

  ResourcePaths get paths;

  /// DTO → model. Usually `=> Order.fromJson(json)`.
  T fromJson(JsonMap json);

  String detailPath(Object id) {
    final template = paths.detail;
    if (template == null) throw StateError('$runtimeType has no detail endpoint.');
    return Endpoints.path(template, [id]);
  }

  @override
  Future<PageResult<T>> list({QueryParams? query}) async =>
      PageResult.fromBody(await client.get<Object?>(paths.list, query: query), fromJson);

  Future<T> get(Object id) async => fromJson(Json.map(await client.get<Object?>(detailPath(id))));

  Future<T> create(JsonMap payload) async =>
      fromJson(Json.map(await client.post<Object?>(paths.create ?? paths.list, body: payload)));

  /// PATCH with only the changed / writable fields.
  Future<T> update(Object id, JsonMap payload) async =>
      fromJson(Json.map(await client.patch<Object?>(detailPath(id), body: payload)));

  Future<void> remove(Object id) => client.delete(detailPath(id));
}
```

### `lib/core/models/json.dart`

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

/// A decoded JSON object as the backend sends it (snake_case keys).
typedef JsonMap = Map<String, dynamic>;

/// Typed readers used by every `fromJson` so bad payloads fail loudly at the boundary.
abstract final class Json {
  /// Coerces a JSON object; throws [FormatException] for anything else.
  static JsonMap map(Object? value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return value.map((key, item) => MapEntry(key.toString(), item));
    throw FormatException('Expected a JSON object, got ${value.runtimeType}.');
  }

  /// Ids are normalised to strings (the backend may send ints or UUIDs).
  static String id(Object? value) => switch (value) {
    final String text when text.isNotEmpty => text,
    final num number => number.toString(),
    _ => throw FormatException('Expected an id, got $value.'),
  };

  static String string(JsonMap json, String key, {String fallback = ''}) {
    final value = json[key];
    return value is String ? value : fallback;
  }

  static String? stringOrNull(JsonMap json, String key) {
    final value = json[key];
    return value is String && value.isNotEmpty ? value : null;
  }

  static bool boolean(JsonMap json, String key, {bool fallback = false}) {
    final value = json[key];
    return value is bool ? value : fallback;
  }

  static int? intOrNull(JsonMap json, String key) {
    final value = json[key];
    return value is num ? value.toInt() : null;
  }

  static DateTime? date(JsonMap json, String key) {
    final value = json[key];
    return value is String ? DateTime.tryParse(value) : null;
  }

  static List<String> stringList(JsonMap json, String key) {
    final value = json[key];
    return value is List ? value.whereType<String>().toList() : const [];
  }
}

/// Base for entity classes: typed camelCase fields, `fromJson` factory, [toJson] for writes.
abstract class BaseModel {
  const BaseModel();

  /// Writable fields only, in the backend's snake_case.
  JsonMap toJson();
}
```

### `lib/core/models/user.dart`

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

import 'package:<project_slug>/core/models/json.dart';

/// Single-tenant role ladder (multi-tenant roles live on the organisation membership).
enum UserRole {
  guest,
  member,
  admin,
  owner;

  static UserRole? tryParse(Object? value) => value is String ? values.asNameMap()[value] : null;
}

/// The signed-in user (`GET accounts/me/`).
class User extends BaseModel {
  const User({
    required this.id,
    required this.email,
    this.firstName = '',
    this.lastName = '',
    this.emailConfirmed = false,
    this.role,
    this.permissions = const [],
    this.createdOn,
  });

  factory User.fromJson(JsonMap json) => User(
    id: Json.id(json['id']),
    email: Json.string(json, 'email'),
    firstName: Json.string(json, 'first_name'),
    lastName: Json.string(json, 'last_name'),
    emailConfirmed: Json.boolean(json, 'email_confirmed'),
    role: UserRole.tryParse(json['role']),
    permissions: Json.stringList(json, 'permissions'),
    createdOn: Json.date(json, 'created_on'),
  );

  final String id;
  final String email;
  final String firstName;
  final String lastName;
  final bool emailConfirmed;

  /// Single-tenant only.
  final UserRole? role;

  /// Single-tenant only: permission codes derived from [role] by the backend.
  final List<String> permissions;
  final DateTime? createdOn;

  @override
  JsonMap toJson() => {'first_name': firstName, 'last_name': lastName};

  String get fullName {
    final name = [firstName, lastName].where((part) => part.isNotEmpty).join(' ');
    return name.isEmpty ? email : name;
  }

  String get initials {
    final parts = fullName.split(RegExp(r'[\s@.]+')).where((part) => part.isNotEmpty).take(2);
    return parts.map((part) => part[0].toUpperCase()).join();
  }

  /// Single-tenant ladder check: `user.hasRoleAtLeast(UserRole.admin)`.
  bool hasRoleAtLeast(UserRole minimum) => role != null && role!.index >= minimum.index;

  User copyWith({String? firstName, String? lastName}) => User(
    id: id,
    email: email,
    firstName: firstName ?? this.firstName,
    lastName: lastName ?? this.lastName,
    emailConfirmed: emailConfirmed,
    role: role,
    permissions: permissions,
    createdOn: createdOn,
  );
}
```

### `lib/core/models/organization.dart`

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
import 'package:<project_slug>/core/models/json.dart';

/// A tenant the current user belongs to (`GET organization/my-orgs/`), with the caller's role
/// and permission codes in it.
class Organization extends BaseModel {
  const Organization({
    required this.id,
    required this.name,
    this.isOwner = false,
    this.roleName,
    this.permissions = const [],
  });

  factory Organization.fromJson(JsonMap json) => Organization(
    id: Json.id(json['id']),
    name: Json.string(json, 'name'),
    isOwner: Json.boolean(json, 'is_owner'),
    roleName: Json.stringOrNull(json, 'role'),
    permissions: Json.stringList(json, 'permissions'),
  );

  final String id;
  final String name;
  final bool isOwner;

  /// The caller's role name (null for owners without a membership row).
  final String? roleName;

  /// The caller's permission codes here (`['*']` = all).
  final List<String> permissions;

  @override
  JsonMap toJson() => {'name': name};

  /// `org.can(const PermissionQuery.single('order:read'))`.
  bool can(PermissionQuery? query) => hasPermissions(permissions, query, isOwner: isOwner);
}
```

### `lib/core/auth/permissions.dart`

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

/// Wildcard permission code granted to super-roles.
const wildcardPermission = '*';

/// A permission requirement: one code, all of several (AND) or any of several (OR).
class PermissionQuery {
  const PermissionQuery.single(String key) : keys = const [], _single = key, requireAll = true;
  const PermissionQuery.all(this.keys) : _single = null, requireAll = true;
  const PermissionQuery.any(this.keys) : _single = null, requireAll = false;

  final List<String> keys;
  final String? _single;
  final bool requireAll;

  List<String> get codes => _single == null ? keys : [_single];
}

/// Pure RBAC check shared by the session controller, models, route guard and widgets.
/// Owners and the `"*"` code pass everything; a null/empty query passes.
bool hasPermissions(List<String> granted, PermissionQuery? query, {bool isOwner = false}) {
  if (query == null || isOwner || granted.contains(wildcardPermission)) return true;
  final codes = query.codes;
  if (codes.isEmpty) return true;
  return query.requireAll ? codes.every(granted.contains) : codes.any(granted.contains);
}
```

### `lib/core/storage/token_store.dart`

The token lives only in the Keychain / Keystore.

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

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Where the opaque API token lives. Only [SecureTokenStore] is used in the app.
abstract interface class TokenStore {
  Future<String?> read();

  /// Persists [token]; `null` deletes it.
  Future<void> write(String? token);
}

/// Keychain (iOS) / Keystore-backed encrypted storage (Android). Never SharedPreferences.
class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
    : _storage =
          storage ??
          const FlutterSecureStorage(
            iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device),
          );

  static const _key = 'auth_token';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> read() => _storage.read(key: _key);

  @override
  Future<void> write(String? token) =>
      token == null ? _storage.delete(key: _key) : _storage.write(key: _key, value: token);
}

/// In-memory store for tests.
class MemoryTokenStore implements TokenStore {
  MemoryTokenStore([this.token]);

  String? token;

  @override
  Future<String?> read() async => token;

  @override
  Future<void> write(String? token) async => this.token = token;
}
```

### `lib/core/auth/session_credentials.dart`

In-memory token + org id for the synchronous interceptor; wipes Keychain leftovers on the first launch after a reinstall.

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
import 'package:<project_slug>/core/storage/token_store.dart';

/// In-memory copy of what the http layer attaches (token, organisation), persisted on change.
///
/// The interceptor reads it synchronously; only the session controller writes it.
class SessionCredentials {
  SessionCredentials({required this._tokenStore, required this._preferences});

  final TokenStore _tokenStore;
  final AppPreferences _preferences;
  String? _token;
  String? _organizationId;

  String? get token => _token;
  String? get organizationId => _organizationId;
  bool get hasToken => _token != null;

  /// Loads persisted values. The keychain survives an uninstall on iOS, so the first launch
  /// of a fresh install wipes any leftover token.
  Future<void> load() async {
    if (!_preferences.isInstalled) {
      await _tokenStore.write(null);
      await _preferences.setOrganizationId(null);
      await _preferences.markInstalled();
    }
    _token = await _tokenStore.read();
    _organizationId = _preferences.organizationId;
  }

  Future<void> setToken(String? value) async {
    _token = value;
    await _tokenStore.write(value);
  }

  Future<void> setOrganizationId(String? value) async {
    _organizationId = value;
    await _preferences.setOrganizationId(value);
  }

  Future<void> clear() async {
    await setToken(null);
    await setOrganizationId(null);
  }
}
```

### `lib/features/auth/data/auth_repository.dart`

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
import 'package:<project_slug>/core/api/endpoints.dart';
import 'package:<project_slug>/core/models/json.dart';
import 'package:<project_slug>/core/models/user.dart';

/// Result of a successful login: the opaque token (shown once) and the user.
class LoginResult {
  const LoginResult({required this.token, required this.user});

  final String token;
  final User user;
}

/// Credential flows. Not a CRUD resource, so it does not extend `BaseRepository`.
class AuthRepository {
  AuthRepository(this._client);

  final ApiClient _client;

  Future<LoginResult> login({required String email, required String password}) async {
    final json = Json.map(
      await _client.post<Object?>(Endpoints.login, body: {'email': email, 'password': password}),
    );
    return LoginResult(
      token: Json.string(json, 'token'),
      user: User.fromJson(Json.map(json['user'])),
    );
  }

  /// Revokes the presented token server-side.
  Future<void> logout() => _client.post<Object?>(Endpoints.logout);

  /// `me/` may return the user directly or wrapped as `{user}`.
  Future<User> me() async {
    final json = Json.map(await _client.get<Object?>(Endpoints.me));
    return User.fromJson(json.containsKey('user') ? Json.map(json['user']) : json);
  }

  Future<User> updateProfile(User user) async =>
      User.fromJson(Json.map(await _client.patch<Object?>(Endpoints.me, body: user.toJson())));
}
```

### `lib/features/organizations/data/organization_repository.dart`

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

import 'package:<project_slug>/core/api/endpoints.dart';
import 'package:<project_slug>/core/data/base_repository.dart';
import 'package:<project_slug>/core/models/json.dart';
import 'package:<project_slug>/core/models/organization.dart';

/// Organisations the caller can switch to (owner orgs + active memberships).
class OrganizationRepository extends BaseRepository<Organization> {
  OrganizationRepository(super.client);

  @override
  ResourcePaths get paths => const ResourcePaths(list: Endpoints.myOrganizations);

  @override
  Organization fromJson(JsonMap json) => Organization.fromJson(json);

  Future<List<Organization>> mine() async => (await list()).items;
}
```

### `test/core/api/endpoints_test.dart`

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

import 'package:<project_slug>/core/api/endpoints.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('fills and encodes positional params', () {
    expect(
      Endpoints.path(Endpoints.organizationMemberDetail, ['a b']),
      'organization/members/a%20b/',
    );
  });

  test('returns templates without params unchanged', () {
    expect(Endpoints.path(Endpoints.me), 'accounts/me/');
  });

  test('fails loudly on a param count mismatch', () {
    expect(() => Endpoints.path(Endpoints.organizationMemberDetail), throwsArgumentError);
    expect(() => Endpoints.path(Endpoints.me, [1]), throwsArgumentError);
  });
}
```

### `test/core/api/api_error_test.dart`

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
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parses the backend error envelope', () {
    final error = ApiError.fromResponse(400, {
      'status': false,
      'err_cd': 'E-C-COR-0004',
      'err_msg': 'Invalid data.',
      'error': {
        'email': ['Enter a valid email.'],
        'non_field_errors': 'Nope.',
      },
    });
    expect(error.code, 'E-C-COR-0004');
    expect(error.message, 'Invalid data.');
    expect(error.isValidationError, isTrue);
    expect(error.firstError('email'), 'Enter a valid email.');
    expect(error.firstError('non_field_errors'), 'Nope.');
    expect(error.firstError('password'), isNull);
  });

  test('falls back to DRF detail and plain field maps', () {
    final error = ApiError.fromResponse(404, {
      'detail': 'Not found.',
      'name': ['Required.'],
    });
    expect(error.message, 'Not found.');
    expect(error.isNotFound, isTrue);
    expect(error.firstError('name'), 'Required.');
    expect(error.fieldErrors.containsKey('detail'), isFalse);
  });

  test('maps a connection failure to status 0', () {
    final error = ApiError.fromDioException(
      DioException.connectionError(
        requestOptions: RequestOptions(path: 'x'),
        reason: 'down',
      ),
    );
    expect(error.isNetworkError, isTrue);
    expect(error.code, 'connectionError');
  });

  test('keeps an ApiError already attached to the DioException', () {
    const attached = ApiError(status: 401, message: 'Invalid token.');
    final error = ApiError.fromDioException(
      DioException(
        requestOptions: RequestOptions(path: 'x'),
        error: attached,
      ),
    );
    expect(identical(error, attached), isTrue);
  });
}
```

### `test/core/api/interceptors_test.dart`

Exercises the real Dio instance through a fake `HttpClientAdapter` — no network.

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

import 'dart:convert';
import 'dart:typed_data';

import 'package:<project_slug>/core/api/api_client.dart';
import 'package:<project_slug>/core/api/api_error.dart';
import 'package:<project_slug>/core/api/interceptors.dart';
import 'package:<project_slug>/core/auth/session_credentials.dart';
import 'package:<project_slug>/core/storage/app_preferences.dart';
import 'package:<project_slug>/core/storage/token_store.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../helpers/factories.dart';

/// Answers every request with [status] + JSON [body] and records the request.
class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.status, this.body);

  final int status;
  final Object? body;
  RequestOptions? lastRequest;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    lastRequest = options;
    return ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  late SessionCredentials credentials;
  late HttpHooks hooks;

  setUp(() async {
    SharedPreferences.setMockInitialValues({'app.installed': true});
    credentials = SessionCredentials(
      tokenStore: MemoryTokenStore('tok'),
      preferences: await AppPreferences.load(),
    );
    await credentials.load();
    await credentials.setOrganizationId('org-1');
    hooks = HttpHooks();
  });

  (ApiClient, FakeAdapter) build(int status, Object? body, {String tenancyMode = 'multi'}) {
    final dio = createDio(
      config: testConfig(tenancyMode: tenancyMode),
      credentials: credentials,
      hooks: hooks,
      timezone: () => 'Asia/Kolkata',
    );
    final adapter = FakeAdapter(status, body);
    dio.httpClientAdapter = adapter;
    return (ApiClient(dio), adapter);
  }

  test('attaches token, tenant and timezone headers to API requests', () async {
    final (client, adapter) = build(200, {'status': true, 'data': <String, Object?>{}});
    await client.get<Object?>('accounts/me/');
    final headers = adapter.lastRequest!.headers;
    expect(headers[authHeader], 'Token tok');
    expect(headers[tenantHeader], 'org-1');
    expect(headers[timezoneHeader], 'Asia/Kolkata');
  });

  test('omits the tenant header in single-tenant mode', () async {
    final (client, adapter) = build(200, {
      'status': true,
      'data': <String, Object?>{},
    }, tenancyMode: 'single');
    await client.get<Object?>('accounts/me/');
    expect(adapter.lastRequest!.headers.containsKey(tenantHeader), isFalse);
  });

  test('never sends the token to other origins', () async {
    final (client, adapter) = build(200, <String, Object?>{});
    await client.get<Object?>('https://cdn.example.com/file.json');
    expect(adapter.lastRequest!.headers.containsKey(authHeader), isFalse);
  });

  test('unwraps the success envelope', () async {
    final (client, _) = build(200, {
      'status': true,
      'data': {'id': 7},
      'version': '1.0.0',
    });
    expect(await client.get<Map<String, dynamic>>('x/'), {'id': 7});
  });

  test('serialises list params DRF-style', () async {
    final (client, adapter) = build(200, {'status': true, 'data': <Object?>[]});
    await client.get<Object?>(
      'orders/',
      query: {
        'status': ['a', 'b'],
      },
    );
    expect(adapter.lastRequest!.uri.query, 'status=a&status=b');
  });

  test('maps errors to ApiError and fires the 401 hook', () async {
    ApiError? seen;
    hooks.onUnauthorized = (error) => seen = error;
    final (client, _) = build(401, {
      'status': false,
      'err_cd': 'E-C-COR-0005',
      'err_msg': 'Invalid or expired token.',
      'error': <String, Object?>{},
    });
    await expectLater(
      client.get<Object?>('accounts/me/'),
      throwsA(isA<ApiError>().having((e) => e.code, 'code', 'E-C-COR-0005')),
    );
    expect(seen?.isUnauthorized, isTrue);
  });

  test('fires the 403 hook', () async {
    ApiError? seen;
    hooks.onForbidden = (error) => seen = error;
    final (client, _) = build(403, {'status': false, 'err_msg': 'Denied.'});
    await expectLater(client.get<Object?>('x/'), throwsA(isA<ApiError>()));
    expect(seen?.isForbidden, isTrue);
  });

  test('treats a 2xx envelope with status false as an error', () async {
    final (client, _) = build(200, {'status': false, 'err_msg': 'Quota exceeded.'});
    await expectLater(
      client.post<Object?>('x/'),
      throwsA(isA<ApiError>().having((e) => e.message, 'message', 'Quota exceeded.')),
    );
  });
}
```

### `test/core/data/base_repository_test.dart`

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

import 'package:<project_slug>/core/data/base_repository.dart';
import 'package:<project_slug>/core/models/json.dart';
import 'package:<project_slug>/core/models/organization.dart';
import 'package:<project_slug>/features/organizations/data/organization_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import '../../helpers/factories.dart';
import '../../helpers/mocks.dart';

/// A CRUD repository with a detail endpoint, as a feature would declare it.
class _OrgCrudRepository extends BaseRepository<Organization> {
  _OrgCrudRepository(super.client);

  @override
  ResourcePaths get paths =>
      const ResourcePaths(list: 'orgs/', detail: 'orgs/%i/', create: 'orgs/new/');

  @override
  Organization fromJson(JsonMap json) => Organization.fromJson(json);
}

void main() {
  late MockApiClient client;

  setUp(() => client = MockApiClient());

  test('list normalises a DRF page into models', () async {
    when(() => client.get<Object?>('orgs/', query: {'limit': 2})).thenAnswer(
      (_) async => {
        'count': 3,
        'next': 'https://api.test/api/orgs/?offset=2',
        'previous': null,
        'results': [
          organizationJson(),
          organizationJson({'id': 'org-2'}),
        ],
      },
    );
    final page = await _OrgCrudRepository(client).list(query: {'limit': 2});
    expect(page.items, hasLength(2));
    expect(page.items.first, isA<Organization>());
    expect(page.count, 3);
    expect(page.hasMore, isTrue);
  });

  test('list accepts a bare array', () async {
    when(
      () => client.get<Object?>('organization/my-orgs/', query: any(named: 'query')),
    ).thenAnswer((_) async => [organizationJson()]);
    final orgs = await OrganizationRepository(client).mine();
    expect(orgs.single.name, 'Acme');
  });

  test('get, create, update and remove hit the right paths', () async {
    final repository = _OrgCrudRepository(client);
    when(() => client.get<Object?>('orgs/org-1/')).thenAnswer((_) async => organizationJson());
    when(
      () => client.post<Object?>('orgs/new/', body: any(named: 'body')),
    ).thenAnswer((_) async => organizationJson());
    when(
      () => client.patch<Object?>('orgs/org-1/', body: {'name': 'New'}),
    ).thenAnswer((_) async => organizationJson({'name': 'New'}));
    when(() => client.delete('orgs/org-1/')).thenAnswer((_) async {});

    expect((await repository.get('org-1')).id, 'org-1');
    expect((await repository.create({'name': 'Acme'})).name, 'Acme');
    expect((await repository.update('org-1', {'name': 'New'})).name, 'New');
    await repository.remove('org-1');
    verify(() => client.delete('orgs/org-1/')).called(1);
  });

  test('list-only repositories fail loudly on detail calls', () {
    expect(() => OrganizationRepository(client).get('x'), throwsStateError);
  });
}
```

### `test/core/models/user_test.dart`

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

import 'package:<project_slug>/core/models/user.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/factories.dart';

void main() {
  test('fromJson maps every field and normalises the id', () {
    final user = User.fromJson(userJson());
    expect(user.id, '1');
    expect(user.email, 'ada@example.com');
    expect(user.firstName, 'Ada');
    expect(user.role, UserRole.member);
    expect(user.emailConfirmed, isTrue);
    expect(user.createdOn, DateTime.utc(2026, 1, 2, 3, 4, 5));
  });

  test('fromJson tolerates missing optional fields', () {
    final user = User.fromJson({'id': 'u-1', 'email': 'x@example.com'});
    expect(user.firstName, '');
    expect(user.role, isNull);
    expect(user.permissions, isEmpty);
    expect(user.createdOn, isNull);
  });

  test('fromJson rejects a missing id', () {
    expect(() => User.fromJson({'email': 'x@example.com'}), throwsFormatException);
  });

  test('toJson round-trips writable fields only', () {
    final user = User.fromJson(userJson()).copyWith(firstName: 'Grace');
    expect(user.toJson(), {'first_name': 'Grace', 'last_name': 'Lovelace'});
  });

  test('fullName, initials and role ladder', () {
    final user = User.fromJson(userJson());
    expect(user.fullName, 'Ada Lovelace');
    expect(user.initials, 'AL');
    expect(User.fromJson({'id': 2, 'email': 'bob@example.com'}).fullName, 'bob@example.com');
    expect(user.hasRoleAtLeast(UserRole.guest), isTrue);
    expect(user.hasRoleAtLeast(UserRole.admin), isFalse);
  });
}
```

### `test/core/models/organization_test.dart`

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
import 'package:<project_slug>/core/models/organization.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/factories.dart';

void main() {
  test('fromJson maps the my-orgs payload', () {
    final org = Organization.fromJson(organizationJson());
    expect(org.id, 'org-1');
    expect(org.name, 'Acme');
    expect(org.roleName, 'Member');
    expect(org.permissions, ['order:read']);
    expect(org.toJson(), {'name': 'Acme'});
  });

  test('can() checks the caller permissions in this org', () {
    final org = Organization.fromJson(organizationJson());
    expect(org.can(const PermissionQuery.single('order:read')), isTrue);
    expect(org.can(const PermissionQuery.single('order:write')), isFalse);
    final owner = Organization.fromJson(
      organizationJson({'is_owner': true, 'permissions': <String>[]}),
    );
    expect(owner.can(const PermissionQuery.single('order:write')), isTrue);
  });
}
```

### `test/core/auth/permissions_test.dart`

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
import 'package:flutter_test/flutter_test.dart';

void main() {
  const granted = ['a', 'b'];

  test('single, all (AND) and any (OR)', () {
    expect(hasPermissions(granted, const PermissionQuery.single('a')), isTrue);
    expect(hasPermissions(granted, const PermissionQuery.single('c')), isFalse);
    expect(hasPermissions(granted, const PermissionQuery.all(['a', 'b'])), isTrue);
    expect(hasPermissions(granted, const PermissionQuery.all(['a', 'c'])), isFalse);
    expect(hasPermissions(granted, const PermissionQuery.any(['c', 'b'])), isTrue);
    expect(hasPermissions(granted, const PermissionQuery.any(['c', 'd'])), isFalse);
  });

  test('null or empty queries pass', () {
    expect(hasPermissions(const [], null), isTrue);
    expect(hasPermissions(const [], const PermissionQuery.all([])), isTrue);
  });

  test('owners and the wildcard pass everything', () {
    expect(hasPermissions(const [], const PermissionQuery.single('x'), isOwner: true), isTrue);
    expect(hasPermissions(const ['*'], const PermissionQuery.single('x')), isTrue);
  });
}
```
