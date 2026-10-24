import io
import json
import zipfile
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import httpx
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.securities.models import Security
from apps.trades import services
from apps.trades.models import CusipMap, DisclosedTrade, Filing, HoldingSnapshot, Person
from apps.trades.sources import ark, house, senate
from apps.trades.sources.common import parse_amount_range
from apps.trades.sources.sec import parse_13f_table, parse_form4


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def info_table(*rows):
    body = "".join(
        f"""<infoTable><nameOfIssuer>{n}</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>{c}</cusip>
        <value>{v}</value><shrsOrPrnAmt><sshPrnamt>{s}</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>{extra}</infoTable>"""
        for n, c, v, s, extra in rows
    )
    return f'<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">{body}</informationTable>'.encode()


def submissions(*filings):
    return {
        "filings": {
            "recent": {
                "form": [f[0] for f in filings],
                "accessionNumber": [f[1] for f in filings],
                "filingDate": [f[2] for f in filings],
                "reportDate": [f[3] for f in filings],
                "primaryDocument": [f[4] for f in filings],
            }
        }
    }


FORM4 = b"""<ownershipDocument>
<issuer><issuerCik>0000320193</issuerCik><issuerName>Apple Inc.</issuerName><issuerTradingSymbol>AAPL</issuerTradingSymbol></issuer>
<reportingOwner><reportingOwnerId><rptOwnerCik>0001214156</rptOwnerCik><rptOwnerName>Cook Timothy D</rptOwnerName></reportingOwnerId>
<reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>1</isOfficer><officerTitle>CEO</officerTitle></reportingOwnerRelationship></reportingOwner>
<nonDerivativeTable>
<nonDerivativeTransaction><transactionDate><value>2026-10-20</value></transactionDate>
<transactionCoding><transactionCode>S</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>10000</value></transactionShares><transactionPricePerShare><value>250.5</value></transactionPricePerShare>
<transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction>
<nonDerivativeTransaction><transactionDate><value>2026-10-20</value></transactionDate>
<transactionCoding><transactionCode>M</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>5000</value></transactionShares>
<transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction>
</nonDerivativeTable></ownershipDocument>"""


class CommonTests(TestCase):
    def test_amount_ranges(self):
        self.assertEqual(parse_amount_range("$1,001 - $15,000"), (Decimal(1001), Decimal(15000)))
        self.assertEqual(parse_amount_range("Over $50,000,000"), (Decimal(50000000), None))
        self.assertEqual(parse_amount_range("--"), (None, None))


