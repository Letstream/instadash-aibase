<!-- Instadash AI Base (managed file — edit via /upgrade, not by hand) — (c) Letstream Ventures Pvt Ltd, https://www.theletstream.com. Provided "AS IS" without warranty unless covered by an explicit written agreement; unauthorized use or redistribution is prohibited. -->
# Building Shared / Generic Components

> How to *construct* the config-driven shells, not just consume them. Read
> [shared-components](shared-components.md) first for the catalogue and public APIs — this page is
> the authoring guide: when to build one, how to decompose it, implementation skeletons for the
> core mechanics, and how to extend them. The complete, tested implementations are in the
> [frontend scaffold](../../bootstrap/scaffold/frontend/shared-components.md). Follow the
> `frontend-design-guidelines` skill for styling/token rules throughout.

---

## 1. When to build a generic component (promotion criteria)

Don't start generic. **Build the concrete feature first, then promote** when the third similar
surface appears. Promote to a `Generic*` shell only when **all** hold:

- The surface recurs across ≥3 features (list page, side form, confirm dialog…).
- The variation between instances is **data, not structure** — it can be expressed as a config
  object + slots, without per-feature branching inside the shell.
- The machinery worth centralising is real (fetching, URL-synced state, pagination, validation) —
  not just markup.

If a surface is truly one-off, keep it local to the feature folder. A shell that needs a growing
pile of `if (feature === "x")` branches was promoted too early — split it instead.

---

## 2. Anatomy of a generic component

Each shell is a small package: an **orchestrator**, a **types file that IS the public API**,
**helpers/composables** for logic, and **co-located sub-components** for each piece.

```
GenericList/
├── GenericList.vue                 # orchestrator: toolbar + DataTable (or #content) + Paginator
├── types/GenericList.types.ts      # ALL config interfaces — the contract (exported)
├── composables/useGenericList.ts   # fetch (resource | endpoint) + URL-synced state
├── helpers/query.ts                # pure: URL query ⇄ typed list state ⇄ request params
├── components/
│   └── FormatCell.vue              # per-cell type-switch renderer (the extension seam)
└── __tests__/                      # query.spec.ts, useGenericList.spec.ts, FormatCell.spec.ts
```

Grow it with more sub-components (`TableToolbar.vue`, `FilterDialog.vue`, …) when the
orchestrator stops fitting on a screen.

**Rules**
- **Contract-first.** Write `types/*.types.ts` before the template. The config interface is the
  component's API; everything else serves it.
- **Decompose by concern.** The orchestrator stays thin — it wires state and delegates rendering.
- **Logic in composables and pure helpers, markup in components** — so it is unit-testable.
- **Co-locate** types, composables, helpers, sub-components and specs inside the shell's folder.
- **Explicit imports** — generic shells are not auto-registered.
- **Data via the data layer** — accept a `ListableResource` (or an endpoint key), never a raw URL
  string, and never import axios.
- Style with **scoped SCSS + BEM + tokens** only (no arbitrary Tailwind, no hex); light + dark.

---

## 3. Build recipe: a self-fetching, URL-synced list

