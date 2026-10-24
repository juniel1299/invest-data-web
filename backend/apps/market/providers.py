"""무료 시세·환율 출처.

- 종가: Stooq CSV (키 불필요, 기본값) 또는 Tiingo (무료 키, PRICE_PROVIDER=tiingo)
- 환율: Frankfurter (ECB 기준환율, 키 불필요)
"""

import csv
import io
from datetime import date
from decimal import Decimal

import httpx
from django.conf import settings

STOOQ_URL = "https://stooq.com/q/d/l/"
TIINGO_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/{start}..{end}"


class ProviderError(Exception):
    pass


def _symbol(ticker):
    # BRK.B 같은 클래스 주식은 두 출처 모두 하이픈을 쓴다
    return ticker.replace(".", "-")


def fetch_closes_stooq(client, ticker, start, end):
    params = {
        "s": f"{_symbol(ticker).lower()}.us",
        "i": "d",
        "d1": start.strftime("%Y%m%d"),
        "d2": end.strftime("%Y%m%d"),
    }
    res = client.get(STOOQ_URL, params=params)
    res.raise_for_status()
    text = res.text.strip()
    if not text or text.lower().startswith("no data"):
        return []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "Close" not in reader.fieldnames:
        raise ProviderError(f"Stooq 응답 형식이 예상과 다릅니다: {text[:80]!r}")
    return [(date.fromisoformat(row["Date"]), Decimal(row["Close"])) for row in reader]


def fetch_closes_tiingo(client, ticker, start, end):
    if not settings.TIINGO_API_KEY:
        raise ProviderError("TIINGO_API_KEY가 설정되지 않았습니다.")
    res = client.get(
        TIINGO_URL.format(ticker=_symbol(ticker)),
        params={
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "token": settings.TIINGO_API_KEY,
        },
    )
    if res.status_code == 404:
        return []
    res.raise_for_status()
    return [(date.fromisoformat(row["date"][:10]), Decimal(str(row["close"]))) for row in res.json()]


def fetch_closes(client, ticker, start, end):
    if settings.PRICE_PROVIDER == "tiingo":
        return fetch_closes_tiingo(client, ticker, start, end)
    return fetch_closes_stooq(client, ticker, start, end)


def fetch_usd_krw(client, start, end):
    res = client.get(
        FRANKFURTER_URL.format(start=start.isoformat(), end=end.isoformat()),
        params={"base": "USD", "symbols": "KRW"},
    )
    res.raise_for_status()
    rates = res.json().get("rates", {})
    return [(date.fromisoformat(day), Decimal(str(v["KRW"]))) for day, v in rates.items()]


# ---------------------------------------------------------------- 시장 지표 (FRED)

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fetch_fred_series(client, series_id, start):
    """FRED 공개 CSV (키 불필요). 휴장일 값은 '.'로 와서 건너뛴다."""
    res = client.get(FRED_CSV_URL, params={"id": series_id, "cosd": start.isoformat()})
    res.raise_for_status()
    rows = list(csv.reader(io.StringIO(res.text.strip())))
    if not rows or len(rows[0]) < 2:
        raise ProviderError(f"FRED {series_id} 응답 형식이 예상과 다릅니다.")
    out = []
    for day, value in (r[:2] for r in rows[1:] if len(r) >= 2):
        if value in (".", ""):
            continue
        out.append((date.fromisoformat(day), Decimal(value)))
    return out


# ---------------------------------------------------------------- 재무 (SEC XBRL)

SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


def fetch_company_facts(client, cik):
    res = client.get(SEC_FACTS_URL.format(cik=cik), headers={"User-Agent": settings.SEC_USER_AGENT})
    if res.status_code == 404:
        return None
    res.raise_for_status()
    return res.json()


# ---------------------------------------------------------------- 뉴스 (Google News RSS)

GOOGLE_NEWS_URL = "https://news.google.com/rss/search"


def fetch_news(client, ticker, name):
    """제목·출처·링크·시각만 가져온다. 본문은 저장하지 않는다."""
    from email.utils import parsedate_to_datetime

    import defusedxml.ElementTree as ET

    query = f'"{ticker}" OR "{name}" stock'
    res = client.get(
        GOOGLE_NEWS_URL, params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    )
    res.raise_for_status()
    root = ET.fromstring(res.content)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate")
        if not (title and link and pub):
            continue
        source = (item.findtext("source") or "").strip()
        # Google News 제목은 "제목 - 출처" 형식이라 출처 부분을 뗀다
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        items.append(
            {"title": title, "url": link, "source": source, "published_at": parsedate_to_datetime(pub)}
        )
    return items


# ---------------------------------------------------------------- 실적 발표일 (Finnhub, 무료 키)

FINNHUB_EARNINGS_URL = "https://finnhub.io/api/v1/calendar/earnings"


def fetch_earnings(client, ticker, start, end):
    if not settings.FINNHUB_API_KEY:
        raise ProviderError("FINNHUB_API_KEY가 설정되지 않았습니다.")
    res = client.get(
        FINNHUB_EARNINGS_URL,
        params={
            "symbol": ticker,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "token": settings.FINNHUB_API_KEY,
        },
    )
    res.raise_for_status()
    return res.json().get("earningsCalendar", [])


# ---------------------------------------------------------------- 배당 (Alpha Vantage, 무료 키)

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


def fetch_dividends(client, ticker):
    if not settings.ALPHA_VANTAGE_API_KEY:
        raise ProviderError("ALPHA_VANTAGE_API_KEY가 설정되지 않았습니다.")
    res = client.get(
        ALPHA_VANTAGE_URL,
        params={"function": "DIVIDENDS", "symbol": ticker, "apikey": settings.ALPHA_VANTAGE_API_KEY},
    )
    res.raise_for_status()
    payload = res.json()
    if "data" not in payload:
        # 무료 한도(하루 25회)를 넘으면 {"Information": "..."}가 온다
        raise ProviderError(str(payload.get("Information") or payload.get("Note") or payload)[:200])

    def day(v):
        return date.fromisoformat(v) if v and v != "None" else None

    return [
        {
            "ex_date": day(r.get("ex_dividend_date")),
            "pay_date": day(r.get("payment_date")),
            "amount": Decimal(r["amount"]),
        }
        for r in payload["data"]
        if day(r.get("ex_dividend_date"))
    ]
