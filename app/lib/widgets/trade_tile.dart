import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../format.dart';
import '../models.dart';
import '../screens/person_screen.dart';
import '../screens/security_screen.dart';

final _md = DateFormat('M/d');

/// 금액 구간(의원·대통령) 또는 주식 수·추정 금액(13F·ARK·내부자).
String tradeAmount(Trade t) {
  if (t.amountMin != null) {
    return t.amountMax == null
        ? '${shortUsd(t.amountMin!)} 이상'
        : '${shortUsd(t.amountMin!)}~${shortUsd(t.amountMax!)}';
  }
  final parts = [
    if (t.shares != null) '${qty(t.shares!)}주',
    if (t.valueUsd != null) '약 ${shortUsd(t.valueUsd!)}',
  ];
  return parts.join(' · ');
}

/// 거래일과 공시일을 함께 보여준다. 공시는 제도상 늦게 나오기 때문이다.
String tradeDates(Trade t) {
  if (t.source == '13F') return '분기 말 비교 · 공시 ${_md.format(t.filedAt)}';
  final traded = t.tradedAt == null ? '' : '거래 ${_md.format(t.tradedAt!)} · ';
  final delay = (t.delayDays ?? 0) > 1 ? ' (${t.delayDays}일 뒤)' : '';
  return '$traded공시 ${_md.format(t.filedAt)}$delay';
}

class TradeTile extends StatelessWidget {
  const TradeTile({super.key, required this.trade, this.showWho = true, this.showSecurity = true});

  final Trade trade;
  final bool showWho;
  final bool showSecurity;

  @override
  Widget build(BuildContext context) {
    final t = trade;
    final color = t.isBuy ? Colors.red.shade600 : Colors.blue.shade600;
    final text = Theme.of(context).textTheme;
    final heading = [
      if (showWho) t.who,
      if (showSecurity) [t.ticker, t.name].where((s) => s.isNotEmpty).join(' '),
    ].join(' · ');
    final sub = [
      tradeAmount(t),
      if (t.owner.isNotEmpty && t.owner != '본인') t.owner,
      if (t.detail.isNotEmpty) t.detail,
    ].where((s) => s.isNotEmpty).join(' · ');
    return ListTile(
      leading: Container(
        width: 52,
        padding: const EdgeInsets.symmetric(vertical: 6),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(t.actionLabel,
            textAlign: TextAlign.center,
            style: text.labelSmall?.copyWith(color: color, fontWeight: FontWeight.w600)),
      ),
      title: Row(
        children: [
          Flexible(child: Text(heading, overflow: TextOverflow.ellipsis)),
          if (t.overlap) ...[
            const SizedBox(width: 6),
            const _Badge('내 종목'),
          ],
        ],
      ),
      subtitle: Text([sub, tradeDates(t)].where((s) => s.isNotEmpty).join('\n')),
      isThreeLine: sub.isNotEmpty,
      trailing: t.url.isEmpty
          ? null
          : IconButton(
              icon: const Icon(Icons.description_outlined),
              tooltip: '공시 원문',
              onPressed: () => launchUrl(Uri.parse(t.url), mode: LaunchMode.externalApplication),
            ),
      onTap: () {
        // 인물 화면에서는 종목으로, 그 밖에서는 인물로 이동한다
        if (!showWho && t.hasSecurity) {
          Navigator.push(context, MaterialPageRoute(builder: (_) => SecurityScreen(ticker: t.ticker)));
        } else if (t.personSlug != null) {
          Navigator.push(context, MaterialPageRoute(builder: (_) => PersonScreen(slug: t.personSlug!)));
        } else if (t.hasSecurity) {
          Navigator.push(context, MaterialPageRoute(builder: (_) => SecurityScreen(ticker: t.ticker)));
        }
      },
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(color: scheme.primaryContainer, borderRadius: BorderRadius.circular(4)),
      child: Text(label, style: TextStyle(fontSize: 11, color: scheme.onPrimaryContainer)),
    );
  }
}
