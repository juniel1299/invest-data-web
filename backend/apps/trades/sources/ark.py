"""ARK Invest ETF 일간 보유 CSV (무료, 장 마감 후 갱신)."""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

BASE = "https://assets.ark-funds.com/fund-documents/funds-etf-csv/"
FUNDS = {
    "ARKK": "ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv",
    "ARKW": "ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS.csv",
    "ARKG": "ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS.csv",
    "ARKF": "ARK_BLOCKCHAIN_&_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.csv",
    "ARKQ": "ARK_AUTONOMOUS_TECH._&_ROBOTICS_ETF_ARKQ_HOLDINGS.csv",
    "ARKX": "ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS.csv",
}


def _num(v):
    try:
        return Decimal((v or "").replace("$", "").replace(",", "").strip())
    except InvalidOperation:
        return None


def parse_holdings(text):
    """반환: (기준일, [{ticker, cusip, name, shares, value}])"""
    as_of, rows = None, []
    for r in csv.DictReader(io.StringIO(text.strip())):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        shares = _num(r.get("shares"))
        if not r.get("date") or shares is None:
            continue  # 끝에 붙는 안내 문구 줄
        as_of = datetime.strptime(r["date"], "%m/%d/%Y").date()
        rows.append(
            {
                "ticker": r.get("ticker", "").upper().split(" ")[0],
                "cusip": r.get("cusip", "").upper(),
                "name": r.get("company", ""),
                "shares": shares,
                "value": _num(r.get("market value ($)")),
            }
        )
    return as_of, rows


def fetch_holdings(client, fund):
    res = client.get(BASE + FUNDS[fund], headers={"User-Agent": "Mozilla/5.0"})
    res.raise_for_status()
    return parse_holdings(res.text)
