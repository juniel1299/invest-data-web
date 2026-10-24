import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../format.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../widgets/news_tile.dart';
import '../widgets/sparkline.dart';
import '../widgets/ticker_field.dart';
import 'security_screen.dart';

/// 지수·금리·환율 요약, 종목 검색, 관심 종목, 내 종목 뉴스.
class MarketScreen extends StatefulWidget {
  const MarketScreen({super.key});

  @override
  State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen> {
  late Future<(MarketOverview, List<Security>, List<NewsArticle>)> _future;
  int _searchKey = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    final api = context.read<AppState>().api;
    setState(() => _future = (api.overview(), api.watches(), api.news()).wait);
  }

  Future<void> _openSecurity(String ticker) async {
    await Navigator.push(
        context, MaterialPageRoute(builder: (_) => SecurityScreen(ticker: ticker)));
    // 상세 화면에서 관심 종목을 바꿨을 수 있다
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('시장'),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh), tooltip: '새로고침'),
        ],
      ),
      body: FutureBuilder(
        future: _future,
        builder: (context, snap) {
          final searchBox = Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: TickerField(
              key: ValueKey(_searchKey),
              label: '종목 검색',
              icon: Icons.search,
              onSelected: (s) {
                if (s == null) return;
                // 다음 검색을 위해 입력란을 비운다
                setState(() => _searchKey++);
                _openSecurity(s.ticker);
              },
            ),
          );
          if (snap.connectionState != ConnectionState.done) {
            return Column(children: [searchBox, const Expanded(child: Center(child: CircularProgressIndicator()))]);
          }
          if (snap.hasError) {
            return Column(children: [searchBox, Expanded(child: Center(child: Text('불러오지 못했습니다: ${snap.error}')))]);
          }
          final (overview, watches, news) = snap.data!;
          final text = Theme.of(context).textTheme;
          return RefreshIndicator(
            onRefresh: () async => _load(),
            child: ListView(
              padding: const EdgeInsets.only(bottom: 24),
              children: [
                searchBox,
                const SizedBox(height: 12),
                SizedBox(
                  height: 132,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    children: [
                      for (final i in [...overview.indices, overview.fx]) _IndexCard(index: i),
                    ],
                  ),
                ),
                _Section('관심 종목'),
                if (watches.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 16),
                    child: Text('종목을 검색해 상세 화면에서 ☆를 누르면 여기에 모여요.'),
                  ),
                for (final w in watches)
                  ListTile(
                    dense: true,
                    title: Text('${w.ticker}  ${w.displayName}'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _openSecurity(w.ticker),
                  ),
                _Section('내 종목 뉴스'),
                if (news.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Text('보유하거나 관심 종목으로 담은 종목의 뉴스가 여기에 나와요.', style: text.bodyMedium),
                  ),
                for (final n in news) NewsTile(article: n),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(this.title);

  final String title;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
        child: Text(title, style: Theme.of(context).textTheme.titleMedium),
      );
}

class _IndexCard extends StatelessWidget {
  const _IndexCard({required this.index});

  final MarketIndex index;

  @override
  Widget build(BuildContext context) {
    final i = index;
    final text = Theme.of(context).textTheme;
    final color = pnlColor(context, i.change);
    final value = i.series == 'FX' ? krw(i.value) : (i.isRate && i.value != null ? '${number(i.value)}%' : number(i.value));
    return SizedBox(
      width: 168,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(i.name, style: text.labelMedium, overflow: TextOverflow.ellipsis),
              Text(value, style: text.titleMedium),
              Text(
                i.change == null ? (i.date ?? '수집 전') : '${signedNumber(i.change)} (${pct(i.changePct)})',
                style: text.bodySmall?.copyWith(color: color),
              ),
              const SizedBox(height: 6),
              Expanded(child: Sparkline(values: i.history, color: color)),
            ],
          ),
        ),
      ),
    );
  }
}
