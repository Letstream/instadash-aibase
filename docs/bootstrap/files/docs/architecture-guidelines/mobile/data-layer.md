<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Mobile Data Layer

> How the Flutter app talks to the backend. Same shape as the web
> [data layer](../frontend/project-structure.md#3-data-layer-layered): registry + one client with
> interceptors → a repository class per domain → typed model classes. Full code in the
> [mobile scaffold](../../bootstrap/scaffold/mobile/data-layer.md).

```
screen ─▶ controller (ChangeNotifier) ─▶ repository (class per domain) ─▶ ApiClient ─▶ Dio + interceptors
   ▲                 │                              │                                        │
   └── models ◀──────┘◀──── Model.fromJson ◀───────┘                    Endpoints registry (%i params)
```

Screens call **controllers** (or a repository for a small local fetch); controllers call
**repositories**; only `lib/core/api/` touches Dio. Nothing else imports `package:dio`.

---

## 1. Backend contract (what the app relies on)

| Aspect | Contract |
|---|---|
| Base | Everything under `/api/` — `API_BASE_URL` ends in `/api/`; registry paths are relative (`accounts/me/`). |
| Success | `{status: true, data, version}` → callers receive `data`. |
| Error | `{status: false, err_cd, err_msg, error, version}` with the HTTP status; `error` holds field errors (`{field: [msg]}`). |
| Auth | `Authorization: Token <opaque token>` from `POST accounts/login/` (`{token, expires_on, user}`). No refresh endpoint — **401 = session over**. |
| Session | `GET/PATCH accounts/me/`, `POST accounts/logout/` (revokes the token). |
| Tenancy | Multi-tenant only: `GET organization/my-orgs/` (`[{id, name, is_owner, role, permissions}]`) and the `X-Organization-Id` header on every request. |
| Timezone | `X-User-Tz: <IANA zone>` on every request. |
| Lists | DRF limit/offset pagination: `?limit=&offset=` → `{count, next, previous, results}`; some endpoints return a bare array. |

---

## 2. Endpoint registry

`lib/core/api/endpoints.dart` declares every path once:

```dart
abstract final class Endpoints {
  static const login = 'accounts/login/';
  static const me = 'accounts/me/';
  static const myOrganizations = 'organization/my-orgs/';
  static const orderDetail = 'orders/%i/';             // %i = positional param

  static String path(String template, [List<Object> params = const []]) { /* fills + URL-encodes, throws on count mismatch */ }
}
Endpoints.path(Endpoints.orderDetail, [id]);           // 'orders/42/'
```

No URL strings anywhere else — not in screens, controllers or repositories. Keep it in sync with
the backend URLconf (a renamed backend route is a one-line change here).

## 3. The one Dio instance + interceptors

`createDio(config, credentials, hooks, timezone)` in `lib/core/api/api_client.dart`:

- `BaseOptions(baseUrl: config.apiBaseUrl, connectTimeout: 15 s, receiveTimeout: 30 s,
  listFormat: ListFormat.multi)` — list params serialise DRF-style (`?status=a&status=b`).
- **`SessionInterceptor`** (request) — adds `Authorization: Token …`, `X-Organization-Id`
  (**multi-tenant only**, from the selected org) and `X-User-Tz`, **only** when the URL starts with
  `apiBaseUrl`. Third-party URLs (CDN, presigned S3) never see the token.
- **`EnvelopeInterceptor`** — `onResponse` unwraps the envelope; a 2xx body with `status: false`
  is rejected as an error. `onError` converts every failure to `ApiError` (attached as
  `DioException.error`) and fires `HttpHooks.onUnauthorized` (401) / `onForbidden` (403).
- `HttpHooks` are plain callbacks assigned in the composition root — the http layer never imports
  controllers or the router.
- Logging: never log headers or bodies in release builds. If a debug `LogInterceptor` is added,
  guard it with `kDebugMode` and `requestHeader: false`.

## 4. `ApiClient` and `ApiError`

```dart
class ApiClient {
  Future<T> get<T>(String path, {QueryParams? query});
  Future<T> post<T>(String path, {Object? body});
  Future<T> put<T>(String path, {Object? body});
  Future<T> patch<T>(String path, {Object? body});
  Future<void> delete(String path);
}
```

- Returns the **unwrapped** payload; throws **only `ApiError`** (every `DioException` is mapped).
- `ApiError`: `status` (0 = no response: offline/timeout/TLS), `code` (`err_cd`), `message`
  (`err_msg` or DRF `detail`), `fieldErrors` (`Map<String, List<String>>`), `firstError(field)`,
  and `isNetworkError / isValidationError / isUnauthorized / isForbidden / isNotFound`.
- Domain error codes (e.g. a quota `err_cd`) are matched on `error.code`, never on message text.
- Screens turn errors into copy with `errorMessage(context, error)` (localized for network/5xx,
  the backend message otherwise) and forms show `error.firstError('field')` under the input.

## 5. Repositories — one class per domain

```dart
class OrderRepository extends BaseRepository<Order> {
  OrderRepository(super.client);

  @override
  ResourcePaths get paths => const ResourcePaths(
    list: Endpoints.orderList,
    detail: Endpoints.orderDetail,          // omit for list-only resources
  );

  @override
  Order fromJson(JsonMap json) => Order.fromJson(json);

  Future<Order> cancel(String id) async =>  // domain calls are extra methods
      fromJson(Json.map(await client.post<Object?>(Endpoints.path(Endpoints.orderCancel, [id]))));
}
```

- `BaseRepository<T>` gives `list({query}) → PageResult<T>`, `get(id)`, `create(payload)`,
  `update(id, payload)` (PATCH), `remove(id)` — all returning **model instances**.
- `PageResult.fromBody` normalises both list shapes (`{results, count, next}` or `[...]`) at the
  boundary; nothing downstream checks the shape again.
- Anything list-driven (`ListController`, pickers) accepts a `ListableRepository<T>`.
- Non-CRUD flows (auth) are plain classes taking an `ApiClient` (`AuthRepository`).
- Repositories are created in the composition root and injected; a feature-local repository may
  be created by its screen's provider from the shared `ApiClient`.

## 6. Models

```dart
class Order extends BaseModel {
  const Order({required this.id, required this.reference, this.total = 0, this.createdOn});

  factory Order.fromJson(JsonMap json) => Order(
    id: Json.id(json['id']),                       // ids normalised to String
    reference: Json.string(json, 'reference'),
    total: Json.intOrNull(json, 'total') ?? 0,
    createdOn: Json.date(json, 'created_on'),
  );

  final String id;
  final String reference;
  final int total;
  final DateTime? createdOn;

  @override
  JsonMap toJson() => {'reference': reference};      // writable fields only, snake_case

  bool get isNew => createdOn == null;               // behaviour lives on the model
}
```

- Immutable (`final` fields, `const` constructor, `copyWith` for edits). snake_case stays at the
  JSON boundary; Dart fields are camelCase.
- Use the `Json` readers — they tolerate missing optional fields and **throw `FormatException`
  on a missing id**, so bad payloads fail at the boundary instead of deep in a widget.
- Entity logic (display names, permission checks, derived state) is a model getter/method.
- Enums parse with a safe fallback (`UserRole.tryParse`); unknown values never crash the app.
- Codegen (`json_serializable`/`freezed`) is **not** the default. A project may adopt it for
  large DTO surfaces — record it in `DOCS.md`, keep models behind the same `fromJson`/`toJson`
  API, and exclude `*.g.dart` from format/lint/header.

## 7. Token, preferences and session storage

| Data | Where | Why |
|---|---|---|
| API token | `SecureTokenStore` → `flutter_secure_storage` (Keychain `first_unlock_this_device` / Android Keystore) | secret |
| Selected org id, theme mode, locale | `AppPreferences` (SharedPreferences, `app.` prefix) | non-secret UI state |
| Anything else sensitive (PII caches, files) | don't cache; if unavoidable, encrypt and clear on logout | least data |

- `SessionCredentials` holds the token + org id **in memory** for the synchronous interceptor and
  persists on change. Only the session controller writes it.
- iOS keeps Keychain items across uninstall: the first launch of a fresh install (no
  `app.installed` flag) wipes any leftover token.
- Android: `android:allowBackup="false"` so encrypted prefs are never restored onto a device
  without their key.
- Logout = best-effort `POST accounts/logout/` then **always** clear token, org id and in-memory
  state. Screens holding per-user data must reset when the session ends.

## 8. Tenancy (multi-tenant mode)

- `TENANCY_MODE` (dart-define) must equal the backend's choice in `DOCS.md`.
- After login/restore the session loads `my-orgs`; a stored org id is kept **only if it is still in
  that list**; exactly one org is auto-selected; otherwise the router sends the user to the
  selector. `selectOrganization(id)` refuses ids not in the list.
- The org id lives in the session, **not in route paths** (a mobile URL is not user-visible); deep
  links that carry an org id go through `selectOrganization` first.
- Permissions come from the current org's `permissions` (owner / `"*"` = all). Single-tenant:
  from the user (`role` ladder + `permissions`), no org calls, no header.
- The server is the boundary: the client check only hides UI; every request is re-authorised by
  the backend (`HasOrgPermission`).

## 9. Pagination, caching, offline

- Lists page with `limit`/`offset` through `ListController` (generation counter drops stale
  responses; `retry()` resumes the failed page).
- No offline database by default. Show cached in-memory data while refreshing; on
  `ApiError.isNetworkError` show the error view with retry — never log the user out.
- If a project needs offline-first, record the choice (e.g. `drift`) in `DOCS.md` and keep it
  behind the repository interface so screens don't change.
- File uploads: `FormData` through `ApiClient.post`, or direct-to-S3 with a presigned URL using a
  **separate** Dio without the session interceptor. Validate size/type before upload.
