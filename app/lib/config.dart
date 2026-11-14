/// 백엔드 주소. 실행할 때 바꿀 수 있다:
/// flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
///
/// 배포용 웹 빌드는 `--dart-define=API_BASE_URL=` 처럼 비워 두면
/// 웹 페이지를 내려준 주소(같은 서버)의 API를 쓴다.
const _apiBaseUrlDefine = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
);

String get apiBaseUrl => _apiBaseUrlDefine.isEmpty ? Uri.base.origin : _apiBaseUrlDefine;
