"""공시를 받아 거래로 저장한다. 출처별 함수는 새로 저장한 거래 목록을 돌려준다."""

import logging
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

import httpx
from django.db import transaction

from apps.securities.models import Security

from .models import CusipMap, DisclosedTrade, Filing, HoldingSnapshot, Person, Source
from .sources import ark, house, openfigi, sec, senate

logger = logging.getLogger(__name__)

# 처음 수집할 때 거슬러 올라갈 13F 분기 수 (변화를 보려면 최소 2개)
F13_INITIAL_QUARTERS = 4
FORM4_LOOKBACK_DAYS = 120
INSIDER_LOOKBACK_DAYS = 30
INSIDER_MAX_PER_RUN = 15
# ETF 설정·환매로 모든 종목이 같은 비율로 늘고 줄어드는 것은 매매로 보지 않는다
ARK_MIN_ACTIVE_CHANGE = Decimal("0.005")


def http_client():
    return httpx.Client(timeout=30, follow_redirects=True)


def resolve_security(ticker):
    if not ticker:
        return None
    t = ticker.upper().replace("/", ".").replace("-", ".")
    return Security.objects.filter(ticker__in={t, t.replace(".", "-")}).first()


def _new_filing(**kw):
    """이미 처리한 공시면 None."""
    filing, created = Filing.objects.get_or_create(source=kw.pop("source"), key=kw.pop("key"), defaults=kw)
    return filing if created else None


def _save_rows(filing, person, rows, filed_at):
    trades = []
    for i, r in enumerate(rows):
        trades.append(
            DisclosedTrade.objects.create(
                filing=filing,
                row=i,
                person=person,
                security=resolve_security(r.get("ticker")),
                filed_at=filed_at,
                **r,
            )
        )
    return trades


# ---------------------------------------------------------------- 13F

def _ticker_for_cusips(client, cusips):
    known = dict(CusipMap.objects.filter(cusip__in=cusips).values_list("cusip", "ticker"))
    missing = [c for c in cusips if c not in known]
    if missing:
        try:
            found = openfigi.map_cusips(client, missing)
        except Exception as exc:  # noqa: BLE001 - 티커가 없어도 보유 기록은 남긴다
            logger.warning("OpenFIGI 실패: %s", exc)
            found = {}
        for c, t in found.items():
            CusipMap.objects.update_or_create(cusip=c, defaults={"ticker": t})
        known.update(found)
    return known


def _diff_holdings(prev, cur):
    """{key: snapshot} 두 개를 비교해 (action, cur_or_prev, delta_shares) 목록."""
    out = []
    for k, h in cur.items():
        p = prev.get(k)
        if p is None:
            out.append(("NEW", h, h.shares))
        elif h.shares > p.shares:
            out.append(("ADD", h, h.shares - p.shares))
        elif h.shares < p.shares:
            out.append(("REDUCE", h, h.shares - p.shares))
    for k, p in prev.items():
        if k not in cur:
            out.append(("EXIT", p, -p.shares))
    return out


def update_13f(person, client):
    filings = [f for f in sec.fetch_filings(client, person.cik, {"13F-HR"}) if f["report"]]
    known = set(Filing.objects.filter(source=Source.F13, person=person).values_list("key", flat=True))
    todo = [f for f in filings if f["accession"] not in known]
    if not known:
        todo = todo[-F13_INITIAL_QUARTERS:]
    trades = []
    for f in todo:
        rows = sec.fetch_13f_table(client, person.cik, f["accession"], f["filed"])
        tickers = _ticker_for_cusips(client, [r["cusip"] for r in rows])
        with transaction.atomic():
            filing = _new_filing(
                source=Source.F13, key=f["accession"], person=person, filed_at=f["filed"],
                period_end=f["report"], url=sec.filing_page(person.cik, f["accession"]),
            )
            if filing is None:
                continue
            # 같은 분기를 새로 다시 낸 경우 뒤의 공시를 기준으로 한다
            HoldingSnapshot.objects.filter(person=person, source=Source.F13, as_of=f["report"]).delete()
            cur = {}
            for r in rows:
                t = tickers.get(r["cusip"], "")
                cur[r["cusip"]] = HoldingSnapshot.objects.create(
                    person=person, source=Source.F13, as_of=f["report"], key=r["cusip"], cusip=r["cusip"],
                    ticker=t, security=resolve_security(t), name=r["name"], shares=r["shares"],
                    value_usd=r["value"], filing=filing,
                )
            prev_date = (
                HoldingSnapshot.objects.filter(person=person, source=Source.F13, as_of__lt=f["report"])
                .order_by("-as_of").values_list("as_of", flat=True).first()
            )
            if prev_date is None:
                continue  # 첫 분기는 비교할 대상이 없다
            prev = {h.key: h for h in HoldingSnapshot.objects.filter(person=person, source=Source.F13, as_of=prev_date)}
            for i, (action, h, delta) in enumerate(_diff_holdings(prev, cur)):
                price = (h.value_usd / h.shares) if h.value_usd and h.shares else None
                trades.append(
                    DisclosedTrade.objects.create(
                        filing=filing, row=i, person=person, security=h.security, ticker=h.ticker,
                        asset_name=h.name, action=action, traded_at=None, filed_at=f["filed"],
                        shares=abs(delta), price=price,
                        detail=f"{prev_date:%Y-%m-%d} → {f['report']:%Y-%m-%d} 분기 말 보유 비교",
                    )
                )
    return trades


