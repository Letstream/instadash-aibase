# Frontend scaffold — shared components

> Part of the [frontend scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the frontend repo root.

Trimmed but working versions of the generic shells described in
[shared-components](../../../architecture-guidelines/frontend/shared-components.md) and
[building-shared-components](../../../architecture-guidelines/frontend/building-shared-components.md).
Extend them there-first: new config fields optional with safe defaults, new column types in
`FormatCell.vue` only.

- `GenericList` — fetches through **either** `config.resource` (a `ListableResource`, rows are
  model instances) **or** `config.endpoint` (an endpoint-registry key); search / offset / limit
  live in the URL; `#content` slot replaces the body; `cell:<fieldKey>` slots customise a cell.
  `type: "function"` columns return **plain text** — there is no `v-html` path.
- `GenericDrawer` — `<component :is>` host; footer actions call the inner component's exposed
  `onSave()` via `getInnerComponent()`.
- `GenericDialog` — the only component that imports PrimeVue `Dialog`; `ConfirmationDialog` is a
  thin prop-in / `hideDialog(confirmed)`-out wrapper over it.
- `GenericEmptyState` — icon + title + description + optional CTA (`@action`).

### `src/components/GenericList/types/GenericList.types.ts`

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

import type { RouteLocationRaw } from "vue-router";

import type { EndpointKey } from "@/api/endpoints";
import type { ListableResource } from "@/api/resources/BaseResource";
import type { QueryParams } from "@/api/types";
import type { PermissionQuery } from "@/utils/permissions";

export type ColumnType =
    "text" | "number" | "date" | "datetime" | "select" | "boolean" | "function";

export interface SelectOption {
    label: string;
    value: string | number | boolean;
}

export interface Column<TRow> {
    header: string;
    /** Dot-path into the row (`"owner.name"`); also names the `cell:<fieldKey>` slot. */
    fieldKey: string;
    type: ColumnType;
    prefix?: string;
    suffix?: string;
    /** Shown when the value is empty. */
    default?: string;
    /** `type: "select"` maps value → label. */
    options?: SelectOption[];
    /** `type: "function"` returns PLAIN TEXT. Custom markup goes in the `cell:<fieldKey>` slot. */
    handler?: (row: TRow) => string;
}

export interface RowAction<TRow> {
    icon: string;
    /** Tooltip + aria-label. */
    label: string;
    severity?: "secondary" | "success" | "info" | "warn" | "danger" | "contrast";
    permission?: PermissionQuery;
    to?: (row: TRow) => RouteLocationRaw;
    onClick?: (row: TRow) => void;
    isVisible?: (row: TRow) => boolean;
}

export interface ToolbarAction {
    label: string;
    icon?: string;
    permission?: PermissionQuery;
    to?: RouteLocationRaw;
    onClick?: () => void;
}

export interface Toolbar {
    title?: string;
    hideSearch?: boolean;
    searchPlaceholder?: string;
    hideRefresh?: boolean;
    actions?: ToolbarAction[];
}

interface TableConfigBase<TRow> {
    columns?: Column<TRow>[];
    actions?: RowAction<TRow>[];
    toolbar?: Toolbar;
    /** Always-on params merged into every request. */
    embeddedFilters?: QueryParams;
    limit?: number;
    disablePagination?: boolean;
    emptyMessage?: string;
    /** Row key for DataTable (default "id"). */
    dataKey?: string;
}

/** The list fetches through EITHER a resource (rows are model instances) OR an endpoint key. */
export type TableConfig<TRow> = TableConfigBase<TRow> &
    (
        | { resource: ListableResource<TRow>; endpoint?: never }
        | { endpoint: EndpointKey; resource?: never }
    );
```

### `src/components/GenericList/helpers/query.ts`

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

import type { LocationQuery, LocationQueryRaw } from "vue-router";

import type { QueryParams } from "@/api/types";

export const DEFAULT_LIMIT = 20;
export const LIST_QUERY_KEYS = ["search", "offset", "limit"] as const;

/** List state that lives in the URL (deep-linkable, back/forward works). */
export interface ListState {
    search: string;
    offset: number;
    limit: number;
}

function firstString(value: LocationQuery[string] | undefined): string {
    const first = Array.isArray(value) ? value[0] : value;
    return typeof first === "string" ? first : "";
}

function nonNegativeInt(value: string, fallback: number): number {
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) || parsed < 0 ? fallback : parsed;
}

export function readListState(
    query: LocationQuery,
    defaultLimit = DEFAULT_LIMIT
): ListState {
    const limit = nonNegativeInt(firstString(query.limit), defaultLimit) || defaultLimit;
    return {
        search: firstString(query.search).trim(),
        offset: nonNegativeInt(firstString(query.offset), 0),
        limit,
    };
}

/** Writes the state into the current query, omitting defaults and keeping foreign keys. */
export function mergeListState(
    query: LocationQuery,
    state: ListState,
    defaultLimit = DEFAULT_LIMIT
): LocationQueryRaw {
    const next: LocationQueryRaw = { ...query };
    for (const key of LIST_QUERY_KEYS) delete next[key];
    if (state.search) next.search = state.search;
    if (state.offset > 0) next.offset = String(state.offset);
    if (state.limit !== defaultLimit) next.limit = String(state.limit);
    return next;
}

export function toRequestParams(
    state: ListState,
    embedded: QueryParams = {}
): QueryParams {
    return {
        ...embedded,
        limit: state.limit,
        offset: state.offset,
        ...(state.search ? { search: state.search } : {}),
    };
}
```

### `src/components/GenericList/composables/useGenericList.ts`

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

import { computed, onBeforeUnmount, ref, shallowRef, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { endpoint } from "@/api/endpoints";
import { ApiError } from "@/api/errors";
import { api } from "@/api/http";
import { normalizeList, type ListDto, type Page, type QueryParams } from "@/api/types";
import { debounce } from "@/utils/debounce";

import {
    DEFAULT_LIMIT,
    mergeListState,
    readListState,
    toRequestParams,
} from "../helpers/query";
import type { TableConfig } from "../types/GenericList.types";

function createFetcher<TRow>(
    config: TableConfig<TRow>
): (params: QueryParams) => Promise<Page<TRow>> {
    if (config.resource) {
        const resource = config.resource;
        return (params) => resource.list(params);
    }
    const path = endpoint(config.endpoint);
    return async (params) => normalizeList(await api.get<ListDto<TRow>>(path, params));
}

/** Fetch + URL-synced search/pagination for GenericList (and custom list bodies). */
export function useGenericList<TRow>(config: TableConfig<TRow>) {
    const route = useRoute();
    const router = useRouter();
    const defaultLimit = config.limit ?? DEFAULT_LIMIT;
    const fetchPage = createFetcher(config);

    const rows = shallowRef<TRow[]>([]) as Ref<TRow[]>;
    const total = ref(0);
    const loading = ref(false);
    const error = shallowRef<ApiError | null>(null);

    const state = computed(() => readListState(route.query, defaultLimit));
    const search = ref(state.value.search);
    const hasActiveFilters = computed(() => state.value.search !== "");

    let requestId = 0;
    async function load(): Promise<void> {
        const current = ++requestId;
        loading.value = true;
        error.value = null;
        try {
            const params = config.disablePagination
                ? {
                      ...config.embeddedFilters,
                      ...(state.value.search ? { search: state.value.search } : {}),
                  }
                : toRequestParams(state.value, config.embeddedFilters);
            const page = await fetchPage(params);
            if (current !== requestId) return; // a newer request superseded this one
            rows.value = page.items;
            total.value = page.count;
        } catch (err) {
            if (current === requestId) error.value = ApiError.from(err);
        } finally {
            if (current === requestId) loading.value = false;
        }
    }

    function pushState(patch: Partial<typeof state.value>, replace = false): void {
        const query = mergeListState(
            route.query,
            { ...state.value, ...patch },
            defaultLimit
        );
        void (replace ? router.replace({ query }) : router.push({ query }));
    }

    const applySearch = debounce(
        (value: string) => pushState({ search: value.trim(), offset: 0 }, true),
        350
    );
    watch(search, (value) => applySearch(value));
    onBeforeUnmount(() => applySearch.cancel());

    watch(
        () => JSON.stringify(state.value),
        () => void load(),
        { immediate: true }
    );

    /** PrimeVue Paginator `@page` handler. */
    function onPage(event: { first: number; rows: number }): void {
        pushState({ offset: event.first, limit: event.rows });
    }

    return {
        rows,
        total,
        loading,
        error,
        search,
        state,
        hasActiveFilters,
        load,
        onPage,
    };
}
```

### `src/components/GenericList/components/FormatCell.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts" generic="TRow">
import { computed } from "vue";

import { formatDate, formatNumber, getByPath } from "@/utils/format";

import type { Column } from "../types/GenericList.types";

/** The type-switch cell renderer — the ONLY place that knows about column types. */
const props = defineProps<{ column: Column<TRow>; row: TRow }>();

const text = computed<string | null>(() => {
    const { column, row } = props;
    const value = getByPath(row, column.fieldKey);
    switch (column.type) {
        case "number":
            return formatNumber(value);
        case "date":
            return formatDate(value);
        case "datetime":
            return formatDate(value, true);
        case "select":
            return (
                column.options?.find((option) => option.value === value)?.label ?? null
            );
        case "function":
            return column.handler ? column.handler(row) : null;
        case "boolean":
            return null;
        default:
            return value === null || value === undefined || value === ""
                ? null
                : String(value);
    }
});

const booleanValue = computed(() => Boolean(getByPath(props.row, props.column.fieldKey)));
</script>

<template>
    <i
        v-if="column.type === 'boolean'"
        :class="booleanValue ? 'pi pi-check' : 'pi pi-minus'"
        :aria-label="String(booleanValue)"
    />
    <span v-else-if="text !== null"
        >{{ column.prefix }}{{ text }}{{ column.suffix }}</span
    >
    <span
        v-else
        class="format-cell__empty"
        >{{ column.default ?? "—" }}</span
    >
</template>

<style scoped lang="scss">
.format-cell__empty {
    color: var(--app-text-muted);
}
</style>
```

### `src/components/GenericList/GenericList.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts" generic="TRow extends object">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { RouterLink } from "vue-router";

import GenericEmptyState from "@/components/GenericEmptyState/GenericEmptyState.vue";
import { useAuthStore } from "@/stores/auth";
import { getByPath } from "@/utils/format";

import FormatCell from "./components/FormatCell.vue";
import { useGenericList } from "./composables/useGenericList";
import type { RowAction, TableConfig } from "./types/GenericList.types";

const props = defineProps<{ config: TableConfig<TRow> }>();

const { t } = useI18n();
const auth = useAuthStore();
const { rows, total, loading, error, search, state, hasActiveFilters, load, onPage } =
    useGenericList<TRow>(props.config);

const toolbarActions = computed(() =>
    (props.config.toolbar?.actions ?? []).filter((action) =>
        auth.hasPermission(action.permission)
    )
);
const rowActions = computed(() =>
    (props.config.actions ?? []).filter((action) => auth.hasPermission(action.permission))
);
const showPaginator = computed(
    () => !props.config.disablePagination && total.value > state.value.limit
);

function visibleActions(row: TRow): RowAction<TRow>[] {
    return rowActions.value.filter((action) => action.isVisible?.(row) ?? true);
}

defineExpose({ reload: load });
</script>

<template>
    <section class="generic-list">
        <header class="generic-list__toolbar">
            <h2
                v-if="config.toolbar?.title"
                class="generic-list__title"
            >
                {{ config.toolbar.title }}
            </h2>
            <div class="generic-list__tools">
                <IconField v-if="!config.toolbar?.hideSearch">
                    <InputIcon class="pi pi-search" />
                    <InputText
                        v-model="search"
                        :placeholder="
                            config.toolbar?.searchPlaceholder ?? t('list.search')
                        "
                        :aria-label="t('list.search')"
                    />
                </IconField>
                <Button
                    v-if="!config.toolbar?.hideRefresh"
                    v-tooltip.bottom="t('list.refresh')"
                    icon="pi pi-refresh"
                    severity="secondary"
                    variant="text"
                    :aria-label="t('list.refresh')"
                    :loading="loading"
                    @click="load"
                />
                <template
                    v-for="action in toolbarActions"
                    :key="action.label"
                >
                    <RouterLink
                        v-if="action.to"
                        v-slot="{ navigate }"
                        :to="action.to"
                        custom
                    >
                        <Button
                            :label="action.label"
                            :icon="action.icon"
                            @click="navigate"
                        />
                    </RouterLink>
                    <Button
                        v-else
                        :label="action.label"
                        :icon="action.icon"
                        @click="action.onClick?.()"
                    />
                </template>
            </div>
        </header>

        <Message
            v-if="error"
            severity="error"
            :closable="false"
        >
            {{ error.message }}
        </Message>

        <!-- Escape hatch: replace the body, keep fetch/search/pagination. -->
        <slot
            name="content"
            :rows="rows"
            :loading="loading"
            :reload="load"
            :has-active-filters="hasActiveFilters"
        >
            <DataTable
                :value="rows"
                :loading="loading"
                :data-key="config.dataKey ?? 'id'"
            >
                <Column
                    v-for="column in config.columns ?? []"
                    :key="column.fieldKey"
                    :header="column.header"
                >
                    <template #body="{ data }">
                        <slot
                            :name="`cell:${column.fieldKey}`"
                            :row="data as TRow"
                            :value="getByPath(data, column.fieldKey)"
                        >
                            <FormatCell
                                :column="column"
                                :row="data as TRow"
                            />
                        </slot>
                    </template>
                </Column>
                <Column v-if="rowActions.length">
                    <template #body="{ data }">
                        <div class="generic-list__row-actions">
                            <template
                                v-for="action in visibleActions(data as TRow)"
                                :key="action.label"
                            >
                                <RouterLink
                                    v-if="action.to"
                                    v-slot="{ navigate }"
                                    :to="action.to(data as TRow)"
                                    custom
                                >
                                    <Button
                                        v-tooltip.top="action.label"
                                        :icon="action.icon"
                                        :severity="action.severity ?? 'secondary'"
                                        :aria-label="action.label"
                                        variant="text"
                                        rounded
                                        @click="navigate"
                                    />
                                </RouterLink>
                                <Button
                                    v-else
                                    v-tooltip.top="action.label"
                                    :icon="action.icon"
                                    :severity="action.severity ?? 'secondary'"
                                    :aria-label="action.label"
                                    variant="text"
                                    rounded
                                    @click="action.onClick?.(data as TRow)"
                                />
                            </template>
                        </div>
                    </template>
                </Column>
                <template #empty>
                    <GenericEmptyState
                        :description="config.emptyMessage ?? t('list.empty')"
                    />
                </template>
            </DataTable>
        </slot>

        <Paginator
            v-if="showPaginator"
            :rows="state.limit"
            :first="state.offset"
            :total-records="total"
            @page="onPage"
        />
    </section>
</template>

<style scoped lang="scss">
.generic-list {
    @apply flex flex-col gap-4;

    &__toolbar {
        @apply flex flex-wrap items-center justify-between gap-3;
    }

    &__title {
        @apply m-0 text-xl font-semibold;
    }

    &__tools {
        @apply flex items-center gap-2;
    }

    &__row-actions {
        @apply flex justify-end gap-1;
    }
}
</style>
```

### `src/components/GenericList/__tests__/query.spec.ts`

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

import { mergeListState, readListState, toRequestParams } from "../helpers/query";

describe("GenericList query helpers", () => {
    it("reads typed state from the URL with safe fallbacks", () => {
        expect(readListState({})).toEqual({ search: "", offset: 0, limit: 20 });
        expect(readListState({ search: " acme ", offset: "40", limit: "50" })).toEqual({
            search: "acme",
            offset: 40,
            limit: 50,
        });
        expect(readListState({ offset: "-3", limit: "abc" }, 10)).toEqual({
            search: "",
            offset: 0,
            limit: 10,
        });
        expect(readListState({ search: ["a", "b"] }).search).toBe("a");
    });

    it("writes state back, omitting defaults and keeping foreign keys", () => {
        const query = mergeListState(
            { tab: "open", offset: "20" },
            { search: "x", offset: 0, limit: 20 }
        );
        expect(query).toEqual({ tab: "open", search: "x" });
        expect(mergeListState({}, { search: "", offset: 40, limit: 50 })).toEqual({
            offset: "40",
            limit: "50",
        });
    });

    it("builds request params with embedded filters", () => {
        expect(
            toRequestParams({ search: "", offset: 0, limit: 20 }, { status: "open" })
        ).toEqual({
            status: "open",
            limit: 20,
            offset: 0,
        });
        expect(toRequestParams({ search: "q", offset: 20, limit: 20 }).search).toBe("q");
    });
});
```

### `src/components/GenericList/__tests__/useGenericList.spec.ts`

Testing a router-dependent composable: mount a tiny host component with a memory-history router.

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

import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { api } from "@/api/http";
import type { ListableResource } from "@/api/resources/BaseResource";

import { useGenericList } from "../composables/useGenericList";
import type { TableConfig } from "../types/GenericList.types";

interface Row {
    id: number;
}

let router: Router;

function mountList(config: TableConfig<Row>) {
    let exposed!: ReturnType<typeof useGenericList<Row>>;
    const Host = defineComponent({
        setup() {
            exposed = useGenericList<Row>(config);
            return () => h("div");
        },
    });
    mount(Host, { global: { plugins: [router] } });
    return () => exposed;
}

beforeEach(async () => {
    router = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: "/list", name: "list", component: { render: () => null } }],
    });
    await router.push("/list?search=acme&offset=20");
    await router.isReady();
});