**Step 1 — the contract** (`types/GenericList.types.ts`): see
[shared-components §2](shared-components.md#2-generic-table--list-genericlist). The key design:
the data source is a discriminated union — `{ resource: ListableResource<TRow> }` **or**
`{ endpoint: EndpointKey }`.

**Step 2 — pure helpers** (`helpers/query.ts`): `readListState(query, defaultLimit)` (strings →
typed, with safe fallbacks), `mergeListState(query, state)` (omit defaults, keep foreign keys),
`toRequestParams(state, embeddedFilters)`.

**Step 3 — the composable** (`composables/useGenericList.ts`): URL state → fetch; search box →
debounced URL write.

```ts
function createFetcher<TRow>(config: TableConfig<TRow>) {
    if (config.resource) {
        const resource = config.resource;
        return (params: QueryParams) => resource.list(params);           // → Page<model>
    }
    const path = endpoint(config.endpoint);
    return async (params: QueryParams) =>
        normalizeList(await api.get<ListDto<TRow>>(path, params));       // → Page<dto>
}

export function useGenericList<TRow>(config: TableConfig<TRow>) {
    const route = useRoute();
    const router = useRouter();
    const defaultLimit = config.limit ?? DEFAULT_LIMIT;
    const fetchPage = createFetcher(config);
    const rows = shallowRef<TRow[]>([]) as Ref<TRow[]>;
    const total = ref(0);
    const loading = ref(false);
    const error = shallowRef<ApiError | null>(null);

    // 1. typed state lives in the URL (deep links, back/forward)
    const state = computed(() => readListState(route.query, defaultLimit));
    const search = ref(state.value.search);

    // 2. fetch; drop out-of-order responses
    let requestId = 0;
    async function load() {
        const current = ++requestId;
        loading.value = true;
        try {
            const page = await fetchPage(toRequestParams(state.value, config.embeddedFilters));
            if (current !== requestId) return;
            rows.value = page.items;
            total.value = page.count;
        } catch (err) {
            if (current === requestId) error.value = ApiError.from(err);
        } finally {
            if (current === requestId) loading.value = false;
        }
    }

    // 3. search → debounced replace; paging → push; URL change → refetch
    const applySearch = debounce(
        (value: string) => router.replace({ query: mergeListState(route.query,
            { ...state.value, search: value.trim(), offset: 0 }, defaultLimit) }),
        350
    );
    watch(search, (value) => applySearch(value));
    onBeforeUnmount(() => applySearch.cancel());
    watch(() => JSON.stringify(state.value), () => void load(), { immediate: true });

    function onPage(event: { first: number; rows: number }) {
        void router.push({ query: mergeListState(route.query,
            { ...state.value, offset: event.first, limit: event.rows }, defaultLimit) });
    }

    return { rows, total, loading, error, search, state, load, onPage };
}
```

**Step 4 — the orchestrator** (`GenericList.vue`, `<script setup lang="ts" generic="TRow extends object">`):
call the composable, render the toolbar (search `InputText`, refresh, permission-filtered actions),
then **either** the `#content` slot **or** a `DataTable` whose column bodies render
``<slot :name="`cell:${column.fieldKey}`">`` falling back to `FormatCell`, then a `Paginator`.
`defineExpose({ reload: load })`.

---

## 4. Build recipe: the type-switch cell renderer (the extension seam)

One small component turns a column + row into **text**. To support a new column type you add a
`case` here — nowhere else.

```vue
<script setup lang="ts" generic="TRow">
const props = defineProps<{ column: Column<TRow>; row: TRow }>();

const text = computed<string | null>(() => {
    const { column, row } = props;
    const value = getByPath(row, column.fieldKey);
    switch (column.type) {
        case "number":   return formatNumber(value);
        case "date":     return formatDate(value);
        case "datetime": return formatDate(value, true);
        case "select":   return column.options?.find((o) => o.value === value)?.label ?? null;
        case "function": return column.handler ? column.handler(row) : null;
        case "boolean":  return null;
        default:         return value == null || value === "" ? null : String(value);
    }
});
</script>

<template>
    <i v-if="column.type === 'boolean'" :class="booleanValue ? 'pi pi-check' : 'pi pi-minus'" />
    <span v-else-if="text !== null">{{ column.prefix }}{{ text }}{{ column.suffix }}</span>
    <span v-else class="format-cell__empty">{{ column.default ?? "—" }}</span>
</template>
```

**Adding a new type:** extend the `ColumnType` union, add one `case`, add a spec case, document
it in [shared-components](shared-components.md) §2. Do not teach the orchestrator about types.

> **Safety.** There is deliberately **no `v-html` path**: `function` columns return plain text
> (rendered with interpolation, so `<b>` shows literally). Rich content — status pills, avatars,
> links — goes in the `cell:<fieldKey>` slot, where it is ordinary, escaped template code.
> ESLint `vue/no-v-html` is an error.

---

## 5. Build recipe: the dynamic host + ref-driven actions (GenericDrawer)

A shell that mounts **any** inner component and drives it without knowing its internals:
`<component :is>` + `v-bind`, and an **exposed method** on the inner instance that
parent-defined footer actions call.

```vue
<script setup lang="ts">
const props = defineProps<{ visible: boolean; config: DrawerConfig }>();
const emit = defineEmits<{ "update:visible": [value: boolean]; updated: [payload: unknown] }>();

const inner = ref<DrawerInnerExposed | null>(null);
const header = ref(props.config.header ?? "");
const actions = ref<DrawerAction[]>(props.config.actions ?? []);
watch(() => props.config, (c) => { header.value = c.header ?? ""; actions.value = c.actions ?? []; });

defineExpose({ getInnerComponent: () => inner.value });
</script>

<template>
    <Drawer :visible="visible" position="right" @update:visible="emit('update:visible', $event)">
        <template #header>{{ header }}</template>
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
            <Button v-for="a in actions" :key="a.label" :label="a.label" :variant="a.variant"
                :severity="a.severity" :loading="a.loading" :disabled="a.disabled" @click="a.handler" />
        </template>
    </Drawer>
</template>
```

**The contract** (symmetric, so every inner form works the same way):
- Inner component is a **pure field editor** — no footer buttons, no drawer chrome.
- It **exposes** submit: `defineExpose({ onSave })`.
- It **talks back up** with `update-header` / `update-actions` (`"original"` resets), `updated`, `close`.
- The **parent** defines `config.actions`; each handler calls `drawer.value?.getInnerComponent()?.onSave?.()`.
- Remount with a changing `:key` on open to reset inner state.
- PrimeVue overlays are teleported — size them with a bound token style
  (`:style="{ width: 'min(var(--app-drawer-width), 100vw)' }"`), not scoped classes.

The same host pattern builds wizards and generic modals — reuse it.

---

## 6. Build recipe: dialogs

Build **one primitive**, `GenericDialog`: props for `header`, `icon`, `message`, `closable`, a
default slot for the body, and an **overridable footer-action array** (`DialogAction`: label,
handler, severity, variant, icon, disabled, loading, visible) — the same action-array idea as the
drawer footer. It is the only component that imports PrimeVue `Dialog`.

Specialisations are thin wrappers that compute `actions`:

```ts
// ConfirmationDialog.vue — prop-in / hideDialog(confirmed)-out
const actions = computed<DialogAction[]>(() => [
    { label: props.cancelLabel || t("common.cancel"), variant: "outlined", severity: "secondary",
      disabled: props.loading, handler: () => emit("hideDialog", false) },
    { label: props.confirmLabel || t("common.confirm"), severity: props.confirmSeverity,
      loading: props.loading, handler: () => emit("hideDialog", true) },
]);
```

**Global, store-driven** dialogs: a store action toggles a flag + payload; `App.vue` mounts the
dialog once and binds them; any code (including an http hook) can open it.

---

## 7. Build recipe: the form seam

- Field components are **controlled**: `props { form, apiErrors }`, `emit("update:form", next)`.
  They never own the model.
- Submit is **exposed**: `defineExpose({ onSave })`. `onSave` calls a **resource** (never axios);
  on `ApiError` it assigns `error.fieldErrors` to `apiErrors` and shows `error.message` for
  non-field errors.
- Present server field errors from `apiErrors[field][0]` next to each input.

For form-heavy apps, promote this into a **schema-driven `FormGenerator`** — `FieldDef` shape in
[shared-components](shared-components.md) §5.

---

## 8. Conventions for authoring shells

| Concern | Rule |
|---------|------|
| Naming | `Generic*` for config/slot-driven shells, one folder each under `src/components/`; small widgets in `src/components/shared/`; BEM roots named after the component (`.generic-list__toolbar`). |
| Types | The config interface lives in `types/<Name>.types.ts` and is the **exported public API**. Changing it is a breaking change for every consumer. |
| Data | Accept a `ListableResource` / resource instance or an endpoint key — never URLs; never import axios. |
| Logic | Fetch/state/URL-sync in a `useX()` composable; pure transforms in `helpers/`; `.vue` files declarative. |
| Extension | Prefer config fields + a type-switch case + slots over props that add structural branches. |
| Slots | Always provide scoped escape-hatch slots (`#content`, `cell:<key>`, `#footer`) with useful scope. |
| Security | No `v-html`; custom markup via slots. |
| Imports | Explicit — never rely on auto-registration for app-owned shells. |
| Styling | Scoped SCSS + BEM + tokens; light + dark (see the skill). |
| Backward-compat | New config fields are **optional with safe defaults**. |

---

## 9. Testing & documentation expectations

- **Unit-test the pure helpers and the composable** — query round-trips, defaults, page↔offset,
  both data sources, list-shape tolerance, debounce, error mapping. Mount the composable in a tiny
  host component with a memory-history router (see [testing](testing.md)).
- **Component-test the type-switch renderer** — one case per `type`, plus "function returns text".
- **Document every new shell** in [shared-components](shared-components.md): config interface,
  usage snippet, new types/fields. A shell isn't "done" until it's in the catalogue.
- `npm run lint`, `npm run type-check`, `npm run test` pass.

---

## Authoring checklist

- [ ] Promoted for the right reason (≥3 uses, variation is data not structure).
- [ ] `types/*.types.ts` written first; config is the whole public API.
- [ ] Data source is a resource or endpoint key; fetch/state/URL-sync in a composable.
- [ ] Cell/field rendering is a single type-switch returning text; rich content via slots; no `v-html`.
- [ ] Dynamic hosts use `<component :is>` + `v-bind` + an **exposed** submit method; footer
      actions are a config-driven array.
- [ ] Escape-hatch slots exist with useful scope.
- [ ] New config fields are optional with safe defaults.
- [ ] Scoped SCSS + BEM + tokens; light + dark; explicit imports.
- [ ] Helpers/composable/renderer have Vitest specs; shell added to the catalogue.
