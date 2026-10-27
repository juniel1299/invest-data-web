import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models.dart';
import '../state/app_state.dart';

/// 티커·영문명·한글명으로 검색해 종목을 고르는 자동완성 입력란.
/// 목록에서 고른 뒤 글자를 바꾸면 선택이 풀린다.
/// [autoSelectExact]면 티커를 정확히 친 경우 목록을 누르지 않아도 그 종목으로 고른다.
class TickerField extends StatefulWidget {
  const TickerField({
    super.key,
    required this.onSelected,
    this.label = '종목 (티커 또는 이름)',
    this.icon,
    this.autoSelectExact = false,
  });

  final ValueChanged<Security?> onSelected;
  final String label;
  final IconData? icon;
  final bool autoSelectExact;

  @override
  State<TickerField> createState() => _TickerFieldState();
}

class _TickerFieldState extends State<TickerField> {
  Security? _selected;
  Timer? _debounce;

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  void _select(Security? s) {
    if (mounted) setState(() => _selected = s);
    widget.onSelected(s);
  }

  Future<Iterable<Security>> _search(TextEditingValue value) {
    final q = value.text.trim();
    if (_selected != null && q.toUpperCase() != _selected!.ticker) _select(null);
    if (q.isEmpty || q.toUpperCase() == _selected?.ticker) return Future.value(const []);
    // 입력이 멈춘 뒤에 검색해서 키 입력마다 요청하지 않는다
    _debounce?.cancel();
    final completer = Completer<Iterable<Security>>();
    final api = context.read<AppState>().api;
    _debounce = Timer(const Duration(milliseconds: 250), () async {
      try {
        final results = await api.searchSecurities(q);
        if (widget.autoSelectExact && mounted) {
          final exact = results.where((s) => s.ticker == q.toUpperCase()).firstOrNull;
          if (exact != null) _select(exact);
        }
        completer.complete(results);
      } catch (_) {
        completer.complete(const []);
      }
    });
    return completer.future;
  }

  @override
  Widget build(BuildContext context) {
    return Autocomplete<Security>(
      displayStringForOption: (s) => s.ticker,
      optionsBuilder: _search,
      onSelected: _select,
      fieldViewBuilder: (context, controller, focus, onSubmit) => TextFormField(
        controller: controller,
        focusNode: focus,
        textCapitalization: TextCapitalization.characters,
        decoration: InputDecoration(
          labelText: widget.label,
          hintText: '예: AAPL, 애플',
          helperText: widget.autoSelectExact && _selected != null
              ? '${_selected!.ticker} ${_selected!.displayName}'
              : null,
          prefixIcon: widget.icon == null ? null : Icon(widget.icon),
        ),
      ),
      optionsViewBuilder: (context, onSelect, options) => Align(
        alignment: Alignment.topLeft,
        child: Material(
          elevation: 4,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 280, maxWidth: 480),
            child: ListView(
              shrinkWrap: true,
              children: [
                for (final s in options)
                  ListTile(
                    dense: true,
                    title: Text('${s.ticker}  ${s.displayName}'),
                    subtitle: Text(s.exchange),
                    onTap: () => onSelect(s),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
