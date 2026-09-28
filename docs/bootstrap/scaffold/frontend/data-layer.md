# Frontend scaffold — data layer

> Part of the [frontend scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the frontend repo root.

Three layers, each depending only on the one below it:

1. **Transport** — `src/api/endpoints.ts` (every backend path once, `%i` params) +
   `src/api/http.ts` (the ONE axios instance: request interceptor adds `Authorization: Token …`,
   `X-Organization-Id` in multi-tenant mode, `X-User-Tz`; response interceptors unwrap the
   `{status, data, version}` envelope and reject with `ApiError`, firing the 401/403 hooks) +
   `ApiClient`, a typed facade resources depend on.
2. **Resources** — one class per domain in `src/api/resources/`, extending
   `BaseResource<TModel, TDto>`; CRUD returns **model instances**. Singletons in `resources/index.ts`.
3. **Models** — TS classes in `src/models/` with typed camelCase fields, methods/getters,
   `static fromJson(dto)` and `toJson()`.

Pinia stores call resources; components call stores (or resources for local data). Nobody but
`http.ts` touches axios.

Adding a domain (e.g. orders): add `orderList`/`orderCreate`/`orderDetail` to the registry, a
`src/models/Order.ts` (`OrderDto`, `Order.fromJson`, `toJson`), and

```ts
export class OrderResource extends BaseResource<Order, OrderDto> {
    protected readonly paths: ResourcePaths = {
        list: endpoints.orderList,
        create: endpoints.orderCreate,
        detail: endpoints.orderDetail, // "orders/%i/"
    };

    protected toModel(dto: OrderDto): Order {
        return Order.fromJson(dto);
    }
}
```

plus specs for the model and the resource (fake `ApiClient`, as below).

### `src/api/types.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

/** Success envelope written by the backend renderer: `{ status: true, data, version }`. */
export interface ApiEnvelope<T> {
    status: boolean;
    data: T;
    version?: string;
}

/** DRF paginated list shape. */
export interface PaginatedDto<T> {
    results: T[];
    count?: number;
    next?: string | null;
    previous?: string | null;
}

/** A list endpoint returns either a paginated object or a bare array. */
export type ListDto<T> = T[] | PaginatedDto<T>;

/** The one list shape the app works with after normalisation. */
export interface Page<T> {
    items: T[];
    count: number;
    next: string | null;
    previous: string | null;
}

export type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryValue | QueryValue[]>;

/** Normalises both list shapes at the boundary so components never branch on it. */
export function normalizeList<T>(body: ListDto<T> | null | undefined): Page<T> {
    if (Array.isArray(body)) {
        return { items: body, count: body.length, next: null, previous: null };
    }
    const items = body?.results ?? [];
    return {
        items,
        count: body?.count ?? items.length,
        next: body?.next ?? null,
        previous: body?.previous ?? null,
    };
}

/** Maps the items of a page, keeping the pagination metadata. */
export function mapPage<TIn, TOut>(
    page: Page<TIn>,
    map: (item: TIn) => TOut
): Page<TOut> {
    return { ...page, items: page.items.map(map) };
}
```

### `src/api/endpoints.ts`

Paths match the backend scaffold's URLconf, served under `VITE_API_BASE` (`/api/`).

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

/**
 * Endpoint registry — every backend path is declared ONCE here, relative to `VITE_API_BASE`
 * (the axios `baseURL`). `%i` marks a positional path parameter filled by `endpoint()`.
 * Keep in sync with the backend URLconf.
 */
export const endpoints = {
    // accounts
    login: "accounts/login/",
    logout: "accounts/logout/",
    me: "accounts/me/",

    // organisations (multi-tenant only)
    myOrganizations: "organization/my-orgs/",
    organizationMemberDetail: "organization/members/%i/",
} as const;

export type EndpointKey = keyof typeof endpoints;

/** Resolves a registry key (or raw template) and fills `%i` params, URL-encoding each one. */
export function endpoint(
    keyOrTemplate: EndpointKey | string,
    ...params: Array<string | number>
): string {
    const template =
        keyOrTemplate in endpoints
            ? endpoints[keyOrTemplate as EndpointKey]
            : keyOrTemplate;
    let index = 0;
    const path = template.replace(/%i/g, () => {
        const value = params[index++];
        if (value === undefined) {
            throw new Error(
                `Missing path parameter ${index} for endpoint "${keyOrTemplate}".`
            );
        }
        return encodeURIComponent(String(value));
    });
    if (index !== params.length) {
        throw new Error(`Too many path parameters for endpoint "${keyOrTemplate}".`);
    }
    return path;
}
```

### `src/api/errors.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { isAxiosError } from "axios";

/** Field-keyed validation errors (`{ email: ["Enter a valid email."] }`). */
export type FieldErrors = Record<string, string[]>;

interface ApiErrorInit {
    status: number;
    message: string;
    code?: string | null;
    fieldErrors?: FieldErrors;
    body?: unknown;
}

const ENVELOPE_KEYS = new Set([
    "status",
    "err_cd",
    "err_msg",
    "error",
    "version",
    "detail",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Normalises DRF / envelope error payloads into `{ field: string[] }`. */
export function normalizeFieldErrors(source: unknown): FieldErrors {
    if (!isRecord(source)) return {};
    const errors: FieldErrors = {};
    for (const [field, value] of Object.entries(source)) {
        if (ENVELOPE_KEYS.has(field)) continue;
        if (Array.isArray(value)) {
            const messages = value.filter((item) => typeof item === "string");
            if (messages.length) errors[field] = messages;
        } else if (typeof value === "string") {
            errors[field] = [value];
        }
    }
    return errors;
}

/**
 * The single error type every API call rejects with. Built from the backend error envelope
 * `{ status: false, err_cd, err_msg, error, version }`; `status === 0` means a network error.
 */
export class ApiError extends Error {
    readonly status: number;
    readonly code: string | null;
    readonly fieldErrors: FieldErrors;
    readonly body: unknown;

    constructor(init: ApiErrorInit) {
        super(init.message);
        this.name = "ApiError";
        this.status = init.status;
        this.code = init.code ?? null;
        this.fieldErrors = init.fieldErrors ?? {};
        this.body = init.body;
    }

    get isNetworkError(): boolean {
        return this.status === 0;
    }

    get isValidationError(): boolean {
        return this.status === 400;
    }

    get isUnauthorized(): boolean {
        return this.status === 401;
    }

    get isForbidden(): boolean {
        return this.status === 403;
    }

    get isNotFound(): boolean {
        return this.status === 404;
    }

    /** First message for a field — what forms render under the input. */
    firstError(field: string): string | null {
        return this.fieldErrors[field]?.[0] ?? null;
    }

    static fromResponse(status: number, body: unknown): ApiError {
        const envelope = isRecord(body) ? body : {};
        const code = typeof envelope.err_cd === "string" ? envelope.err_cd : null;
        const message =
            (typeof envelope.err_msg === "string" && envelope.err_msg) ||
            (typeof envelope.detail === "string" && envelope.detail) ||
            `Request failed with status ${status}`;
        const fieldSource = "error" in envelope ? envelope.error : envelope;
        return new ApiError({
            status,
            code,
            message,
            fieldErrors: normalizeFieldErrors(fieldSource),
            body,
        });
    }

    static from(error: unknown): ApiError {
        if (error instanceof ApiError) return error;
        if (isAxiosError(error)) {
            if (error.response) {
                return ApiError.fromResponse(error.response.status, error.response.data);
            }
            return new ApiError({
                status: 0,
                code: error.code ?? null,
                message: error.message,
            });
        }
        const message = error instanceof Error ? error.message : String(error);
        return new ApiError({ status: 0, message });
    }
}
```

### `src/api/http.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import axios, {
    type AxiosInstance,
    type AxiosResponse,
    type InternalAxiosRequestConfig,
} from "axios";

import { appConfig } from "@/config/app";

import { ApiError } from "./errors";
import type { ApiEnvelope, QueryParams } from "./types";

export const AUTH_HEADER = "Authorization";
export const TENANT_HEADER = "X-Organization-Id";
export const TIMEZONE_HEADER = "X-User-Tz";

/**
 * Session hooks the http layer calls. Wired once in `main.ts` (see `plugins/session.ts`) so
 * the http module never imports the store or router — no cycles, trivially testable.
 */
export interface HttpHooks {
    getToken(): string | null;
    getOrganizationId(): string | null;
    onUnauthorized(error: ApiError): void;
    onForbidden(error: ApiError): void;
}

const defaultHooks: HttpHooks = {
    getToken: () => null,
    getOrganizationId: () => null,
    onUnauthorized: () => undefined,
    onForbidden: () => undefined,
};

const hooks: HttpHooks = { ...defaultHooks };

export function configureHttp(next: Partial<HttpHooks>): void {
    Object.assign(hooks, next);
}

export function resetHttpHooks(): void {
    Object.assign(hooks, defaultHooks);
}

/** Absolute URLs to other origins never receive the token. */
export function isApiRequest(url: string | undefined): boolean {
    if (!url || !/^[a-z][a-z\d+.-]*:\/\//i.test(url)) return true;
    return url.startsWith(new URL(appConfig.apiBase, window.location.origin).href);
}

export function attachSessionHeaders(
    config: InternalAxiosRequestConfig
): InternalAxiosRequestConfig {
    if (!isApiRequest(config.url)) return config;
    const token = hooks.getToken();
    if (token) config.headers.set(AUTH_HEADER, `Token ${token}`);
    const organizationId = hooks.getOrganizationId();
    if (organizationId) config.headers.set(TENANT_HEADER, organizationId);
    config.headers.set(TIMEZONE_HEADER, Intl.DateTimeFormat().resolvedOptions().timeZone);
    return config;
}

export function isEnvelope(body: unknown): body is ApiEnvelope<unknown> {
    return (
        typeof body === "object" &&
        body !== null &&
        typeof (body as { status?: unknown }).status === "boolean" &&
        "data" in body
    );
}

/** Replaces `response.data` with the envelope's inner `data` so callers get the payload. */
export function unwrapEnvelope(response: AxiosResponse): AxiosResponse {
    if (isEnvelope(response.data)) response.data = response.data.data;
    return response;
}

/** Maps every failure to `ApiError` and triggers the global 401 / 403 flows. */
export function rejectWithApiError(error: unknown): Promise<never> {
    const apiError = ApiError.from(error);
    if (apiError.isUnauthorized) hooks.onUnauthorized(apiError);
    else if (apiError.isForbidden) hooks.onForbidden(apiError);
    return Promise.reject(apiError);
}

/** The ONE axios instance of the app. */
export const http: AxiosInstance = axios.create({
    baseURL: appConfig.apiBase,
    timeout: 30_000,
    headers: { Accept: "application/json" },
    // DRF style arrays: ?status=a&status=b
    paramsSerializer: { indexes: null },
});

http.interceptors.request.use(attachSessionHeaders);
http.interceptors.response.use(unwrapEnvelope, rejectWithApiError);

/** Typed facade over the axios instance; resources depend on this, tests fake it. */
export class ApiClient {
    private readonly instance: AxiosInstance;

    constructor(instance: AxiosInstance) {
        this.instance = instance;
    }

    async get<T>(url: string, params?: QueryParams): Promise<T> {
        return (await this.instance.get<T>(url, { params })).data;
    }

    async post<T>(url: string, body?: unknown): Promise<T> {
        return (await this.instance.post<T>(url, body)).data;
    }

    async put<T>(url: string, body?: unknown): Promise<T> {
        return (await this.instance.put<T>(url, body)).data;
    }

    async patch<T>(url: string, body?: unknown): Promise<T> {
        return (await this.instance.patch<T>(url, body)).data;
    }

    async delete<T = void>(url: string): Promise<T> {
        return (await this.instance.delete<T>(url)).data;
    }
}

export const api = new ApiClient(http);
```

### `src/api/resources/BaseResource.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { endpoint } from "../endpoints";
import { api, type ApiClient } from "../http";
import {
    mapPage,
    normalizeList,
    type ListDto,
    type Page,
    type QueryParams,
} from "../types";

/** Paths of a CRUD resource, as endpoint templates (`detail` holds one `%i` for the id). */
export interface ResourcePaths {
    list: string;
    /** omit for list-only resources; get/update/remove then throw */
    detail?: string;
    /** defaults to `list` (DRF router style) */
    create?: string;
}

/** What list-driven components (GenericList, selects) need from a resource. */
export interface ListableResource<TModel> {
    list(params?: QueryParams): Promise<Page<TModel>>;
}

/**
 * One class per domain resource. Subclasses declare `paths` and `toModel`; they inherit typed
 * CRUD that returns MODEL INSTANCES, never raw DTOs. Add domain calls as extra methods.
 */
export abstract class BaseResource<
    TModel,
    TDto,
    TWrite = Partial<TDto>,
> implements ListableResource<TModel> {
    protected abstract readonly paths: ResourcePaths;
    protected readonly client: ApiClient;

    constructor(client: ApiClient = api) {
        this.client = client;
    }

    /** DTO → model. Usually `return Order.fromJson(dto)`. */
    protected abstract toModel(dto: TDto): TModel;

    protected detailPath(id: string | number): string {
        if (!this.paths.detail) {
            throw new Error(`${this.constructor.name} has no detail endpoint.`);
        }
        return endpoint(this.paths.detail, id);
    }

    async list(params?: QueryParams): Promise<Page<TModel>> {
        const body = await this.client.get<ListDto<TDto>>(this.paths.list, params);
        return mapPage(normalizeList(body), (dto) => this.toModel(dto));
    }

    async get(id: string | number): Promise<TModel> {
        return this.toModel(await this.client.get<TDto>(this.detailPath(id)));
    }

    async create(payload: TWrite): Promise<TModel> {
        const path = this.paths.create ?? this.paths.list;
        return this.toModel(await this.client.post<TDto>(path, payload));
    }

    async update(id: string | number, payload: TWrite): Promise<TModel> {
        return this.toModel(await this.client.patch<TDto>(this.detailPath(id), payload));
    }

    async remove(id: string | number): Promise<void> {
        await this.client.delete(this.detailPath(id));
    }
}
```

### `src/api/resources/OrganizationResource.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { Organization, type OrganizationDto } from "@/models/Organization";

import { endpoints } from "../endpoints";

import { BaseResource, type ResourcePaths } from "./BaseResource";

export class OrganizationResource extends BaseResource<Organization, OrganizationDto> {
    protected readonly paths: ResourcePaths = {
        list: endpoints.myOrganizations,
    };

    protected toModel(dto: OrganizationDto): Organization {
        return Organization.fromJson(dto);
    }

    /** Organisations the caller can switch to (owner orgs + active memberships). */
    async mine(): Promise<Organization[]> {
        return (await this.list()).items;
    }
}
```

### `src/api/resources/AuthResource.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { User, type UserDto } from "@/models/User";

import { endpoints } from "../endpoints";
import { api, type ApiClient } from "../http";

export interface LoginPayloadDto {
    token: string;
    user: UserDto;
}

export interface LoginResult {
    token: string;
    user: User;
}

/** `me/` may return the user directly or wrapped as `{ user }`. */
type MeDto = UserDto | { user: UserDto };

/** Credential flows. Not a CRUD resource, so it does not extend `BaseResource`. */
export class AuthResource {
    private readonly client: ApiClient;

    constructor(client: ApiClient = api) {
        this.client = client;
    }

    async login(email: string, password: string): Promise<LoginResult> {
        const dto = await this.client.post<LoginPayloadDto>(endpoints.login, {
            email,
            password,
        });
        return { token: dto.token, user: User.fromJson(dto.user) };
    }

    async logout(): Promise<void> {
        await this.client.post(endpoints.logout);
    }

    async me(): Promise<User> {
        const dto = await this.client.get<MeDto>(endpoints.me);
        return User.fromJson("user" in dto ? dto.user : dto);
    }
}
```

### `src/api/resources/index.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { AuthResource } from "./AuthResource";
import { OrganizationResource } from "./OrganizationResource";

export { BaseResource, type ListableResource, type ResourcePaths } from "./BaseResource";
export { AuthResource, type LoginResult } from "./AuthResource";
export { OrganizationResource } from "./OrganizationResource";

/** Shared singletons — stores and components import these, tests `vi.mock` this module. */
export const authResource = new AuthResource();
export const organizationResource = new OrganizationResource();
```

### `src/api/__tests__/endpoints.spec.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { describe, expect, it } from "vitest";

import { endpoint, endpoints } from "@/api/endpoints";
import { mapPage, normalizeList } from "@/api/types";

describe("endpoint()", () => {
    it("returns registry paths unchanged when they have no params", () => {
        expect(endpoint("login")).toBe(endpoints.login);
    });

    it("fills and encodes positional params", () => {
        expect(endpoint("organizationMemberDetail", "u-1")).toBe(
            "organization/members/u-1/"
        );
        expect(endpoint("things/%i/sub/%i/", "a b", 2)).toBe("things/a%20b/sub/2/");
    });

    it("rejects missing or extra params", () => {
        expect(() => endpoint("organizationMemberDetail")).toThrow(/Missing/);
        expect(() => endpoint("login", 1)).toThrow(/Too many/);
    });
});

describe("normalizeList()", () => {
    it("accepts a bare array", () => {
        expect(normalizeList([1, 2])).toEqual({
            items: [1, 2],
            count: 2,
            next: null,
            previous: null,
        });
    });

    it("accepts the DRF paginated shape", () => {
        const page = normalizeList({
            results: [1],
            count: 40,
            next: "n",
            previous: null,
        });
        expect(page).toEqual({ items: [1], count: 40, next: "n", previous: null });
    });

    it("tolerates empty bodies and maps items", () => {
        expect(normalizeList(null).items).toEqual([]);
        expect(mapPage(normalizeList([1, 2]), (n) => n * 2).items).toEqual([2, 4]);
    });
});
```

### `src/api/__tests__/errors.spec.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { AxiosError, AxiosHeaders, type AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";

import { ApiError, normalizeFieldErrors } from "@/api/errors";

function axiosErrorWith(status: number, data: unknown): AxiosError {
    const response = {
        status,
        data,
        statusText: "",
        headers: {},
        config: { headers: new AxiosHeaders() },
    } as AxiosResponse;
    return new AxiosError("failed", "ERR_BAD_REQUEST", undefined, undefined, response);
}

describe("ApiError", () => {
    it("parses the error envelope", () => {
        const error = ApiError.from(
            axiosErrorWith(400, {
                status: false,
                err_cd: "ERR_VALIDATION",
                err_msg: "Invalid input.",
                error: { email: ["Enter a valid email."], name: "Required." },
                version: "1",
            })
        );
        expect(error.status).toBe(400);
        expect(error.code).toBe("ERR_VALIDATION");
        expect(error.message).toBe("Invalid input.");
        expect(error.isValidationError).toBe(true);
        expect(error.firstError("email")).toBe("Enter a valid email.");
        expect(error.firstError("name")).toBe("Required.");
        expect(error.firstError("missing")).toBeNull();
    });

    it("parses a plain DRF error body", () => {
        const error = ApiError.fromResponse(403, { detail: "Nope." });
        expect(error.isForbidden).toBe(true);
        expect(error.message).toBe("Nope.");
        expect(error.fieldErrors).toEqual({});
    });

    it("maps network failures to status 0", () => {
        const error = ApiError.from(new AxiosError("Network Error", "ERR_NETWORK"));
        expect(error.isNetworkError).toBe(true);
        expect(error.code).toBe("ERR_NETWORK");
    });

    it("wraps unknown errors and passes ApiError through", () => {
        const wrapped = ApiError.from(new Error("boom"));
        expect(wrapped.message).toBe("boom");
        expect(ApiError.from(wrapped)).toBe(wrapped);
        expect(ApiError.from("text").message).toBe("text");
        expect(ApiError.fromResponse(500, null).message).toMatch(/500/);
    });

    it("exposes status helpers", () => {
        expect(ApiError.fromResponse(401, {}).isUnauthorized).toBe(true);
        expect(ApiError.fromResponse(404, {}).isNotFound).toBe(true);
    });
});

describe("normalizeFieldErrors", () => {
    it("keeps string arrays and strings, drops the rest", () => {
        expect(
            normalizeFieldErrors({
                a: ["x", 1],
                b: "y",
                c: { nested: true },
                err_cd: "E",
            })
        ).toEqual({
            a: ["x"],
            b: ["y"],
        });
        expect(normalizeFieldErrors(["not", "a", "record"])).toEqual({});
    });
});
```

### `src/api/__tests__/http.spec.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import {
    AxiosError,
    AxiosHeaders,
    type AxiosResponse,
    type InternalAxiosRequestConfig,
} from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/errors";
import {
    ApiClient,
    attachSessionHeaders,
    configureHttp,
    isApiRequest,
    rejectWithApiError,
    resetHttpHooks,
    unwrapEnvelope,
} from "@/api/http";

function requestConfig(url = "accounts/me/"): InternalAxiosRequestConfig {
    return { url, headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
}

function response(data: unknown): AxiosResponse {
    return { data, status: 200, statusText: "OK", headers: {}, config: requestConfig() };
}

afterEach(() => {
    resetHttpHooks();
});

describe("request interceptor", () => {
    it("adds token, tenant and timezone headers", () => {
        configureHttp({ getToken: () => "abc", getOrganizationId: () => "42" });
        const config = attachSessionHeaders(requestConfig());
        expect(config.headers.get("Authorization")).toBe("Token abc");
        expect(config.headers.get("X-Organization-Id")).toBe("42");
        expect(config.headers.get("X-User-Tz")).toBeTruthy();
    });

    it("omits headers without a session", () => {
        const config = attachSessionHeaders(requestConfig());
        expect(config.headers.has("Authorization")).toBe(false);
        expect(config.headers.has("X-Organization-Id")).toBe(false);
    });

    it("never sends the token to another origin", () => {
        configureHttp({ getToken: () => "abc" });
        expect(isApiRequest("https://third-party.example/upload")).toBe(false);
        expect(isApiRequest(`${window.location.origin}/api/x/`)).toBe(true);
        const config = attachSessionHeaders(
            requestConfig("https://third-party.example/upload")
        );
        expect(config.headers.has("Authorization")).toBe(false);
    });
});

describe("response interceptors", () => {
    it("unwraps the success envelope", () => {
        expect(
            unwrapEnvelope(response({ status: true, data: { id: 1 }, version: "1" })).data
        ).toEqual({
            id: 1,
        });
        expect(unwrapEnvelope(response([1, 2])).data).toEqual([1, 2]);
    });

    it("rejects with ApiError and triggers the 401 / 403 hooks", async () => {
        const onUnauthorized = vi.fn();
        const onForbidden = vi.fn();
        configureHttp({ onUnauthorized, onForbidden });

        const failing = (status: number) =>
            new AxiosError("x", "ERR", undefined, undefined, {
                ...response({ status: false, err_msg: "denied" }),
                status,
            });

        await expect(rejectWithApiError(failing(401))).rejects.toBeInstanceOf(ApiError);
        expect(onUnauthorized).toHaveBeenCalledOnce();

        await expect(rejectWithApiError(failing(403))).rejects.toMatchObject({
            status: 403,
        });
        expect(onForbidden).toHaveBeenCalledOnce();

        await expect(rejectWithApiError(failing(400))).rejects.toMatchObject({
            message: "denied",
        });
        expect(onUnauthorized).toHaveBeenCalledOnce();
    });
});

describe("ApiClient", () => {
    it("returns response data for every verb", async () => {
        const instance = {
            get: vi.fn().mockResolvedValue({ data: "g" }),
            post: vi.fn().mockResolvedValue({ data: "p" }),
            put: vi.fn().mockResolvedValue({ data: "u" }),
            patch: vi.fn().mockResolvedValue({ data: "a" }),
            delete: vi.fn().mockResolvedValue({ data: undefined }),
        };
        const client = new ApiClient(instance as never);
        expect(await client.get("x/", { q: 1 })).toBe("g");
        expect(instance.get).toHaveBeenCalledWith("x/", { params: { q: 1 } });
        expect(await client.post("x/", {})).toBe("p");
        expect(await client.put("x/", {})).toBe("u");
        expect(await client.patch("x/", {})).toBe("a");
        expect(await client.delete("x/")).toBeUndefined();
    });
});
```

### `src/api/resources/__tests__/resources.spec.ts`

Resources take the `ApiClient` in their constructor, so specs pass a fake client — no module mocking or network.

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/http";
import { AuthResource } from "@/api/resources/AuthResource";
import { BaseResource, type ResourcePaths } from "@/api/resources/BaseResource";
import { OrganizationResource } from "@/api/resources/OrganizationResource";
import { Organization } from "@/models/Organization";
import { User } from "@/models/User";
import { organizationDto, userDto } from "@/test/factories";

/** A fake ApiClient: resources take the client in their constructor, so no module mocking. */
function fakeClient() {
    return {
        get: vi.fn(),
        post: vi.fn(),
        put: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
    };
}

interface WidgetDto {
    id: number;
    label: string;
}

class Widget {
    constructor(
        readonly id: string,
        readonly label: string
    ) {}
}

class WidgetResource extends BaseResource<Widget, WidgetDto> {
    protected readonly paths: ResourcePaths = {
        list: "widgets/list/",
        create: "widgets/create/",
        detail: "widgets/%i/",
    };

    protected toModel(dto: WidgetDto): Widget {
        return new Widget(String(dto.id), dto.label);
    }
}

describe("BaseResource", () => {
    it("lists and maps DTOs to models (both list shapes)", async () => {
        const client = fakeClient();
        const resource = new WidgetResource(client as unknown as ApiClient);

        client.get.mockResolvedValueOnce({ results: [{ id: 1, label: "a" }], count: 9 });
        const page = await resource.list({ search: "a" });
        expect(client.get).toHaveBeenCalledWith("widgets/list/", { search: "a" });
        expect(page.count).toBe(9);
        expect(page.items[0]).toBeInstanceOf(Widget);

        client.get.mockResolvedValueOnce([{ id: 2, label: "b" }]);
        expect((await resource.list()).items[0]?.label).toBe("b");
    });

    it("gets, creates, updates and removes through the right paths", async () => {
        const client = fakeClient();
        const resource = new WidgetResource(client as unknown as ApiClient);
        client.get.mockResolvedValue({ id: 3, label: "c" });
        client.post.mockResolvedValue({ id: 4, label: "d" });
        client.patch.mockResolvedValue({ id: 3, label: "e" });

        expect((await resource.get(3)).label).toBe("c");
        expect(client.get).toHaveBeenCalledWith("widgets/3/");
        expect((await resource.create({ label: "d" })).id).toBe("4");
        expect(client.post).toHaveBeenCalledWith("widgets/create/", { label: "d" });
        expect((await resource.update(3, { label: "e" })).label).toBe("e");
        expect(client.patch).toHaveBeenCalledWith("widgets/3/", { label: "e" });
        await resource.remove(3);
        expect(client.delete).toHaveBeenCalledWith("widgets/3/");
    });
});

describe("OrganizationResource", () => {
    it("returns Organization instances for mine()", async () => {
        const client = fakeClient();
        client.get.mockResolvedValue([
            organizationDto(),
            organizationDto({ id: 11, name: "Beta" }),
        ]);
        const orgs = await new OrganizationResource(
            client as unknown as ApiClient
        ).mine();
        expect(client.get).toHaveBeenCalledWith("organization/my-orgs/", undefined);
        expect(orgs.map((org) => org.name)).toEqual(["Acme", "Beta"]);
        expect(orgs[0]).toBeInstanceOf(Organization);
    });

    it("is list-only: detail calls fail loudly", async () => {
        const resource = new OrganizationResource(fakeClient() as unknown as ApiClient);
        await expect(resource.get(1)).rejects.toThrow(/no detail endpoint/);
    });
});

describe("AuthResource", () => {
    it("logs in and returns the token + User model", async () => {
        const client = fakeClient();
        client.post.mockResolvedValue({ token: "t0k", user: userDto() });
        const result = await new AuthResource(client as unknown as ApiClient).login(
            "a@b.c",
            "pw"
        );
        expect(client.post).toHaveBeenCalledWith("accounts/login/", {
            email: "a@b.c",
            password: "pw",
        });
        expect(result.token).toBe("t0k");
        expect(result.user).toBeInstanceOf(User);
    });

    it("accepts both me() shapes and logs out", async () => {
        const client = fakeClient();
        const resource = new AuthResource(client as unknown as ApiClient);
        client.get.mockResolvedValueOnce(userDto({ id: 1 }));
        client.get.mockResolvedValueOnce({ user: userDto({ id: 2 }) });
        expect((await resource.me()).id).toBe("1");
        expect((await resource.me()).id).toBe("2");
        await resource.logout();
        expect(client.post).toHaveBeenCalledWith("accounts/logout/");
    });
});
```

### `src/models/BaseModel.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

/**
 * Base class for domain entities. Every model:
 * - has typed, camelCase fields (the DTO stays snake_case at the API boundary),
 * - is built with `static fromJson(dto)` and serialised back with `toJson()`,
 * - carries its behaviour as methods/getters instead of helpers scattered in components.
 */
export abstract class BaseModel<TDto extends object> {
    abstract readonly id: string;

    /** Serialises the writable fields back to the API (snake_case) shape. */
    abstract toJson(): Partial<TDto>;

    /** Same entity (same class + id), regardless of field values. */
    equals(other: BaseModel<TDto> | null | undefined): boolean {
        return !!other && other.constructor === this.constructor && other.id === this.id;
    }

    /** Ids are normalised to strings (int PKs and UUIDs alike) for route params & headers. */
    protected static toId(value: string | number): string {
        return String(value);
    }

    protected static toDate(value: string | null | undefined): Date | null {
        if (!value) return null;
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? null : date;
    }
}
```

### `src/models/User.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { initials } from "@/utils/format";

import { BaseModel } from "./BaseModel";

/** Single-tenant role ladder (multi-tenant roles live on the organisation membership). */
export type UserRole = "owner" | "admin" | "member" | "guest";

const ROLE_RANK: Record<UserRole, number> = { guest: 0, member: 1, admin: 2, owner: 3 };

export interface UserDto {
    id: number | string;
    email: string;
    first_name?: string | null;
    last_name?: string | null;
    avatar?: string | null;
    email_confirmed?: boolean;
    /** single-tenant only */
    role?: UserRole | null;
    /** single-tenant only, optional: permission codes derived from `role` by the backend */
    permissions?: string[] | null;
    created_on?: string | null;
}

export interface UserInit {
    id: string;
    email: string;
    firstName?: string;
    lastName?: string;
    avatarUrl?: string | null;
    emailConfirmed?: boolean;
    role?: UserRole | null;
    permissions?: string[];
    createdOn?: Date | null;
}

export class User extends BaseModel<UserDto> {
    readonly id: string;
    email: string;
    firstName: string;
    lastName: string;
    avatarUrl: string | null;
    emailConfirmed: boolean;
    role: UserRole | null;
    permissions: string[];
    readonly createdOn: Date | null;

    constructor(init: UserInit) {
        super();
        this.id = init.id;
        this.email = init.email;
        this.firstName = init.firstName ?? "";
        this.lastName = init.lastName ?? "";
        this.avatarUrl = init.avatarUrl ?? null;
        this.emailConfirmed = init.emailConfirmed ?? false;
        this.role = init.role ?? null;
        this.permissions = init.permissions ?? [];
        this.createdOn = init.createdOn ?? null;
    }

    static fromJson(dto: UserDto): User {
        return new User({
            id: BaseModel.toId(dto.id),
            email: dto.email,
            firstName: dto.first_name ?? "",
            lastName: dto.last_name ?? "",
            avatarUrl: dto.avatar ?? null,
            emailConfirmed: dto.email_confirmed ?? false,
            role: dto.role ?? null,
            permissions: dto.permissions ?? [],
            createdOn: BaseModel.toDate(dto.created_on),
        });
    }

    toJson(): Partial<UserDto> {
        return { first_name: this.firstName, last_name: this.lastName };
    }

    get fullName(): string {
        return [this.firstName, this.lastName].filter(Boolean).join(" ") || this.email;
    }

    get initials(): string {
        return initials(this.fullName);
    }

    /** Single-tenant ladder check: `user.hasRoleAtLeast("admin")`. */
    hasRoleAtLeast(role: UserRole): boolean {
        return this.role !== null && ROLE_RANK[this.role] >= ROLE_RANK[role];
    }
}
```

### `src/models/Organization.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { hasPermissions, type PermissionQuery } from "@/utils/permissions";

import { BaseModel } from "./BaseModel";

/** One entry of `GET organization/my-orgs/` — the caller's view of a tenant. */
export interface OrganizationDto {
    id: number | string;
    name: string;
    is_owner?: boolean;
    /** the caller's role name in this org (null for owners without a membership row) */
    role?: string | null;
    /** the caller's permission codes in this org (`["*"]` = all) */
    permissions?: string[];
}

export interface OrganizationInit {
    id: string;
    name: string;
    isOwner?: boolean;
    roleName?: string | null;
    permissions?: string[];
}

/** A tenant the current user belongs to, with the caller's role + permission codes in it. */
export class Organization extends BaseModel<OrganizationDto> {
    readonly id: string;
    name: string;
    readonly isOwner: boolean;
    readonly roleName: string | null;
    readonly permissions: string[];

    constructor(init: OrganizationInit) {
        super();
        this.id = init.id;
        this.name = init.name;
        this.isOwner = init.isOwner ?? false;
        this.roleName = init.roleName ?? null;
        this.permissions = init.permissions ?? [];
    }

    static fromJson(dto: OrganizationDto): Organization {
        return new Organization({
            id: BaseModel.toId(dto.id),
            name: dto.name,
            isOwner: dto.is_owner ?? false,
            roleName: dto.role ?? null,
            permissions: dto.permissions ?? [],
        });
    }

    toJson(): Partial<OrganizationDto> {
        return { name: this.name };
    }

    /** `org.can("order:read")` — owners and `"*"` roles can do everything. */
    can(query: PermissionQuery | null | undefined): boolean {
        return hasPermissions(this.permissions, query, { isOwner: this.isOwner });
    }

    get roleLabel(): string {
        return this.isOwner ? "Owner" : (this.roleName ?? "Member");
    }
}
```

### `src/models/index.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

export { BaseModel } from "./BaseModel";
export { Organization, type OrganizationDto } from "./Organization";
export { User, type UserDto, type UserRole } from "./User";
```

### `src/models/__tests__/User.spec.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { describe, expect, it } from "vitest";

import { User } from "@/models/User";
import { userDto } from "@/test/factories";

describe("User", () => {
    it("maps the DTO to typed camelCase fields", () => {
        const user = User.fromJson(userDto({ id: 7, role: "admin", permissions: ["*"] }));
        expect(user.id).toBe("7");
        expect(user.firstName).toBe("Ada");
        expect(user.emailConfirmed).toBe(true);
        expect(user.createdOn).toBeInstanceOf(Date);
        expect(user.permissions).toEqual(["*"]);
    });

    it("fills defaults for missing optional fields", () => {
        const user = User.fromJson({ id: "u1", email: "x@example.com" });
        expect(user.firstName).toBe("");
        expect(user.avatarUrl).toBeNull();
        expect(user.role).toBeNull();
        expect(user.permissions).toEqual([]);
        expect(user.createdOn).toBeNull();
    });

    it("serialises writable fields back to snake_case", () => {
        const user = User.fromJson(userDto());
        user.firstName = "Augusta";
        expect(user.toJson()).toEqual({ first_name: "Augusta", last_name: "Lovelace" });
    });

    it("derives display helpers", () => {
        expect(User.fromJson(userDto()).fullName).toBe("Ada Lovelace");
        expect(User.fromJson(userDto()).initials).toBe("AL");
        const nameless = User.fromJson(userDto({ first_name: null, last_name: null }));
        expect(nameless.fullName).toBe("ada@example.com");
    });

    it("compares roles on the single-tenant ladder", () => {
        const admin = User.fromJson(userDto({ role: "admin" }));
        expect(admin.hasRoleAtLeast("member")).toBe(true);
        expect(admin.hasRoleAtLeast("owner")).toBe(false);
        expect(User.fromJson(userDto()).hasRoleAtLeast("guest")).toBe(false);
    });

    it("treats same class + id as equal", () => {
        const a = User.fromJson(userDto());
        const b = User.fromJson(userDto({ first_name: "Other" }));
        expect(a.equals(b)).toBe(true);
        expect(a.equals(null)).toBe(false);
    });
});
```

### `src/models/__tests__/Organization.spec.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { describe, expect, it } from "vitest";

import { Organization } from "@/models/Organization";
import { organizationDto } from "@/test/factories";

describe("Organization", () => {
    it("maps the DTO including the caller's role", () => {
        const org = Organization.fromJson(organizationDto());
        expect(org.id).toBe("10");
        expect(org.roleName).toBe("Member");
        expect(org.permissions).toEqual(["order:read"]);
        expect(org.toJson()).toEqual({ name: "Acme" });
    });

    it("checks permissions through the shared RBAC rules", () => {
        const member = Organization.fromJson(organizationDto());
        expect(member.can("order:read")).toBe(true);
        expect(member.can("order:delete")).toBe(false);

        const owner = Organization.fromJson(
            organizationDto({ is_owner: true, role: null, permissions: [] })
        );
        expect(owner.can("order:delete")).toBe(true);
        expect(owner.roleLabel).toBe("Owner");
    });

    it("falls back when no role is present", () => {
        const org = Organization.fromJson({ id: "abc", name: "Solo" });
        expect(org.permissions).toEqual([]);
        expect(org.roleLabel).toBe("Member");
    });
});
```

### `src/stores/app.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { DARK_MODE_CLASS } from "@/theme";
import { appStorage, StorageKeys } from "@/utils/storage";

export type ThemeMode = "light" | "dark";

function preferredTheme(): ThemeMode {
    const stored = appStorage.get(StorageKeys.theme);
    if (stored === "light" || stored === "dark") return stored;
    const prefersDark =
        typeof window !== "undefined" &&
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;
    return prefersDark ? "dark" : "light";
}

/** App-wide UI state: theme (light/dark are both first-class). */
export const useAppStore = defineStore("app", () => {
    const theme = ref<ThemeMode>(preferredTheme());
    const isDark = computed(() => theme.value === "dark");

    function applyTheme(): void {
        document.documentElement.classList.toggle(DARK_MODE_CLASS, isDark.value);
    }

    function setTheme(mode: ThemeMode): void {
        theme.value = mode;
        appStorage.set(StorageKeys.theme, mode);
        applyTheme();
    }

    function toggleTheme(): void {
        setTheme(isDark.value ? "light" : "dark");
    }

    return { theme, isDark, applyTheme, setTheme, toggleTheme };
});
```

### `src/stores/auth.ts`

Setup store: token, user, organisations, `currentOrgId`, and the RBAC getters (`permissions`, `isOwner`, `hasPermission`). In single-tenant mode organisations are never loaded and permissions come from the user.

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { authResource, organizationResource } from "@/api/resources";
import { appConfig } from "@/config/app";
import type { Organization } from "@/models/Organization";
import type { User } from "@/models/User";
import { hasPermissions, type PermissionQuery } from "@/utils/permissions";
import { appStorage, StorageKeys } from "@/utils/storage";

/**
 * Session + tenancy + RBAC. Opaque token auth: there is no refresh flow, so any 401 ends the
 * session (`clearSession`) and the user logs in again.
 */
export const useAuthStore = defineStore("auth", () => {
    const token = ref<string | null>(appStorage.get(StorageKeys.token));
    const user = ref<User | null>(null);
    const organizations = ref<Organization[]>([]);
    const organizationsLoaded = ref(false);
    const currentOrgId = ref<string | null>(
        appConfig.isMultiTenant ? appStorage.get(StorageKeys.organizationId) : null
    );

    // ---- getters ---------------------------------------------------------------------
    const isAuthenticated = computed(() => token.value !== null && user.value !== null);

    const currentOrganization = computed<Organization | null>(
        () => organizations.value.find((org) => org.id === currentOrgId.value) ?? null
    );

    /** Permission codes in the active scope (current org, or the user in single-tenant). */
    const permissions = computed<string[]>(() =>
        appConfig.isMultiTenant
            ? (currentOrganization.value?.permissions ?? [])
            : (user.value?.permissions ?? [])
    );

    const isOwner = computed<boolean>(() =>
        appConfig.isMultiTenant
            ? (currentOrganization.value?.isOwner ?? false)
            : user.value?.role === "owner"
    );

    /** The RBAC core: drives route meta, nav items and buttons. */
    function hasPermission(query: PermissionQuery | null | undefined): boolean {
        return hasPermissions(permissions.value, query, { isOwner: isOwner.value });
    }

    // ---- actions ---------------------------------------------------------------------
    function setToken(value: string | null): void {
        token.value = value;
        appStorage.set(StorageKeys.token, value);
    }

    function setCurrentOrgId(id: string | null): void {
        currentOrgId.value = id;
        appStorage.set(StorageKeys.organizationId, id);
    }

    async function login(email: string, password: string): Promise<User> {
        const result = await authResource.login(email, password);
        setToken(result.token);
        user.value = result.user;
        if (appConfig.isMultiTenant) await loadOrganizations();
        return result.user;
    }

    async function loadOrganizations(): Promise<Organization[]> {
        organizations.value = await organizationResource.mine();
        organizationsLoaded.value = true;
        const stillMember = organizations.value.some(
            (org) => org.id === currentOrgId.value
        );
        if (!stillMember) {
            const only =
                organizations.value.length === 1 ? organizations.value[0] : undefined;
            setCurrentOrgId(only?.id ?? null);
        }
        return organizations.value;
    }

    /** Switches tenant. Returns false when the user is not a member (never trust the URL). */
    function selectOrganization(id: string): boolean {
        if (!organizations.value.some((org) => org.id === id)) return false;
        setCurrentOrgId(id);
        return true;
    }

    /** Restores the session from the stored token. Returns whether the user is logged in. */
    async function ensureSession(): Promise<boolean> {
        if (!token.value) return false;
        try {
            if (!user.value) user.value = await authResource.me();
            if (appConfig.isMultiTenant && !organizationsLoaded.value) {
                await loadOrganizations();
            }
            return true;
        } catch {
            clearSession();
            return false;
        }
    }

    function clearSession(): void {
        setToken(null);
        setCurrentOrgId(null);
        user.value = null;
        organizations.value = [];
        organizationsLoaded.value = false;
    }

    async function logout(): Promise<void> {
        try {
            if (token.value) await authResource.logout();
        } catch {
            // the token is dropped locally either way
        } finally {
            clearSession();
        }
    }

    return {
        token,
        user,
        organizations,
        organizationsLoaded,
        currentOrgId,
        isAuthenticated,
        currentOrganization,
        permissions,
        isOwner,
        hasPermission,
        login,
        loadOrganizations,
        selectOrganization,
        ensureSession,
        clearSession,
        logout,
    };
});
```

### `src/stores/__tests__/auth.spec.ts`

Stores are tested with a real Pinia and the resource singletons replaced via `vi.mock`.

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { authResource, organizationResource } from "@/api/resources";
import { Organization } from "@/models/Organization";
import { User } from "@/models/User";
import { useAuthStore } from "@/stores/auth";
import { organizationDto, userDto } from "@/test/factories";

// Replace the resource singletons; the store only talks to resources, never to axios.
vi.mock("@/api/resources", () => ({
    authResource: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
    organizationResource: { mine: vi.fn() },
}));

const acme = Organization.fromJson(organizationDto());
const beta = Organization.fromJson(
    organizationDto({
        id: 11,
        name: "Beta",
        role: "Admin",
        permissions: ["*"],
    })
);

beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(authResource.me).mockResolvedValue(User.fromJson(userDto()));
    vi.mocked(organizationResource.mine).mockResolvedValue([acme, beta]);
});

describe("auth store (multi-tenant)", () => {
    it("logs in, persists the token and loads organisations", async () => {
        vi.mocked(authResource.login).mockResolvedValue({
            token: "t0k",
            user: User.fromJson(userDto()),
        });
        const auth = useAuthStore();
        await auth.login("ada@example.com", "pw");

        expect(auth.isAuthenticated).toBe(true);
        expect(window.localStorage.getItem("app:token")).toBe("t0k");
        expect(auth.organizations).toHaveLength(2);
        expect(auth.currentOrgId).toBeNull(); // several orgs → user must choose
    });

    it("auto-selects the only organisation", async () => {
        vi.mocked(organizationResource.mine).mockResolvedValue([acme]);
        const auth = useAuthStore();
        await auth.loadOrganizations();
        expect(auth.currentOrgId).toBe(acme.id);
        expect(window.localStorage.getItem("app:organizationId")).toBe(acme.id);
    });

    it("only selects organisations the user belongs to", async () => {
        const auth = useAuthStore();
        await auth.loadOrganizations();
        expect(auth.selectOrganization("999")).toBe(false);
        expect(auth.selectOrganization(beta.id)).toBe(true);
        expect(auth.currentOrganization?.name).toBe("Beta");
    });

    it("scopes permissions to the current organisation", async () => {
        const auth = useAuthStore();
        await auth.loadOrganizations();

        auth.selectOrganization(acme.id);
        expect(auth.hasPermission("order:read")).toBe(true);
        expect(auth.hasPermission("order:delete")).toBe(false);
        expect(
            auth.hasPermission({ keys: ["order:delete", "order:read"], operator: "OR" })
        ).toBe(true);

        auth.selectOrganization(beta.id); // wildcard role
        expect(auth.hasPermission(["order:delete", "billing:manage"])).toBe(true);
    });

    it("restores a session from the stored token", async () => {
        window.localStorage.setItem("app:token", "t0k");
        const auth = useAuthStore();
        expect(await auth.ensureSession()).toBe(true);
        expect(auth.user?.email).toBe("ada@example.com");
        expect(auth.organizationsLoaded).toBe(true);
        expect(await auth.ensureSession()).toBe(true);
        expect(authResource.me).toHaveBeenCalledOnce();
    });

    it("has no session without a token, and clears it when me() fails", async () => {
        expect(await useAuthStore().ensureSession()).toBe(false);

        window.localStorage.setItem("app:token", "stale");
        setActivePinia(createPinia());
        vi.mocked(authResource.me).mockRejectedValue(new Error("401"));
        const auth = useAuthStore();
        expect(await auth.ensureSession()).toBe(false);
        expect(auth.token).toBeNull();
        expect(window.localStorage.getItem("app:token")).toBeNull();
    });

    it("logs out even when the API call fails", async () => {
        window.localStorage.setItem("app:token", "t0k");
        vi.mocked(authResource.logout).mockRejectedValue(new Error("offline"));
        const auth = useAuthStore();
        await auth.ensureSession();
        await auth.logout();
        expect(auth.isAuthenticated).toBe(false);
        expect(auth.organizations).toEqual([]);
    });
});
```

### `src/stores/__tests__/auth.single-tenant.spec.ts`

The tenancy toggle is exercised by mocking `@/config/app`.

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { authResource, organizationResource } from "@/api/resources";
import type * as AppConfigModule from "@/config/app";
import { User } from "@/models/User";
import { useAuthStore } from "@/stores/auth";
import { userDto } from "@/test/factories";

// Build-time tenancy toggle: mock the config module to exercise single-tenant mode.
vi.mock("@/config/app", async () => {
    const actual = await vi.importActual<typeof AppConfigModule>("@/config/app");
    return {
        ...actual,
        appConfig: new actual.AppConfig({ VITE_TENANCY_MODE: "single" }),
    };
});

vi.mock("@/api/resources", () => ({
    authResource: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
    organizationResource: { mine: vi.fn() },
}));

beforeEach(() => {
    setActivePinia(createPinia());
    window.localStorage.setItem("app:token", "t0k");
});

describe("auth store (single-tenant)", () => {
    it("never loads organisations and reads permissions from the user", async () => {
        vi.mocked(authResource.me).mockResolvedValue(
            User.fromJson(userDto({ role: "member", permissions: ["order:read"] }))
        );
        const auth = useAuthStore();
        expect(await auth.ensureSession()).toBe(true);
        expect(organizationResource.mine).not.toHaveBeenCalled();
        expect(auth.hasPermission("order:read")).toBe(true);
        expect(auth.hasPermission("order:delete")).toBe(false);
    });

    it("treats the owner role as all-permissions", async () => {
        vi.mocked(authResource.me).mockResolvedValue(
            User.fromJson(userDto({ role: "owner" }))
        );
        const auth = useAuthStore();
        await auth.ensureSession();
        expect(auth.isOwner).toBe(true);
        expect(auth.hasPermission("billing:manage")).toBe(true);
    });
});
```

### `src/stores/__tests__/app.spec.ts`

```ts
/**
 * <Project Name>
 * Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
 * Author: <Legal Entity Name>
 *
 * Built on Instadash AI Base by Letstream
 * (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
 * Template portions (c) Letstream Ventures Pvt Ltd.
 *
 * The Instadash AI Base template is provided "AS IS", without warranty of any
 * kind, express or implied, including merchantability, fitness for a particular
 * purpose and non-infringement, unless covered by an explicit written agreement
 * with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
 * redistribution of the template, in whole or in part, is prohibited and may
 * result in legal action and remedies available under applicable law.
 */

import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useAppStore } from "@/stores/app";

beforeEach(() => {
    setActivePinia(createPinia());
    document.documentElement.classList.remove("app-dark");
});

describe("app store — theme", () => {
    it("toggles the dark class and persists the choice", () => {
        const app = useAppStore();
        expect(app.theme).toBe("light");
        app.toggleTheme();
        expect(app.isDark).toBe(true);
        expect(document.documentElement.classList.contains("app-dark")).toBe(true);
        expect(window.localStorage.getItem("app:theme")).toBe("dark");
        app.setTheme("light");
        expect(document.documentElement.classList.contains("app-dark")).toBe(false);
    });

    it("restores the stored theme", () => {
        window.localStorage.setItem("app:theme", "dark");
        expect(useAppStore().theme).toBe("dark");
    });
});
```
