import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../format.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../widgets/principle_checks.dart';
import '../widgets/trade_tile.dart';
import '../widgets/load_error.dart';
import 'alert_settings_screen.dart';
import 'notifications_screen.dart';
import 'person_screen.dart';
import 'security_screen.dart';

/// 매매 탭: 공시 피드, 인물 목록, 투자 원칙 점검.
class TradesScreen extends StatefulWidget {
  const TradesScreen({super.key});

  @override
  State<TradesScreen> createState() => _TradesScreenState();
}

class _TradesScreenState extends State<TradesScreen> {
  int _unread = 0;

  @override
  void initState() {
    super.initState();
    _loadUnread();
  }

  Future<void> _loadUnread() async {
    try {
      final (unread, _) = await context.read<AppState>().api.notifications();
      if (mounted) setState(() => _unread = unread);
    } catch (_) {
      // 알림 수는 못 받아도 화면은 그린다
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('매매'),
          actions: [
            IconButton(
              tooltip: '알림',
              icon: Badge(
                isLabelVisible: _unread > 0,
                label: Text('$_unread'),
                child: const Icon(Icons.notifications_outlined),
              ),
              onPressed: () async {
                await Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen()));
                _loadUnread();
              },
            ),
            IconButton(
              tooltip: '알림 설정',
              icon: const Icon(Icons.tune),
              onPressed: () => Navigator.push(
                  context, MaterialPageRoute(builder: (_) => const AlertSettingsScreen())),
            ),
          ],
          bottom: const TabBar(tabs: [Tab(text: '거래 피드'), Tab(text: '인물'), Tab(text: '원칙 점검')]),
        ),
        body: const TabBarView(children: [_Feed(), _People(), _Principles()]),
      ),
    );
  }
}

class _Feed extends StatefulWidget {
  const _Feed();

  @override
  State<_Feed> createState() => _FeedState();
}