class ThirteenFTests(TestCase):
    def setUp(self):
        self.aapl = Security.objects.create(ticker="AAPL", name="Apple", exchange="Nasdaq")
        self.ko = Security.objects.create(ticker="KO", name="Coca-Cola", exchange="NYSE")
        self.person = Person.objects.create(slug="buffett", name="Buffett", name_ko="버핏", kind="INVESTOR", cik=1067983, track_13f=True)

    def test_parse_merges_and_skips_options(self):
        xml = info_table(
            ("APPLE INC", "037833100", "1000", "10", ""),
            ("APPLE INC", "037833100", "500", "5", ""),
            ("APPLE INC", "037833100", "99", "1", "<putCall>Call</putCall>"),
        )
        rows = parse_13f_table(xml)
        self.assertEqual(rows, [{"cusip": "037833100", "name": "APPLE INC", "shares": Decimal(15), "value": Decimal(1500)}])
        self.assertEqual(parse_13f_table(xml, dollars=False)[0]["value"], Decimal(1500000))

    def test_quarter_diff(self):
        q1 = info_table(("APPLE INC", "037833100", "2000", "10", ""), ("COCA COLA", "191216100", "500", "50", ""))
        q2 = info_table(("APPLE INC", "037833100", "1500", "6", ""), ("CHEVRON", "166764100", "900", "9", ""))
        figi_calls = []

        def handler(req):
            url = str(req.url)
            if "submissions" in url:
                return httpx.Response(200, json=submissions(
                    ("13F-HR", "0001-26-000001", "2026-05-15", "2026-03-31", "primary_doc.xml"),
                    ("13F-HR/A", "0001-26-000009", "2026-06-01", "2026-03-31", "primary_doc.xml"),
                    ("13F-HR", "0001-26-000002", "2026-08-14", "2026-06-30", "primary_doc.xml"),
                ))
            if url.endswith("index.json"):
                return httpx.Response(200, json={"directory": {"item": [{"name": "primary_doc.xml"}, {"name": "infotable.xml"}]}})
            if url.endswith("infotable.xml"):
                return httpx.Response(200, content=q1 if "000126000001" in url else q2)
            if "openfigi" in url:
                jobs = json.loads(req.content)
                figi_calls.append([j["idValue"] for j in jobs])
                names = {"037833100": "AAPL", "191216100": "KO", "166764100": "CVX"}
                return httpx.Response(200, json=[{"data": [{"ticker": names[j["idValue"]], "exchCode": "US"}]} for j in jobs])
            return httpx.Response(404)

        trades = services.update_13f(self.person, client_for(handler))
        by = {t.ticker: t for t in trades}
        self.assertEqual(set(by), {"AAPL", "KO", "CVX"})
        self.assertEqual((by["AAPL"].action, by["AAPL"].shares), ("REDUCE", Decimal(4)))
        self.assertEqual(by["KO"].action, "EXIT")
        self.assertEqual(by["KO"].security, self.ko)
        self.assertEqual(by["CVX"].action, "NEW")
        self.assertIsNone(by["CVX"].security)  # 종목 마스터에 없는 티커
        self.assertEqual(by["CVX"].filed_at, date(2026, 8, 14))
        # 정정 공시는 건너뛰고, 한 번 찾은 CUSIP은 다시 묻지 않는다
        self.assertEqual(Filing.objects.filter(source="13F").count(), 2)
        self.assertEqual(sum(len(c) for c in figi_calls), 3)
        self.assertEqual(CusipMap.objects.get(cusip="166764100").ticker, "CVX")
        # 다시 돌려도 같은 공시는 다시 처리하지 않는다
        self.assertEqual(services.update_13f(self.person, client_for(handler)), [])


class Form4Tests(TestCase):
    def test_parse(self):
        p = parse_form4(FORM4)
        self.assertEqual((p["ticker"], p["owner_name"], p["owner_title"]), ("AAPL", "Cook Timothy D", "CEO, 이사"))
        self.assertEqual([t["code"] for t in p["transactions"]], ["S", "M"])

    def test_insiders_keep_open_market_only(self):
        aapl = Security.objects.create(ticker="AAPL", name="Apple", exchange="Nasdaq", cik=320193)

        def handler(req):
            url = str(req.url)
            if "submissions" in url:
                return httpx.Response(200, json=submissions(
                    ("4", "0001-26-000100", "2026-10-21", "", "xslF345X05/wk-form4.xml"),
                    ("4", "0001-26-000050", "2026-08-01", "", "xslF345X05/old.xml"),
                    ("8-K", "0001-26-000101", "2026-10-21", "", "x.htm"),
                ))
            self.assertTrue(url.endswith("/000126000100/wk-form4.xml"), url)
            return httpx.Response(200, content=FORM4)

        trades = services.update_insiders(aapl, client_for(handler), today=date(2026, 10, 24))
        self.assertEqual(len(trades), 1)
        t = trades[0]
        self.assertEqual((t.action, t.shares, t.price, t.security), ("SELL", Decimal(10000), Decimal("250.5"), aapl))
        self.assertIsNone(t.person)
        self.assertEqual(t.value_usd, Decimal("2505000.0"))

    def test_owner_cik_links_tracked_person(self):
        aapl = Security.objects.create(ticker="AAPL", name="Apple", exchange="Nasdaq", cik=320193)
        cook = Person.objects.create(slug="cook", name="Cook", name_ko="쿡", kind="INVESTOR", cik=1214156)

        def handler(req):
            if "submissions" in str(req.url):
                return httpx.Response(200, json=submissions(("4", "0001-26-000100", "2026-10-21", "", "a/f.xml")))
            return httpx.Response(200, content=FORM4)

        trades = services.update_insiders(aapl, client_for(handler), today=date(2026, 10, 24))
        self.assertEqual(trades[0].person, cook)


