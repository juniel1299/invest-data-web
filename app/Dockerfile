# 배포용: Flutter 웹을 빌드해서 Caddy가 내보낸다. Caddy는 /api, /admin, /static 을 백엔드로 넘긴다.
FROM debian:bookworm-slim AS build

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git unzip xz-utils \
 && rm -rf /var/lib/apt/lists/*

# Flutter stable (x86 PC와 오라클 ARM 서버 모두에서 돈다)
ARG FLUTTER_VERSION=stable
RUN git clone --depth 1 --branch ${FLUTTER_VERSION} https://github.com/flutter/flutter.git /opt/flutter
ENV PATH="/opt/flutter/bin:${PATH}"
RUN flutter config --no-analytics && flutter precache --web

WORKDIR /src
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get
COPY . .
# API_BASE_URL을 비우면 앱이 자기를 내려준 주소(같은 서버)의 API를 쓴다
RUN flutter build web --release --no-web-resources-cdn --dart-define=API_BASE_URL=

FROM caddy:2-alpine
COPY --from=build /src/build/web /srv