class _FeedState extends State<_Feed> with AutomaticKeepAliveClientMixin {
  static const _scopes = {'mine': '내 종목', 'all': '전체', 'following': '팔로우'};
  static const _kinds = {
    null: '모두',
    'PRESIDENT': '대통령',
    'HOUSE': '하원',
    'SENATE': '상원',
    'INVESTOR': '투자자',
    'INSIDER': '내부자',
  };
  String _scope = 'mine';
  String? _kind;
  late Future<List<Trade>> _future;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() {
        _future = context.read<AppState>().api.tradeFeed(scope: _scope, kind: _kind);
      });

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: SegmentedButton<String>(
            segments: [for (final e in _scopes.entries) ButtonSegment(value: e.key, label: Text(e.value))],
            selected: {_scope},
            showSelectedIcon: false,
            onSelectionChanged: (s) {
              _scope = s.first;
              _load();
            },
          ),
        ),
        SizedBox(
          height: 48,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            children: [
              for (final e in _kinds.entries)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: ChoiceChip(
                    label: Text(e.value),
                    selected: _kind == e.key,
                    onSelected: (_) {
                      _kind = e.key;
                      _load();
                    },
                  ),
                ),
            ],
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Trade>>(
            future: _future,
            builder: (context, snap) {
              if (snap.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snap.hasError) return LoadError(error: snap.error!, onRetry: _load);
              final items = snap.data!;
              if (items.isEmpty) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text(
                      _scope == 'mine'
                          ? '내 보유·관심 종목을 거래한 공시가 아직 없어요.\n전체 피드에서 다른 거래를 볼 수 있어요.'
                          : _scope == 'following'
                              ? '팔로우한 인물의 거래가 없어요.\n인물 탭에서 팔로우할 수 있어요.'
                              : '아직 모은 거래 공시가 없어요.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                );
              }
              return RefreshIndicator(
                onRefresh: () async => _load(),
                child: ListView.separated(
                  itemCount: items.length,
                  separatorBuilder: (_, _) => const Divider(height: 1, indent: 16, endIndent: 16),
                  itemBuilder: (_, i) => TradeTile(trade: items[i]),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _People extends StatefulWidget {
  const _People();

  @override
  State<_People> createState() => _PeopleState();
}

class _PeopleState extends State<_People> with AutomaticKeepAliveClientMixin {
  late Future<List<PersonSummary>> _future;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() {
        _future = context.read<AppState>().api.people();
      });

  Future<void> _toggle(PersonSummary p) async {
    final api = context.read<AppState>().api;
    try {
      await api.follow(p.slug, !p.isFollowing);
      setState(() => p.isFollowing = !p.isFollowing);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return FutureBuilder<List<PersonSummary>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) return LoadError(error: snap.error!, onRetry: _load);
        // 원칙 점검 인물은 '원칙 점검' 탭에서 다룬다
        final people = snap.data!.where((p) => p.kind != 'PRINCIPLE').toList();
        final groups = <String, List<PersonSummary>>{};
        for (final p in people) {
          groups.putIfAbsent(p.isCurrentPresident ? '현직 대통령' : p.kindLabel, () => []).add(p);
        }
        return RefreshIndicator(
          onRefresh: () async => _load(),
          child: ListView(
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              for (final g in groups.entries) ...[
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
                  child: Text(g.key, style: Theme.of(context).textTheme.titleSmall),
                ),
                for (final p in g.value)
                  ListTile(
                    title: Text(p.nameKo),
                    subtitle: Text([
                      p.title,
                      if (p.lastFiledAt != null) '최근 공시 ${p.lastFiledAt}',
                      if (p.recentTrades > 0) '90일 ${p.recentTrades}건',
                    ].where((s) => s.isNotEmpty).join(' · ')),
                    onTap: () async {
                      await Navigator.push(
                          context, MaterialPageRoute(builder: (_) => PersonScreen(slug: p.slug)));
                      _load();
                    },
                    trailing: p.isFollowing
                        ? FilledButton.tonal(onPressed: () => _toggle(p), child: const Text('팔로잉'))
                        : OutlinedButton(onPressed: () => _toggle(p), child: const Text('팔로우')),
                  ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class _Principles extends StatefulWidget {
  const _Principles();

  @override
  State<_Principles> createState() => _PrinciplesState();
}

class _PrinciplesState extends State<_Principles> with AutomaticKeepAliveClientMixin {
  late Future<(BogleResult, List<SecurityPrinciples>)> _future;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() {
        _future = context.read<AppState>().api.principles();
      });

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final text = Theme.of(context).textTheme;
    return FutureBuilder(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) return LoadError(error: snap.error!, onRetry: _load);
        final (bogle, secs) = snap.data!;
        return ListView(
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            Card(
              margin: const EdgeInsets.all(16),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('존 보글이라면', style: text.titleMedium),
                    const SizedBox(height: 4),
                    Text('같은 날 같은 금액으로 S&P 500을 사고 팔았다면', style: text.bodySmall),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(child: _Figure('내 포트폴리오', usd(bogle.myValue))),
                        Expanded(child: _Figure('S&P 500이었다면', usd(bogle.indexValue))),
                        Expanded(
                          child: _Figure('차이', signedUsd(bogle.difference),
                              color: pnlColor(context, bogle.difference)),
                        ),
                      ],
                    ),
                    if (bogle.missingIndexDays > 0)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text('지수 자료가 없는 날의 거래 ${bogle.missingIndexDays}건은 빼고 계산했어요.',
                            style: text.bodySmall),
                      ),
                    const Divider(height: 24),
                    PrincipleChecks(checks: bogle.checks),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
              child: Text('그레이엄·린치 기준으로 본 내 종목', style: text.titleMedium),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text('SEC 재무와 최근 종가로 계산한 참고용 점검이에요. ○ 통과, ✕ 미달, – 자료 없음.',
                  style: text.bodySmall),
            ),
            if (secs.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('보유하거나 관심 종목으로 담은 종목이 없어요.'),
              ),
            for (final s in secs)
              ExpansionTile(
                title: Text('${s.ticker}  ${s.name}'),
                subtitle: Text('그레이엄 ${s.score('graham')} · 린치 ${s.score('lynch')}${s.held ? '' : ' · 관심 종목'}'),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                children: [
                  Align(alignment: Alignment.centerLeft, child: Text('벤저민 그레이엄', style: text.labelLarge)),
                  PrincipleChecks(checks: s.graham),
                  const SizedBox(height: 8),
                  Align(alignment: Alignment.centerLeft, child: Text('피터 린치', style: text.labelLarge)),
                  PrincipleChecks(checks: s.lynch),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () => Navigator.push(
                          context, MaterialPageRoute(builder: (_) => SecurityScreen(ticker: s.ticker))),
                      child: const Text('종목 상세'),
                    ),
                  ),
                ],
              ),
          ],
        );
      },
    );
  }
}

class _Figure extends StatelessWidget {
  const _Figure(this.label, this.value, {this.color});

  final String label;
  final String value;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: text.labelSmall),
        Text(value, style: text.titleSmall?.copyWith(color: color)),
      ],
    );
  }
}