ARK_CSV = """date,fund,company,ticker,cusip,shares,"market value ($)","weight (%)"
{d},ARKK,TESLA INC,TSLA,88160R101,"{tsla}","$1,000,000.00",10.00%
{d},ARKK,ROKU INC,ROKU,77543R102,"{roku}","$500,000.00",5.00%
{d},ARKK,COINBASE,COIN,19260Q107,"{coin}","$300,000.00",3.00%
{extra}
"Investors should carefully consider the investment objectives..."
"""


class ArkTests(TestCase):
    def setUp(self):
        self.person = Person.objects.create(slug="cathie-wood", name="Wood", name_ko="캐시 우드", kind="INVESTOR", track_ark=True)
        self.tsla = Security.objects.create(ticker="TSLA", name="Tesla", exchange="Nasdaq")

    def test_parse(self):
        as_of, rows = ark.parse_holdings(ARK_CSV.format(d="10/23/2026", tsla="1,000", roku="500", coin="300", extra=""))
        self.assertEqual(as_of, date(2026, 10, 23))
        self.assertEqual([r["ticker"] for r in rows], ["TSLA", "ROKU", "COIN"])
        self.assertEqual(rows[0]["shares"], Decimal(1000))

    def test_creation_flows_are_not_trades(self):
        def csv_for(day, shares):
            head = 'date,fund,company,ticker,cusip,shares,"market value ($)","weight (%)"\n'
            return head + "".join(f'{day},ARKK,{t} INC,{t},CUSIP{t},"{n:,}","$1,000.00",1%\n' for t, n in shares.items())

        base = {"TSLA": 1000, "ROKU": 500, "COIN": 300, "HOOD": 400, "SHOP": 600, "CRSP": 700}
        # 다음 날: 모든 종목 2% 증가(ETF 설정) + ROKU만 10% 추가 매수 + COIN 전량 매도 + PLTR 신규
        nxt = {t: round(n * 1.02) for t, n in base.items() if t != "COIN"}
        nxt["ROKU"] = round(500 * 1.02) + 50
        nxt["PLTR"] = 200
        fund_csv = {}

        def handler(req):
            if "ARKK" not in req.url.path:
                return httpx.Response(200, text='date,fund,company,ticker,cusip,shares,"market value ($)","weight (%)"\n')
            return httpx.Response(200, text=fund_csv["text"])

        fund_csv["text"] = csv_for("10/22/2026", base)
        self.assertEqual(services.update_ark(self.person, client_for(handler)), [])
        fund_csv["text"] = csv_for("10/23/2026", nxt)
        trades = {t.ticker: t for t in services.update_ark(self.person, client_for(handler))}
        self.assertEqual(set(trades), {"ROKU", "COIN", "PLTR"})
        self.assertEqual((trades["ROKU"].action, trades["ROKU"].shares), ("BUY", Decimal(50)))
        self.assertEqual((trades["COIN"].action, trades["COIN"].detail), ("SELL", "ARKK 전량 매도"))
        self.assertEqual(trades["PLTR"].detail, "ARKK 신규 편입")
        self.assertEqual(trades["PLTR"].traded_at, date(2026, 10, 23))


