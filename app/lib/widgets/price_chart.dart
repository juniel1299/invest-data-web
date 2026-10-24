import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../format.dart';
import '../models.dart';

final _axisDay = DateFormat('M/d');

/// 종가 선 차트. 기간 첫날보다 오르면 빨강, 내리면 파랑.
class PriceChart extends StatelessWidget {
  const PriceChart({super.key, required this.points});

  final List<PricePoint> points;

  @override
  Widget build(BuildContext context) {
    if (points.length < 2) {
      return const Center(child: Text('차트를 그릴 종가가 아직 없어요.'));
    }
    final color = pnlColor(context, points.last.close - points.first.close);
    final spots = [
      for (var i = 0; i < points.length; i++) FlSpot(i.toDouble(), points[i].close),
    ];
    final labelEvery = (points.length / 4).ceilToDouble();
    final small = Theme.of(context).textTheme.bodySmall;
    return LineChart(
      LineChartData(
        gridData: const FlGridData(show: true, drawVerticalLine: false),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(),
          rightTitles: const AxisTitles(),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 56,
              // 양 끝 값은 눈금과 겹쳐 보여서 뺀다
              getTitlesWidget: (v, meta) => v == meta.min || v == meta.max
                  ? const SizedBox()
                  : SideTitleWidget(
                      meta: meta,
                      child: Text(v.toStringAsFixed(v >= 1000 ? 0 : 1), style: small),
                    ),
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              interval: labelEvery,
              getTitlesWidget: (v, meta) {
                final i = v.toInt();
                if (i < 0 || i >= points.length || v != i.toDouble()) return const SizedBox();
                return SideTitleWidget(
                    meta: meta, child: Text(_axisDay.format(points[i].date), style: small));
              },
            ),
          ),
        ),
        lineTouchData: LineTouchData(
          touchTooltipData: LineTouchTooltipData(
            getTooltipItems: (spots) => [
              for (final s in spots)
                LineTooltipItem(
                  '${day(points[s.x.toInt()].date)}\n${usd(s.y)}',
                  const TextStyle(color: Colors.white, fontSize: 12),
                ),
            ],
          ),
        ),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            color: color,
            barWidth: 2,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(show: true, color: color.withValues(alpha: 0.08)),
          ),
        ],
      ),
    );
  }
}
