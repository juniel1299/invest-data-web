import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../format.dart';
import '../models.dart';
import '../state/app_state.dart';
import 'transaction_form_screen.dart';

/// 한 종목의 거래 내역. 여기서 거래를 고치거나 지우면 보유 현황이 다시 계산된다.
class HoldingScreen extends StatefulWidget {
  const HoldingScreen({super.key, required this.ticker, required this.name});

  final String ticker;
  final String name;

  @override
  State<HoldingScreen> createState() => _HoldingScreenState();
}

class _HoldingScreenState extends State<HoldingScreen> {
  late Future<List<TradeTransaction>> _future;
  bool _changed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(
      () => _future = context.read<AppState>().api.transactions(ticker: widget.ticker));

  Future<void> _edit({TradeTransaction? tx, String side = 'BUY'}) async {
    final saved = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => TransactionFormScreen(initial: tx, ticker: widget.ticker, side: side),
      ),
    );
    if (saved == true) {
      _changed = true;
      _load();
    }
  }

  Future<void> _delete(TradeTransaction tx) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('거래를 삭제할까요?'),
        content: Text('${day(tx.tradedAt)} ${tx.isBuy ? '매수' : '매도'} ${qty(tx.quantity)}주'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('취소')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('삭제')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    try {
      await context.read<AppState>().api.deleteTransaction(tx.id!);
      _changed = true;
      _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.pop(context, _changed);
      },
      child: Scaffold(
        appBar: AppBar(title: Text('${widget.ticker} ${widget.name}')),
        body: FutureBuilder<List<TradeTransaction>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) return Center(child: Text('불러오지 못했습니다: ${snap.error}'));
            final items = snap.data!;
            return ListView(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Expanded(
                        child: FilledButton.tonal(
                            onPressed: () => _edit(side: 'BUY'), child: const Text('매수 추가')),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton.tonal(
                            onPressed: () => _edit(side: 'SELL'), child: const Text('매도 추가')),
                      ),
                    ],
                  ),
                ),
                for (final tx in items)
                  ListTile(
                    leading: CircleAvatar(
                      backgroundColor: tx.isBuy ? Colors.red.shade50 : Colors.blue.shade50,
                      child: Text(tx.isBuy ? '매수' : '매도',
                          style: TextStyle(
                              fontSize: 12,
                              color: tx.isBuy ? Colors.red.shade700 : Colors.blue.shade700)),
                    ),
                    title: Text('${qty(tx.quantity)}주 × ${usd(tx.price)}'),
                    subtitle: Text([
                      day(tx.tradedAt),
                      if (tx.fxRate != null) '환율 ${krw(tx.fxRate)}',
                      if (tx.memo.isNotEmpty) tx.memo,
                    ].join(' · ')),
                    onTap: () => _edit(tx: tx),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline),
                      tooltip: '삭제',
                      onPressed: () => _delete(tx),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}
