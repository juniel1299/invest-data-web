import 'package:flutter/foundation.dart';

import '../api/api_client.dart';

/// 로그인 상태와 표시 통화를 들고 있다.
class AppState extends ChangeNotifier {
  AppState(this.api) {
    api.onUnauthorized = () => notifyListeners();
  }

  final ApiClient api;
  bool ready = false;
  String currency = 'KRW';

  bool get loggedIn => api.isLoggedIn;

  Future<void> init() async {
    await api.loadTokens();
    if (api.isLoggedIn) await _loadMe();
    ready = true;
    notifyListeners();
  }

  Future<void> login(String email, String password, {bool register = false}) async {
    register ? await api.register(email, password) : await api.login(email, password);
    await _loadMe();
    notifyListeners();
  }

  Future<void> logout() async {
    await api.logout();
    notifyListeners();
  }

  Future<void> toggleCurrency() async {
    currency = currency == 'KRW' ? 'USD' : 'KRW';
    notifyListeners();
    await api.setDisplayCurrency(currency);
  }

  Future<void> _loadMe() async {
    try {
      currency = (await api.me())['display_currency'] ?? 'KRW';
    } on ApiException {
      // 토큰이 만료됐으면 ApiClient가 로그아웃 처리한다
    }
  }
}
