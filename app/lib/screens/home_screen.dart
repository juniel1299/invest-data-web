import 'package:flutter/material.dart';

import 'calendar_screen.dart';
import 'market_screen.dart';
import 'portfolio_screen.dart';

/// 로그인 뒤 첫 화면. 아래 탭으로 포트폴리오·시장·일정을 오간다.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _tab = 0;
  // 탭을 다시 열 때마다 새로 불러오도록 키를 바꾼다 (다른 탭에서 거래·관심 종목이 바뀌었을 수 있다)
  final _visits = [0, 0, 0];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _tab,
        children: [
          PortfolioScreen(key: ValueKey('portfolio-${_visits[0]}')),
          MarketScreen(key: ValueKey('market-${_visits[1]}')),
          CalendarScreen(key: ValueKey('calendar-${_visits[2]}')),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() {
          if (i != _tab) _visits[i]++;
          _tab = i;
        }),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.pie_chart_outline), label: '포트폴리오'),
          NavigationDestination(icon: Icon(Icons.show_chart), label: '시장'),
          NavigationDestination(icon: Icon(Icons.event_outlined), label: '일정'),
        ],
      ),
    );
  }
}
