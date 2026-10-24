from datetime import date, datetime, timedelta, timezone
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.market.models import CalendarEvent, Fundamentals, FxRate, MacroPoint, NewsItem, PriceDaily
from apps.portfolio.models import Transaction, Watch
from apps.securities.models import Security

User = get_user_model()


class MarketApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("me@example.com", "s3cure-pass-123")
        self.client.force_authenticate(self.user)
        self.aapl = Security.objects.create(ticker="AAPL", name="Apple Inc.", name_ko="애플", exchange="Nasdaq", cik=320193)
        self.msft = Security.objects.create(ticker="MSFT", name="Microsoft", exchange="Nasdaq")
        self.ko = Security.objects.create(ticker="KO", name="Coca-Cola", exchange="NYSE")
        self.today = date.today()

    def test_overview(self):
        MacroPoint.objects.create(series="SP500", date=self.today - timedelta(days=1), value=100)
        MacroPoint.objects.create(series="SP500", date=self.today, value=102)
        FxRate.objects.create(date=self.today, usd_krw=1400)
        data = self.client.get("/api/market/overview/").data
        sp = next(i for i in data["indices"] if i["series"] == "SP500")
        self.assertEqual((sp["value"], sp["change"], sp["change_pct"]), (102.0, 2.0, 2.0))
        self.assertEqual(sp["history"], [100.0, 102.0])
        self.assertIsNone(next(i for i in data["indices"] if i["series"] == "VIXCLS")["value"])
        self.assertEqual(data["fx"]["value"], 1400.0)
        self.assertIsNone(data["fx"]["change"])

    def test_news_only_mine(self):
        Transaction.objects.create(user=self.user, security=self.aapl, side="BUY", quantity=1, price=1, traded_at=self.today)
        Watch.objects.create(user=self.user, security=self.ko)
        now = datetime.now(timezone.utc)
        for sec in (self.aapl, self.msft, self.ko):
            NewsItem.objects.create(security=sec, title=f"{sec.ticker} news", url=f"https://n/{sec.ticker}", published_at=now)
        res = self.client.get("/api/market/news/")
        self.assertEqual({n["ticker"] for n in res.data}, {"AAPL", "KO"})
        res = self.client.get("/api/market/news/?ticker=msft")
        self.assertEqual([n["ticker"] for n in res.data], ["MSFT"])

    def test_calendar(self):
        Watch.objects.create(user=self.user, security=self.aapl)
        CalendarEvent.objects.create(kind="FOMC", date=self.today + timedelta(days=3), title="FOMC 금리 결정")
        CalendarEvent.objects.create(kind="EARNINGS", security=self.aapl, date=self.today + timedelta(days=5), title="AAPL 실적 발표")
        CalendarEvent.objects.create(kind="EARNINGS", security=self.msft, date=self.today + timedelta(days=5), title="MSFT 실적 발표")
        CalendarEvent.objects.create(kind="EARNINGS", security=self.aapl, date=self.today - timedelta(days=5), title="지난 실적")
        CalendarEvent.objects.create(kind="EARNINGS", security=self.aapl, date=self.today + timedelta(days=60), title="먼 실적")
        res = self.client.get("/api/market/calendar/")
        self.assertEqual([e["title"] for e in res.data], ["FOMC 금리 결정", "AAPL 실적 발표"])
        self.assertEqual(res.data[1]["name"], "애플")
        self.assertEqual(len(self.client.get("/api/market/calendar/?days=90").data), 3)
        self.assertEqual(len(self.client.get("/api/market/calendar/?days=abc").data), 2)

    @mock.patch("apps.market.services.update_fundamentals")
    @mock.patch("apps.market.services.update_prices")
    def test_detail(self, update_prices, update_fundamentals):
        for i, close in enumerate([180, 220, 200, 210]):
            PriceDaily.objects.create(security=self.aapl, date=self.today - timedelta(days=3 - i), close=close)
        Fundamentals.objects.create(
            security=self.aapl, shares_outstanding=1000, eps_ttm=7, revenue_ttm=500, net_income_ttm=100,
            annual=[{"year": 2025, "revenue": 400}], as_of=date(2026, 6, 30),
        )
        CalendarEvent.objects.create(kind="EX_DIVIDEND", security=self.aapl, date=self.today - timedelta(days=30), title="배당락", detail={"amount": 1.05})
        CalendarEvent.objects.create(kind="EARNINGS", security=self.aapl, date=self.today + timedelta(days=10), title="실적")
        Watch.objects.create(user=self.user, security=self.aapl)

        d = self.client.get("/api/securities/aapl/").data
        update_prices.assert_not_called()
        update_fundamentals.assert_not_called()
        self.assertEqual((d["price"], d["change"], d["change_pct"]), (210.0, 10.0, 5.0))
        self.assertEqual((d["high_52w"], d["low_52w"]), (220.0, 180.0))
        self.assertEqual(d["market_cap"], 210000.0)
        self.assertEqual(d["per"], 30.0)
        self.assertEqual(d["dividend_ttm"], 1.05)
        self.assertEqual(d["dividend_yield"], 0.5)
        self.assertTrue(d["is_watched"])
        self.assertEqual([e["title"] for e in d["events"]], ["실적"])
        self.assertEqual(d["annual"], [{"year": 2025, "revenue": 400}])

    @mock.patch("apps.market.services.update_fundamentals", side_effect=RuntimeError("blocked"))
    @mock.patch("apps.market.services.update_prices", side_effect=RuntimeError("blocked"))
    def test_detail_fetches_new_ticker_and_survives_failure(self, update_prices, update_fundamentals):
        res = self.client.get("/api/securities/AAPL/")
        self.assertEqual(res.status_code, 200)
        update_prices.assert_called_once()
        update_fundamentals.assert_called_once()
        self.assertIsNone(res.data["price"])
        self.assertIsNone(res.data["per"])
        self.assertFalse(res.data["is_watched"])

    def test_detail_unknown(self):
        self.assertEqual(self.client.get("/api/securities/ZZZZ/").status_code, 404)

    def test_prices_range(self):
        for days in (10, 60, 300):
            PriceDaily.objects.create(security=self.msft, date=self.today - timedelta(days=days), close=days)
        self.assertEqual(len(self.client.get("/api/securities/MSFT/prices/?range=1M").data), 1)
        self.assertEqual(len(self.client.get("/api/securities/MSFT/prices/").data), 2)
        rows = self.client.get("/api/securities/MSFT/prices/?range=1Y").data
        self.assertEqual([r["close"] for r in rows], [300.0, 60.0, 10.0])

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/market/overview/").status_code, 401)


@mock.patch("apps.portfolio.views.backfill_security_task.delay")
class WatchApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("me@example.com", "s3cure-pass-123")
        self.client.force_authenticate(self.user)
        Security.objects.create(ticker="AAPL", name="Apple Inc.", exchange="Nasdaq")

    def test_add_list_remove(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post("/api/portfolio/watches/", {"ticker": "aapl"}, format="json")
        self.assertEqual(res.status_code, 201)
        delay.assert_called_once()
        self.assertEqual(self.client.post("/api/portfolio/watches/", {"ticker": "AAPL"}, format="json").status_code, 200)
        self.assertEqual([w["ticker"] for w in self.client.get("/api/portfolio/watches/").data], ["AAPL"])
        self.assertEqual(self.client.delete("/api/portfolio/watches/aapl/").status_code, 204)
        self.assertEqual(self.client.get("/api/portfolio/watches/").data, [])

    def test_unknown_ticker(self, delay):
        self.assertEqual(self.client.post("/api/portfolio/watches/", {"ticker": "ZZZZ"}, format="json").status_code, 404)
