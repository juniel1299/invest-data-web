import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/app_state.dart';

import 'calendar_screen.dart';
import 'market_screen.dart';
import 'portfolio_screen.dart';
import 'trades_screen.dart';

/// 로그인 뒤 첫 화면. 아래 탭으로 포트폴리오·시장·매매·일정을 오간다.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _tab = 0;
  // 다른 탭에서 거래·관심 종목 등이 바뀐 경우에만 키를 바꿔 다시 불러온다.
  // 바뀐 게 없으면 탭을 오가도 화면과 스크롤 위치를 그대로 둔다.
  final _visits = [0, 0, 0, 0];
  late final _seen = List.filled(4, context.read<AppState>().api.revision);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _tab,
        children: [
          PortfolioScreen(key: ValueKey('portfolio-${_visits[0]}')),
          MarketScreen(key: ValueKey('market-${_visits[1]}')),
          TradesScreen(key: ValueKey('trades-${_visits[2]}')),
          CalendarScreen(key: ValueKey('calendar-${_visits[3]}')),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) {
          final revision = context.read<AppState>().api.revision;
          setState(() {
            _seen[_tab] = revision;
            if (i != _tab && _seen[i] != revision) {
              _visits[i]++;
              _seen[i] = revision;
            }
            _tab = i;
          });
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.pie_chart_outline), label: '포트폴리오'),
          NavigationDestination(icon: Icon(Icons.show_chart), label: '시장'),
          NavigationDestination(icon: Icon(Icons.swap_horiz), label: '매매'),
          NavigationDestination(icon: Icon(Icons.event_outlined), label: '일정'),
        ],
      ),
    );
  }
}
