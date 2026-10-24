from datetime import date, timedelta
from decimal import Decimal

import httpx
from django.db.models import Max, Min, Q

from apps.securities.models import Security

from .fundamentals import parse_company_facts
from .models import CalendarEvent, Fundamentals, FxRate, MacroPoint, NewsItem, PriceDaily
from .providers import (
    fetch_closes,
    fetch_company_facts,
    fetch_dividends,
    fetch_earnings,
    fetch_fred_series,
    fetch_news,
    fetch_usd_krw,
)

# 처음 수집할 때 가져올 기간
INITIAL_LOOKBACK_DAYS = 400


def _client(client):
    return client or httpx.Client(timeout=30, follow_redirects=True)


def update_prices(security, client=None, today=None):
    """마지막으로 저장한 날 다음부터 오늘까지 종가를 받아 저장한다. 저장한 건수를 돌려준다."""
    today = today or date.today()
    last = security.prices.aggregate(d=Max("date"))["d"]
    start = last + timedelta(days=1) if last else today - timedelta(days=INITIAL_LOOKBACK_DAYS)
    if start > today:
        return 0
    owns = client is None
    client = _client(client)
    try:
        rows = fetch_closes(client, security.ticker, start, today)
    finally:
        if owns:
            client.close()
    PriceDaily.objects.bulk_create(
        [PriceDaily(security=security, date=d, close=c) for d, c in rows],
        ignore_conflicts=True,
    )
    return len(rows)


def tracked_securities():
    """누군가 보유했거나 관심 종목으로 담은 종목. 시세·뉴스·일정은 이 종목들만 모은다."""
    return Security.objects.filter(
        Q(transactions__isnull=False) | Q(watchers__isnull=False)
    ).distinct()


def update_fx(client=None, today=None):
    """원/달러 환율을 채운다. 가장 오래된 거래일까지 거슬러 올라가 매수 시점 환율을 쓸 수 있게 한다."""
    from apps.portfolio.models import Transaction

    today = today or date.today()
    last = FxRate.objects.aggregate(d=Max("date"))["d"]
    first_trade = Transaction.objects.aggregate(d=Min("traded_at"))["d"]
    first_fx = FxRate.objects.aggregate(d=Min("date"))["d"]

    ranges = []
    default_start = today - timedelta(days=INITIAL_LOOKBACK_DAYS)
    if last is None:
        ranges.append((min(filter(None, [first_trade, default_start])), today))
    else:
        if last < today:
            ranges.append((last + timedelta(days=1), today))
        if first_trade and first_fx and first_trade < first_fx:
            ranges.append((first_trade, first_fx - timedelta(days=1)))

    owns = client is None
    client = _client(client)
    saved = 0
    try:
        for start, end in ranges:
            rows = fetch_usd_krw(client, start, end)
            FxRate.objects.bulk_create(
                [FxRate(date=d, usd_krw=r) for d, r in rows], ignore_conflicts=True
            )
            saved += len(rows)
    finally:
        if owns:
            client.close()
    return saved


def latest_close(security):
    return security.prices.order_by("-date").first()


def fx_on(day=None):
    """그날(없으면 그 이전 가장 가까운 날)의 환율. day가 없으면 최신 환율."""
    qs = FxRate.objects.all()
    if day:
        qs = qs.filter(date__lte=day)
    row = qs.order_by("-date").first()
    return row.usd_krw if row else None


# ---------------------------------------------------------------- 시장 지표

MACRO_SERIES = {
    "SP500": "S&P 500",
    "NASDAQCOM": "나스닥 종합",
    "DJIA": "다우존스",
    "VIXCLS": "VIX",
    "DGS10": "미국 10년물 금리",
}


BENCHMARK_SERIES = "SP500"


def _first_trade_date():
    from apps.portfolio.models import Transaction

    return Transaction.objects.aggregate(d=Min("traded_at"))["d"]