# ---------------------------------------------------------------- Form 4

def _form4_trades(filing, person, security, parsed):
    """공개 시장 매수(P)·매도(S)만 거래로 본다. 스톡옵션 행사·증여 등은 뺀다."""
    trades = []
    for i, tx in enumerate(parsed["transactions"]):
        if tx["code"] not in ("P", "S"):
            continue
        trades.append(
            DisclosedTrade.objects.create(
                filing=filing, row=i, person=person, security=security or resolve_security(parsed["ticker"]),
                ticker=parsed["ticker"], asset_name=parsed["issuer_name"],
                action="BUY" if tx["code"] == "P" else "SELL", traded_at=tx["date"], filed_at=filing.filed_at,
                shares=tx["shares"], price=tx["price"], owner="본인",
                actor_name=parsed["owner_name"], actor_title=parsed["owner_title"],
            )
        )
    return trades


def _process_form4s(client, cik, filings, person=None, security=None, limit=None):
    known = set(Filing.objects.filter(source=Source.FORM4, key__in=[f["accession"] for f in filings]).values_list("key", flat=True))
    todo = [f for f in filings if f["accession"] not in known]
    if limit:
        todo = todo[-limit:]
    persons = {p.cik: p for p in Person.objects.filter(active=True, cik__isnull=False)}
    trades = []
    for f in todo:
        parsed = sec.fetch_form4(client, cik, f["accession"], f["primary_doc"])
        who = person or persons.get(parsed["owner_cik"])
        with transaction.atomic():
            filing = _new_filing(
                source=Source.FORM4, key=f["accession"], person=who,
                security=security or resolve_security(parsed["ticker"]),
                filed_at=f["filed"], url=sec.filing_page(cik, f["accession"]),
            )
            if filing:
                trades += _form4_trades(filing, who, security, parsed)
    return trades


def update_form4_person(person, client, today=None):
    since = (today or date.today()) - timedelta(days=FORM4_LOOKBACK_DAYS)
    filings = [f for f in sec.fetch_filings(client, person.cik, {"4"}) if f["filed"] >= since]
    return _process_form4s(client, person.cik, filings, person=person)


def update_insiders(security, client, today=None):
    """보유·관심 종목 회사의 임원·대주주 매매."""
    if not security.cik:
        return []
    since = (today or date.today()) - timedelta(days=INSIDER_LOOKBACK_DAYS)
    filings = [f for f in sec.fetch_filings(client, security.cik, {"4"}) if f["filed"] >= since]
    return _process_form4s(client, security.cik, filings, security=security, limit=INSIDER_MAX_PER_RUN)


# ---------------------------------------------------------------- ARK

def _ark_active_trades(prev, cur):
    """설정·환매로 생긴 일괄 증감(중앙값 비율)을 빼고 남은 변화만 매매로 본다."""
    ratios = [cur[k].shares / prev[k].shares for k in cur if k in prev and prev[k].shares]
    base = Decimal(str(median(ratios))) if ratios else Decimal(1)
    out = []
    for k, h in cur.items():
        p = prev.get(k)
        if p is None:
            out.append(("BUY", h, h.shares, "신규 편입"))
            continue
        active = h.shares - p.shares * base
        if p.shares and abs(active) / p.shares >= ARK_MIN_ACTIVE_CHANGE:
            out.append(("BUY" if active > 0 else "SELL", h, abs(active), ""))
    for k, p in prev.items():
        if k not in cur:
            out.append(("SELL", p, p.shares, "전량 매도"))
    return out


