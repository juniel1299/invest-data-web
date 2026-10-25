import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../format.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../widgets/ticker_field.dart';

/// 매수·매도 한 건을 등록하거나 고친다.
/// "보유 현황만" 넣고 싶으면 매수 한 건에 평균 단가와 수량을 넣으면 된다.
class TransactionFormScreen extends StatefulWidget {
  const TransactionFormScreen({super.key, this.initial, this.ticker, this.side = 'BUY'});

  final TradeTransaction? initial;
  final String? ticker;
  final String side;

  @override
  State<TransactionFormScreen> createState() => _TransactionFormScreenState();
}

class _TransactionFormScreenState extends State<TransactionFormScreen> {
  final _form = GlobalKey<FormState>();
  late String? _ticker = widget.initial?.ticker ?? widget.ticker;
  late String _side = widget.initial?.side ?? widget.side;
  late DateTime _date = widget.initial?.tradedAt ?? DateTime.now();
  late final _qty = TextEditingController(text: _num(widget.initial?.quantity));
  late final _price = TextEditingController(text: _num(widget.initial?.price));
  late final _fx = TextEditingController(text: _num(widget.initial?.fxRate));
  late final _memo = TextEditingController(text: widget.initial?.memo ?? '');
  bool _busy = false;
  String? _error;
  // 단가 칸 옆에 보여줄 최근 종가
  double? _lastClose;
  String? _lastCloseDate;

  @override
  void initState() {
    super.initState();
    if (_ticker != null && widget.initial == null) _loadQuote(_ticker!);
  }

  void _onTicker(Security? s) {
    _ticker = s?.ticker;
    setState(() => _lastClose = null);
    if (s != null) _loadQuote(s.ticker);
  }

  Future<void> _loadQuote(String ticker) async {
    try {
      final d = await context.read<AppState>().api.securityDetail(ticker);
      if (!mounted || _ticker != ticker || d.price == null) return;
      setState(() {
        _lastClose = d.price;
        _lastCloseDate = d.priceDate;
      });
    } catch (_) {
      // 종가는 참고용이라 못 받아도 입력은 계속할 수 있다
    }
  }

  static String _num(double? v) =>
      v == null ? '' : v.toString().replaceFirst(RegExp(r'\.0+$'), '');

  static String? _positive(String? v, {bool optional = false}) {
    if (v == null || v.trim().isEmpty) return optional ? null : '입력해주세요';
    final n = double.tryParse(v.replaceAll(',', ''));
    return n == null || n <= 0 ? '0보다 큰 숫자를 입력해주세요' : null;
  }

  double? _parse(TextEditingController c) =>
      c.text.trim().isEmpty ? null : double.parse(c.text.replaceAll(',', ''));

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _save() async {
    if (_ticker == null) {
      setState(() => _error = '목록에서 종목을 골라주세요.');
      return;
    }
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.read<AppState>().api.saveTransaction(TradeTransaction(
            id: widget.initial?.id,
            ticker: _ticker!,
            side: _side,
            quantity: _parse(_qty)!,
            price: _parse(_price)!,
            fxRate: _parse(_fx),
            tradedAt: _date,
            memo: _memo.text.trim(),
          ));
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final editing = widget.initial != null;
    final numberKeyboard = const TextInputType.numberWithOptions(decimal: true);
    return Scaffold(
      appBar: AppBar(title: Text(editing ? '거래 수정' : '거래 추가')),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (widget.ticker == null && !editing)
              TickerField(autoSelectExact: true, onSelected: _onTicker)
            else
              InputDecorator(
                decoration: const InputDecoration(labelText: '종목'),
                child: Text(_ticker!),
              ),
            const SizedBox(height: 16),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'BUY', label: Text('매수')),
                ButtonSegment(value: 'SELL', label: Text('매도')),
              ],
              selected: {_side},
              onSelectionChanged: (s) => setState(() => _side = s.first),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _qty,
              decoration: const InputDecoration(labelText: '수량 (주)', hintText: '소수점 가능'),
              keyboardType: numberKeyboard,
              validator: _positive,
            ),
            TextFormField(
              controller: _price,
              decoration: InputDecoration(
                labelText: '단가 (USD)',
                hintText: '보유 현황만 넣을 땐 평균 단가',
                helperText: _lastClose == null ? null : '최근 종가 ${usd(_lastClose)} ($_lastCloseDate)',
                suffixIcon: _lastClose == null
                    ? null
                    : TextButton(
                        onPressed: () => _price.text = _num(_lastClose),
                        child: const Text('종가 넣기'),
                      ),
              ),
              keyboardType: numberKeyboard,
              validator: _positive,
            ),
            TextFormField(
              controller: _fx,
              decoration: const InputDecoration(
                  labelText: '환율 (원/달러, 선택)', hintText: '비우면 거래일 기준환율로 계산'),
              keyboardType: numberKeyboard,
              validator: (v) => _positive(v, optional: true),
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('거래일'),
              subtitle: Text(day(_date)),
              trailing: const Icon(Icons.calendar_today),
              onTap: _pickDate,
            ),
            TextFormField(
              controller: _memo,
              decoration: const InputDecoration(labelText: '메모 (선택)'),
              maxLength: 200,
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            FilledButton(onPressed: _busy ? null : _save, child: const Text('저장')),
          ],
        ),
      ),
    );
  }
}