HOUSE_INDEX = b"""<?xml version="1.0" encoding="utf-8"?><FinancialDisclosure>
<Member><Prefix>Hon.</Prefix><Last>Pelosi</Last><First>Nancy</First><Suffix/><FilingType>P</FilingType><StateDst>CA11</StateDst><Year>2026</Year><FilingDate>10/20/2026</FilingDate><DocID>20031111</DocID></Member>
<Member><Prefix/><Last>Pelosi</Last><First>Nancy</First><Suffix/><FilingType>O</FilingType><StateDst>CA11</StateDst><Year>2026</Year><FilingDate>5/15/2026</FilingDate><DocID>10070000</DocID></Member>
<Member><Prefix/><Last>Pelosi</Last><First>Someone</First><Suffix/><FilingType>P</FilingType><StateDst>NY01</StateDst><Year>2026</Year><FilingDate>10/20/2026</FilingDate><DocID>20039999</DocID></Member>
<Member><Prefix/><Last>Khanna</Last><First>Ro</First><Suffix/><FilingType>P</FilingType><StateDst>CA17</StateDst><Year>2026</Year><FilingDate>10/21/2026</FilingDate><DocID>8221234</DocID></Member>
</FinancialDisclosure>"""

PTR_TEXT = """Filing ID #20031111
P T R
Clerk of the House of Representatives
ID Owner Asset Transaction
Type
Date Notification
Date
Amount Cap.
Gains >
$200?
SP Alphabet Inc. - Class A Common
Stock (GOOGL) [ST]
P 10/01/2026 10/01/2026 $500,001 -
$1,000,000
F S : New
D : Purchased 50 call options with a strike price of $150.
SP Apple Inc. - Common Stock (AAPL)
[ST]
S (partial) 10/02/2026 10/03/2026 $1,000,001 - $5,000,000
F S : New
JT US Treasury Bill [GS] P 10/05/2026 10/05/2026 $15,001 - $50,000
* For the complete list of asset type abbreviations, please visit
"""


class HouseTests(TestCase):
    def test_parse_index(self):
        rows = house.parse_index(HOUSE_INDEX)
        self.assertEqual(rows[0]["doc_id"], "20031111")
        self.assertEqual(rows[0]["filed"], date(2026, 10, 20))

    def test_parse_ptr_text(self):
        rows = house.parse_ptr_text(PTR_TEXT)
        self.assertEqual([r["ticker"] for r in rows], ["GOOGL", "AAPL", ""])
        self.assertEqual([r["action"] for r in rows], ["BUY", "PARTIAL_SELL", "BUY"])
        self.assertEqual(rows[0]["asset_name"], "Alphabet Inc. - Class A Common Stock")
        self.assertEqual(rows[0]["owner"], "배우자")
        self.assertEqual((rows[0]["amount_min"], rows[0]["amount_max"]), (Decimal(500001), Decimal(1000000)))
        self.assertEqual(rows[1]["traded_at"], date(2026, 10, 2))
        self.assertEqual((rows[2]["asset_name"], rows[2]["owner"], rows[2]["detail"]), ("US Treasury Bill", "공동", "국채"))

    def test_update_house_matches_member_and_state(self):
        googl = Security.objects.create(ticker="GOOGL", name="Alphabet", exchange="Nasdaq")
        pelosi = Person.objects.create(slug="pelosi", name="Pelosi", name_ko="펠로시", kind="HOUSE", house_last_name="Pelosi", house_state="CA")
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, "w") as z:
            z.writestr("2026FD.xml", HOUSE_INDEX)
            z.writestr("2026FD.txt", "ignored")
        fetched = []

        def handler(req):
            if req.url.path.endswith("2026FD.zip"):
                return httpx.Response(200, content=zipped.getvalue())
            fetched.append(req.url.path)
            return httpx.Response(200, content=b"%PDF")

        with mock.patch.object(house, "pdf_text", return_value=PTR_TEXT):
            trades = services.update_house(client_for(handler), year=2026)
        self.assertEqual(fetched, ["/public_disc/ptr-pdfs/2026/20031111.pdf"])
        self.assertEqual(len(trades), 3)
        self.assertEqual(trades[0].security, googl)
        self.assertEqual(trades[0].person, pelosi)
        self.assertEqual(trades[0].filed_at, date(2026, 10, 20))

    def test_scanned_pdf_keeps_link_only(self):
        Person.objects.create(slug="khanna", name="Khanna", name_ko="칸나", kind="HOUSE", house_last_name="Khanna")
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, "w") as z:
            z.writestr("2026FD.xml", HOUSE_INDEX)

        def handler(req):
            return httpx.Response(200, content=zipped.getvalue() if req.url.path.endswith(".zip") else b"%PDF")

        with mock.patch.object(house, "pdf_text", return_value=""):
            self.assertEqual(services.update_house(client_for(handler), year=2026), [])
        f = Filing.objects.get(source="HOUSE")
        self.assertFalse(f.parsed)
        self.assertTrue(f.url.endswith("/2026/8221234.pdf"))


