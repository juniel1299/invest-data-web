import 'package:flutter/material.dart';

/// 화면을 불러오지 못했을 때 이유와 다시 시도 버튼을 보여준다.
class LoadError extends StatelessWidget {
  const LoadError({super.key, required this.error, required this.onRetry, this.what = '불러오지'});

  final Object error;
  final VoidCallback onRetry;
  final String what;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off_outlined, size: 40, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text('$what 못했어요', style: text.titleMedium),
            const SizedBox(height: 4),
            Text('$error', style: text.bodySmall, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.tonalIcon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('다시 시도'),
            ),
          ],
        ),
      ),
    );
  }
}