def update_macro(client=None, today=None):
    today = today or date.today()
    owns = client is None
    client = _client(client)
    saved = {}
    try:
        for series in MACRO_SERIES:
            last = MacroPoint.objects.filter(series=series).aggregate(d=Max("date"))["d"]
            start = last + timedelta(days=1) if last else today - timedelta(days=INITIAL_LOOKBACK_DAYS)
            if series == BENCHMARK_SERIES:
                # 보글 비교(같은 날 S&P 500을 샀다면)를 위해 첫 거래일까지 채운다
                first = _first_trade_date()
                first_saved = MacroPoint.objects.filter(series=series).aggregate(d=Min("date"))["d"]
                if first and first_saved and first < first_saved:
                    rows = fetch_fred_series(client, series, first)
                    MacroPoint.objects.bulk_create(
                        [MacroPoint(series=series, date=d, value=v) for d, v in rows if d < first_saved],
                        ignore_conflicts=True,
                    )
                elif first and not first_saved:
                    start = min(start, first)
            if start > today:
                continue
            rows = fetch_fred_series(client, series, start)
            MacroPoint.objects.bulk_create(
                [MacroPoint(series=series, date=d, value=v) for d, v in rows], ignore_conflicts=True
            )
            saved[series] = len(rows)
    finally:
        if owns:
            client.close()
    return saved


# ---------------------------------------------------------------- 재무

def update_fundamentals(security, client=None):
    if not security.cik:
        return None
    owns = client is None
    client = _client(client)
    try:
        facts = fetch_company_facts(client, security.cik)
    finally:
        if owns:
            client.close()
    if facts is None:
        return None
    obj, _ = Fundamentals.objects.update_or_create(security=security, defaults=parse_company_facts(facts))
    return obj


# ---------------------------------------------------------------- 뉴스

NEWS_KEEP_PER_SECURITY = 30


def update_news(security, client=None):
    owns = client is None
    client = _client(client)
    try:
        items = fetch_news(client, security.ticker, security.name)
    finally:
        if owns:
            client.close()
    NewsItem.objects.bulk_create(
        [NewsItem(security=security, **{**i, "title": i["title"][:500]}) for i in items],
        ignore_conflicts=True,
    )
    keep = security.news.order_by("-published_at").values_list("id", flat=True)[:NEWS_KEEP_PER_SECURITY]
    security.news.exclude(id__in=list(keep)).delete()
    return len(items)


# ---------------------------------------------------------------- 일정

EARNINGS_LOOKAHEAD_DAYS = 90


def update_earnings(security, client=None, today=None):
    today = today or date.today()
    owns = client is None
    client = _client(client)
    try:
        rows = fetch_earnings(
            client, security.ticker, today - timedelta(days=7), today + timedelta(days=EARNINGS_LOOKAHEAD_DAYS)
        )
    finally:
        if owns:
            client.close()
    for r in rows:
        symbol = (r.get("symbol") or security.ticker).upper()
        if symbol not in {security.ticker, security.ticker.replace(".", "-")}:
            continue
        CalendarEvent.objects.update_or_create(
            kind=CalendarEvent.Kind.EARNINGS,
            security=security,
            date=date.fromisoformat(r["date"]),
            defaults={
                "title": f"{security.ticker} 실적 발표",
                "detail": {
                    "hour": r.get("hour") or "",
                    "quarter": r.get("quarter"),
                    "year": r.get("year"),
                    "eps_estimate": r.get("epsEstimate"),
                    "eps_actual": r.get("epsActual"),
                },
            },
        )
    return len(rows)


def update_dividends(security, client=None, today=None):
    """최근 2년 배당 이력과 발표된 다음 배당을 저장한다."""
    today = today or date.today()
    owns = client is None
    client = _client(client)
    try:
        rows = fetch_dividends(client, security.ticker)
    finally:
        if owns:
            client.close()
    since = today - timedelta(days=730)
    for r in rows:
        if r["ex_date"] < since:
            continue
        detail = {"amount": float(r["amount"])}
        CalendarEvent.objects.update_or_create(
            kind=CalendarEvent.Kind.EX_DIVIDEND,
            security=security,
            date=r["ex_date"],
            defaults={"title": f"{security.ticker} 배당락", "detail": detail},
        )
        if r["pay_date"]:
            CalendarEvent.objects.update_or_create(
                kind=CalendarEvent.Kind.DIVIDEND_PAY,
                security=security,
                date=r["pay_date"],
                defaults={"title": f"{security.ticker} 배당 지급", "detail": detail},
            )
    return len(rows)


def dividends_ttm(security, today=None):
    today = today or date.today()
    rows = security.events.filter(
        kind=CalendarEvent.Kind.EX_DIVIDEND, date__gt=today - timedelta(days=365), date__lte=today
    )
    return sum((Decimal(str(e.detail.get("amount", 0))) for e in rows), Decimal("0"))
