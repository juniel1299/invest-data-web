double? _d(Object? v) => v == null ? null : (v is num ? v.toDouble() : double.parse(v as String));

class Security {
  Security({required this.ticker, required this.name, this.nameKo = '', this.exchange = ''});

  final String ticker;
  final String name;
  final String nameKo;
  final String exchange;

  factory Security.fromJson(Map<String, dynamic> j) => Security(
        ticker: j['ticker'],
        name: j['name'],
        nameKo: j['name_ko'] ?? '',
        exchange: j['exchange'] ?? '',
      );

  String get displayName => nameKo.isNotEmpty ? nameKo : name;
}

class Holding {
  Holding(this.j);

  final Map<String, dynamic> j;

  String get ticker => j['ticker'];
  String get name => (j['name_ko'] as String?)?.isNotEmpty == true ? j['name_ko'] : j['name'];
  double get quantity => _d(j['quantity'])!;
  double get avgPrice => _d(j['avg_price'])!;
  double? get avgFx => _d(j['avg_fx']);
  double get costUsd => _d(j['cost_usd'])!;
  double? get lastClose => _d(j['last_close']);
  String? get lastCloseDate => j['last_close_date'];
  double? get valueUsd => _d(j['value_usd']);
  double? get pnlUsd => _d(j['pnl_usd']);
  double? get pnlPct => _d(j['pnl_pct']);
  double? get valueKrw => _d(j['value_krw']);
  double? get pnlKrw => _d(j['pnl_krw']);
  double? get pnlKrwPct => _d(j['pnl_krw_pct']);
  double? get fxPnlKrw => _d(j['fx_pnl_krw']);
  double? get weight => _d(j['weight']);
}

class PortfolioSummary {
  PortfolioSummary(this.j)
      : holdings = (j['holdings'] as List).map((h) => Holding(h)).toList();

  final Map<String, dynamic> j;
  final List<Holding> holdings;

  Map<String, dynamic> get _t => j['totals'];
  double? get fxRate => _d(j['fx_rate']);
  double get costUsd => _d(_t['cost_usd'])!;
  double get valueUsd => _d(_t['value_usd'])!;
  double get pnlUsd => _d(_t['pnl_usd'])!;
  double? get pnlPct => _d(_t['pnl_pct']);
  double? get valueKrw => _d(_t['value_krw']);
  double? get pnlKrw => _d(_t['pnl_krw']);
  double? get pnlKrwPct => _d(_t['pnl_krw_pct']);
  double? get realizedUsd => _d(_t['realized_usd']);
  List<String> get unpriced => List<String>.from(_t['unpriced']);
}

class TradeTransaction {
  TradeTransaction({
    this.id,
    required this.ticker,
    this.name = '',
    required this.side,
    required this.quantity,
    required this.price,
    this.fxRate,
    required this.tradedAt,
    this.memo = '',
  });

  final int? id;
  final String ticker;
  final String name;
  final String side; // BUY | SELL
  final double quantity;
  final double price;
  final double? fxRate;
  final DateTime tradedAt;
  final String memo;

  bool get isBuy => side == 'BUY';

  factory TradeTransaction.fromJson(Map<String, dynamic> j) => TradeTransaction(
        id: j['id'],
        ticker: j['ticker'],
        name: (j['name_ko'] as String?)?.isNotEmpty == true ? j['name_ko'] : j['name'] ?? '',
        side: j['side'],
        quantity: _d(j['quantity'])!,
        price: _d(j['price'])!,
        fxRate: _d(j['fx_rate']),
        tradedAt: DateTime.parse(j['traded_at']),
        memo: j['memo'] ?? '',
      );

  Map<String, dynamic> toJson() => {
        'ticker': ticker,
        'side': side,
        'quantity': quantity.toString(),
        'price': price.toString(),
        'fx_rate': fxRate?.toString(),
        'traded_at': tradedAt.toIso8601String().substring(0, 10),
        'memo': memo,
      };
}

List<double> _doubles(Object? v) => [for (final x in (v as List? ?? const [])) _d(x)!];

/// 지수·금리·환율 한 줄.
class MarketIndex {
  MarketIndex(this.j);

