import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../format.dart';
import '../models.dart';
import '../state/app_state.dart';
import 'digest_screen.dart';
import 'security_screen.dart';
import 'transaction_form_screen.dart';

class PortfolioScreen extends StatefulWidget {
  const PortfolioScreen({super.key});

  @override
  State<PortfolioScreen> createState() => _PortfolioScreenState();
}

class _PortfolioScreenState extends State<PortfolioScreen> {
  late Future<PortfolioSummary> _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() => _future = context.read<AppState>().api.summary());

  Future<void> _open(Widget screen) async {
    final changed = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => screen));
    if (changed == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('내 포트폴리오'),
        actions: [
          TextButton(onPressed: state.toggleCurrency, child: Text(state.currency)),
          IconButton(
            onPressed: () => _open(const DigestListScreen()),
            icon: const Icon(Icons.summarize_outlined),
            tooltip: '오늘의 정리',
          ),
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh), tooltip: '새로고침'),
          IconButton(onPressed: state.logout, icon: const Icon(Icons.logout), tooltip: '로그아웃'),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _open(const TransactionFormScreen()),
        icon: const Icon(Icons.add),
        label: const Text('종목 추가'),
      ),
      body: FutureBuilder<PortfolioSummary>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('불러오지 못했습니다: ${snap.error}'));
          }
          final s = snap.data!;
          final krwMode = state.currency == 'KRW';
          return RefreshIndicator(
            onRefresh: () async => _load(),
            child: ListView(
              padding: const EdgeInsets.only(bottom: 96),
              children: [
                _TotalsCard(summary: s, krwMode: krwMode),
                if (s.holdings.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(32),
                    child: Text('아직 등록한 종목이 없어요.\n오른쪽 아래 버튼으로 보유 종목을 추가하세요.',
                        textAlign: TextAlign.center),
                  ),
                for (final h in s.holdings)
                  _HoldingTile(
                    holding: h,
                    krwMode: krwMode,
                    onTap: () => _open(SecurityScreen(ticker: h.ticker)),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _TotalsCard extends StatelessWidget {
  const _TotalsCard({required this.summary, required this.krwMode});

  final PortfolioSummary summary;
  final bool krwMode;

  @override
  Widget build(BuildContext context) {
    final s = summary;
    final text = Theme.of(context).textTheme;
    final useKrw = krwMode && s.valueKrw != null;
    final pnl = useKrw ? s.pnlKrw : s.pnlUsd;
    final pnlPct = useKrw ? s.pnlKrwPct : s.pnlPct;
    return Card(
      margin: const EdgeInsets.all(16),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('평가금액', style: text.labelLarge),
            Text(useKrw ? krw(s.valueKrw) : usd(s.valueUsd), style: text.headlineMedium),
            Text(useKrw ? usd(s.valueUsd) : krw(s.valueKrw), style: text.bodyMedium),
            const SizedBox(height: 8),
            Text(
              '${useKrw ? signedKrw(pnl) : signedUsd(pnl)}  (${pct(pnlPct)})',
              style: text.titleMedium?.copyWith(color: pnlColor(context, pnl)),
            ),
            const SizedBox(height: 8),
            Text(
              '환율 ${s.fxRate == null ? '-' : krw(s.fxRate)} · 실현손익 ${signedUsd(s.realizedUsd)}',
              style: text.bodySmall,
            ),
            if (s.unpriced.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('종가를 아직 받지 못한 종목: ${s.unpriced.join(', ')}',
                    style: text.bodySmall?.copyWith(color: Theme.of(context).colorScheme.error)),
              ),
          ],
        ),
      ),
    );
  }
}

class _HoldingTile extends StatelessWidget {
  const _HoldingTile({required this.holding, required this.krwMode, required this.onTap});

  final Holding holding;
  final bool krwMode;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final h = holding;
    final useKrw = krwMode && h.valueKrw != null;
    final pnl = useKrw ? h.pnlKrw : h.pnlUsd;
    final pnlPct = useKrw ? h.pnlKrwPct : h.pnlPct;
    return ListTile(
      onTap: onTap,
      title: Text('${h.ticker}  ${h.name}', overflow: TextOverflow.ellipsis),
      subtitle: Text('${qty(h.quantity)}주 · 평균 ${usd(h.avgPrice)}'
          '${h.weight == null ? '' : ' · 비중 ${h.weight!.toStringAsFixed(1)}%'}'),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(useKrw ? krw(h.valueKrw) : usd(h.valueUsd)),
          Text(pct(pnlPct), style: TextStyle(color: pnlColor(context, pnl))),
        ],
      ),
    );
  }
}
