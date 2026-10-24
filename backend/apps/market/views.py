import logging
from datetime import date, timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.securities.models import Security

from . import services
from .models import CalendarEvent, FxRate, MacroPoint, NewsItem

logger = logging.getLogger(__name__)

RANGES = {"1M": 31, "3M": 92, "6M": 183, "1Y": 366}


def _f(v, places=2):
    return None if v is None else round(float(v), places)


def _change(latest, prev):
    if latest is None or prev is None or not prev:
        return None, None
    diff = latest - prev
    return _f(diff, 4), _f(diff / prev * 100)


def user_securities(user):
    """이 사용자가 보유했거나 관심 종목으로 담은 종목."""
    return Security.objects.filter(
        Q(transactions__user=user) | Q(watchers__user=user)
    ).distinct()


def _ensure(security, fn, exists):
    """처음 보는 종목은 화면을 열 때 바로 받아온다. 실패해도 화면은 있는 데이터로 그린다."""
    if exists:
        return
    try:
        fn(security)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s 즉시 수집 실패: %s", security.ticker, exc)


@api_view(["GET"])
def overview(request):
    indices = []
    for series, name in services.MACRO_SERIES.items():
        points = list(MacroPoint.objects.filter(series=series).order_by("-date")[:30])
        latest = points[0] if points else None
        change, change_pct = _change(
            latest.value if latest else None, points[1].value if len(points) > 1 else None
        )
        indices.append(
            {
                "series": series,
                "name": name,
                "value": _f(latest.value) if latest else None,
                "date": latest.date.isoformat() if latest else None,
                "change": change,
                "change_pct": change_pct,
                "history": [_f(p.value) for p in reversed(points)],
            }
        )
    fx = list(FxRate.objects.order_by("-date")[:30])
    fx_change, fx_pct = _change(fx[0].usd_krw if fx else None, fx[1].usd_krw if len(fx) > 1 else None)
    return Response(
        {
            "indices": indices,
            "fx": {
                "name": "원/달러 환율",
                "value": _f(fx[0].usd_krw) if fx else None,
                "date": fx[0].date.isoformat() if fx else None,
                "change": fx_change,
                "change_pct": fx_pct,
                "history": [_f(r.usd_krw) for r in reversed(fx)],
            },
        }
    )


def _news_json(n):
    return {
        "ticker": n.security.ticker,
        "title": n.title,
        "url": n.url,
        "source": n.source,
        "published_at": n.published_at.isoformat(),
    }


@api_view(["GET"])
def news(request):
    ticker = request.query_params.get("ticker")
    qs = NewsItem.objects.select_related("security")
    if ticker:
        qs = qs.filter(security__ticker=ticker.upper())
    else:
        qs = qs.filter(security__in=user_securities(request.user))
    return Response([_news_json(n) for n in qs[:50]])


def _event_json(e):
    return {
        "date": e.date.isoformat(),
        "kind": e.kind,
        "kind_label": e.get_kind_display(),
        "ticker": e.security.ticker if e.security else None,
        "name": (e.security.name_ko or e.security.name) if e.security else None,
        "title": e.title,
        "detail": e.detail,
    }


@api_view(["GET"])
def calendar(request):
    try:
        days = min(int(request.query_params.get("days", 30)), 180)
    except ValueError:
        days = 30
    today = date.today()
    qs = CalendarEvent.objects.select_related("security").filter(
        Q(security__isnull=True) | Q(security__in=user_securities(request.user)),
        date__gte=today,
        date__lte=today + timedelta(days=days),
    )
    return Response([_event_json(e) for e in qs])


@api_view(["GET"])
def security_detail(request, ticker):
    from apps.portfolio.models import Watch

    sec = get_object_or_404(Security, ticker=ticker.upper())
    _ensure(sec, services.update_prices, sec.prices.exists())
    _ensure(sec, services.update_fundamentals, hasattr(sec, "fundamentals") or not sec.cik)
    sec.refresh_from_db()

    year = list(sec.prices.filter(date__gte=date.today() - timedelta(days=365)).order_by("-date"))
    latest = year[0] if year else None
    change, change_pct = _change(latest.close if latest else None, year[1].close if len(year) > 1 else None)

    fund = getattr(sec, "fundamentals", None)
    price = latest.close if latest else None
    market_cap = price * fund.shares_outstanding if price and fund and fund.shares_outstanding else None
    per = price / fund.eps_ttm if price and fund and fund.eps_ttm and fund.eps_ttm > 0 else None
    div = services.dividends_ttm(sec)
    today = date.today()

    return Response(
        {
            "ticker": sec.ticker,
            "name": sec.name,
            "name_ko": sec.name_ko,
            "exchange": sec.exchange,
            "price": _f(price, 4),
            "price_date": latest.date.isoformat() if latest else None,
            "change": change,
            "change_pct": change_pct,
            "high_52w": _f(max(p.close for p in year), 4) if year else None,
            "low_52w": _f(min(p.close for p in year), 4) if year else None,
            "market_cap": _f(market_cap, 0),
            "per": _f(per),
            "eps_ttm": _f(fund.eps_ttm) if fund else None,
            "revenue_ttm": _f(fund.revenue_ttm, 0) if fund else None,
            "net_income_ttm": _f(fund.net_income_ttm, 0) if fund else None,
            "fundamentals_as_of": fund.as_of.isoformat() if fund and fund.as_of else None,
            "annual": fund.annual if fund else [],
            "dividend_ttm": _f(div, 4) if div else None,
            "dividend_yield": _f(div / price * 100) if div and price else None,
            "is_watched": Watch.objects.filter(user=request.user, security=sec).exists(),
            "events": [_event_json(e) for e in sec.events.filter(date__gte=today)[:5]],
            "news": [_news_json(n) for n in sec.news.select_related("security")[:5]],
        }
    )


@api_view(["GET"])
def security_prices(request, ticker):
    sec = get_object_or_404(Security, ticker=ticker.upper())
    days = RANGES.get(request.query_params.get("range", "6M"), RANGES["6M"])
    rows = sec.prices.filter(date__gte=date.today() - timedelta(days=days)).order_by("date")
    return Response([{"date": p.date.isoformat(), "close": _f(p.close, 4)} for p in rows])
