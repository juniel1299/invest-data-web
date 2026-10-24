import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models.dart';

final _when = DateFormat('M/d HH:mm');

/// 뉴스 제목 한 줄. 누르면 원문을 브라우저로 연다.
class NewsTile extends StatelessWidget {
  const NewsTile({super.key, required this.article, this.showTicker = true});

  final NewsArticle article;
  final bool showTicker;

  @override
  Widget build(BuildContext context) {
    final a = article;
    return ListTile(
      title: Text(a.title, maxLines: 2, overflow: TextOverflow.ellipsis),
      subtitle: Text([
        if (showTicker) a.ticker,
        if (a.source.isNotEmpty) a.source,
        _when.format(a.publishedAt),
      ].join(' · ')),
      trailing: const Icon(Icons.open_in_new, size: 18),
      onTap: () => launchUrl(Uri.parse(a.url), mode: LaunchMode.externalApplication),
    );
  }
}