afterEach(() => {
    vi.useRealTimers();
});

describe("useGenericList", () => {
    it("fetches through a resource using the URL state", async () => {
        const resource: ListableResource<Row> = {
            list: vi.fn().mockResolvedValue({
                items: [{ id: 1 }],
                count: 21,
                next: null,
                previous: null,
            }),
        };
        const list = mountList({ resource, embeddedFilters: { status: "open" } });
        await flushPromises();

        expect(resource.list).toHaveBeenCalledWith({
            status: "open",
            search: "acme",
            offset: 20,
            limit: 20,
        });
        expect(list().rows.value).toEqual([{ id: 1 }]);
        expect(list().total.value).toBe(21);
        expect(list().hasActiveFilters.value).toBe(true);
    });

    it("fetches through an endpoint key and normalises the list shape", async () => {
        const get = vi.spyOn(api, "get").mockResolvedValue([{ id: 7 }]);
        const list = mountList({ endpoint: "myOrganizations", disablePagination: true });
        await flushPromises();

        expect(get).toHaveBeenCalledWith("organization/my-orgs/", { search: "acme" });
        expect(list().rows.value).toEqual([{ id: 7 }]);
    });

    it("pushes paging and debounced search into the URL, refetching", async () => {
        vi.useFakeTimers();
        const resource: ListableResource<Row> = {
            list: vi
                .fn()
                .mockResolvedValue({ items: [], count: 0, next: null, previous: null }),
        };
        const list = mountList({ resource });
        await flushPromises();

        list().onPage({ first: 40, rows: 20 });
        await flushPromises();
        expect(router.currentRoute.value.query.offset).toBe("40");

        list().search.value = "beta";
        await flushPromises();
        vi.advanceTimersByTime(400);
        await flushPromises();
        expect(router.currentRoute.value.query).toEqual({ search: "beta" });
        expect(resource.list).toHaveBeenLastCalledWith({
            search: "beta",
            offset: 0,
            limit: 20,
        });
    });

    it("exposes API failures as ApiError", async () => {
        const resource: ListableResource<Row> = {
            list: vi.fn().mockRejectedValue(new Error("offline")),
        };
        const list = mountList({ resource });
        await flushPromises();
        expect(list().error.value?.message).toBe("offline");
        expect(list().loading.value).toBe(false);
    });
});
```

### `src/components/GenericList/__tests__/FormatCell.spec.ts`

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

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import FormatCell from "../components/FormatCell.vue";
import type { Column } from "../types/GenericList.types";

type Row = Record<string, unknown>;

function render(column: Column<Row>, row: Row) {
    // FormatCell is generic; tests pin its row type to `unknown`.
    return mount(FormatCell, { props: { column: column as Column<unknown>, row } });
}

describe("FormatCell", () => {
    it("renders text with prefix/suffix and dot-paths", () => {
        const wrapper = render(
            {
                header: "Owner",
                fieldKey: "owner.name",
                type: "text",
                prefix: "@",
                suffix: "!",
            },
            { owner: { name: "ada" } }
        );
        expect(wrapper.text()).toBe("@ada!");
    });

    it("falls back to the default for empty values", () => {
        expect(
            render(
                { header: "N", fieldKey: "n", type: "text", default: "n/a" },
                {}
            ).text()
        ).toBe("n/a");
        expect(
            render({ header: "N", fieldKey: "n", type: "number" }, { n: null }).text()
        ).toBe("—");
    });

    it("maps select values to labels", () => {
        const column: Column<Row> = {
            header: "Status",
            fieldKey: "status",
            type: "select",
            options: [{ label: "Open", value: "open" }],
        };
        expect(render(column, { status: "open" }).text()).toBe("Open");
    });

    it("renders booleans as icons and function columns as plain text", () => {
        const bool = render(
            { header: "A", fieldKey: "active", type: "boolean" },
            { active: true }
        );
        expect(bool.find("i").classes()).toContain("pi-check");

        const fn = render(
            {
                header: "F",
                fieldKey: "x",
                type: "function",
                handler: () => "<b>safe</b>",
            },
            {}
        );
        expect(fn.text()).toBe("<b>safe</b>");
        expect(fn.find("b").exists()).toBe(false);
    });

    it("formats numbers and dates", () => {
        expect(
            render({ header: "N", fieldKey: "n", type: "number" }, { n: 1000 }).text()
        ).toMatch(/1.000/);
        expect(
            render(
                { header: "D", fieldKey: "d", type: "date" },
                { d: "2024-01-02T00:00:00Z" }
            ).text()
        ).toContain("2024");
    });
});
```

