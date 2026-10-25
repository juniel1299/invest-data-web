import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../format.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../widgets/trade_tile.dart';
import '../widgets/load_error.dart';
import 'security_screen.dart';

final _dayLabel = DateFormat('M/d(E)', 'ko');
String _iso(DateTime d) => DateFormat('yyyy-MM-dd').format(d);

/// 거래일마다 쌓이는 장 마감 요약 목록. 이메일로 받은 것과 같은 내용이다.
class DigestListScreen extends StatefulWidget {
  const DigestListScreen({super.key});

  @override
  State<DigestListScreen> createState() => _DigestListScreenState();
}

class _DigestListScreenState extends State<DigestListScreen> {
  late Future<List<DigestBrief>> _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() {
        _future = context.read<AppState>().api.digests();
      });

  String _subtitle(DigestBrief b) => [
        if (b.changePct != null) '내 포트폴리오 ${pct(b.changePct)}',
        '공시 ${b.tradeTotal}건',
        if (b.newsCount > 0) '뉴스 ${b.newsCount}건',
      ].join(' · ');

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('오늘의 정리')),
      body: FutureBuilder<List<DigestBrief>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) return LoadError(error: snap.error!, onRetry: _load);
          final rows = snap.data!;
          if (rows.isEmpty) return const Center(child: Text('아직 요약이 없어요.'));
          return ListView.separated(
            itemCount: rows.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final b = rows[i];
              return ListTile(
                title: Text('${_dayLabel.format(b.date)} 마감${b.earlyClose ? ' (조기 마감)' : ''}'),
                subtitle: Text(_subtitle(b)),
                trailing: b.emailed ? const Icon(Icons.mark_email_read_outlined, size: 20) : null,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => DigestScreen(date: _iso(b.date))),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class DigestScreen extends StatefulWidget {
  const DigestScreen({super.key, required this.date});

  /// YYYY-MM-DD 또는 latest
  final String date;

  @override
  State<DigestScreen> createState() => _DigestScreenState();
}

class _DigestScreenState extends State<DigestScreen> {
  late Future<Digest> _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() {
        _future = context.read<AppState>().api.digest(widget.date);
      });

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Digest>(
      future: _future,
      builder: (context, snap) {
        final d = snap.data;
        return Scaffold(
          appBar: AppBar(title: Text(d == null ? '장 마감 요약' : '${_dayLabel.format(d.date)} 마감 요약')),
          body: snap.connectionState != ConnectionState.done
              ? const Center(child: CircularProgressIndicator())
              : snap.hasError
                  ? LoadError(error: snap.error!, onRetry: _load)
                  : _body(context, d!),
        );
      },
    );
  }

  Widget _section(BuildContext context, String title, List<Widget> children) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 20, 16, 6),
            child: Text(title, style: Theme.of(context).textTheme.titleMedium),
          ),
          ...children,
        ],
      );

  Widget _empty(String text) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        child: Text(text, style: const TextStyle(color: Colors.grey)),
      );

  Widget _body(BuildContext context, Digest d) {
    final text = Theme.of(context).textTheme;
    final p = d.portfolio;
    return ListView(
      padding: const EdgeInsets.only(bottom: 32),
      children: [
        if (d.earlyClose)
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Text('오늘은 조기 마감일(13:00 마감)이었어요.'),
          ),
        _section(context, '내 포트폴리오', [
          if (p == null)
            _empty('보유 종목이 없어요.')
          else
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(usd(d.p('value_usd')), style: text.headlineSmall),
                  if (d.p('value_krw') != null) Text(krw(d.p('value_krw')), style: text.bodyMedium),
                  const SizedBox(height: 8),
                  Text(
                    '오늘 ${signedUsd(d.p('change_usd'))} (${pct(d.p('change_pct'))})'
                    '${d.p('change_krw') == null ? '' : ' · ${signedKrw(d.p('change_krw'))}'}',
                    style: text.titleSmall?.copyWith(color: pnlColor(context, d.p('change_usd'))),
                  ),
                  Text('총 수익률 ${pct(d.p('pnl_pct'))}'
                      '${d.p('pnl_krw_pct') == null ? '' : ' (원화 ${pct(d.p('pnl_krw_pct'))})'}'),
                ],
              ),
            ),
          for (final m in [...d.up, ...d.down])
            ListTile(
              dense: true,
              title: Text('${m['ticker']} · ${m['name']}'),
              trailing: Text(
                pct((m['change_pct'] as num).toDouble()),
                style: TextStyle(color: pnlColor(context, (m['change_pct'] as num).toDouble())),
              ),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => SecurityScreen(ticker: m['ticker'])),
              ),
            ),
        ]),
        _section(context, '시장', [
          if (d.market.isEmpty) _empty('시장 데이터가 아직 없어요.'),
          for (final m in d.market)
            ListTile(
              dense: true,
              title: Text(m['name']),
              subtitle: Text('${m['date']} 기준'),
              trailing: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(number((m['value'] as num?)?.toDouble())),
                  Text(
                    pct((m['change_pct'] as num?)?.toDouble()),
                    style: TextStyle(color: pnlColor(context, (m['change_pct'] as num?)?.toDouble())),
                  ),
                ],
              ),
            ),
        ]),
        _section(context, '오늘 공시된 매매', [
          if (d.trades.isEmpty) _empty('새로 공시된 매매가 없어요.'),
          for (final t in d.trades) TradeTile(trade: t),
          if (d.tradeTotal > d.trades.length) _empty('전체 ${d.tradeTotal}건 중 ${d.trades.length}건만 보여드려요.'),
        ]),
        if (d.news.isNotEmpty)
          _section(context, '내 종목 뉴스', [
            for (final n in d.news)
              ListTile(
                dense: true,
                title: Text(n['title']),
                subtitle: Text('${n['ticker']}${(n['source'] ?? '').isEmpty ? '' : ' · ${n['source']}'}'),
                onTap: () => launchUrl(Uri.parse(n['url'])),
              ),
          ]),
        _section(context, '${_dayLabel.format(d.nextTradingDay)} 일정', [
          if (d.tomorrow.isEmpty) _empty('예정된 일정이 없어요.'),
          for (final e in d.tomorrow)
            ListTile(
              dense: true,
              title: Text([if (e['ticker'] != null) e['ticker'], e['kind_label']].join(' ')),
              subtitle: (e['title'] ?? '').isEmpty ? null : Text(e['title']),
            ),
        ]),
      ],
    );
  }
}
