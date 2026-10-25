import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../format.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../widgets/news_tile.dart';
import '../widgets/price_chart.dart';
import '../widgets/principle_checks.dart';
import '../widgets/trade_tile.dart';
import '../widgets/load_error.dart';
import 'calendar_screen.dart';
import 'holding_screen.dart';
import 'person_screen.dart';
import 'transaction_form_screen.dart';

const _ranges = ['1M', '3M', '6M', '1Y'];
const _rangeLabels = {'1M': '1개월', '3M': '3개월', '6M': '6개월', '1Y': '1년'};

/// 종목 상세: 가격 차트, 주요 지표, 연간 실적, 다가오는 일정, 뉴스.
class SecurityScreen extends StatefulWidget {
  const SecurityScreen({super.key, required this.ticker});

  final String ticker;

  @override
  State<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends State<SecurityScreen> {
  late Future<SecurityDetail> _detail;
  late Future<List<PricePoint>> _prices;
  String _range = '6M';
  bool _changed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    final api = context.read<AppState>().api;
    setState(() {
      _detail = api.securityDetail(widget.ticker);
      // 처음 보는 종목은 상세 요청이 종가를 받아오므로, 그 뒤에 차트를 읽는다
      _prices = _detail.then((_) => api.prices(widget.ticker, range: _range));
    });
  }

  void _setRange(String r) {
    final api = context.read<AppState>().api;
    setState(() {
      _range = r;
      _prices = api.prices(widget.ticker, range: r);
    });
  }

  Future<void> _toggleWatch(SecurityDetail d) async {
    final api = context.read<AppState>().api;
    final messenger = ScaffoldMessenger.of(context);
    try {
      d.isWatched ? await api.unwatch(d.ticker) : await api.watch(d.ticker);
      setState(() => d.isWatched = !d.isWatched);
      messenger.showSnackBar(SnackBar(
          content: Text(d.isWatched ? '관심 종목에 담았어요.' : '관심 종목에서 뺐어요.'),
          duration: const Duration(seconds: 2)));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _push(Widget screen) async {
    final changed = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => screen));
    if (changed == true) {
      _changed = true;
      _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<SecurityDetail>(
      future: _detail,
      builder: (context, snap) {
        final d = snap.data;
        final scaffold = Scaffold(
          appBar: AppBar(
            title: Text(d == null ? widget.ticker : '${d.ticker} ${d.displayName}',
                overflow: TextOverflow.ellipsis),
            actions: [
              if (d != null)
                IconButton(
                  onPressed: () => _toggleWatch(d),
                  icon: Icon(d.isWatched ? Icons.star : Icons.star_border),
                  tooltip: d.isWatched ? '관심 종목에서 빼기' : '관심 종목에 담기',
                ),
            ],
          ),
          body: switch (snap) {
            AsyncSnapshot(connectionState: != ConnectionState.done) =>
              const Center(child: CircularProgressIndicator()),
            AsyncSnapshot(:final error?) => LoadError(error: error, onRetry: _load),
            _ => _body(context, d!),
          },
        );
        // 여기서 거래를 기록했으면 포트폴리오가 다시 계산하도록 알린다
        return PopScope(
          canPop: false,
          onPopInvokedWithResult: (didPop, _) {
            if (!didPop) Navigator.pop(context, _changed);
          },
          child: scaffold,
        );
      },
    );
  }

  Widget _body(BuildContext context, SecurityDetail d) {
    final text = Theme.of(context).textTheme;
    return RefreshIndicator(
      onRefresh: () async => _load(),
      child: ListView(
        padding: const EdgeInsets.only(bottom: 32),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(d.name, style: text.bodySmall),
                Text(usd(d.price), style: text.headlineMedium),
                Text(
                  d.price == null
                      ? '아직 종가를 받지 못했어요.'
                      : '${signedUsd(d.change)} (${pct(d.changePct)}) · ${d.priceDate} 종가',
                  style: text.bodyMedium?.copyWith(color: pnlColor(context, d.change)),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 16, 16, 0),
            child: SizedBox(
              height: 220,
              child: FutureBuilder<List<PricePoint>>(
                future: _prices,
                builder: (context, snap) => snap.hasData
                    ? PriceChart(points: snap.data!)
                    : snap.hasError
                        ? LoadError(error: snap.error!, onRetry: () => _setRange(_range), what: '차트를 불러오지')
                        : const Center(child: CircularProgressIndicator()),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: SegmentedButton<String>(
              segments: [
                for (final r in _ranges) ButtonSegment(value: r, label: Text(_rangeLabels[r]!)),
              ],
              selected: {_range},
              showSelectedIcon: false,
              onSelectionChanged: (s) => _setRange(s.first),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () => _push(TransactionFormScreen(ticker: d.ticker, side: 'BUY')),
                    icon: const Icon(Icons.add),
                    label: const Text('매수 기록'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _push(HoldingScreen(ticker: d.ticker, name: d.displayName)),
                    icon: const Icon(Icons.receipt_long_outlined),
                    label: const Text('거래 내역'),
                  ),
                ),
              ],
            ),
          ),
          _title(context, '주요 지표'),
          _Stats(detail: d),
          if (d.annual.isNotEmpty) ...[
            _title(context, '연간 실적'),
            _AnnualTable(rows: d.annual),
          ],
          if (d.fundamentalsAsOf != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: Text('재무: SEC 공시 기준 (최근 12개월 = ${d.fundamentalsAsOf}까지)', style: text.bodySmall),
            ),
          if (d.events.isNotEmpty) ...[
            _title(context, '다가오는 일정'),
            for (final e in d.events) CalendarTile(item: e, showDate: true),
          ],
          if (d.holders.isNotEmpty || d.trades.isNotEmpty) ...[
            _title(context, '이 종목을 거래한 사람'),
            for (final h in d.holders)
              ListTile(
                dense: true,
                leading: const Icon(Icons.account_balance_wallet_outlined),
                title: Text('${h.nameKo} 보유 · 포트폴리오의 ${h.weight?.toStringAsFixed(1) ?? '-'}%'),
                subtitle: Text('${h.asOf} 기준 · ${h.valueUsd == null ? '-' : shortUsd(h.valueUsd!)}'
                    '${h.change == 'NEW' ? ' · 신규 편입' : ''}'),
                onTap: () => Navigator.push(
                    context, MaterialPageRoute(builder: (_) => PersonScreen(slug: h.slug))),
              ),
            for (final t in d.trades) TradeTile(trade: t, showSecurity: false),
          ],
          if (d.principles != null) ...[
            _title(context, '투자 원칙 점검'),
            ExpansionTile(
              title: Text('벤저민 그레이엄 ${d.principles!.score('graham')}'),
              subtitle: const Text('PER·PBR·그레이엄 넘버·흑자·배당'),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              children: [PrincipleChecks(checks: d.principles!.graham)],
            ),
            ExpansionTile(
              title: Text('피터 린치 ${d.principles!.score('lynch')}'),
              subtitle: const Text('EPS 성장률과 PEG'),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              children: [PrincipleChecks(checks: d.principles!.lynch)],
            ),
          ],
          _title(context, '뉴스'),
          if (d.news.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Text('아직 모은 뉴스가 없어요. 관심 종목에 담으면 한 시간마다 모아요.'),
            ),
          for (final n in d.news) NewsTile(article: n, showTicker: false),
        ],
      ),
    );
  }

  Widget _title(BuildContext context, String t) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
        child: Text(t, style: Theme.of(context).textTheme.titleMedium),
      );
}