### `src/components/GenericDrawer/types/GenericDrawer.types.ts`

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

import type { Component } from "vue";

export interface DrawerAction {
    label: string;
    handler: () => void | Promise<void>;
    variant?: "outlined" | "text";
    severity?: "secondary" | "success" | "info" | "warn" | "danger" | "contrast";
    icon?: string;
    disabled?: boolean;
    loading?: boolean;
}

export interface DrawerConfig {
    header?: string;
    icon?: string;
    /** Inner form/detail component; it owns no footer buttons. */
    component: Component;
    /** Bound to the inner component with v-bind. */
    props?: Record<string, unknown>;
    /** Footer buttons; handlers reach the inner component via `getInnerComponent()`. */
    actions?: DrawerAction[];
}

/** What an inner component may expose for the drawer's footer actions to call. */
export interface DrawerInnerExposed {
    onSave?: () => void | Promise<void>;
}

/** Sentinel an inner component emits to restore the configured header/actions. */
export const ORIGINAL = "original" as const;
```

### `src/components/GenericDrawer/GenericDrawer.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { ref, watch } from "vue";

import {
    ORIGINAL,
    type DrawerAction,
    type DrawerConfig,
    type DrawerInnerExposed,
} from "./types/GenericDrawer.types";

const props = defineProps<{ visible: boolean; config: DrawerConfig }>();
const emit = defineEmits<{
    "update:visible": [value: boolean];
    updated: [payload: unknown];
}>();

