import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../format.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../widgets/trade_tile.dart';
import 'security_screen.dart';

/// 인물 상세: 최근 거래, 보유 추정 포트폴리오, 내 포트폴리오와 겹치는 정도, 공시 원문.
class PersonScreen extends StatefulWidget {
  const PersonScreen({super.key, required this.slug});

  final String slug;

  @override
  State<PersonScreen> createState() => _PersonScreenState();
}

class _PersonScreenState extends State<PersonScreen> {
  late Future<PersonDetail> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<AppState>().api.person(widget.slug);
  }

  Future<void> _toggle(PersonDetail p) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await context.read<AppState>().api.follow(p.slug, !p.isFollowing);
      setState(() => p.isFollowing = !p.isFollowing);
      messenger.showSnackBar(SnackBar(
        content: Text(p.isFollowing ? '${p.nameKo}의 새 거래를 알려드릴게요.' : '팔로우를 끊었어요.'),
        duration: const Duration(seconds: 2),
      ));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<PersonDetail>(
      future: _future,
      builder: (context, snap) {
        final p = snap.data;
        return Scaffold(
          appBar: AppBar(title: Text(p?.nameKo ?? '')),
          body: switch (snap) {
            AsyncSnapshot(connectionState: != ConnectionState.done) =>
              const Center(child: CircularProgressIndicator()),
            AsyncSnapshot(:final error?) => Center(child: Text('불러오지 못했습니다: $error')),
            _ => _body(context, p!),
          },
        );
      },
    );
  }

  Widget _body(BuildContext context, PersonDetail p) {
    final text = Theme.of(context).textTheme;
    final isFund = p.holdings.isNotEmpty;
    return ListView(
      padding: const EdgeInsets.only(bottom: 32),
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(p.nameKo, style: text.headlineSmall),
                        Text('${p.name} · ${p.isCurrentPresident ? '현직 대통령' : p.kindLabel}', style: text.bodySmall),
                      ],
                    ),
                  ),
                  p.isFollowing
                      ? FilledButton.tonal(onPressed: () => _toggle(p), child: const Text('팔로잉'))
                      : FilledButton(onPressed: () => _toggle(p), child: const Text('팔로우')),
                ],
              ),
              const SizedBox(height: 8),
              if (p.title.isNotEmpty) Text(p.title, style: text.bodyMedium),
              if (p.note.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(p.note, style: text.bodySmall?.copyWith(color: Colors.orange.shade800)),
                ),
              if (p.sources.isNotEmpty || p.sourceUrl.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      for (final s in p.sources) Chip(label: Text(s), visualDensity: VisualDensity.compact),
                      if (p.sourceUrl.isNotEmpty)
                        TextButton.icon(
                          onPressed: () =>
                              launchUrl(Uri.parse(p.sourceUrl), mode: LaunchMode.externalApplication),
                          icon: const Icon(Icons.open_in_new, size: 16),
                          label: const Text('공시 원문 위치'),
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
        if (isFund) _overlapCard(context, p),
        if (isFund) ...[
          _title(context, '보유 상위 종목', '${p.holdingsAsOf} 기준 · 전체 ${p.holdingsCount}개'),
          for (final h in p.holdings) _HoldingRow(holding: h),
        ],
        _title(context, '최근 거래', isFund ? '13F는 분기 말 보유를 비교한 추정이에요' : null),
        if (p.trades.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16),
            child: Text('아직 모은 거래가 없어요.'),
          ),
        for (final t in p.trades) TradeTile(trade: t, showWho: false),
        if (p.unparsedFilings.isNotEmpty) ...[
          _title(context, '내용을 읽지 못한 공시', '손으로 쓴 스캔본 등은 원문으로 확인하세요'),
          for (final f in p.unparsedFilings)
            ListTile(
              dense: true,
              leading: const Icon(Icons.picture_as_pdf_outlined),
              title: Text('${f['source_label']} · ${f['filed_at']}'),
              onTap: () => launchUrl(Uri.parse(f['url']), mode: LaunchMode.externalApplication),
            ),
        ],
      ],
    );
  }

  Widget _overlapCard(BuildContext context, PersonDetail p) {
    final text = Theme.of(context).textTheme;
    final w = p.overlapWeight ?? 0;
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('내 포트폴리오와 겹치는 종목', style: text.labelLarge),
            const SizedBox(height: 4),
            Text(
              p.overlapTickers.isEmpty
                  ? '겹치는 종목이 없어요.'
                  : '${p.overlapTickers.join(', ')} · ${p.nameKo} 포트폴리오의 ${w.toStringAsFixed(1)}%',
              style: text.titleMedium,
            ),
          ],
        ),
      ),
    );
  }

  Widget _title(BuildContext context, String t, [String? sub]) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(t, style: Theme.of(context).textTheme.titleMedium),
            if (sub != null) Text(sub, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      );
}

final _pct = NumberFormat('+0.0;-0.0');

class _HoldingRow extends StatelessWidget {
  const _HoldingRow({required this.holding});

  final FamousHolding holding;

  @override
  Widget build(BuildContext context) {
    final h = holding;
    final c = h.change;
    final (label, color) = switch (c) {
      'NEW' => ('신규', Colors.red.shade600),
      num v when v > 0 => ('${_pct.format(v)}%', Colors.red.shade600),
      num v when v < 0 => ('${_pct.format(v)}%', Colors.blue.shade600),
      _ => ('', null),
    };
    return ListTile(
      dense: true,
      title: Text('${h.ticker}  ${h.name}', overflow: TextOverflow.ellipsis),
      subtitle: Text('${h.weight?.toStringAsFixed(1) ?? '-'}% · ${h.valueUsd == null ? '-' : shortUsd(h.valueUsd!)}'),
      trailing: label.isEmpty ? null : Text(label, style: TextStyle(color: color)),
      onTap: h.hasSecurity
          ? () => Navigator.push(context, MaterialPageRoute(builder: (_) => SecurityScreen(ticker: h.ticker)))
          : null,
    );
  }
}
