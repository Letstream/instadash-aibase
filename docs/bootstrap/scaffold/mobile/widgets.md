# Mobile scaffold — generic widgets

> Part of the [mobile scaffold](README.md). Each `### \`path\`` block is the **exact, complete** file content, relative to the mobile repo root (`mobile/`).

Domain-agnostic building blocks every screen reuses (rules in
[ui-and-theming](../../../architecture-guidelines/mobile/ui-and-theming.md)): `EmptyState`,
`ErrorView` + `errorMessage()`, `LoadingButton`, `AppTextField` (shows backend field errors),
`showConfirmDialog` / `showAppSnackBar`, and the paged list pair `ListController<T>` +
`ResourceListView<T>`.

A feature list screen is then only:

```dart
ChangeNotifierProvider(
  create: (context) => ListController<Order>(repository: OrderRepository(context.read<ApiClient>())),
  child: Builder(
    builder: (context) => ResourceListView<Order>(
      controller: context.read<ListController<Order>>(),
      itemBuilder: (context, order) => ListTile(key: ValueKey(order.id), title: Text(order.reference)),
    ),
  ),
)
```

### `lib/core/widgets/empty_state.dart`

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

/// Centered icon + title (+ message, + action) for empty lists, errors and placeholders.
class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, this.message, this.action});

  final IconData icon;
  final String title;
  final String? message;

  /// Usually a button (retry, create first item).
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final message = this.message;
    final action = this.action;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: AppSizes.maxContentWidth),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: AppSizes.iconLg, color: context.colors.textMuted),
              const SizedBox(height: AppSpacing.md),
              Text(title, style: context.textTheme.titleMedium, textAlign: TextAlign.center),
              if (message != null) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  message,
                  style: context.textTheme.bodyMedium?.copyWith(color: context.colors.textMuted),
                  textAlign: TextAlign.center,
                ),
              ],
              if (action != null) ...[const SizedBox(height: AppSpacing.lg), action],
            ],
          ),
        ),
      ),
    );
  }
}
```

### `lib/core/widgets/error_view.dart`

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
import 'package:<project_slug>/core/widgets/empty_state.dart';
import 'package:flutter/material.dart';

/// User-facing message for any error: localized copy for network/unknown failures, the
/// backend's `err_msg` otherwise.
String errorMessage(BuildContext context, Object? error) {
  if (error is ApiError) {
    if (error.isNetworkError) return context.l10n.errorNetwork;
    if (error.status >= 500) return context.l10n.errorGeneric;
    return error.message;
  }
  return context.l10n.errorGeneric;
}

/// Full-area error state with a retry action.
class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.error, this.onRetry});

  final Object? error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final onRetry = this.onRetry;
    return EmptyState(
      icon: Icons.cloud_off_outlined,
      title: errorMessage(context, error),
      action: onRetry == null
          ? null
          : OutlinedButton(onPressed: onRetry, child: Text(context.l10n.actionRetry)),
    );
  }
}
```

### `lib/core/widgets/loading_button.dart`

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

/// Primary action button that shows a spinner and ignores taps while [onPressed] runs.
class LoadingButton extends StatefulWidget {
  const LoadingButton({super.key, required this.label, required this.onPressed, this.icon});

  final String label;
  final IconData? icon;

  /// `null` disables the button.
  final Future<void> Function()? onPressed;

  @override
  State<LoadingButton> createState() => _LoadingButtonState();
}

class _LoadingButtonState extends State<LoadingButton> {
  bool _busy = false;

  Future<void> _run() async {
    final action = widget.onPressed;
    if (action == null || _busy) return;
    setState(() => _busy = true);
    try {
      await action();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final icon = widget.icon;
    final child = _busy
        ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))
        : Text(widget.label);
    final onPressed = widget.onPressed == null || _busy ? null : _run;
    return icon == null || _busy
        ? FilledButton(onPressed: onPressed, child: child)
        : FilledButton.icon(onPressed: onPressed, icon: Icon(icon), label: child);
  }
}
```

### `lib/core/widgets/app_text_field.dart`

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
import 'package:flutter/material.dart';

/// Labelled text input that shows a backend field error (`ApiError.firstError(name)`) under
/// the field. Pair with a `Form` for client-side validation.
class AppTextField extends StatelessWidget {
  const AppTextField({
    super.key,
    required this.name,
    required this.label,
    required this.controller,
    this.apiError,
    this.validator,
    this.obscureText = false,
    this.keyboardType,
    this.textInputAction,
    this.autofillHints,
    this.onSubmitted,
  });

  /// Backend field name (snake_case) used to look up [apiError].
  final String name;
  final String label;
  final TextEditingController controller;
  final ApiError? apiError;
  final FormFieldValidator<String>? validator;
  final bool obscureText;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;
  final ValueChanged<String>? onSubmitted;

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: controller,
      decoration: InputDecoration(labelText: label, errorText: apiError?.firstError(name)),
      validator: validator,
      obscureText: obscureText,
      keyboardType: keyboardType,
      textInputAction: textInputAction,
      autofillHints: autofillHints,
      onFieldSubmitted: onSubmitted,
    );
  }
}
```

