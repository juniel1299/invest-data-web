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
