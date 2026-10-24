/// 백엔드 주소. 실행할 때 바꿀 수 있다:
/// flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
);