const inner = ref<DrawerInnerExposed | null>(null);
const header = ref(props.config.header ?? "");
const actions = ref<DrawerAction[]>(props.config.actions ?? []);

// A new config (e.g. opening for another record) resets header + footer.
watch(
    () => props.config,
    (config) => {
        header.value = config.header ?? "";
        actions.value = config.actions ?? [];
    }
);

function onUpdateHeader(value: string): void {
    header.value = value === ORIGINAL ? (props.config.header ?? "") : value;
}

function onUpdateActions(value: DrawerAction[] | typeof ORIGINAL): void {
    actions.value = value === ORIGINAL ? (props.config.actions ?? []) : value;
}

defineExpose({ getInnerComponent: () => inner.value });
</script>

<template>
    <Drawer
        :visible="visible"
        position="right"
        :style="{ width: 'min(var(--app-drawer-width), 100vw)' }"
        @update:visible="emit('update:visible', $event)"
    >
        <template #header>
            <div class="generic-drawer__header">
                <i
                    v-if="config.icon"
                    :class="config.icon"
                    aria-hidden="true"
                />
                <span class="generic-drawer__title">{{ header }}</span>
            </div>
        </template>

        <component
            :is="config.component"
            ref="inner"
            v-bind="config.props"
            @update-header="onUpdateHeader"
            @update-actions="onUpdateActions"
            @updated="emit('updated', $event)"
            @close="emit('update:visible', false)"
        />

        <template #footer>
            <div
                v-if="actions.length"
                class="generic-drawer__footer"
            >
                <Button
                    v-for="action in actions"
                    :key="action.label"
                    :label="action.label"
                    :variant="action.variant"
                    :severity="action.severity"
                    :icon="action.icon"
                    :disabled="action.disabled"
                    :loading="action.loading"
                    @click="action.handler"
                />
            </div>
        </template>
    </Drawer>