SENATE_PTR = """<html><table class="table"><thead><tr><th>#</th><th>Transaction Date</th></tr></thead><tbody>
<tr><td>1</td><td>10/14/2026</td><td>Spouse</td><td><a href="https://finance.yahoo.com/q?s=NVDA">NVDA</a></td>
<td>NVIDIA Corporation</td><td>Stock</td><td>Purchase</td><td>$15,001 - $50,000</td><td>--</td></tr>
<tr><td>2</td><td>10/15/2026</td><td>Self</td><td>--</td><td>Some Muni Bond</td><td>Municipal Security</td><td>Sale (Partial)</td><td>$1,001 - $15,000</td><td>--</td></tr>
</tbody></table></html>"""


class SenateTests(TestCase):
    def test_full_flow(self):
        nvda = Security.objects.create(ticker="NVDA", name="NVIDIA", exchange="Nasdaq")
        Person.objects.create(slug="tuberville", name="T", name_ko="터버빌", kind="SENATE", senate_first_name="Tommy", senate_last_name="Tuberville")
        seen = []

        def handler(req):
            seen.append((req.method, req.url.path))
            if req.url.path == "/search/home/" and req.method == "GET":
                return httpx.Response(200, text='<input type="hidden" name="csrfmiddlewaretoken" value="tok123">',
                                      headers={"Set-Cookie": "csrftoken=cookie123; Path=/"})
            if req.url.path == "/search/home/":
                self.assertIn(b"prohibition_agreement=1", req.content)
                return httpx.Response(200, text="ok")
            if req.url.path == "/search/report/data/":
                self.assertEqual(req.headers["X-CSRFToken"], "cookie123")
                self.assertIn(b"last_name=Tuberville", req.content)
                return httpx.Response(200, json={"data": [
                    ["Tommy", "Tuberville", "Tuberville, Tommy (Senator)", '<a href="/search/view/ptr/abc-123/" target="_blank">PTR</a>', "10/20/2026"],
                    ["Tommy", "Tuberville", "Tuberville, Tommy (Senator)", '<a href="/search/view/paper/def-456/" target="_blank">PTR</a>', "10/01/2026"],
                ]})
            if req.url.path == "/search/view/ptr/abc-123/":
                return httpx.Response(200, text=SENATE_PTR)
            return httpx.Response(404)

        trades = services.update_senate(client_for(handler), since=date(2026, 1, 1))
        self.assertEqual([(t.ticker, t.action, t.owner) for t in trades], [("NVDA", "BUY", "배우자"), ("", "PARTIAL_SELL", "본인")])
        self.assertEqual(trades[0].security, nvda)
        self.assertEqual(trades[1].detail, "Municipal Security")
        paper = Filing.objects.get(key="def-456")
        self.assertFalse(paper.parsed)
        self.assertNotIn(("GET", "/search/view/paper/def-456/"), seen)

    def test_parse_html(self):
        self.assertEqual(len(senate.parse_ptr_html(SENATE_PTR)), 2)


class SeedPeopleTests(TestCase):
    def test_idempotent_and_keeps_edits(self):
        call_command("seed_people", stdout=io.StringIO())
        Person.objects.filter(slug="pelosi").update(name_ko="펠로시(수정)")
        call_command("seed_people", stdout=io.StringIO())
        self.assertEqual(Person.objects.get(slug="pelosi").name_ko, "펠로시(수정)")
        self.assertEqual(Person.objects.filter(is_current_president=True).get().slug, "trump")
        self.assertEqual(Person.objects.filter(kind="PRINCIPLE").count(), 3)
