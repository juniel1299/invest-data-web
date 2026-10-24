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
docker compose exec web python manage.py seed_fomc           # FOMC 금리 결정일 넣기
docker compose exec web python manage.py update_market_data  # 지수·종가·환율·재무·뉴스·일정 바로 받기
docker compose exec web python manage.py seed_people         # 추적 인물 기본 명단 넣기
docker compose exec web python manage.py update_trades       # 13F·ARK·내부자·의원 거래 바로 받기
```

`update_market_data --only prices|macro|fundamentals|news|calendar`, `update_trades --only 13f|ark|insiders|congress`로 한 가지만 받을 수도 있습니다.

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
| GET, POST | `/api/portfolio/watches/` | 관심 종목 목록 / 추가 (`{"ticker": "AAPL"}`) |
| DELETE | `/api/portfolio/watches/<ticker>/` | 관심 종목 빼기 |
| GET | `/api/securities/<ticker>/` | 종목 상세: 종가, 52주 범위, 시가총액, PER, EPS, 배당수익률, 연간 실적, 다가오는 일정, 뉴스 |
| GET | `/api/securities/<ticker>/prices/?range=6M` | 차트용 종가 (1M, 3M, 6M, 1Y) |
| GET | `/api/market/overview/` | S&P 500·나스닥·다우·VIX·미국 10년물 금리·원/달러 환율 |
| GET | `/api/market/news/` | 보유·관심 종목 뉴스 (`?ticker=AAPL`로 한 종목만) |
| GET | `/api/market/calendar/?days=60` | FOMC와 보유·관심 종목의 실적 발표·배당 일정 |
| GET | `/api/trades/feed/?scope=mine` | 공시된 거래. `scope`: `all`, `mine`(내 보유·관심 종목), `following`. `kind`: `PRESIDENT`, `HOUSE`, `SENATE`, `INVESTOR`, `INSIDER` |
| GET | `/api/trades/people/` | 추적 인물 목록 (최근 공시일, 90일 거래 수, 팔로우 여부) |
| GET | `/api/trades/people/<slug>/` | 인물 상세: 최근 거래, 보유 상위 종목과 직전 대비 변화, 내 포트폴리오와 겹치는 비중 |
| POST, DELETE | `/api/trades/people/<slug>/follow/` | 팔로우 / 끊기 |
| GET | `/api/trades/notifications/` | 알림함 (읽지 않은 수 포함) |
| POST | `/api/trades/notifications/read/` | 모두 읽음 |
| GET | `/api/trades/principles/` | 그레이엄·린치 기준 종목 점검, 보글식 S&P 500 비교 |
| GET | `/api/digest/` | 지난 장 마감 요약 목록 (날짜, 내 포트폴리오 등락, 공시·뉴스 수) |
| GET | `/api/digest/<YYYY-MM-DD>/`, `/api/digest/latest/` | 그날 요약 (이메일과 같은 내용) |

종목 상세(`/api/securities/<ticker>/`)에는 이 종목을 거래·보유한 인물과 원칙 점검도 함께 들어 있습니다.
알림 설정(`daily_email`, `ntfy_topic`, `notify_follow`, `notify_overlap`, `notify_insider`)은 `/api/auth/me/`에서 바꿉니다.

보유 현황은 거래 내역에서 이동평균법으로 계산합니다. 보유 현황만 넣고 싶으면 평균 단가로 매수 한 건을 넣으면 됩니다.
환율을 비워두면 거래일의 ECB 기준환율을 씁니다.

## 데이터 출처 (모두 무료)

| 데이터 | 출처 | 비고 |
| --- | --- | --- |
| 종목 목록 | SEC `company_tickers_exchange.json` | `SEC_USER_AGENT` 필요 |
| 일간 종가 | Stooq CSV | 키 불필요. `PRICE_PROVIDER=tiingo` + `TIINGO_API_KEY`로 Tiingo(무료 키)로 바꿀 수 있음 |
| 원/달러 환율 | Frankfurter (ECB 기준환율) | 키 불필요, 유럽 영업일 기준 |
| 지수·금리 | FRED 공개 CSV | 키 불필요. 장 마감 다음 날 아침에 반영되는 경우가 많음 |
| 재무 (매출·순이익·EPS·발행주식수) | SEC XBRL companyfacts | `SEC_USER_AGENT` 필요. 최근 12개월은 최근 연간 + 올해 누적 − 작년 같은 기간 누적 |
| 뉴스 | Google News RSS | 키 불필요. 제목·출처·링크만 저장 |
| 실적 발표일 | Finnhub | [무료 키](https://finnhub.io/register) `FINNHUB_API_KEY`. 없으면 건너뜀 |
| 배당 | Alpha Vantage | [무료 키](https://www.alphavantage.co/support/#api-key) `ALPHA_VANTAGE_API_KEY`, 하루 25회. 없으면 건너뜀 |
| FOMC | 연준 공식 일정 | `seed_fomc` 명령으로 넣음. 새 해 일정은 명령 파일이나 관리자 화면에서 추가 |
| 투자자 분기 보유 | SEC 13F | 분기 말 보유를 직전 분기와 비교해 매매를 추정. 분기 종료 후 최대 45일 뒤 공시 |
| CUSIP → 티커 | OpenFIGI | 키 없이 사용 가능, `OPENFIGI_API_KEY`(무료)가 있으면 빠름 |
| 캐시 우드 | ARK ETF 일간 보유 CSV | 전날 대비 변화에서 ETF 설정·환매로 인한 일괄 증감을 빼고 매매로 봄 |
| 내부자·대주주 매매 | SEC Form 4 | 공개 시장 매수(P)·매도(S)만. 보유·관심 종목 회사와 버핏·애크먼·아이칸 본인 제출분 |
| 하원 의원 | 하원 Clerk 연도별 색인 + PTR PDF | 전자 제출본만 읽음. 손으로 쓴 스캔본은 원문 링크만 보여줌 |
| 상원 의원 | 상원 eFD | 약관 동의 후 검색. 법으로 상업적 이용이 제한되어 개인용으로만 씀 |
| 대통령 | OGE 278-T PDF | 자동 수집하지 않음. 관리자 화면 → 공시 → 추가에서 출처 `OGE 278-T`로 공시와 거래 줄을 입력 |
| 푸시 알림 | ntfy | 무료. 휴대폰에 ntfy 앱을 깔고 앱 설정에 적은 주제를 구독 |

## 정기 작업

Celery Beat가 미국 동부 시간 기준으로 실행합니다.

| 작업 | 시각 | 내용 |
| --- | --- | --- |
| `sync_securities_task` | 매일 05:00 ET | SEC 티커 목록으로 종목 마스터 갱신 |
| `update_market_data_task` | 평일 16:30 ET | 환율과 보유·관심 종목 종가 갱신 |
| `update_macro_task` | 평일 19:00 ET | 지수·금리 |
| `update_news_task` | 매시 10분 | 보유·관심 종목 뉴스 (종목당 최근 30건 보관) |
| `update_calendar_task` | 매일 06:00 ET | 실적 발표일·배당 (키가 있는 출처만) |
| `update_fundamentals_task` | 일요일 07:00 ET | SEC 재무 |
| `update_13f_task` | 매일 08:00 ET | 투자자 13F, 버핏·애크먼·아이칸 Form 4 |
| `update_ark_task` | 평일 21:00 ET | ARK ETF 일간 보유 변화 |
| `update_insiders_task` | 2시간마다 | 보유·관심 종목 내부자 Form 4 |
| `update_congress_task` | 매일 07:40, 13:40, 19:40 ET | 하원 PTR, 상원 eFD |
| `send_daily_summaries_task` | 거래일 17:00 ET (조기 마감일 14:00) | 장 마감 요약을 만들고 이메일 발송. 휴장일은 건너뜀 |

새 거래가 들어오면 최근 3일 안에 공시된 것만 알립니다. 팔로우한 인물의 거래, 내 보유·관심 종목을 추적 인물이 거래한 경우, 보유·관심 종목 내부자의 100만 달러 이상 매매가 대상입니다.

### 장 마감 요약 이메일

거래일마다 내 포트폴리오 등락, 많이 오르고 내린 종목, 지수·금리·환율, 그날 공시된 매매(내 종목과 겹치는 것 먼저), 내 종목 뉴스, 다음 거래일 일정을 한 통으로 보냅니다.
뉴욕증시 휴장일과 조기 마감일은 `apps/market/calendar_us.py`가 규칙으로 계산합니다. 임시 휴장(국장 등)은 그 파일의 `EXTRA_CLOSED`에 날짜를 넣으세요.
같은 내용이 앱 포트폴리오 화면 위쪽 '오늘의 정리'에도 쌓이고, 받기 싫으면 앱의 알림 설정에서 끕니다.

Gmail로 보내려면 Google 계정에서 2단계 인증을 켜고 [앱 비밀번호](https://myaccount.google.com/apppasswords)를 만든 뒤 `.env`에 넣습니다 (무료, 하루 500통).

```bash
EMAIL_URL=smtp+tls://you%40gmail.com:앱비밀번호16자리@smtp.gmail.com:587
DEFAULT_FROM_EMAIL=미국 주식 모음 <you@gmail.com>
APP_URL=http://localhost:8080
```

`EMAIL_URL`을 비워두면 메일을 보내지 않고 터미널(web·worker 로그)에 출력합니다. 앱 비밀번호의 공백은 빼고 붙여 쓰세요.

```bash
docker compose exec web python manage.py send_daily_summary --user you@gmail.com --force  # 지금 한 통 보내 보기
docker compose exec web python manage.py send_daily_summary --date 2026-10-23 --no-email  # 그날 요약만 만들기
```

### 추적 인물 바꾸기

관리자 화면 → 인물에서 추가·비활성화하고, 수집 출처(CIK, 13F·Form 4·ARK 여부, 하원 성·주, 상원 이름)를 정합니다.
현직 대통령이 바뀌면 새 인물에 '현직 대통령'을 켜고 이전 인물은 끄면 됩니다. 과거 기록은 그대로 남습니다.
`seed_people`의 CIK는 SEC EDGAR에서 한 번 확인해 주세요.

포트폴리오나 관심 종목에 처음 넣은 종목은 저장하는 즉시 종가·재무·뉴스를 받아옵니다.
종목 상세 화면을 처음 열 때도 종가와 재무가 없으면 그 자리에서 받아옵니다.