</template>

<style scoped lang="scss">
.generic-drawer {
    &__header {
        @apply flex items-center gap-2;
    }

    &__title {
        @apply font-semibold;
    }

    &__footer {
        @apply flex justify-end gap-2;
    }
}
</style>
```

### `src/components/GenericDialog/types/GenericDialog.types.ts`

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

import type { ButtonProps } from "primevue/button";

/** One footer button of a GenericDialog; the array order is the render order. */
export interface DialogAction {
    label: string;
    handler: () => void | Promise<void>;
    severity?: ButtonProps["severity"];
    variant?: "outlined" | "text";
    icon?: string;
    disabled?: boolean;
    loading?: boolean;
    visible?: boolean;
}
```

### `src/components/GenericDialog/GenericDialog.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import type { DialogAction } from "./types/GenericDialog.types";

/**
 * The ONE dialog primitive (the only place that imports PrimeVue `Dialog`). Confirm, form,
 * info and destructive dialogs are all configured through props, slots and `actions`.
 */
withDefaults(
    defineProps<{
        visible: boolean;
        header?: string;
        icon?: string;
        message?: string;
        actions?: DialogAction[];
        closable?: boolean;
    }>(),
    { header: "", icon: "", message: "", actions: () => [], closable: true }
);

const emit = defineEmits<{ "update:visible": [value: boolean] }>();
</script>

