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
