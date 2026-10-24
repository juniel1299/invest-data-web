"""하원 Clerk 공시: 연도별 색인(zip 속 XML) + 거래 신고(PTR) PDF."""

import io
import re
import zipfile
from datetime import datetime

import defusedxml.ElementTree as ET

from .common import owner_label, parse_amount_range

INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PTR_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"


def _mdy(v):
    return datetime.strptime(v.strip(), "%m/%d/%Y").date()


def parse_index(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for m in root.iter("Member"):
        f = {c.tag: (c.text or "").strip() for c in m}
        if not f.get("DocID") or not f.get("FilingDate"):
            continue
        out.append(
            {
                "last": f.get("Last", ""),
                "first": f.get("First", ""),
                "state_dst": f.get("StateDst", ""),
                "filing_type": f.get("FilingType", ""),
                "filed": _mdy(f["FilingDate"]),
                "doc_id": f["DocID"],
                "year": int(f.get("Year") or 0),
            }
        )
    return out


def fetch_index(client, year):
    res = client.get(INDEX_URL.format(year=year))
    res.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".xml"))
        return parse_index(z.read(name))


def pdf_text(content):
    """전자 제출본은 글자를 뽑을 수 있고, 손으로 쓴 스캔본은 빈 문자열이 나온다."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def fetch_ptr_text(client, year, doc_id):
    res = client.get(PTR_URL.format(year=year, doc_id=doc_id))
    res.raise_for_status()
    return pdf_text(res.content)


_ROW = re.compile(
    r"\[(?P<atype>[A-Z]{2})\]\s*"
    r"(?P<type>P|S\s*\(partial\)|S|E)\s+"
    r"(?P<traded>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?P<notified>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?P<amount>Over\s+\$[\d,]+|\$[\d,]+\s*-\s*\$[\d,]+|\$[\d,]+)",
    re.IGNORECASE,
)
_TICKER = re.compile(r"\(([A-Z][A-Z0-9.\-/]{0,9})\)\s*$")
_OWNER = re.compile(r"(?:^|\s)(SP|JT|DC)\s+(?=\S)")
_DESC = re.compile(r"(?:F\s*S\s*:|S\s*O\s*:|D\s*:|Filing ID #\S+)")
TYPES = {"P": "BUY", "S": "SELL", "E": "EXCHANGE"}
ASSET_TYPES = {"ST": "", "OP": "옵션", "OT": "기타", "CS": "회사채", "GS": "국채", "EF": "ETF", "MF": "펀드"}


def parse_ptr_text(text):
    """PTR PDF에서 뽑은 글자에서 거래 줄을 찾는다.

    줄 바꿈 위치가 제각각이라 공백을 하나로 합친 뒤 '[ST] P 01/14/2026 01/14/2026 $1,001 - $15,000'
    같은 고정된 꼬리를 기준으로 자르고, 그 앞부분에서 명의·자산명·티커를 읽는다.
    """
    flat = re.sub(r"\s+", " ", text or "").replace("\x00", "")
    rows, prev_end = [], 0
    for m in _ROW.finditer(flat):
        head = flat[prev_end : m.start()].strip()
        prev_end = m.end()
        # 앞 거래의 설명(F S:, D: ...) 뒤에서부터가 이번 거래다
        parts = _DESC.split(head)
        head = parts[-1] if len(parts) > 1 else head
        owner = ""
        om = None
        for om in _OWNER.finditer(head):
            pass
        if om:
            owner, head = om.group(1), head[om.end() :]
        tm = _TICKER.search(head)
        ticker = tm.group(1).replace("/", ".") if tm else ""
        asset = (head[: tm.start()] if tm else head).strip(" -")
        kind = re.sub(r"\s+", "", m.group("type").upper())
        action = "PARTIAL_SELL" if kind.startswith("S(") else TYPES[kind]
        lo, hi = parse_amount_range(m.group("amount"))
        rows.append(
            {
                "ticker": ticker,
                "asset_name": asset[-255:],
                "owner": owner_label(owner),
                "action": action,
                "traded_at": _mdy(m.group("traded")),
                "amount_min": lo,
                "amount_max": hi,
                "detail": ASSET_TYPES.get(m.group("atype").upper(), m.group("atype")),
            }
        )
    return rows