<template>
    <Dialog
        :visible="visible"
        :header="header"
        :closable="closable"
        modal
        :style="{ width: 'min(var(--app-dialog-width), 92vw)' }"
        @update:visible="emit('update:visible', $event)"
    >
        <div class="generic-dialog__body">
            <i
                v-if="icon"
                :class="icon"
                class="generic-dialog__icon"
                aria-hidden="true"
            />
            <slot>
                <p class="generic-dialog__message">{{ message }}</p>
            </slot>
        </div>
        <template #footer>
            <slot
                name="footer"
                :actions="actions"
            >
                <template
                    v-for="action in actions"
                    :key="action.label"
                >
                    <Button
                        v-if="action.visible !== false"
                        :label="action.label"
                        :severity="action.severity"
                        :variant="action.variant"
                        :icon="action.icon"
                        :disabled="action.disabled"
                        :loading="action.loading"
                        @click="action.handler"
                    />
                </template>
            </slot>
        </template>
    </Dialog>
</template>

<style scoped lang="scss">
.generic-dialog {
    &__body {
        @apply flex items-start gap-4;
    }

    &__icon {
        font-size: 1.75rem;
        color: var(--app-text-muted);
    }

    &__message {
        @apply m-0;
        color: var(--app-text);
    }
}
</style>
```

### `src/components/ConfirmationDialog/ConfirmationDialog.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import GenericDialog from "@/components/GenericDialog/GenericDialog.vue";
import type { DialogAction } from "@/components/GenericDialog/types/GenericDialog.types";