### `lib/core/widgets/app_dialogs.dart`

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
import 'package:flutter/material.dart';

/// The app's confirm dialog. Resolves to true only when the user confirms.
/// Secondary (cancel) action first, primary last; destructive actions use the error colour.
Future<bool> showConfirmDialog(
  BuildContext context, {
  required String title,
  required String message,
  String? confirmLabel,
  bool destructive = false,
}) async {
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (dialogContext) {
      final scheme = Theme.of(dialogContext).colorScheme;
      return AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(dialogContext.l10n.actionCancel),
          ),
          FilledButton(
            style: destructive
                ? FilledButton.styleFrom(
                    backgroundColor: scheme.error,
                    foregroundColor: scheme.onError,
                  )
                : null,
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(confirmLabel ?? dialogContext.l10n.actionConfirm),
          ),
        ],
      );
    },
  );
  return confirmed ?? false;
}

/// Transient feedback. Errors use the error colour.
void showAppSnackBar(BuildContext context, String message, {bool isError = false}) {
  final scheme = Theme.of(context).colorScheme;
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Text(message, style: isError ? TextStyle(color: scheme.onError) : null),
        backgroundColor: isError ? scheme.error : null,
      ),
    );
}
```

### `lib/core/widgets/resource_list/list_controller.dart`

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
import 'package:<project_slug>/core/data/base_repository.dart';
import 'package:flutter/foundation.dart';

/// Paginated list state over any [ListableRepository] (limit/offset, as the backend's
/// `StandardPagination`). Owns loading, refresh, load-more, search and error state.
class ListController<T> extends ChangeNotifier {
  ListController({required this.repository, this.pageSize = 20, this._filters = const {}});

  final ListableRepository<T> repository;
  final int pageSize;
  QueryParams _filters;

  List<T> _items = const [];
  int _count = 0;
  bool _hasMore = true;
  bool _loading = false;
  Object? _error;
  int _generation = 0;

  List<T> get items => _items;
  int get count => _count;
  bool get hasMore => _hasMore;
  bool get isLoading => _loading;
  Object? get error => _error;
  bool get isEmpty => !_loading && _error == null && _items.isEmpty;
  QueryParams get filters => _filters;

  /// Replaces filters (search, status, …) and reloads from the first page.
  Future<void> setFilters(QueryParams filters) {
    _filters = filters;
    return refresh();
  }

  /// Loads the first page, discarding what is shown.
  Future<void> refresh() async {
    final generation = ++_generation;
    _loading = true;
    _error = null;
    notifyListeners();
    await _fetch(offset: 0, generation: generation, append: false);
  }

  /// Appends the next page; no-op while loading or at the end.
  Future<void> loadMore() async {
    if (_loading || !_hasMore || _error != null) return;
    final generation = _generation;
    _loading = true;
    notifyListeners();
    await _fetch(offset: _items.length, generation: generation, append: true);
  }

  /// Retries whatever failed last (first page or next page).
  Future<void> retry() {
    if (_items.isEmpty) return refresh();
    _error = null;
    return loadMore();
  }

  Future<void> _fetch({required int offset, required int generation, required bool append}) async {
    try {
      final page = await repository.list(query: {..._filters, 'limit': pageSize, 'offset': offset});
      if (generation != _generation) return; // a newer refresh won the race
      _items = append ? [..._items, ...page.items] : page.items;
      _count = page.count;
      _hasMore = page.hasMore;
    } catch (error) {
      if (generation != _generation) return;
      _error = error;
    }
    _loading = false;
    notifyListeners();
  }
}
```

### `lib/core/widgets/resource_list/resource_list_view.dart`

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
import 'package:<project_slug>/core/theme/app_tokens.dart';
import 'package:<project_slug>/core/widgets/empty_state.dart';
import 'package:<project_slug>/core/widgets/error_view.dart';
import 'package:<project_slug>/core/widgets/resource_list/list_controller.dart';
import 'package:flutter/material.dart';

/// The generic list screen body: first-load spinner, pull-to-refresh, infinite scroll,
/// empty and error states. Feed it a [ListController] and an [itemBuilder]; screens never
/// hand-roll pagination.
class ResourceListView<T> extends StatefulWidget {
  const ResourceListView({
    super.key,
    required this.controller,
    required this.itemBuilder,
    this.emptyIcon = Icons.inbox_outlined,
    this.emptyTitle,
    this.emptyMessage,
    this.padding = const EdgeInsets.symmetric(vertical: AppSpacing.sm),
  });

  final ListController<T> controller;
  final Widget Function(BuildContext context, T item) itemBuilder;
  final IconData emptyIcon;
  final String? emptyTitle;
  final String? emptyMessage;
  final EdgeInsets padding;

  @override
  State<ResourceListView<T>> createState() => _ResourceListViewState<T>();
}

class _ResourceListViewState<T> extends State<ResourceListView<T>> {
  @override
  void initState() {
    super.initState();
    if (widget.controller.items.isEmpty && !widget.controller.isLoading) {
      widget.controller.refresh();
    }
  }

