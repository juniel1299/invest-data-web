# invest-data-web

미국 주식 포트폴리오와 정치인·유명 투자자의 매매 공시를 한 곳에서 보는 개인용 서비스입니다.

- 백엔드: Django + Django REST Framework (`backend/`)
- 수집 작업: Celery + Redis
- DB: PostgreSQL
- 앱·웹: Flutter (`app/`, 실행 방법은 [app/README.md](app/README.md))

## 실행 (Docker)

```bash
cp .env.example .env        # SECRET_KEY, SEC_USER_AGENT 값을 채우세요
docker compose up --build
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py sync_securities     # 종목 마스터 적재
docker compose exec web python manage.py update_market_data  # 보유 종목 종가·환율 바로 받기
```

앱은 따로 띄웁니다: `cd app && flutter run -d chrome`

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
| GET, POST | `/api/portfolio/transactions/` | 내 매수·매도 내역 (`?ticker=AAPL`로 거르기) |
| GET, PUT, PATCH, DELETE | `/api/portfolio/transactions/<id>/` | 거래 한 건 수정·삭제 |
| GET, POST | `/api/portfolio/accounts/` | 계좌 (선택) |
| GET | `/api/portfolio/summary/` | 보유 현황, 평가금액, 달러·원화 수익률, 환차익 |

보유 현황은 거래 내역에서 이동평균법으로 계산합니다. 보유 현황만 넣고 싶으면 평균 단가로 매수 한 건을 넣으면 됩니다.
환율을 비워두면 거래일의 ECB 기준환율을 씁니다.

## 데이터 출처 (모두 무료)

| 데이터 | 출처 | 비고 |
| --- | --- | --- |
| 종목 목록 | SEC `company_tickers_exchange.json` | `SEC_USER_AGENT` 필요 |
| 일간 종가 | Stooq CSV | 키 불필요. `PRICE_PROVIDER=tiingo` + `TIINGO_API_KEY`로 Tiingo(무료 키)로 바꿀 수 있음 |
| 원/달러 환율 | Frankfurter (ECB 기준환율) | 키 불필요, 유럽 영업일 기준 |

## 정기 작업

Celery Beat가 미국 동부 시간 기준으로 실행합니다.

| 작업 | 시각 | 내용 |
| --- | --- | --- |
| `sync_securities_task` | 매일 05:00 ET | SEC 티커 목록으로 종목 마스터 갱신 |
| `update_market_data_task` | 평일 16:30 ET | 환율과 보유 종목 종가 갱신 |

포트폴리오에 처음 넣은 종목은 저장하는 즉시 종가와 환율을 받아옵니다.
