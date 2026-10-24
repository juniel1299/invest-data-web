"""SEC EDGAR: 제출 목록, 13F 보유표, Form 4 (모두 무료, User-Agent 필수)."""

from datetime import date
from decimal import Decimal

import defusedxml.ElementTree as ET
from django.conf import settings

from .common import SourceError, strip_ns

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{name}"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/index.json"
FILING_PAGE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{accession}-index.htm"


def _get(client, url):
    res = client.get(url, headers={"User-Agent": settings.SEC_USER_AGENT})
    res.raise_for_status()
    return res


def filing_page(cik, accession):
    return FILING_PAGE_URL.format(cik=cik, acc=accession.replace("-", ""), accession=accession)


def fetch_filings(client, cik, forms):
    """최근 제출 목록 중 forms에 해당하는 것. 오래된 것부터."""
    recent = _get(client, SUBMISSIONS_URL.format(cik=cik)).json()["filings"]["recent"]
    out = []
    for i, form in enumerate(recent["form"]):
        if form not in forms:
            continue
        out.append(
            {
                "form": form,
                "accession": recent["accessionNumber"][i],
                "filed": date.fromisoformat(recent["filingDate"][i]),
                "report": date.fromisoformat(recent["reportDate"][i]) if recent["reportDate"][i] else None,
                "primary_doc": recent["primaryDocument"][i],
            }
        )
    return sorted(out, key=lambda f: (f["filed"], f["accession"]))


def _children(el):
    return {strip_ns(c.tag): c for c in el}


def _text(el, *path):
    for p in path:
        if el is None:
            return None
        el = _children(el).get(p)
    return el.text.strip() if el is not None and el.text else None


# ---------------------------------------------------------------- 13F

def parse_13f_table(xml_bytes, dollars=True):
    """정보표(infoTable)를 CUSIP별로 합친다. 풋·콜 옵션은 뺀다."""
    root = ET.fromstring(xml_bytes)
    rows = {}
    for info in root.iter():
        if strip_ns(info.tag) != "infoTable":
            continue
        if _text(info, "putCall"):
            continue
        if (_text(info, "shrsOrPrnAmt", "sshPrnamtType") or "SH") != "SH":
            continue  # 채권 원금(PRN)은 주식 수가 아니다
        cusip = (_text(info, "cusip") or "").upper()
        if not cusip:
            continue
        value = Decimal(_text(info, "value") or "0")
        if not dollars:
            value *= 1000  # 2023년 이전 13F는 천 달러 단위
        shares = Decimal(_text(info, "shrsOrPrnAmt", "sshPrnamt") or "0")
        row = rows.setdefault(cusip, {"cusip": cusip, "name": _text(info, "nameOfIssuer") or "", "shares": Decimal(0), "value": Decimal(0)})
        row["shares"] += shares
        row["value"] += value
    return list(rows.values())


# 2023년 1월 3일 제출분부터 value를 달러 단위로 적는다
F13_DOLLAR_CUTOVER = date(2023, 1, 3)


def fetch_13f_table(client, cik, accession, filed):
    acc = accession.replace("-", "")
    items = _get(client, INDEX_URL.format(cik=cik, acc=acc)).json()["directory"]["item"]
    names = [i["name"] for i in items if i["name"].lower().endswith(".xml") and i["name"].lower() != "primary_doc.xml"]
    if not names:
        raise SourceError(f"13F 정보표를 찾지 못했습니다: {accession}")
    xml = _get(client, ARCHIVE_URL.format(cik=cik, acc=acc, name=names[0])).content
    return parse_13f_table(xml, dollars=filed >= F13_DOLLAR_CUTOVER)


# ---------------------------------------------------------------- Form 4

def parse_form4(xml_bytes):
    root = ET.fromstring(xml_bytes)
    kids = _children(root)
    owner = kids.get("reportingOwner")
    rel = _children(owner).get("reportingOwnerRelationship") if owner is not None else None
    roles = []
    if rel is not None:
        r = {strip_ns(c.tag): (c.text or "").strip() for c in rel}
        if r.get("officerTitle"):
            roles.append(r["officerTitle"])
        if r.get("isDirector") in ("1", "true"):
            roles.append("이사")
        if r.get("isTenPercentOwner") in ("1", "true"):
            roles.append("10% 대주주")
    txs = []
    table = kids.get("nonDerivativeTable")
    for tx in table if table is not None else []:
        if strip_ns(tx.tag) != "nonDerivativeTransaction":
            continue
        code = _text(tx, "transactionCoding", "transactionCode")
        day = _text(tx, "transactionDate", "value")
        shares = _text(tx, "transactionAmounts", "transactionShares", "value")
        price = _text(tx, "transactionAmounts", "transactionPricePerShare", "value")
        txs.append(
            {
                "code": code,
                "date": date.fromisoformat(day[:10]) if day else None,
                "shares": Decimal(shares) if shares else None,
                "price": Decimal(price) if price else None,
                "acquired": _text(tx, "transactionAmounts", "transactionAcquiredDisposedCode", "value") == "A",
            }
        )
    return {
        "ticker": (_text(root, "issuer", "issuerTradingSymbol") or "").upper(),
        "issuer_cik": int(_text(root, "issuer", "issuerCik") or 0),
        "issuer_name": _text(root, "issuer", "issuerName") or "",
        "owner_cik": int(_text(owner, "reportingOwnerId", "rptOwnerCik") or 0) if owner is not None else 0,
        "owner_name": _text(owner, "reportingOwnerId", "rptOwnerName") or "" if owner is not None else "",
        "owner_title": ", ".join(roles),
        "transactions": txs,
    }


def fetch_form4(client, cik, accession, primary_doc):
    # primaryDocument는 "xslF345X05/form4.xml"처럼 화면용 경로라 앞부분을 떼면 원본 XML이다
    name = primary_doc.split("/")[-1]
    return parse_form4(_get(client, ARCHIVE_URL.format(cik=cik, acc=accession.replace("-", ""), name=name)).content)
