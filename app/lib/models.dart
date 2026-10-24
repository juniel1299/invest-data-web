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
        trades = [for (final t in j['trades'] as List? ?? const []) Trade(t)],
        holders = [for (final h in j['holders'] as List? ?? const []) FamousHolder(h)],
        principles = j['principles'] == null ? null : SecurityPrinciples(j['principles']),
        isWatched = j['is_watched'] == true;

  final Map<String, dynamic> j;
  final List<AnnualFinancials> annual;
  final List<CalendarItem> events;
  final List<NewsArticle> news;
  final List<Trade> trades;
  final List<FamousHolder> holders;
  final SecurityPrinciples? principles;
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

String? _s(Object? v) => v as String?;

/// 공시된 거래 한 건 (의원·투자자·내부자).
class Trade {
  Trade(this.j);

  final Map<String, dynamic> j;

  int get id => j['id'];
  String? get personSlug => (j['person'] as Map?)?['slug'];
  String get who {
    final p = j['person'] as Map?;
    if (p != null) return p['name_ko'];
    final title = _s(j['actor_title']) ?? '';
    return title.isEmpty ? j['actor_name'] : '${j['actor_name']} ($title)';
  }

  String? get kindLabel => (j['person'] as Map?)?['kind_label'] ?? (j['person'] == null ? '내부자' : null);
  String get ticker => j['ticker'] ?? '';
  String get name => j['name'] ?? '';
  bool get hasSecurity => j['has_security'] == true;
  String get action => j['action'];
  String get actionLabel => j['action_label'];
  bool get isBuy => j['is_buy'] == true;
  DateTime? get tradedAt => j['traded_at'] == null ? null : DateTime.parse(j['traded_at']);
  DateTime get filedAt => DateTime.parse(j['filed_at']);
  int? get delayDays => j['delay_days'];
  double? get amountMin => _d(j['amount_min']);
  double? get amountMax => _d(j['amount_max']);
  double? get shares => _d(j['shares']);
  double? get price => _d(j['price']);
  double? get valueUsd => _d(j['value_usd']);
  String get owner => j['owner'] ?? '';
  String get detail => j['detail'] ?? '';
  String get source => j['source'];
  String get sourceLabel => j['source_label'];
  String get url => j['url'] ?? '';
  bool get overlap => j['overlap'] == true;
}

class PersonSummary {
  PersonSummary(this.j);

  final Map<String, dynamic> j;

  String get slug => j['slug'];
  String get name => j['name'];
  String get nameKo => j['name_ko'];
  String get kind => j['kind'];
  String get kindLabel => j['kind_label'];
  String get title => j['title'] ?? '';
  String get note => j['note'] ?? '';
  bool get isCurrentPresident => j['is_current_president'] == true;
  bool isFollowing = false;
  String? get lastFiledAt => j['last_filed_at'];
  int get recentTrades => j['recent_trades'] ?? 0;
}

class FamousHolding {
  FamousHolding(this.j);

  final Map<String, dynamic> j;

  String get ticker => j['ticker'] ?? '';
  String get name => j['name'] ?? '';
  bool get hasSecurity => j['has_security'] == true;
  double? get shares => _d(j['shares']);
  double? get valueUsd => _d(j['value_usd']);
  double? get weight => _d(j['weight']);

  /// 직전 기록 대비 주식 수 변화(%), 새로 담았으면 'NEW', 비교할 기록이 없으면 null.
  Object? get change => j['change_pct'];
}

class PersonDetail {
  PersonDetail(this.j)
      : trades = [for (final t in j['trades'] as List) Trade(t)],
        holdings = [for (final h in j['holdings'] as List) FamousHolding(h)],
        isFollowing = j['is_following'] == true;

  final Map<String, dynamic> j;
  final List<Trade> trades;
  final List<FamousHolding> holdings;
  bool isFollowing;

  String get slug => j['slug'];
  String get nameKo => j['name_ko'];
  String get name => j['name'];
  String get kind => j['kind'];
  String get kindLabel => j['kind_label'];
  String get title => j['title'] ?? '';
  String get note => j['note'] ?? '';
  bool get isCurrentPresident => j['is_current_president'] == true;
  String get sourceUrl => j['source_url'] ?? '';
  List<String> get sources => List<String>.from(j['sources'] ?? const []);
  String? get holdingsAsOf => j['holdings_as_of'];
  int get holdingsCount => j['holdings_count'] ?? 0;
  List<String> get overlapTickers => List<String>.from(j['overlap']?['tickers'] ?? const []);
  double? get overlapWeight => _d(j['overlap']?['weight']);
  List<Map<String, dynamic>> get unparsedFilings =>
      [for (final f in j['unparsed_filings'] as List? ?? const []) Map<String, dynamic>.from(f)];
}

/// 원칙 점검 한 줄. pass가 null이면 자료가 없어 판단하지 못한 것.
class PrincipleCheck {
  PrincipleCheck(this.j);

  final Map<String, dynamic> j;

  String get label => j['label'];
  String get value => j['value'];
  bool? get pass => j['pass'];
}

List<PrincipleCheck> _checks(Object? v) => [for (final c in v as List? ?? const []) PrincipleCheck(c)];

class SecurityPrinciples {
  SecurityPrinciples(this.j)
      : graham = _checks(j['graham']),
        lynch = _checks(j['lynch']);

  final Map<String, dynamic> j;
  final List<PrincipleCheck> graham;
  final List<PrincipleCheck> lynch;

  String get ticker => j['ticker'];
  String get name => j['name'] ?? '';
  bool get held => j['held'] == true;
  String score(String key) => '${j['${key}_score']['passed']}/${j['${key}_score']['checked']}';
}

class BogleResult {
  BogleResult(this.j) : checks = _checks(j['checks']);

  final Map<String, dynamic> j;
  final List<PrincipleCheck> checks;

  double? get myValue => _d(j['my_value_usd']);
  double? get indexValue => _d(j['index_value_usd']);
  double? get difference => _d(j['difference_usd']);
  int get missingIndexDays => j['missing_index_days'] ?? 0;
}

class FamousHolder {
  FamousHolder(this.j);

  final Map<String, dynamic> j;

  String get slug => j['slug'];
  String get nameKo => j['name_ko'];
  String get asOf => j['as_of'];
  double? get weight => _d(j['weight']);
  double? get valueUsd => _d(j['value_usd']);
  Object? get change => j['change_pct'];
}

class AppNotification {
  AppNotification(this.j) : trade = Trade(j['trade']);

  final Map<String, dynamic> j;
  final Trade trade;

  String get reasonLabel => j['reason_label'];
  String get title => j['title'];
  String get body => j['body'];
  DateTime get createdAt => DateTime.parse(j['created_at']).toLocal();
  bool get read => j['read'] == true;
}
