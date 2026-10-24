import io
from datetime import date
from decimal import Decimal

import httpx
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.market import providers, services
from apps.market.fundamentals import parse_company_facts
from apps.market.models import CalendarEvent, MacroPoint
from apps.securities.models import Security


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def fact(start, end, val, filed, form="10-K"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


COMPANY_FACTS = {
    "facts": {
        "dei": {
            "EntityCommonStockSharesOutstanding": {
                "units": {
                    "shares": [
                        {"end": "2025-07-15", "val": 900, "accn": "a1"},
                        # 클래스 두 개가 같은 날짜로 보고된 경우 더한다
                        {"end": "2026-07-20", "val": 600, "accn": "a2"},
                        {"end": "2026-07-20", "val": 400, "accn": "a2b"},
                        # 같은 값이 다른 보고서에 반복돼도 한 번만 센다
                        {"end": "2026-07-20", "val": 600, "accn": "a2"},
                    ]
                }
            }
        },
        "us-gaap": {
            # 예전 태그는 오래된 연도까지만 있다
            "SalesRevenueNet": {
                "units": {"USD": [fact("2022-01-01", "2022-12-31", 50, "2023-02-01")]}
            },
            "Revenues": {
                "units": {
                    "USD": [
                        fact("2024-01-01", "2024-12-31", 100, "2025-02-01"),
                        fact("2025-01-01", "2025-12-31", 110, "2026-02-01"),
                        # 정정 보고로 같은 기간 값이 바뀌면 나중 값을 쓴다
                        fact("2025-01-01", "2025-12-31", 120, "2026-03-01", form="10-K/A"),
                        fact("2025-01-01", "2025-06-30", 50, "2025-08-01", form="10-Q"),
                        fact("2026-01-01", "2026-06-30", 70, "2026-08-01", form="10-Q"),
                        fact("2026-04-01", "2026-06-30", 40, "2026-08-01", form="10-Q"),
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {"USD": [fact("2025-01-01", "2025-12-31", 30, "2026-02-01")]}
            },
            "EarningsPerShareDiluted": {
                "units": {"USD/shares": [fact("2025-01-01", "2025-12-31", 2.5, "2026-02-01")]}
            },
        },
    }
}

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Apple beats estimates - Reuters</title><link>https://news.example/1</link>
<pubDate>Thu, 22 Oct 2026 13:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
<item><title>No date</title><link>https://news.example/2</link></item>
</channel></rss>"""


class FredTests(TestCase):
    def test_parse_skips_holidays(self):
        csv = "observation_date,SP500\n2026-10-21,5800.1\n2026-10-22,.\n2026-10-23,5850.5\n"
        rows = providers.fetch_fred_series(client_for(lambda r: httpx.Response(200, text=csv)), "SP500", date(2026, 10, 1))
        self.assertEqual(rows, [(date(2026, 10, 21), Decimal("5800.1")), (date(2026, 10, 23), Decimal("5850.5"))])

    def test_update_macro_resumes(self):
        MacroPoint.objects.create(series="SP500", date=date(2026, 10, 22), value=1)
        seen = {}

        def handler(request):
            seen[request.url.params["id"]] = request.url.params["cosd"]
            return httpx.Response(200, text="observation_date,X\n2026-10-23,2\n")

        saved = services.update_macro(client_for(handler), today=date(2026, 10, 23))
        self.assertEqual(seen["SP500"], "2026-10-23")
        self.assertEqual(set(seen), set(services.MACRO_SERIES))
        self.assertEqual(saved["SP500"], 1)
        self.assertEqual(MacroPoint.objects.filter(series="SP500").count(), 2)


class FundamentalsTests(TestCase):
    def test_parse(self):
        f = parse_company_facts(COMPANY_FACTS)
        self.assertEqual(f["shares_outstanding"], 1000)
        # TTM = 2025년 120 + 2026 상반기 70 - 2025 상반기 50
        self.assertEqual(f["revenue_ttm"], Decimal("140"))
        self.assertEqual(f["as_of"], date(2026, 6, 30))
        self.assertEqual(f["net_income_ttm"], Decimal("30"))
        self.assertEqual(f["eps_ttm"], Decimal("2.5"))
        self.assertEqual([r["year"] for r in f["annual"]], [2024, 2025])
        self.assertEqual(f["annual"][1], {"year": 2025, "end": "2025-12-31", "revenue": 120.0, "net_income": 30.0, "eps": 2.5})

    def test_update_saves(self):
        sec = Security.objects.create(ticker="AAPL", name="Apple", exchange="Nasdaq", cik=320193)

        def handler(request):
            self.assertIn("CIK0000320193", request.url.path)
            self.assertTrue(request.headers["User-Agent"])
            return httpx.Response(200, json=COMPANY_FACTS)

        services.update_fundamentals(sec, client_for(handler))
        self.assertEqual(sec.fundamentals.shares_outstanding, 1000)

    def test_missing_company(self):
        sec = Security.objects.create(ticker="X", name="X", exchange="NYSE", cik=1)
        self.assertIsNone(services.update_fundamentals(sec, client_for(lambda r: httpx.Response(404))))


class NewsTests(TestCase):
    def test_parse_and_keep_limit(self):
        sec = Security.objects.create(ticker="AAPL", name="Apple", exchange="Nasdaq")
        saved = services.update_news(sec, client_for(lambda r: httpx.Response(200, content=RSS)))
        self.assertEqual(saved, 1)
        item = sec.news.get()
        self.assertEqual(item.title, "Apple beats estimates")
        self.assertEqual(item.source, "Reuters")
        # 같은 기사는 다시 저장하지 않는다
        services.update_news(sec, client_for(lambda r: httpx.Response(200, content=RSS)))
        self.assertEqual(sec.news.count(), 1)


@override_settings(FINNHUB_API_KEY="k", ALPHA_VANTAGE_API_KEY="k")
class CalendarSourceTests(TestCase):
    def setUp(self):
        self.sec = Security.objects.create(ticker="BRK.B", name="Berkshire", exchange="NYSE")

    def test_earnings(self):
        body = {
            "earningsCalendar": [
                {"symbol": "BRK-B", "date": "2026-11-02", "hour": "bmo", "quarter": 3, "year": 2026, "epsEstimate": 5.1},
                {"symbol": "OTHER", "date": "2026-11-03"},
            ]
        }
        services.update_earnings(self.sec, client_for(lambda r: httpx.Response(200, json=body)), today=date(2026, 10, 23))
        e = CalendarEvent.objects.get()
        self.assertEqual((e.kind, e.date, e.detail["hour"]), ("EARNINGS", date(2026, 11, 2), "bmo"))

    @override_settings(FINNHUB_API_KEY="")
    def test_earnings_needs_key(self):
        with self.assertRaises(providers.ProviderError):
            services.update_earnings(self.sec, client_for(lambda r: httpx.Response(200)))

    def test_dividends(self):
        body = {
            "data": [
                {"ex_dividend_date": "2026-08-10", "payment_date": "2026-08-14", "amount": "0.26"},
                {"ex_dividend_date": "2026-05-11", "payment_date": "None", "amount": "0.25"},
                {"ex_dividend_date": "2020-05-11", "payment_date": "2020-05-14", "amount": "0.20"},
            ]
        }
        services.update_dividends(self.sec, client_for(lambda r: httpx.Response(200, json=body)), today=date(2026, 10, 23))
        self.assertEqual(self.sec.events.filter(kind="EX_DIVIDEND").count(), 2)
        self.assertEqual(self.sec.events.filter(kind="DIVIDEND_PAY").count(), 1)
        self.assertEqual(services.dividends_ttm(self.sec, today=date(2026, 10, 23)), Decimal("0.51"))

    def test_dividend_limit_message(self):
        body = {"Information": "Our standard API rate limit is 25 requests per day."}
        with self.assertRaisesMessage(providers.ProviderError, "25 requests"):
            services.update_dividends(self.sec, client_for(lambda r: httpx.Response(200, json=body)))


class SeedFomcTests(TestCase):
    def test_idempotent(self):
        call_command("seed_fomc", stdout=io.StringIO())
        call_command("seed_fomc", stdout=io.StringIO())
        self.assertEqual(CalendarEvent.objects.filter(kind="FOMC").count(), 8)