  bool _onScroll(ScrollNotification notification) {
    if (notification.metrics.extentAfter < 400) widget.controller.loadMore();
    return false;
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final controller = widget.controller;
        final items = controller.items;
        if (items.isEmpty && controller.isLoading) {
          return const Center(child: CircularProgressIndicator());
        }
        if (items.isEmpty && controller.error != null) {
          return ErrorView(error: controller.error, onRetry: controller.retry);
        }
        if (controller.isEmpty) {
          return RefreshIndicator(
            onRefresh: controller.refresh,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                const SizedBox(height: AppSpacing.xxl),
                EmptyState(
                  icon: widget.emptyIcon,
                  title: widget.emptyTitle ?? context.l10n.emptyTitle,
                  message: widget.emptyMessage,
                ),
              ],
            ),
          );
        }
        final showFooter = controller.hasMore || controller.error != null;
        return NotificationListener<ScrollNotification>(
          onNotification: _onScroll,
          child: RefreshIndicator(
            onRefresh: controller.refresh,
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: widget.padding,
              itemCount: items.length + (showFooter ? 1 : 0),
              itemBuilder: (context, index) {
                if (index < items.length) return widget.itemBuilder(context, items[index]);
                return _ListFooter(controller: controller);
              },
            ),
          ),
        );
      },
    );
  }
}

class _ListFooter extends StatelessWidget {
  const _ListFooter({required this.controller});

  final ListController<Object?> controller;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Center(
        child: controller.error != null
            ? TextButton(onPressed: controller.retry, child: Text(context.l10n.actionRetry))
            : const CircularProgressIndicator(),
      ),
    );
  }
}
```

### `test/core/widgets/empty_state_test.dart`

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

import 'package:<project_slug>/core/widgets/empty_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/pump_app.dart';

void main() {
  for (final mode in [ThemeMode.light, ThemeMode.dark]) {
    testWidgets('renders title, message and action (${mode.name})', (tester) async {
      var tapped = false;
      await tester.pumpApp(
        Scaffold(
          body: EmptyState(
            icon: Icons.inbox_outlined,
            title: 'No orders',
            message: 'Create the first one.',
            action: TextButton(onPressed: () => tapped = true, child: const Text('Create')),
          ),
        ),
        themeMode: mode,
      );
      expect(find.text('No orders'), findsOneWidget);
      expect(find.text('Create the first one.'), findsOneWidget);
      await tester.tap(find.text('Create'));
      expect(tapped, isTrue);
    });
  }
}
```

### `test/core/widgets/list_controller_test.dart`

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
import 'package:<project_slug>/core/api/api_error.dart';
import 'package:<project_slug>/core/api/page_result.dart';
import 'package:<project_slug>/core/data/base_repository.dart';
import 'package:<project_slug>/core/widgets/resource_list/list_controller.dart';
import 'package:flutter_test/flutter_test.dart';

/// Serves `total` integers with limit/offset paging and records every query.
class FakeNumbers implements ListableRepository<int> {
  FakeNumbers(this.total);

  final int total;
  final queries = <QueryParams>[];
  Object? failWith;

  @override
  Future<PageResult<int>> list({QueryParams? query}) async {
    queries.add(query ?? const {});
    final error = failWith;
    if (error != null) throw error;
    final offset = query?['offset']! as int;
    final limit = query?['limit']! as int;
    final end = (offset + limit).clamp(0, total);
    return PageResult(
      items: [for (var i = offset; i < end; i++) i],
      count: total,
      next: end < total ? 'next' : null,
    );
  }
}

void main() {
  test('refresh then loadMore pages through with limit/offset', () async {
    final repository = FakeNumbers(5);
    final controller = ListController<int>(repository: repository, pageSize: 2);
    await controller.refresh();
    expect(controller.items, [0, 1]);
    expect(controller.hasMore, isTrue);
    await controller.loadMore();
    await controller.loadMore();
    expect(controller.items, [0, 1, 2, 3, 4]);
    expect(controller.hasMore, isFalse);
    await controller.loadMore();
    expect(repository.queries, hasLength(3));
  });

  test('filters are sent and reset paging', () async {
    final repository = FakeNumbers(3);
    final controller = ListController<int>(repository: repository, pageSize: 2);
    await controller.setFilters({'search': 'x'});
    expect(repository.queries.last, {'search': 'x', 'limit': 2, 'offset': 0});
  });

  test('errors are exposed, and retry recovers', () async {
    final repository = FakeNumbers(1)..failWith = const ApiError(status: 0, message: 'offline');
    final controller = ListController<int>(repository: repository);
    await controller.refresh();
    expect(controller.error, isA<ApiError>());
    expect(controller.isEmpty, isFalse);
    repository.failWith = null;
    await controller.retry();
    expect(controller.items, [0]);
    expect(controller.error, isNull);
  });

  test('empty result', () async {
    final controller = ListController<int>(repository: FakeNumbers(0));
    await controller.refresh();
    expect(controller.isEmpty, isTrue);
  });
}
```
