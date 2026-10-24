import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

final _usd = NumberFormat.currency(locale: 'en_US', symbol: '\$');
final _krw = NumberFormat.currency(locale: 'ko_KR', symbol: '₩', decimalDigits: 0);
final _qty = NumberFormat('#,##0.######');

String usd(double? v) => v == null ? '-' : _usd.format(v);
String krw(double? v) => v == null ? '-' : _krw.format(v);
String qty(double v) => _qty.format(v);
String pct(double? v) => v == null ? '-' : '${v > 0 ? '+' : ''}${v.toStringAsFixed(2)}%';
String signedUsd(double? v) => v == null ? '-' : '${v > 0 ? '+' : ''}${usd(v)}';
String signedKrw(double? v) => v == null ? '-' : '${v > 0 ? '+' : ''}${krw(v)}';
String day(DateTime d) => DateFormat('yyyy-MM-dd').format(d);

/// 한국 증시 관례대로 상승은 빨강, 하락은 파랑.
Color pnlColor(BuildContext context, double? v) {
  if (v == null || v == 0) return Theme.of(context).colorScheme.onSurfaceVariant;
  return v > 0 ? Colors.red.shade600 : Colors.blue.shade600;
}

/// 큰 달러 금액을 조·억 대신 미국식 T/B/M으로 줄인다.
String compactUsd(double? v) {
  if (v == null) return '-';
  final a = v.abs();
  final sign = v < 0 ? '-' : '';
  if (a >= 1e12) return '$sign\$${(a / 1e12).toStringAsFixed(2)}T';
  if (a >= 1e9) return '$sign\$${(a / 1e9).toStringAsFixed(2)}B';
  if (a >= 1e6) return '$sign\$${(a / 1e6).toStringAsFixed(1)}M';
  return usd(v);
}

final _num = NumberFormat('#,##0.00');
String number(double? v) => v == null ? '-' : _num.format(v);
String signedNumber(double? v) => v == null ? '-' : '${v > 0 ? '+' : ''}${_num.format(v)}';
