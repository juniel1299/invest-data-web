import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';
import '../models.dart';

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);

  final int statusCode;
  final String message;

  @override
  String toString() => message;
}

/// 백엔드 API. access 토큰이 만료되면 refresh 토큰으로 한 번 다시 시도한다.
class ApiClient {
  ApiClient({http.Client? client, this.baseUrl = apiBaseUrl}) : _http = client ?? http.Client();

  final http.Client _http;
  final String baseUrl;
  String? _access;
  String? _refresh;
  void Function()? onUnauthorized;

  bool get isLoggedIn => _refresh != null;

  Future<void> loadTokens() async {
    final prefs = await SharedPreferences.getInstance();
    _access = prefs.getString('access');
    _refresh = prefs.getString('refresh');
  }

  Future<void> _saveTokens() async {
    final prefs = await SharedPreferences.getInstance();
    if (_refresh == null) {
      await prefs.remove('access');
      await prefs.remove('refresh');
    } else {
      await prefs.setString('access', _access!);
      await prefs.setString('refresh', _refresh!);
    }
  }

  Future<void> login(String email, String password) async {
    final data = await _send('POST', '/api/auth/token/',
        body: {'email': email, 'password': password}, auth: false);
    _access = data['access'];
    _refresh = data['refresh'];
    await _saveTokens();
  }

  Future<void> register(String email, String password) async {
    await _send('POST', '/api/auth/register/',
        body: {'email': email, 'password': password}, auth: false);
    await login(email, password);
  }

  Future<void> logout() async {
    _access = null;
    _refresh = null;
    await _saveTokens();
  }

  Future<Map<String, dynamic>> me() async => await _send('GET', '/api/auth/me/');

  Future<void> setDisplayCurrency(String currency) =>
      _send('PATCH', '/api/auth/me/', body: {'display_currency': currency});

  Future<List<Security>> searchSecurities(String q) async {
    final data = await _send('GET', '/api/securities/?q=${Uri.encodeQueryComponent(q)}');
    return (data as List).map((j) => Security.fromJson(j)).toList();
  }

  Future<PortfolioSummary> summary() async =>
      PortfolioSummary(await _send('GET', '/api/portfolio/summary/'));

  Future<List<TradeTransaction>> transactions({String? ticker}) async {
    final q = ticker == null ? '' : '?ticker=${Uri.encodeQueryComponent(ticker)}';
    final data = await _send('GET', '/api/portfolio/transactions/$q');
    return (data as List).map((j) => TradeTransaction.fromJson(j)).toList();
  }

  Future<void> saveTransaction(TradeTransaction t) => t.id == null
      ? _send('POST', '/api/portfolio/transactions/', body: t.toJson())
      : _send('PUT', '/api/portfolio/transactions/${t.id}/', body: t.toJson());

  Future<void> deleteTransaction(int id) => _send('DELETE', '/api/portfolio/transactions/$id/');

  Future<MarketOverview> overview() async =>
      MarketOverview(await _send('GET', '/api/market/overview/'));

  Future<List<NewsArticle>> news({String? ticker}) async {
    final q = ticker == null ? '' : '?ticker=${Uri.encodeQueryComponent(ticker)}';
    final data = await _send('GET', '/api/market/news/$q');
    return [for (final j in data as List) NewsArticle(j)];
  }

  Future<List<CalendarItem>> calendar({int days = 60}) async {
    final data = await _send('GET', '/api/market/calendar/?days=$days');
    return [for (final j in data as List) CalendarItem(j)];
  }

  Future<SecurityDetail> securityDetail(String ticker) async =>
      SecurityDetail(await _send('GET', '/api/securities/${Uri.encodeComponent(ticker)}/'));

  Future<List<PricePoint>> prices(String ticker, {String range = '6M'}) async {
    final data =
        await _send('GET', '/api/securities/${Uri.encodeComponent(ticker)}/prices/?range=$range');
    return [for (final j in data as List) PricePoint.fromJson(j)];
  }

