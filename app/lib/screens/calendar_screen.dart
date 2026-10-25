import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models.dart';
import '../state/app_state.dart';
import 'security_screen.dart';

final _dayHeader = DateFormat('M월 d일 (E)', 'ko');

/// 앞으로 60일 동안의 FOMC, 내 종목 실적 발표·배당 일정.
class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  late Future<List<CalendarItem>> _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() {
        _future = context.read<AppState>().api.calendar(days: 60);
      });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('일정'),
        actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh), tooltip: '새로고침')],
      ),
      body: FutureBuilder<List<CalendarItem>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) return Center(child: Text('불러오지 못했습니다: ${snap.error}'));
          final items = snap.data!;
          if (items.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Text('앞으로 60일 동안 잡힌 일정이 없어요.\n보유·관심 종목의 실적 발표와 배당, FOMC가 여기에 나와요.',
                    textAlign: TextAlign.center),
              ),
            );
          }
          final children = <Widget>[];
          DateTime? current;
          for (final e in items) {
            if (current != e.date) {
              current = e.date;
              children.add(Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
                child: Text(_dayHeader.format(e.date), style: Theme.of(context).textTheme.titleSmall),
              ));
            }
            children.add(CalendarTile(item: e));
          }
          return RefreshIndicator(
            onRefresh: () async => _load(),
            child: ListView(padding: const EdgeInsets.only(bottom: 24), children: children),
          );
        },
      ),
    );
  }
}

class CalendarTile extends StatelessWidget {
  const CalendarTile({super.key, required this.item, this.showDate = false});

  final CalendarItem item;
  final bool showDate;

  static const _icons = {
    'EARNINGS': Icons.campaign_outlined,
    'EX_DIVIDEND': Icons.content_cut,
    'DIVIDEND_PAY': Icons.payments_outlined,
    'FOMC': Icons.account_balance_outlined,
  };

  @override
  Widget build(BuildContext context) {
    final e = item;
    final sub = [
      if (showDate) DateFormat('M/d (E)', 'ko').format(e.date),
      // FOMC처럼 종목 없는 일정은 제목이 곧 종류다
      if (e.ticker != null) e.kindLabel,
      if (e.description.isNotEmpty) e.description,
    ].join(' · ');
    return ListTile(
      leading: Icon(_icons[e.kind] ?? Icons.event),
      title: Text(e.ticker == null ? e.title : '${e.ticker}  ${e.name ?? ''}'),
      subtitle: sub.isEmpty ? null : Text(sub),
      onTap: e.ticker == null
          ? null
          : () => Navigator.push(
              context, MaterialPageRoute(builder: (_) => SecurityScreen(ticker: e.ticker!))),
    );
  }
}
