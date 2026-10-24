import 'package:flutter/material.dart';

import '../models.dart';

/// 원칙 점검 줄 목록. ○ 통과, ✕ 미달, – 자료 없음.
class PrincipleChecks extends StatelessWidget {
  const PrincipleChecks({super.key, required this.checks});

  final List<PrincipleCheck> checks;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      children: [
        for (final c in checks)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Row(
              children: [
                SizedBox(
                  width: 24,
                  child: Text(
                    c.pass == null ? '–' : (c.pass! ? '○' : '✕'),
                    style: text.titleSmall?.copyWith(
                      color: c.pass == null
                          ? Theme.of(context).colorScheme.outline
                          : (c.pass! ? Colors.green.shade700 : Colors.orange.shade800),
                    ),
                  ),
                ),
                Expanded(child: Text(c.label, style: text.bodyMedium)),
                Text(c.value, style: text.bodyMedium),
              ],
            ),
          ),
      ],
    );
  }
}