  Future<List<Security>> watches() async {
    final data = await _send('GET', '/api/portfolio/watches/');
    return [for (final j in data as List) Security.fromJson({...j, 'exchange': ''})];
  }

  Future<void> watch(String ticker) =>
      _send('POST', '/api/portfolio/watches/', body: {'ticker': ticker});

  Future<void> unwatch(String ticker) =>
      _send('DELETE', '/api/portfolio/watches/${Uri.encodeComponent(ticker)}/');

  Future<Map<String, dynamic>> updateMe(Map<String, dynamic> fields) async =>
      Map<String, dynamic>.from(await _send('PATCH', '/api/auth/me/', body: fields));

  Future<List<Trade>> tradeFeed({String scope = 'all', String? kind}) async {
    final k = kind == null ? '' : '&kind=$kind';
    final data = await _send('GET', '/api/trades/feed/?scope=$scope$k');
    return [for (final j in data as List) Trade(j)];
  }

  Future<List<PersonSummary>> people() async {
    final data = await _send('GET', '/api/trades/people/');
    return [
      for (final j in data as List) PersonSummary(j)..isFollowing = j['is_following'] == true,
    ];
  }

  Future<PersonDetail> person(String slug) async =>
      PersonDetail(await _send('GET', '/api/trades/people/$slug/'));

  Future<void> follow(String slug, bool on) =>
      _send(on ? 'POST' : 'DELETE', '/api/trades/people/$slug/follow/');

  Future<(BogleResult, List<SecurityPrinciples>)> principles() async {
    final data = await _send('GET', '/api/trades/principles/');
    return (
      BogleResult(data['bogle']),
      [for (final s in data['securities'] as List) SecurityPrinciples(s)],
    );
  }

  Future<(int, List<AppNotification>)> notifications() async {
    final data = await _send('GET', '/api/trades/notifications/');
    return (data['unread'] as int, [for (final n in data['items'] as List) AppNotification(n)]);
  }

  Future<void> markNotificationsRead() => _send('POST', '/api/trades/notifications/read/');

  Future<dynamic> _send(String method, String path,
      {Map<String, dynamic>? body, bool auth = true, bool retried = false}) async {
    final req = http.Request(method, Uri.parse('$baseUrl$path'))
      ..headers['Content-Type'] = 'application/json';
    if (auth && _access != null) req.headers['Authorization'] = 'Bearer $_access';
    if (body != null) req.body = jsonEncode(body);

    final res = await http.Response.fromStream(await _http.send(req));
    if (res.statusCode == 401 && auth && !retried && await _refreshAccess()) {
      return _send(method, path, body: body, auth: auth, retried: true);
    }
    if (res.statusCode == 401 && auth) {
      await logout();
      onUnauthorized?.call();
    }
    final text = utf8.decode(res.bodyBytes);
    final decoded = text.isEmpty ? null : jsonDecode(text);
    if (res.statusCode >= 400) throw ApiException(res.statusCode, _errorMessage(decoded));
    return decoded;
  }

  Future<bool> _refreshAccess() async {
    if (_refresh == null) return false;
    final res = await _http.post(Uri.parse('$baseUrl/api/auth/token/refresh/'),
        headers: {'Content-Type': 'application/json'}, body: jsonEncode({'refresh': _refresh}));
    if (res.statusCode != 200) return false;
    _access = jsonDecode(res.body)['access'];
    await _saveTokens();
    return true;
  }

  /// DRF 오류 응답({"field": ["msg"]} 등)을 한 줄로 만든다.
  static String _errorMessage(Object? decoded) {
    if (decoded is Map) {
      if (decoded['detail'] != null) return decoded['detail'].toString();
      return decoded.values
          .map((v) => v is List ? v.join(' ') : v.toString())
          .join('\n');
    }
    return '요청을 처리하지 못했습니다.';
  }
}
