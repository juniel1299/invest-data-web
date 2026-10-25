"""거래일 하루 요약 내용을 만든다 (이메일과 앱 '오늘의 정리'가 같은 내용을 쓴다)."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Q

from apps.market import calendar_us
from apps.market.models import CalendarEvent, FxRate, MacroPoint, NewsItem, PriceDaily
from apps.market.services import MACRO_SERIES
from apps.market.views import user_securities
from apps.portfolio.calculations import build_positions
from apps.portfolio.models import Transaction
from apps.portfolio.summary import build_summary
from apps.trades.models import DisclosedTrade
from apps.trades.views import trade_json

ET = ZoneInfo("America/New_York")
MAX_TRADES = 15
MAX_NEWS = 5
MOVERS = 3


def _f(v, places=2):
    return None if v is None else round(float(v), places)


def _pct(now, before):
    return _f((now - before) / before * 100) if now is not None and before else None


def _closes(security, day):
    """그날(없으면 그 전 가장 가까운 날) 종가와 그 직전 종가."""
    rows = list(PriceDaily.objects.filter(security=security, date__lte=day).order_by("-date")[:2])
    return (rows[0] if rows else None), (rows[1] if len(rows) > 1 else None)


def _portfolio(user, day):
    txs = list(Transaction.objects.filter(user=user, traded_at__lte=day).select_related("security"))
    if not txs:
        return None, []
    summary = build_summary(txs)
    totals = summary["totals"]
    change = Decimal(0)
    movers = []
    for pos in build_positions(txs).values():
        if pos.quantity == 0:
            continue
        cur, prev = _closes(pos.security, day)
        if not (cur and prev):
            continue
        change += pos.quantity * (cur.close - prev.close)
        movers.append(
            {
                "ticker": pos.security.ticker,
                "name": pos.security.name_ko or pos.security.name,
                "close": _f(cur.close),
                "change_pct": _pct(cur.close, prev.close),
                "date": cur.date.isoformat(),
            }
        )
    value = Decimal(str(totals["value_usd"]))
    fx = FxRate.objects.filter(date__lte=day).order_by("-date").first()
    portfolio = {
        "value_usd": totals["value_usd"],
        "value_krw": totals["value_krw"],
        "pnl_usd": totals["pnl_usd"],
        "pnl_pct": totals["pnl_pct"],
        "pnl_krw": totals["pnl_krw"],
        "pnl_krw_pct": totals["pnl_krw_pct"],
        "change_usd": _f(change),
        "change_pct": _pct(value, value - change) if change else 0.0,
        "change_krw": _f(change * fx.usd_krw, 0) if fx else None,
        "fx": _f(fx.usd_krw) if fx else None,
        "unpriced": totals["unpriced"],
    }
    return portfolio, movers


def _market(day):
    rows = []
    for series, name in MACRO_SERIES.items():
        pts = list(MacroPoint.objects.filter(series=series, date__lte=day).order_by("-date")[:2])
        if pts:
            rows.append(
                {
                    "series": series,
                    "name": name,
                    "value": _f(pts[0].value),
                    "change": _f(pts[0].value - pts[1].value) if len(pts) > 1 else None,
                    "change_pct": _pct(pts[0].value, pts[1].value) if len(pts) > 1 else None,
                    "date": pts[0].date.isoformat(),
                }
            )
    fx = list(FxRate.objects.filter(date__lte=day).order_by("-date")[:2])
    if fx:
        rows.append(
            {
                "series": "FX",
                "name": "원/달러 환율",
                "value": _f(fx[0].usd_krw),
                "change": _f(fx[0].usd_krw - fx[1].usd_krw) if len(fx) > 1 else None,
                "change_pct": _pct(fx[0].usd_krw, fx[1].usd_krw) if len(fx) > 1 else None,
                "date": fx[0].date.isoformat(),
            }
        )
    return rows


def _trades(user, day, mine):
    """직전 거래일 다음 날부터 오늘까지 공시된 거래. 내 종목과 겹치는 것을 먼저."""
    since = calendar_us.previous_trading_day(day) + timedelta(days=1)
    qs = DisclosedTrade.objects.select_related("person", "security", "filing").filter(
        filed_at__gte=since, filed_at__lte=day
    ).filter(Q(person__active=True) | Q(person__isnull=True, security_id__in=mine))
    rows = [trade_json(t, mine) for t in qs]
    rows.sort(key=lambda t: (not t["overlap"], t["person"] is None))
    return rows[:MAX_TRADES], len(rows)


def _news(user, day, secs):
    end = datetime.combine(day, time(23, 59), tzinfo=ET)
    qs = NewsItem.objects.select_related("security").filter(
        security__in=secs, published_at__gte=end - timedelta(days=1), published_at__lte=end
    )[:MAX_NEWS]
    return [
        {"ticker": n.security.ticker, "title": n.title, "url": n.url, "source": n.source}
        for n in qs
    ]


def _tomorrow(day, secs):
    nxt = calendar_us.next_trading_day(day)
    qs = CalendarEvent.objects.select_related("security").filter(
        Q(security__isnull=True) | Q(security__in=secs), date__gt=day, date__lte=nxt
    )
    return nxt, [
        {
            "date": e.date.isoformat(),
            "kind_label": e.get_kind_display(),
            "ticker": e.security.ticker if e.security else None,
            "title": e.title,
        }
        for e in qs
    ]


def build(user, day):
    secs = user_securities(user)
    mine = frozenset(secs.values_list("id", flat=True))
    portfolio, movers = _portfolio(user, day)
    priced = sorted((m for m in movers if m["change_pct"] is not None), key=lambda m: m["change_pct"])
    trades, trade_total = _trades(user, day, mine)
    nxt, events = _tomorrow(day, secs)
    return {
        "date": day.isoformat(),
        "early_close": calendar_us.is_early_close(day),
        "portfolio": portfolio,
        "movers": {
            "up": [m for m in reversed(priced) if m["change_pct"] > 0][:MOVERS],
            "down": [m for m in priced if m["change_pct"] < 0][:MOVERS],
        },
        "market": _market(day),
        "trades": trades,
        "trade_total": trade_total,
        "news": _news(user, day, secs),
        "next_trading_day": nxt.isoformat(),
        "tomorrow": events,
    }


def has_content(data):
    return bool(data["portfolio"] or data["trades"] or data["news"] or data["tomorrow"])
