# invest_app (Flutter)

웹, 안드로이드, 아이폰에서 같은 코드로 도는 앱입니다. 백엔드(`../backend`)가 먼저 떠 있어야 합니다.

## 실행

```bash
flutter pub get

# 웹 (크롬)
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000

# 안드로이드 에뮬레이터: 에뮬레이터에서 내 PC는 10.0.2.2 입니다
flutter run -d emulator-5554 --dart-define=API_BASE_URL=http://10.0.2.2:8000

# 실제 폰: PC와 같은 와이파이에서 PC의 IP를 넣습니다
flutter run --dart-define=API_BASE_URL=http://192.168.0.10:8000
```

폰에서 PC의 백엔드에 붙으려면 `.env`의 `ALLOWED_HOSTS`에 PC IP를 추가하고,
백엔드를 `0.0.0.0:8000`으로 띄워야 합니다(Docker Compose는 이미 그렇게 뜹니다).

## 내 폰에 설치 (앱스토어 없이, 무료)

- 안드로이드: `flutter build apk --dart-define=API_BASE_URL=http://<PC IP>:8000` 후
  `build/app/outputs/flutter-apk/app-release.apk`를 폰으로 옮겨 설치
- 아이폰: Xcode에서 무료 Apple ID로 서명해 내 기기에 설치 (7일마다 다시 설치 필요)

## 테스트

```bash
flutter analyze
flutter test
```
