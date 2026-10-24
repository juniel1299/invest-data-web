"""상원 eFD (efdsearch.senate.gov). 이용 약관 동의 후 검색하는 구조라 세션을 유지한다.

eFD 공시는 법으로 상업적 이용이 제한된다. 이 프로젝트는 개인 공부용이라 쓴다.
"""

import re
from datetime import datetime
from html.parser import HTMLParser

from .common import SourceError, owner_label, parse_amount_range

BASE = "https://efdsearch.senate.gov"
HOME = BASE + "/search/home/"
SEARCH = BASE + "/search/"
DATA = BASE + "/search/report/data/"
PTR_REPORT_TYPE = "[11]"

_TOKEN = re.compile(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"')
_LINK = re.compile(r'href="([^"]+)"')
TYPES = {"purchase": "BUY", "sale (full)": "SELL", "sale (partial)": "PARTIAL_SELL", "sale": "SELL", "exchange": "EXCHANGE"}


class _Table(HTMLParser):
    """첫 번째 tbody의 행을 [칸 글자, ...] 목록으로 모은다."""

    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._in_body = [], None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tbody":
            self._in_body = True
        elif self._in_body and tag == "tr":
            self._row = []
        elif self._row is not None and tag == "td":
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == "tbody":
            self._in_body = False

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_ptr_html(html):
    t = _Table()
    t.feed(html)
    rows = []
    for cells in t.rows:
        if len(cells) < 8:
            continue
        _, day, owner, ticker, asset, asset_type, kind, amount = cells[:8]
        action = TYPES.get(kind.strip().lower())
        if not action:
            continue
        lo, hi = parse_amount_range(amount)
        rows.append(
            {
                "ticker": "" if ticker.strip() in ("--", "") else ticker.strip().upper(),
                "asset_name": asset[:255],
                "owner": owner_label(owner),
                "action": action,
                "traded_at": datetime.strptime(day.strip(), "%m/%d/%Y").date(),
                "amount_min": lo,
                "amount_max": hi,
                "detail": "" if asset_type.lower().startswith("stock") else asset_type,
            }
        )
    return rows


class EfdSession:
    def __init__(self, client):
        self.client = client
        self.agreed = False

    def agree(self):
        res = self.client.get(HOME)
        res.raise_for_status()
        m = _TOKEN.search(res.text)
        if not m:
            raise SourceError("eFD 약관 페이지 형식이 바뀌었습니다.")
        res = self.client.post(
            HOME,
            data={"prohibition_agreement": "1", "csrfmiddlewaretoken": m.group(1)},
            headers={"Referer": HOME},
        )
        res.raise_for_status()
        self.agreed = True

    def search_ptrs(self, first_name, last_name, since):
        if not self.agreed:
            self.agree()
        token = self.client.cookies.get("csrftoken", "")
        res = self.client.post(
            DATA,
            data={
                "start": "0",
                "length": "100",
                "report_types": PTR_REPORT_TYPE,
                "filer_types": "[]",
                "submitted_start_date": since.strftime("%m/%d/%Y 00:00:00"),
                "submitted_end_date": "",
                "candidate_state": "",
                "senator_state": "",
                "office_id": "",
                "first_name": first_name,
                "last_name": last_name,
                "csrfmiddlewaretoken": token,
            },
            headers={"Referer": SEARCH, "X-CSRFToken": token},
        )
        res.raise_for_status()
        out = []
        for row in res.json().get("data", []):
            link = _LINK.search(row[3])
            if not link:
                continue
            path = link.group(1)
            out.append(
                {
                    "url": BASE + path if path.startswith("/") else path,
                    "key": path.rstrip("/").split("/")[-1],
                    "paper": "/paper/" in path,
                    "filed": datetime.strptime(row[4].strip(), "%m/%d/%Y").date(),
                }
            )
        return out

    def fetch_ptr(self, url):
        res = self.client.get(url, headers={"Referer": SEARCH})
        res.raise_for_status()
        return parse_ptr_html(res.text)