  final Map<String, dynamic> j;

  String get series => j['series'] ?? 'FX';
  String get name => j['name'];
  double? get value => _d(j['value']);
  String? get date => j['date'];
  double? get change => _d(j['change']);
  double? get changePct => _d(j['change_pct']);
  List<double> get history => _doubles(j['history']);

  /// 금리·VIX는 포인트 단위라 통화 기호 없이 보여준다.
  bool get isRate => series == 'DGS10';
}

class MarketOverview {
  MarketOverview(Map<String, dynamic> j)
      : indices = [for (final i in j['indices'] as List) MarketIndex(i)],
        fx = MarketIndex(j['fx']);

  final List<MarketIndex> indices;
  final MarketIndex fx;
}

class NewsArticle {
  NewsArticle(this.j);

  final Map<String, dynamic> j;

  String get ticker => j['ticker'];
  String get title => j['title'];
  String get url => j['url'];
  String get source => j['source'] ?? '';
  DateTime get publishedAt => DateTime.parse(j['published_at']).toLocal();
}

class CalendarItem {
  CalendarItem(this.j);

  final Map<String, dynamic> j;

  DateTime get date => DateTime.parse(j['date']);
  String get kind => j['kind'];
  String get kindLabel => j['kind_label'];
  String? get ticker => j['ticker'];
  String? get name => j['name'];
  String get title => j['title'];
  Map<String, dynamic> get detail => Map<String, dynamic>.from(j['detail'] ?? const {});

  String get description {
    final d = detail;
    switch (kind) {
      case 'EARNINGS':
        final hour = {'bmo': '장 시작 전', 'amc': '장 마감 후'}[d['hour']];
        final est = _d(d['eps_estimate']);
        return [
          ?hour,
          if (est != null) '예상 EPS \$${est.toStringAsFixed(2)}',
        ].join(' · ');
      case 'EX_DIVIDEND':
      case 'DIVIDEND_PAY':
        final amount = _d(d['amount']);
        return amount == null ? '' : '주당 \$${amount.toStringAsFixed(4)}';
      default:
        return '';
    }
  }
}

class PricePoint {
  PricePoint(this.date, this.close);

  final DateTime date;
  final double close;

  factory PricePoint.fromJson(Map<String, dynamic> j) =>
      PricePoint(DateTime.parse(j['date']), _d(j['close'])!);
}

class AnnualFinancials {
  AnnualFinancials(this.j);

  final Map<String, dynamic> j;

  int get year => j['year'];
  double? get revenue => _d(j['revenue']);
  double? get netIncome => _d(j['net_income']);
  double? get eps => _d(j['eps']);
}

class SecurityDetail {
  SecurityDetail(this.j)
      : annual = [for (final a in j['annual'] as List? ?? const []) AnnualFinancials(a)],
        events = [for (final e in j['events'] as List? ?? const []) CalendarItem(e)],
        news = [for (final n in j['news'] as List? ?? const []) NewsArticle(n)],
        isWatched = j['is_watched'] == true;

  final Map<String, dynamic> j;
  final List<AnnualFinancials> annual;
  final List<CalendarItem> events;
  final List<NewsArticle> news;
  bool isWatched;

  String get ticker => j['ticker'];
  String get name => j['name'];
  String get nameKo => j['name_ko'] ?? '';
  String get displayName => nameKo.isNotEmpty ? nameKo : name;
  String get exchange => j['exchange'] ?? '';
  double? get price => _d(j['price']);
  String? get priceDate => j['price_date'];
  double? get change => _d(j['change']);
  double? get changePct => _d(j['change_pct']);
  double? get high52w => _d(j['high_52w']);
  double? get low52w => _d(j['low_52w']);
  double? get marketCap => _d(j['market_cap']);
  double? get per => _d(j['per']);
  double? get epsTtm => _d(j['eps_ttm']);
  double? get revenueTtm => _d(j['revenue_ttm']);
  double? get netIncomeTtm => _d(j['net_income_ttm']);
  String? get fundamentalsAsOf => j['fundamentals_as_of'];
  double? get dividendTtm => _d(j['dividend_ttm']);
  double? get dividendYield => _d(j['dividend_yield']);
}
