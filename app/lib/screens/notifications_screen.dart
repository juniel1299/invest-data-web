import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models.dart';
import '../state/app_state.dart';
import '../widgets/trade_tile.dart';

final _when = DateFormat('M/d HH:mm');

/// 앱 안 알림함. 열면 모두 읽음으로 표시한다.
class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  late Future<(int, List<AppNotification>)> _future;

  @override
  void initState() {
    super.initState();
    final api = context.read<AppState>().api;
    _future = api.notifications().then((r) async {
      if (r.$1 > 0) await api.markNotificationsRead();
      return r;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('알림')),
      body: FutureBuilder(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) return Center(child: Text('불러오지 못했습니다: ${snap.error}'));
          final (_, items) = snap.data!;
          if (items.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Text('아직 알림이 없어요.\n인물을 팔로우하거나 종목을 담아 두면, 새 거래 공시가 나올 때 알려드려요.',
                    textAlign: TextAlign.center),
              ),
            );
          }
          return ListView.separated(
            itemCount: items.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final n = items[i];
              return Container(
                color: n.read ? null : Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.25),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
                      child: Text('${n.reasonLabel} · ${_when.format(n.createdAt)}',
                          style: Theme.of(context).textTheme.labelSmall),
                    ),
                    TradeTile(trade: n.trade),
                  ],
                ),
              );
            },
          );
        },
      ),
    );
  }
}
