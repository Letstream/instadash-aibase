<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Shared / Generic Components

> The reuse layer. Instead of rebuilding tables, side panels, dialogs and forms per feature, the
> app provides a small set of **config- and slot-driven, domain-agnostic shells**. A feature page
> becomes *declarative*: it hands over a config object and a **data source** (an API resource or an
> endpoint key), and the shell provides the machinery (fetching, URL-synced state, pagination,
> actions). This page covers the approach and each shell's **public API / usage**. For **how to
> build/author** these shells see [building-shared-components](building-shared-components.md).
> Working, tested versions ship in the [frontend scaffold](../../bootstrap/scaffold/frontend/shared-components.md).
> Styling rules: the `frontend-design-guidelines` skill. Data layer: [project-structure §3](project-structure.md#3-data-layer-layered).

---

## 1. The philosophy

**Behavior is data, not code.** Each generic shell exposes a **typed config interface** (its
public API) exported from a sibling `types/` file. A feature supplies the config; the shell reads
it. Four repeatable techniques:

1. **One config object per feature surface** — `TableConfig`, `DrawerConfig`. The config *is* the
   contract.
2. **Type-switch renderers** — a cell/field is rendered by branching on a `type` string
   (`text | number | date | datetime | select | boolean | function`). Extend by adding a case, not
   a new component. `type: "function"` returns **plain text**.
3. **Slot escape hatches** — replace the *body* (`#content`) or a single cell (`cell:<fieldKey>`)
   via scoped slots while keeping all the free machinery (search, pagination, fetch). Custom
   markup always goes through a slot — never `v-html`.
4. **Dynamic host + ref-driven actions** — a shell mounts arbitrary inner content via
   `<component :is>` and drives its actions through an **exposed method** on the inner instance.

**Naming:** `Generic*` = these shells (each in its own folder under `src/components/`); small
presentational widgets live in `src/components/shared/`. Shells are **explicitly imported** by
consumers (only PrimeVue components are auto-registered).

---

## 2. Generic Table / List (`GenericList`)

A single config drives an entire list page: it reads/writes list state (`search`, `offset`,
`limit`) **to the URL query string** (deep-linkable, back/forward works), **fetches its own data**
from its data source, and renders either a default `DataTable` or a custom body via `#content`.

**Data source — either one:**
- `resource: ListableResource<TRow>` — any `BaseResource` (e.g. `orderResource`); rows are **model
  instances**, so columns can read getters (`fieldKey: "displayName"`). Preferred.
- `endpoint: EndpointKey` — a key of the endpoint registry (no path params); rows are raw DTOs,
  normalised from `{results, count}` or a bare array.

**Public API**

| Kind | Name | Notes |
|------|------|-------|
| prop | `config: TableConfig<TRow>` | columns, actions, toolbar, `resource` **or** `endpoint`, `embeddedFilters`, `limit`, `disablePagination`, `emptyMessage`, `dataKey` |
| slot | `#content` | scoped `{ rows, loading, reload, hasActiveFilters }` — replace the body, keep the machinery |
| slot | `cell:<fieldKey>` | scoped `{ row, value }` — custom markup for one column |
| exposed | `reload()` | parents force a refresh via a template ref |

**The schema** (from `GenericList/types/GenericList.types.ts`):

```ts
type ColumnType = "text" | "number" | "date" | "datetime" | "select" | "boolean" | "function";

interface Column<TRow> {
    header: string;
    fieldKey: string;              // dot-path ("owner.name"); also names the cell:<fieldKey> slot
    type: ColumnType;
    prefix?: string;
    suffix?: string;
    default?: string;              // shown for empty values (default "—")
    options?: SelectOption[];      // type "select": value → label
    handler?: (row: TRow) => string; // type "function": returns PLAIN TEXT
}

interface RowAction<TRow> {
    icon: string;
    label: string;                 // tooltip + aria-label
    severity?: "secondary" | "success" | "info" | "warn" | "danger" | "contrast";
    permission?: PermissionQuery;  // filtered with auth.hasPermission
    to?: (row: TRow) => RouteLocationRaw;
    onClick?: (row: TRow) => void;
    isVisible?: (row: TRow) => boolean;
}

interface Toolbar {
    title?: string;
    hideSearch?: boolean;
    searchPlaceholder?: string;
    hideRefresh?: boolean;
    actions?: ToolbarAction[];     // { label, icon?, permission?, to? | onClick? }
}

type TableConfig<TRow> = {
    columns?: Column<TRow>[];
    actions?: RowAction<TRow>[];
    toolbar?: Toolbar;
    embeddedFilters?: QueryParams; // always-on params merged into every request
    limit?: number;                // default 20
    disablePagination?: boolean;
    emptyMessage?: string;
    dataKey?: string;              // default "id"
} & ({ resource: ListableResource<TRow> } | { endpoint: EndpointKey });
```

**How it works internally** (see the build recipe): `useGenericList(config)` derives typed list
state from `route.query`, debounces the search box into `router.replace`, pushes paging with
`router.push`, and a watch on that state (re)fetches — ignoring out-of-order responses. Errors
surface as an `ApiError` banner. One URL-synced list per page (they share the query keys).

**Usage — default table fed a resource:**

```vue
<GenericList :config="config" />
```
```ts
const config: TableConfig<Order> = {
    resource: orderResource,
    columns: [
        { header: t("orders.reference"), fieldKey: "reference", type: "text" },
        { header: t("orders.total"), fieldKey: "total", type: "number", default: "0" },
        { header: t("orders.created"), fieldKey: "createdOn", type: "date" },
        { header: t("orders.status"), fieldKey: "status", type: "select", options: ORDER_STATUSES },
    ],
    actions: [
        { icon: "pi pi-pencil", label: t("common.edit"), permission: "order:update",
          to: (order) => ({ name: "order-edit", params: { id: order.id } }) },
    ],
    toolbar: { title: t("orders.title"),
               actions: [{ label: t("orders.create"), icon: "pi pi-plus", onClick: openCreateDrawer }] },
    embeddedFilters: { archived: false },
};
```

**Usage — custom cell and custom body (keep search/pagination/fetch for free):**

```vue
<GenericList :config="config">
    <template #cell:status="{ row }">
        <StatusPill :status="row.status" />
    </template>
</GenericList>

<GenericList :config="config">
    <template #content="{ rows, reload }">
        <GenericEmptyState v-if="!rows.length" :button-label="t('orders.create')" @action="openCreateDrawer" />
        <div v-else class="order-grid">
            <OrderCard v-for="order in rows" :key="order.id" :order="order" @updated="reload" />
        </div>
    </template>
</GenericList>
```

---

## 3. Generic Sidebar / Drawer (`GenericDrawer`)

A right-side drawer that **dynamically renders any component** via `<component :is>` and wires a
**config-driven footer action bar**. Used for detail panels and side forms (create/edit/view).

**Public API**

| Kind | Name | Notes |
|------|------|-------|
| prop | `visible: boolean` | `v-model:visible` |
| prop | `config: DrawerConfig` | `{ header, icon?, component, props?, actions? }` |
| emits | `update:visible`, `updated` | close / inner-saved |
| exposed | `getInnerComponent()` | the inner instance (typed `DrawerInnerExposed`, e.g. `onSave`) |

```ts
interface DrawerAction {
    label: string;
    handler: () => void | Promise<void>;
    variant?: "outlined" | "text";
    severity?: "secondary" | "success" | "info" | "warn" | "danger" | "contrast";
    icon?: string;
    disabled?: boolean;
    loading?: boolean;
}
interface DrawerConfig {
    header?: string;
    icon?: string;
    component: Component;              // the inner form/detail component
    props?: Record<string, unknown>;   // bound with v-bind
    actions?: DrawerAction[];          // footer buttons
}
```

**The interaction contract:**
- The inner component is mounted with `v-bind="config.props"` and **talks back up** by emitting
  `update-header` / `update-actions` (the value `"original"` restores the configured one), plus
  `updated` / `close`.
- **Footer buttons do not live in the inner form.** The parent defines `actions` whose handler
  reaches in through the exposed ref: `drawer.value?.getInnerComponent()?.onSave?.()`.
- Remount with a changing `:key` on open to reset inner state.

```ts
const drawer = ref<InstanceType<typeof GenericDrawer> | null>(null);
const drawerConfig = computed<DrawerConfig>(() => ({
    header: t("members.changeRole"),
    component: ChangeRoleForm,
    props: { member: props.member },
    actions: [
        { label: t("common.cancel"), variant: "outlined", severity: "secondary",
          handler: () => (visible.value = false) },
        { label: t("common.save"), handler: () => drawer.value?.getInnerComponent()?.onSave?.() },
    ],
}));
```

---

## 4. Dialogs (`GenericDialog`, `ConfirmationDialog`)

**`GenericDialog` is the one dialog primitive** — the only component allowed to import PrimeVue
`Dialog`. It covers confirms, forms, info and destructive dialogs:

| Kind | Name | Notes |
|------|------|-------|
| prop | `visible`, `header`, `icon`, `message`, `closable` | defaults keep width/padding/icon sizing consistent |
| prop | `actions: DialogAction[]` | footer buttons `{ label, handler, severity?, variant?, icon?, disabled?, loading?, visible? }` in render order |
| slot | default / `#footer` | body content (e.g. a form) / custom footer |
| emits | `update:visible` | |

**`ConfirmationDialog`** — the local, prop-driven confirm built on it. The parent owns `visible`,
listens for a single `hideDialog(confirmed: boolean)` and does the work itself:

```vue
<ConfirmationDialog
    :visible="confirmVisible"
    :header="t('orders.deleteTitle')"
    :message="t('orders.deleteBody')"
    :confirm-label="t('common.delete')"
    confirm-severity="danger"
    :loading="deleting"
    @hide-dialog="onConfirm"
/>
```

**Global, store-driven dialogs** — for cross-cutting flows (e.g. an upgrade prompt triggered by
a quota `err_cd`), mount one `GenericDialog`-based component **once** in `App.vue` and drive it
from a store flag + payload, so any code — including an http hook — can open it.

Filter and import dialogs follow the same **prop-in / event-out** convention.

---

## 5. Forms — the generic seam

Two valid approaches; pick one per project and apply it consistently.

**(a) Convention-based (controlled field components) — the baseline.**
Validation is authoritative on the **server**. The seam:

- Field components are **controlled**: they receive `form` + `apiErrors` as props and emit
  `update:form` (they never own the model — state is lifted to the parent/drawer).
- **`apiErrors`** is the `FieldErrors` (`Record<string, string[]>`) of the caught `ApiError`.
  Each field binds `:invalid` and shows the first message.
- Submit is exposed as **`onSave()`** (`defineExpose({ onSave })`), which the drawer footer calls.

```vue
<InputText
    id="member-email"
    :model-value="form.email"
    :invalid="!!apiErrors.email"
    @update:model-value="updateField('email', $event)"
/>
<Message v-if="apiErrors.email" severity="error" variant="simple" size="small">
    {{ apiErrors.email[0] }}
</Message>
```
```ts
const props = defineProps<{ form: MemberForm; apiErrors: FieldErrors }>();
const emit = defineEmits<{ "update:form": [value: MemberForm] }>();

function updateField<K extends keyof MemberForm>(key: K, value: MemberForm[K]): void {
    emit("update:form", { ...props.form, [key]: value });
}
// onSave(): await memberResource.update(id, payload); on ApiError → apiErrors = error.fieldErrors
```

**(b) Schema-driven form generator (`FormGenerator`) — recommended for form-heavy apps.**
A `FormGenerator` renders inputs from a **field schema** and centralises validation, dirty-state
and submission:

```ts
interface FieldDef {
    key: string;
    type: "text" | "number" | "select" | "multiselect" | "textarea" | "date" | "checkbox";
    label: string;
    options?: SelectOption[];
    rules?: ValidationRule[];      // optional client-side rules (e.g. zod)
    hint?: string;
    placeholder?: string;
    disabled?: boolean;
}
```
```vue
<FormGenerator v-model="form" :schema="fields" :api-errors="apiErrors" @submit="onSave" />
```

Either way, client errors and server `apiErrors` are presented the same way, and backend field
errors are always shown.

---

## 6. Other shared components (catalogue)

| Component | Purpose | Key props / events |
|-----------|---------|--------------------|
| `GenericEmptyState` | Centred empty / error state (icon + title + text + optional CTA) | `icon`, `title`, `description`, `buttonLabel`, `buttonIcon`; `@action` |
| `shared/StatusPill` | The status indicator (instead of raw `Tag`) — create with the first status | `status`, `options` |
| `shared/AppAvatar` | Avatar with initials fallback (PrimeVue `Avatar` wrapper); accepts a URL or `File`/`Blob` | `image`, `label` |
| `layouts/components/ThemeToggle` | Light/dark switch bound to the app store | — |
| `layouts/components/OrgSwitcher` | Multi-tenant org switch (navigates to the new org's dashboard) | — |

Add every new shell/widget to this table with its props.

---

## 7. Replication checklist

- [ ] Each generic shell has a **typed config interface** in a sibling `types/` file — that's its API.
- [ ] `GenericList` takes a **resource or an endpoint key**, owns fetching, URL-synced
      search/pagination; `#content` and `cell:<fieldKey>` slots customise without losing machinery.
- [ ] Cells render via one **type-switch** (`FormatCell`); `function` columns return text; no `v-html`.
- [ ] `GenericDrawer` hosts inner content via `<component :is>`; footer actions call the **exposed**
      `getInnerComponent().onSave()`; inner content talks back via `update-header`/`update-actions`.
- [ ] All dialogs go through `GenericDialog` (confirms via `ConfirmationDialog`); cross-cutting
      dialogs are mounted once and store-driven.
- [ ] Forms follow one seam; server field errors from `ApiError.fieldErrors` are always shown.
- [ ] Shells are explicitly imported; only PrimeVue is auto-registered.
