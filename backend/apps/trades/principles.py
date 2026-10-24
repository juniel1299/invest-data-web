"""공시가 없는 투자자(린치·그레이엄·보글)의 원칙으로 내 종목과 포트폴리오를 점검한다.

결과는 참고용이다. 재무는 SEC 공시, 가격은 최근 종가 기준이다.
"""

import math
from decimal import Decimal

from django.conf import settings

from apps.market.models import MacroPoint
from apps.market.services import BENCHMARK_SERIES, dividends_ttm, latest_close


def _check(label, value, ok):
    return {"label": label, "value": value, "pass": ok}


def _fmt(v, suffix="", places=1):
    return "-" if v is None else f"{v:,.{places}f}{suffix}"


def eps_growth(annual):
    """연간 EPS의 연평균 성장률(%). 처음·끝 EPS가 모두 양수일 때만 계산한다."""
    eps = [(a["year"], a.get("eps")) for a in annual if a.get("eps") is not None]
    if len(eps) < 3:
        return None
    (y0, e0), (y1, e1) = eps[0], eps[-1]
    if e0 <= 0 or e1 <= 0 or y1 <= y0:
        return None
    return ((e1 / e0) ** (1 / (y1 - y0)) - 1) * 100


def check_security(sec):
    fund = getattr(sec, "fundamentals", None)
    last = latest_close(sec)
    price = float(last.close) if last else None
    eps = float(fund.eps_ttm) if fund and fund.eps_ttm is not None else None
    shares = fund.shares_outstanding if fund else None
    bps = float(fund.equity) / shares if fund and fund.equity and shares else None
    per = price / eps if price and eps and eps > 0 else None
    pbr = price / bps if price and bps and bps > 0 else None
    annual = fund.annual if fund else []
    div = dividends_ttm(sec)

    graham_number = math.sqrt(22.5 * eps * bps) if eps and bps and eps > 0 and bps > 0 else None
    incomes = [a.get("net_income") for a in annual if a.get("net_income") is not None]
    graham = [
        _check("PER 15배 이하", _fmt(per, "배"), None if per is None else per <= 15),
        _check("PBR 1.5배 이하", _fmt(pbr, "배"), None if pbr is None else pbr <= 1.5),
        _check("PER × PBR 22.5 이하", _fmt(per * pbr if per and pbr else None),
               None if not (per and pbr) else per * pbr <= 22.5),
        _check("주가가 그레이엄 넘버 이하", "-" if graham_number is None else f"${graham_number:,.2f}",
               None if graham_number is None or price is None else price <= graham_number),
        _check(f"최근 {len(incomes)}년 모두 흑자", f"{sum(1 for i in incomes if i > 0)}/{len(incomes)}년",
               None if not incomes else all(i > 0 for i in incomes)),
        # 배당 자료는 Alpha Vantage 키가 있어야 모이므로, 키가 없으면 판단하지 않는다
        _check("배당 지급", "-" if not div else f"${div:,.2f}/년",
               True if div else (False if settings.ALPHA_VANTAGE_API_KEY else None)),
    ]
    growth = eps_growth(annual)
    peg = per / growth if per and growth and growth > 0 else None
    lynch = [
        _check("EPS 연평균 성장률", _fmt(growth, "%"), None if growth is None else growth > 0),
        _check("PEG 1 이하 (PER ÷ 성장률)", _fmt(peg, places=2), None if peg is None else peg <= 1),
        _check("성장률 25% 이하 (지나친 고성장 경계)", _fmt(growth, "%"), None if growth is None else growth <= 25),
    ]
    return {
        "ticker": sec.ticker,
        "name": sec.name_ko or sec.name,
        "price": price,
        "graham": graham,
        "lynch": lynch,
        "graham_score": _score(graham),
        "lynch_score": _score(lynch),
    }


def _score(checks):
    known = [c for c in checks if c["pass"] is not None]
    return {"passed": sum(1 for c in known if c["pass"]), "checked": len(known)}


def _signed_usd(v):
    return f"{'+' if v >= 0 else '-'}${abs(v):,.0f}"


def _benchmark_on(day):
    p = MacroPoint.objects.filter(series=BENCHMARK_SERIES, date__lte=day).order_by("-date").first()
    return p.value if p else None


def bogle(transactions, summary):
    """같은 날 같은 금액으로 S&P 500을 사고 팔았다면 지금 얼마인지 비교한다."""
    latest = MacroPoint.objects.filter(series=BENCHMARK_SERIES).order_by("-date").first()
    units, missing = Decimal(0), 0
    for t in sorted(transactions, key=lambda t: (t.traded_at, t.id)):
        level = _benchmark_on(t.traded_at)
        if level is None:
            missing += 1
            continue
        amount = t.quantity * t.price
        units += amount / level if t.side == "BUY" else -amount / level
    holdings = summary["holdings"]
    totals = summary["totals"]
    weights = [h["weight"] for h in holdings if h.get("weight") is not None]
    max_weight = max(weights) if weights else None
    index_value = float(units * latest.value) if latest and units else None
    # 매도 대금은 양쪽 모두 빠져나간 것으로 보므로 지금 평가액끼리 비교한다
    my_value = totals.get("value_usd") or 0
    return {
        "my_value_usd": round(my_value, 2),
        "index_value_usd": round(index_value, 2) if index_value is not None else None,
        "difference_usd": round(my_value - index_value, 2) if index_value is not None else None,
        "index_as_of": latest.date.isoformat() if latest else None,
        "missing_index_days": missing,
        "checks": [
            _check("보유 종목 10개 이상 (분산)", f"{len(holdings)}개", len(holdings) >= 10 if holdings else None),
            _check("한 종목 비중 20% 이하", _fmt(max_weight, "%"), None if max_weight is None else max_weight <= 20),
            _check("S&P 500보다 나은 성과", "-" if index_value is None else _signed_usd(my_value - index_value),
                   None if index_value is None else my_value >= index_value),
        ],
    }
