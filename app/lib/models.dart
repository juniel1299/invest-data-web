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