/** Prop-in / `hideDialog(confirmed)`-out confirm, built on GenericDialog. */
const props = withDefaults(
    defineProps<{
        visible: boolean;
        header?: string;
        message?: string;
        icon?: string;
        confirmLabel?: string;
        cancelLabel?: string;
        confirmSeverity?: DialogAction["severity"];
        loading?: boolean;
    }>(),
    {
        header: "",
        message: "",
        icon: "pi pi-exclamation-triangle",
        confirmLabel: "",
        cancelLabel: "",
        confirmSeverity: "primary",
        loading: false,
    }
);

const emit = defineEmits<{ hideDialog: [confirmed: boolean] }>();
const { t } = useI18n();

const actions = computed<DialogAction[]>(() => [
    {
        label: props.cancelLabel || t("common.cancel"),
        variant: "outlined",
        severity: "secondary",
        disabled: props.loading,
        handler: () => emit("hideDialog", false),
    },
    {
        label: props.confirmLabel || t("common.confirm"),
        severity: props.confirmSeverity,
        loading: props.loading,
        handler: () => emit("hideDialog", true),
    },
]);
</script>

<template>
    <GenericDialog
        :visible="visible"
        :header="header"
        :icon="icon"
        :message="message"
        :actions="actions"
        @update:visible="!$event && emit('hideDialog', false)"
    />
