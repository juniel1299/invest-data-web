import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:invest_app/api/api_client.dart';
import 'package:invest_app/format.dart';
import 'package:invest_app/models.dart';
import 'package:invest_app/widgets/trade_tile.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('summary JSON is parsed', () {
    final s = PortfolioSummary({
      'fx_rate': 1400.0,
      'totals': {
        'cost_usd': 1000.0,
        'value_usd': 1200.0,
        'pnl_usd': 200.0,
        'pnl_pct': 20.0,
        'value_krw': 1680000,
        'pnl_krw': 380000,
        'pnl_krw_pct': 29.23,
        'realized_usd': 0.0,
        'unpriced': [],
      },
      'holdings': [
        {'ticker': 'AAPL', 'name': 'Apple Inc.', 'name_ko': '애플', 'quantity': 10.0,
         'avg_price': 100.0, 'cost_usd': 1000.0, 'value_usd': 1200.0, 'pnl_pct': 20.0},
      ],
    });
    expect(s.valueKrw, 1680000);
    expect(s.holdings.single.name, '애플');
  });

  test('refreshes the access token once on 401', () async {
    var calls = 0;
    final client = MockClient((req) async {
      if (req.url.path == '/api/auth/token/') {
        return http.Response(jsonEncode({'access': 'old', 'refresh': 'r'}), 200);
      }
      if (req.url.path == '/api/auth/token/refresh/') {
        return http.Response(jsonEncode({'access': 'new'}), 200);
      }
      calls++;
      if (req.headers['Authorization'] == 'Bearer old') return http.Response('{}', 401);
      return http.Response(jsonEncode({'email': 'a@b.c', 'display_currency': 'USD'}), 200);
    });
    final api = ApiClient(client: client, baseUrl: 'http://x');
    await api.login('a@b.c', 'pw');
    final me = await api.me();
    expect(me['display_currency'], 'USD');
    expect(calls, 2);
  });

  test('DRF field errors become one message', () async {
    final api = ApiClient(
      client: MockClient((_) async => http.Response(
          jsonEncode({'quantity': ['2026-02-01에 보유 수량보다 많은 AAPL를 매도합니다.']}), 400)),
      baseUrl: 'http://x',
    );
    await expectLater(
      api.saveTransaction(TradeTransaction(
          ticker: 'AAPL', side: 'SELL', quantity: 1, price: 1, tradedAt: DateTime(2026))),
      throwsA(predicate((e) => e.toString().contains('보유 수량보다 많은'))),
    );
  });

  test('security detail JSON is parsed', () {
    final d = SecurityDetail({
      'ticker': 'AAPL', 'name': 'Apple Inc.', 'name_ko': '애플', 'price': 210.0,
      'change': 10.0, 'market_cap': 3.2e12, 'per': 30.0, 'is_watched': true,
      'annual': [{'year': 2025, 'revenue': 4e11, 'net_income': 1e11, 'eps': 6.5}],
      'events': [{'date': '2026-11-02', 'kind': 'EARNINGS', 'kind_label': '실적 발표',
        'ticker': 'AAPL', 'name': '애플', 'title': 'AAPL 실적 발표',
        'detail': {'hour': 'amc', 'eps_estimate': 1.6}}],
      'news': [],
    });
    expect(d.displayName, '애플');
    expect(d.isWatched, true);
    expect(d.annual.single.eps, 6.5);
    expect(d.events.single.description, '장 마감 후 · 예상 EPS \$1.60');
    expect(compactUsd(d.marketCap), '\$3.20T');
  });

  test('market overview keeps FX separate from indices', () {
    final o = MarketOverview({
      'indices': [{'series': 'DGS10', 'name': '미국 10년물 금리', 'value': 4.1, 'history': [4.0, 4.1]}],
      'fx': {'name': '원/달러 환율', 'value': 1400.0, 'history': []},
    });
    expect(o.indices.single.isRate, true);
    expect(o.fx.series, 'FX');
    expect(o.indices.single.history, [4.0, 4.1]);
  });

  test('politician trade shows amount range and filing delay', () {
    final t = Trade({
      'id': 1, 'person': {'slug': 'pelosi', 'name_ko': '낸시 펠로시', 'kind': 'HOUSE', 'kind_label': '하원의원'},
      'ticker': 'NVDA', 'name': '엔비디아', 'has_security': true, 'action': 'BUY', 'action_label': '매수',
      'is_buy': true, 'traded_at': '2026-10-01', 'filed_at': '2026-10-20', 'delay_days': 19,
      'amount_min': 1000001, 'amount_max': 5000000, 'owner': '배우자', 'source': 'HOUSE',
      'source_label': '하원 거래 신고', 'url': 'https://x', 'overlap': true,
    });
    expect(t.who, '낸시 펠로시');
    expect(tradeAmount(t), '\$1.0M~\$5.0M');
    expect(tradeDates(t), '거래 10/1 · 공시 10/20 (19일 뒤)');
  });

  test('insider and 13F trades', () {
    final insider = Trade({
      'id': 2, 'person': null, 'actor_name': 'Cook Timothy D', 'actor_title': 'CEO', 'ticker': 'AAPL',
      'name': '애플', 'action': 'SELL', 'action_label': '매도', 'is_buy': false, 'traded_at': null,
      'filed_at': '2026-10-21', 'shares': 10000, 'value_usd': 2505000, 'source': 'FORM4', 'source_label': 'Form 4',
    });
    expect(insider.who, 'Cook Timothy D (CEO)');
    expect(insider.kindLabel, '내부자');
    expect(tradeAmount(insider), '10,000주 · 약 \$2.5M');
    final f13 = Trade({...insider.j, 'source': '13F', 'shares': 4, 'value_usd': 900});
    expect(tradeDates(f13), '분기 말 비교 · 공시 10/21');
    expect(tradeAmount(f13), '4주 · 약 \$900');
  });

  test('digest JSON is parsed', () {
    final d = Digest({
      'date': '2026-10-23', 'early_close': false,
      'portfolio': {'value_usd': 3240.0, 'change_usd': 40.0, 'change_pct': 1.25, 'change_krw': 56000},
      'movers': {'up': [{'ticker': 'AAPL', 'name': '애플', 'change_pct': 5.0}], 'down': []},
      'market': [{'series': 'SP500', 'name': 'S&P 500', 'value': 6060.0, 'change_pct': 1.0, 'date': '2026-10-23'}],
      'trades': [], 'trade_total': 0, 'news': [], 'next_trading_day': '2026-10-26', 'tomorrow': [],
      'emailed_at': null,
    });
    expect(d.p('change_usd'), 40.0);
    expect(d.up.single['ticker'], 'AAPL');
    expect(d.nextTradingDay, DateTime(2026, 10, 26));
    expect(d.emailed, isFalse);
    expect(Digest({...d.j, 'portfolio': null}).p('value_usd'), isNull);
  });
}
