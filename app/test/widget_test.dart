import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:invest_app/api/api_client.dart';
import 'package:invest_app/format.dart';
import 'package:invest_app/models.dart';
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
}