</template>
```

### `src/components/GenericEmptyState/GenericEmptyState.vue`

```vue
<!--
    <Project Name>
    Copyright (c) <YEAR> <Legal Entity Name>. All rights reserved.
    Author: <Legal Entity Name>

    Built on Instadash AI Base by Letstream
    (Letstream Ventures Pvt Ltd, https://www.theletstream.com, hello@theletstream.com).
    Template portions (c) Letstream Ventures Pvt Ltd.

    The Instadash AI Base template is provided "AS IS", without warranty of any
    kind, express or implied, including merchantability, fitness for a particular
    purpose and non-infringement, unless covered by an explicit written agreement
    with Letstream Ventures Pvt Ltd. Unauthorized use, copying, modification or
    redistribution of the template, in whole or in part, is prohibited and may
    result in legal action and remedies available under applicable law.
-->

<script setup lang="ts">
withDefaults(
    defineProps<{
        icon?: string;
        title?: string;
        description?: string;
        buttonLabel?: string;
        buttonIcon?: string;
    }>(),
    {
        icon: "pi pi-inbox",
        title: "",
        description: "",
        buttonLabel: "",
        buttonIcon: "",
    }
);

const emit = defineEmits<{ action: [] }>();
</script>

<template>
    <div class="empty-state">
        <i
            :class="icon"
            class="empty-state__icon"
            aria-hidden="true"
        />
        <h2
            v-if="title"
            class="empty-state__title"
        >
            {{ title }}
        </h2>
        <p
            v-if="description"
            class="empty-state__description"
        >
            {{ description }}
        </p>
        <Button
            v-if="buttonLabel"
            :label="buttonLabel"
            :icon="buttonIcon || undefined"
            @click="emit('action')"
        />
    </div>
</template>

<style scoped lang="scss">
.empty-state {
    @apply flex flex-col items-center gap-3 py-12 text-center;

    &__icon {
        font-size: 2.5rem;
        color: var(--app-text-muted);
    }

    &__title {
        @apply m-0 text-lg font-semibold;
        color: var(--app-text);
    }

    &__description {
        @apply m-0 max-w-md;
        color: var(--app-text-muted);
    }
}
</style>
```

### `src/components/GenericEmptyState/__tests__/GenericEmptyState.spec.ts`

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

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import GenericEmptyState from "../GenericEmptyState.vue";

describe("GenericEmptyState", () => {
    it("renders copy and emits action from the CTA", async () => {
        const wrapper = mount(GenericEmptyState, {
            props: {
                title: "Nothing",
                description: "Create one.",
                buttonLabel: "Create",
            },
        });
        expect(wrapper.text()).toContain("Nothing");
        expect(wrapper.text()).toContain("Create one.");
        await wrapper.find("button").trigger("click");
        expect(wrapper.emitted("action")).toHaveLength(1);
    });

    it("hides the CTA without a label", () => {
        expect(mount(GenericEmptyState).find("button").exists()).toBe(false);
    });
});
```
