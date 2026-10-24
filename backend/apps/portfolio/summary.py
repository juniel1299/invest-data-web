"""포트폴리오 요약: 평가금액, 달러·원화 수익률, 환차익."""

from decimal import Decimal

from apps.market.services import fx_on, latest_close

from .calculations import build_positions


def _f(value, places=2):
    return None if value is None else float(round(value, places))


def build_summary(transactions):
    fx_now = fx_on()
    positions = build_positions(transactions)
    holdings = []
    realized_usd = sum((p.realized_usd for p in positions.values()), Decimal("0"))

    for pos in positions.values():
        if pos.quantity == 0:
            continue
        sec = pos.security
        price = latest_close(sec)
        row = {
            "ticker": sec.ticker,
            "name": sec.name,
            "name_ko": sec.name_ko,
            "quantity": _f(pos.quantity, 6),
            "avg_price": _f(pos.avg_price, 4),
            "avg_fx": _f(pos.avg_fx),
            "cost_usd": _f(pos.cost_usd),
            "last_close": None,
            "last_close_date": None,
            "value_usd": None,
            "pnl_usd": None,
            "pnl_pct": None,
            "value_krw": None,
            "pnl_krw": None,
            "pnl_krw_pct": None,
            "fx_pnl_krw": None,
            "weight": None,
            "_value": None,
        }
        if price:
            value = pos.quantity * price.close
            pnl = value - pos.cost_usd
            row.update(
                last_close=_f(price.close, 4),
                last_close_date=price.date.isoformat(),
                value_usd=_f(value),
                pnl_usd=_f(pnl),
                pnl_pct=_f(pnl / pos.cost_usd * 100) if pos.cost_usd else None,
                _value=value,
            )
            if fx_now and pos.avg_fx:
                value_krw = value * fx_now
                pnl_krw = value_krw - pos.cost_krw
                row.update(
                    value_krw=_f(value_krw, 0),
                    pnl_krw=_f(pnl_krw, 0),
                    pnl_krw_pct=_f(pnl_krw / pos.cost_krw * 100),
                    # 원화 손익 = 주가 손익 × 현재 환율 + 환차익
                    fx_pnl_krw=_f(pos.cost_usd * (fx_now - pos.avg_fx), 0),
                )
        holdings.append(row)

    total_value = sum((h["_value"] for h in holdings if h["_value"] is not None), Decimal("0"))
    for h in holdings:
        if h["_value"] is not None and total_value:
            h["weight"] = _f(h["_value"] / total_value * 100)
    holdings.sort(key=lambda h: h["_value"] or 0, reverse=True)
    for h in holdings:
        del h["_value"]

    priced = [h for h in holdings if h["value_usd"] is not None]
    cost = sum(h["cost_usd"] for h in priced)
    value = sum(h["value_usd"] for h in priced)
    krw = [h for h in priced if h["value_krw"] is not None]
    value_krw = sum(h["value_krw"] for h in krw)
    pnl_krw = sum(h["pnl_krw"] for h in krw)
    return {
        "fx_rate": _f(fx_now),
        "totals": {
            "cost_usd": round(cost, 2),
            "value_usd": round(value, 2),
            "pnl_usd": round(value - cost, 2),
            "pnl_pct": round((value - cost) / cost * 100, 2) if cost else None,
            "value_krw": round(value_krw) if krw else None,
            "pnl_krw": round(pnl_krw) if krw else None,
            "pnl_krw_pct": round(pnl_krw / (value_krw - pnl_krw) * 100, 2) if krw and value_krw != pnl_krw else None,
            "realized_usd": _f(realized_usd),
            "unpriced": [h["ticker"] for h in holdings if h["value_usd"] is None],
        },
        "holdings": holdings,
    }
