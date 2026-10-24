from datetime import date
from decimal import Decimal

import httpx
from django.test import TestCase, override_settings

from apps.market.models import FxRate, PriceDaily
from apps.market.services import fx_on, update_fx, update_prices
from apps.securities.models import Security

STOOQ_CSV = """Date,Open,High,Low,Close,Volume
2026-10-21,250,252,249,251.5,1000
2026-10-22,251,255,250,254.25,1000
"""


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


class PriceTests(TestCase):
    def setUp(self):
        self.sec = Security.objects.create(ticker="BRK.B", name="Berkshire", exchange="NYSE")

    def test_stooq_saves_closes(self):
        seen = {}

        def handler(request):
            seen["s"] = request.url.params["s"]
            return httpx.Response(200, text=STOOQ_CSV)

        saved = update_prices(self.sec, client_for(handler), today=date(2026, 10, 23))
        self.assertEqual(saved, 2)
        self.assertEqual(seen["s"], "brk-b.us")
        self.assertEqual(self.sec.prices.first().close, Decimal("254.25"))

    def test_resumes_after_last_saved_day(self):
        PriceDaily.objects.create(security=self.sec, date=date(2026, 10, 21), close=1)
        seen = {}

        def handler(request):
            seen["d1"] = request.url.params["d1"]
            return httpx.Response(200, text=STOOQ_CSV)

        update_prices(self.sec, client_for(handler), today=date(2026, 10, 23))
        self.assertEqual(seen["d1"], "20261022")
        # 이미 있는 날은 덮어쓰지 않는다
        self.assertEqual(self.sec.prices.count(), 2)

    def test_no_data(self):
        saved = update_prices(
            self.sec, client_for(lambda r: httpx.Response(200, text="No data")), today=date(2026, 10, 23)
        )
        self.assertEqual(saved, 0)

    @override_settings(PRICE_PROVIDER="tiingo", TIINGO_API_KEY="k")
    def test_tiingo(self):
        def handler(request):
            self.assertIn("/BRK-B/", request.url.path)
            return httpx.Response(200, json=[{"date": "2026-10-22T00:00:00.000Z", "close": 254.25}])

        update_prices(self.sec, client_for(handler), today=date(2026, 10, 23))
        self.assertEqual(self.sec.prices.get().close, Decimal("254.25"))


class FxTests(TestCase):
    def test_update_and_lookup(self):
        def handler(request):
            return httpx.Response(
                200, json={"rates": {"2026-10-21": {"KRW": 1400.5}, "2026-10-22": {"KRW": 1410}}}
            )

        self.assertEqual(update_fx(client_for(handler), today=date(2026, 10, 23)), 2)
        self.assertEqual(fx_on(date(2026, 10, 25)), Decimal("1410"))
        self.assertEqual(fx_on(date(2026, 10, 21)), Decimal("1400.5"))
        self.assertIsNone(fx_on(date(2026, 1, 1)))
        self.assertEqual(fx_on(), Decimal("1410"))

    def test_skips_when_up_to_date(self):
        FxRate.objects.create(date=date(2026, 10, 23), usd_krw=1400)
        calls = []
        update_fx(client_for(lambda r: calls.append(r) or httpx.Response(200, json={})), today=date(2026, 10, 23))
        self.assertEqual(calls, [])
