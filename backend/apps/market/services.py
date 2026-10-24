from datetime import date, timedelta

import httpx
from django.db.models import Max, Min

from apps.securities.models import Security

from .models import FxRate, PriceDaily
from .providers import fetch_closes, fetch_usd_krw

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


def held_securities():
    return Security.objects.filter(transactions__isnull=False).distinct()


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