def update_ark(person, client):
    trades = []
    for fund in ark.FUNDS:
        as_of, rows = ark.fetch_holdings(client, fund)
        if not as_of or HoldingSnapshot.objects.filter(person=person, source=Source.ARK, fund=fund, as_of=as_of).exists():
            continue
        with transaction.atomic():
            filing = _new_filing(
                source=Source.ARK, key=f"{fund}-{as_of:%Y%m%d}", person=person, filed_at=as_of,
                period_end=as_of, url=ark.BASE + ark.FUNDS[fund],
            )
            cur = {}
            for r in rows:
                key = r["ticker"] or r["cusip"]
                if not key or key in cur:
                    continue
                cur[key] = HoldingSnapshot.objects.create(
                    person=person, source=Source.ARK, fund=fund, as_of=as_of, key=key[:20], cusip=r["cusip"][:9],
                    ticker=r["ticker"], security=resolve_security(r["ticker"]), name=r["name"],
                    shares=r["shares"], value_usd=r["value"], filing=filing,
                )
            prev_date = (
                HoldingSnapshot.objects.filter(person=person, source=Source.ARK, fund=fund, as_of__lt=as_of)
                .order_by("-as_of").values_list("as_of", flat=True).first()
            )
            if prev_date is None:
                continue
            prev = {h.key: h for h in HoldingSnapshot.objects.filter(person=person, source=Source.ARK, fund=fund, as_of=prev_date)}
            for i, (action, h, shares, note) in enumerate(_ark_active_trades(prev, cur)):
                price = (h.value_usd / h.shares) if h.value_usd and h.shares else None
                trades.append(
                    DisclosedTrade.objects.create(
                        filing=filing, row=i, person=person, security=h.security, ticker=h.ticker,
                        asset_name=h.name, action=action, traded_at=as_of, filed_at=as_of,
                        shares=shares.quantize(Decimal(1)), price=price, detail=" ".join(filter(None, [fund, note])),
                    )
                )
    # 일간 보유는 최근 30일만 남긴다 (매매는 거래로 남아 있다)
    HoldingSnapshot.objects.filter(person=person, source=Source.ARK, as_of__lt=date.today() - timedelta(days=30)).delete()
    return trades


# ---------------------------------------------------------------- 의회

def update_house(client, year=None):
    year = year or date.today().year
    people = list(Person.objects.filter(active=True, kind=Person.Kind.HOUSE).exclude(house_last_name=""))
    if not people:
        return []
    index = [m for m in house.fetch_index(client, year) if m["filing_type"] == "P"]
    known = set(Filing.objects.filter(source=Source.HOUSE).values_list("key", flat=True))
    trades = []
    for person in people:
        for m in index:
            if m["last"].lower() != person.house_last_name.lower() or m["doc_id"] in known:
                continue
            if person.house_state and not m["state_dst"].upper().startswith(person.house_state.upper()):
                continue
            rows = house.parse_ptr_text(house.fetch_ptr_text(client, year, m["doc_id"]))
            with transaction.atomic():
                filing = _new_filing(
                    source=Source.HOUSE, key=m["doc_id"], person=person, filed_at=m["filed"],
                    url=house.PTR_URL.format(year=year, doc_id=m["doc_id"]), parsed=bool(rows),
                )
                if filing:
                    trades += _save_rows(filing, person, rows, m["filed"])
    return trades


def update_senate(client, since=None):
    people = list(Person.objects.filter(active=True, kind=Person.Kind.SENATE).exclude(senate_last_name=""))
    if not people:
        return []
    since = since or date(date.today().year - 1, 1, 1)
    session = senate.EfdSession(client)
    known = set(Filing.objects.filter(source=Source.SENATE).values_list("key", flat=True))
    trades = []
    for person in people:
        for report in session.search_ptrs(person.senate_first_name, person.senate_last_name, since):
            if report["key"] in known:
                continue
            rows = [] if report["paper"] else session.fetch_ptr(report["url"])
            with transaction.atomic():
                filing = _new_filing(
                    source=Source.SENATE, key=report["key"], person=person, filed_at=report["filed"],
                    url=report["url"], parsed=not report["paper"],
                )
                if filing:
                    trades += _save_rows(filing, person, rows, report["filed"])
    return trades
