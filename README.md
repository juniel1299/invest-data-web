# invest-data-web

미국 주식 포트폴리오와 정치인·유명 투자자의 매매 공시를 한 곳에서 보는 개인용 서비스입니다.

- 백엔드: Django + Django REST Framework (`backend/`)
- 수집 작업: Celery + Redis
- DB: PostgreSQL
- 앱·웹: Flutter (예정)

## 실행 (Docker)

```bash
cp .env.example .env        # SECRET_KEY, SEC_USER_AGENT 값을 채우세요
docker compose up --build
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py sync_securities   # 종목 마스터 적재
```

- API: http://localhost:8000/api/health/
- 관리자 화면: http://localhost:8000/admin/

## 실행 (Docker 없이)

SQLite로 바로 돌려볼 수 있습니다. Celery 작업은 Redis가 있어야 동작합니다.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py test
python manage.py runserver
```

## API

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/auth/register/` | 회원가입 (email, password) |
| POST | `/api/auth/token/` | 로그인, access/refresh 토큰 발급 |
| POST | `/api/auth/token/refresh/` | access 토큰 재발급 |
| GET, PATCH | `/api/auth/me/` | 내 정보, 표시 통화(KRW/USD) 변경 |
| GET | `/api/securities/?q=apple` | 종목 검색 (티커·영문명·한글명) |

## 정기 작업

Celery Beat가 미국 동부 시간 기준으로 실행합니다.

| 작업 | 시각 | 내용 |
| --- | --- | --- |
| `sync_securities_task` | 매일 05:00 ET | SEC 티커 목록으로 종목 마스터 갱신 |
