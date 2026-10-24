import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/app_state.dart';

/// 알림 종류 켜기·끄기와 ntfy 푸시 주제.
class AlertSettingsScreen extends StatefulWidget {
  const AlertSettingsScreen({super.key});

  @override
  State<AlertSettingsScreen> createState() => _AlertSettingsScreenState();
}

class _AlertSettingsScreenState extends State<AlertSettingsScreen> {
  final _topic = TextEditingController();
  Map<String, dynamic>? _me;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    context.read<AppState>().api.me().then((me) {
      if (!mounted) return;
      setState(() {
        _me = Map<String, dynamic>.from(me);
        _topic.text = me['ntfy_topic'] ?? '';
      });
    });
  }

  @override
  void dispose() {
    _topic.dispose();
    super.dispose();
  }

  Future<void> _save(Map<String, dynamic> fields) async {
    setState(() => _saving = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final me = await context.read<AppState>().api.updateMe(fields);
      setState(() => _me = me);
      messenger.showSnackBar(const SnackBar(content: Text('저장했어요.'), duration: Duration(seconds: 2)));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _switch(String key, String title, String subtitle) => SwitchListTile(
        title: Text(title),
        subtitle: Text(subtitle),
        value: _me![key] == true,
        onChanged: _saving ? null : (v) => _save({key: v}),
      );

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('알림 설정')),
      body: _me == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                _switch('daily_email', '장 마감 요약 이메일',
                    '거래일마다 미국 동부 17:00(한국 아침 6~7시)에 ${_me!['email']}로 보내요'),
                const Divider(height: 32),
                _switch('notify_overlap', '내 종목을 누가 거래하면', '보유·관심 종목을 추적 인물이 사고팔았을 때'),
                _switch('notify_follow', '팔로우한 인물의 새 거래', '팔로우한 인물의 모든 새 공시'),
                _switch('notify_insider', '내부자 대량 매매', '보유·관심 종목 임원·대주주의 100만 달러 이상 매매'),
                const Divider(height: 32),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('휴대폰 푸시 (ntfy)', style: text.titleMedium),
                      const SizedBox(height: 4),
                      Text(
                        '무료 앱 ntfy를 설치하고, 아래에 적은 주제 이름을 앱에서 구독하면 푸시가 와요. '
                        '주제 이름을 아는 사람은 누구나 알림을 볼 수 있으니 추측하기 어려운 이름으로 정하세요. '
                        '비워두면 앱 안 알림함에만 쌓여요.',
                        style: text.bodySmall,
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _topic,
                        decoration: const InputDecoration(
                          labelText: 'ntfy 주제',
                          hintText: '예: invest-a8f3k2x9',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      FilledButton(
                        onPressed: _saving ? null : () => _save({'ntfy_topic': _topic.text.trim()}),
                        child: const Text('주제 저장'),
                      ),
                    ],
                  ),
                ),
              ],
            ),
    );
  }
}