class _Stats extends StatelessWidget {
  const _Stats({required this.detail});

  final SecurityDetail detail;

  @override
  Widget build(BuildContext context) {
    final d = detail;
    final items = [
      ('시가총액', compactUsd(d.marketCap)),
      ('PER', d.per == null ? '-' : '${d.per!.toStringAsFixed(1)}배'),
      ('EPS (12개월)', usd(d.epsTtm)),
      ('배당수익률', d.dividendYield == null ? '-' : '${d.dividendYield!.toStringAsFixed(2)}%'),
      ('52주 최고', usd(d.high52w)),
      ('52주 최저', usd(d.low52w)),
      ('매출 (12개월)', compactUsd(d.revenueTtm)),
      ('순이익 (12개월)', compactUsd(d.netIncomeTtm)),
    ];
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: LayoutBuilder(
        builder: (context, c) {
          final cols = c.maxWidth > 560 ? 4 : 2;
          final w = (c.maxWidth - (cols - 1) * 12) / cols;
          return Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              for (final (label, value) in items)
                SizedBox(
                  width: w,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(label, style: text.labelMedium),
                      Text(value, style: text.titleSmall),
                    ],
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _AnnualTable extends StatelessWidget {
  const _AnnualTable({required this.rows});

  final List<AnnualFinancials> rows;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: DataTable(
        columnSpacing: 28,
        headingRowHeight: 36,
        dataRowMinHeight: 32,
        dataRowMaxHeight: 36,
        columns: const [
          DataColumn(label: Text('회계연도')),
          DataColumn(label: Text('매출'), numeric: true),
          DataColumn(label: Text('순이익'), numeric: true),
          DataColumn(label: Text('EPS'), numeric: true),
        ],
        rows: [
          for (final r in rows.reversed)
            DataRow(cells: [
              DataCell(Text('${r.year}')),
              DataCell(Text(compactUsd(r.revenue))),
              DataCell(Text(compactUsd(r.netIncome))),
              DataCell(Text(usd(r.eps))),
            ]),
        ],
      ),
    );
  }
}
