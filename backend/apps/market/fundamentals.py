"""SEC companyfacts JSON에서 매출·순이익·EPS·발행주식수를 뽑는다."""

from datetime import date
from decimal import Decimal

REVENUE_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
]


def _entries(facts, taxonomy, tag, unit):
    try:
        rows = facts["facts"][taxonomy][tag]["units"][unit]
    except KeyError:
        return []
    out = []
    for r in rows:
        if "start" not in r or r.get("form") not in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
            continue
        start, end = date.fromisoformat(r["start"]), date.fromisoformat(r["end"])
        out.append({"start": start, "end": end, "days": (end - start).days, "val": Decimal(str(r["val"])), "filed": r["filed"]})
    return out


def _dedupe(entries):
    """같은 기간이 여러 보고서에 반복되면 가장 나중에 제출된 값을 쓴다."""
    best = {}
    for e in entries:
        key = (e["start"], e["end"])
        if key not in best or e["filed"] > best[key]["filed"]:
            best[key] = e
    return sorted(best.values(), key=lambda e: e["end"])


def _annual(entries):
    return [e for e in entries if 350 <= e["days"] <= 380]


def _ttm(entries):
    """최근 12개월 = 최근 연간 + (올해 누적 - 작년 같은 기간 누적). 반환: (값, 기준일)."""
    annual = _annual(entries)
    if not annual:
        return None, None
    last = annual[-1]
    ytd = [e for e in entries if e["end"] > last["end"] and 80 <= e["days"] < 350 and e["start"] > last["start"]]
    if not ytd:
        return last["val"], last["end"]
    cur = max(ytd, key=lambda e: (e["end"], e["days"]))
    prev = [
        e
        for e in entries
        if abs(e["days"] - cur["days"]) <= 7 and 350 <= (cur["end"] - e["end"]).days <= 380
    ]
    if not prev:
        return last["val"], last["end"]
    return last["val"] + cur["val"] - prev[0]["val"], cur["end"]


def _pick_revenue(facts):
    best = []
    for tag in REVENUE_TAGS:
        rows = _dedupe(_entries(facts, "us-gaap", tag, "USD"))
        if rows and (not best or rows[-1]["end"] > best[-1]["end"]):
            best = rows
    return best


def parse_company_facts(facts):
    revenue = _pick_revenue(facts)
    net_income = _dedupe(_entries(facts, "us-gaap", "NetIncomeLoss", "USD"))
    eps = _dedupe(_entries(facts, "us-gaap", "EarningsPerShareDiluted", "USD/shares"))

    by_end = {}
    for name, rows in (("revenue", revenue), ("net_income", net_income), ("eps", eps)):
        for e in _annual(rows):
            row = by_end.setdefault(e["end"], {"year": e["end"].year, "end": e["end"].isoformat()})
            row[name] = float(e["val"])
    annual = [by_end[k] for k in sorted(by_end)][-5:]

    revenue_ttm, as_of = _ttm(revenue)
    net_income_ttm, ni_as_of = _ttm(net_income)
    eps_ttm, _ = _ttm(eps)

    shares = None
    try:
        rows = facts["facts"]["dei"]["EntityCommonStockSharesOutstanding"]["units"]["shares"]
        latest = max(r["end"] for r in rows)
        # 클래스가 여러 개인 회사(GOOGL 등)는 같은 날짜 값을 더한다
        same_day = {(r["accn"], r["val"]) for r in rows if r["end"] == latest}
        shares = int(sum(val for _, val in same_day))
    except (KeyError, ValueError):
        pass

    return {
        "shares_outstanding": shares,
        "revenue_ttm": revenue_ttm,
        "net_income_ttm": net_income_ttm,
        "eps_ttm": eps_ttm,
        "annual": annual,
        "as_of": as_of or ni_as_of,
    }
