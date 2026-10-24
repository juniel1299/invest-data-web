from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.market.models import FxRate, PriceDaily
from apps.portfolio.models import Transaction
from apps.securities.models import Security

User = get_user_model()


@mock.patch("apps.portfolio.views.backfill_security_task.delay")
class PortfolioApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("me@example.com", "s3cure-pass-123")
        self.client.force_authenticate(self.user)
        self.aapl = Security.objects.create(ticker="AAPL", name="Apple Inc.", name_ko="애플", exchange="Nasdaq")
        self.msft = Security.objects.create(ticker="MSFT", name="Microsoft", exchange="Nasdaq")

    def add(self, **kw):
        data = {"ticker": "aapl", "side": "BUY", "quantity": "10", "price": "100", "traded_at": "2026-01-05"}
        data.update(kw)
        return self.client.post("/api/portfolio/transactions/", data, format="json")

    def test_create_and_list(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            res = self.add()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["ticker"], "AAPL")
        delay.assert_called_once()
        self.assertEqual(len(self.client.get("/api/portfolio/transactions/").data), 1)

    def test_unknown_ticker(self, delay):
        self.assertEqual(self.add(ticker="ZZZZ").status_code, 400)

    def test_rejects_oversell(self, delay):
        self.add()
        res = self.add(side="SELL", quantity="11", traded_at="2026-02-01")
        self.assertEqual(res.status_code, 400)
        self.assertIn("quantity", res.data)

    def test_rejects_edit_that_breaks_later_sell(self, delay):
        buy = self.add().data
        self.add(side="SELL", quantity="8", traded_at="2026-02-01")
        res = self.client.patch(f"/api/portfolio/transactions/{buy['id']}/", {"quantity": "5"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_other_users_data_hidden(self, delay):
        other = User.objects.create_user("x@example.com", "s3cure-pass-123")
        Transaction.objects.create(
            user=other, security=self.aapl, side="BUY", quantity=1, price=1, traded_at=date(2026, 1, 1)
        )
        self.assertEqual(self.client.get("/api/portfolio/transactions/").data, [])

    def test_summary(self, delay):
        FxRate.objects.create(date=date(2026, 1, 5), usd_krw=Decimal("1300"))
        FxRate.objects.create(date=date(2026, 10, 22), usd_krw=Decimal("1400"))
        PriceDaily.objects.create(security=self.aapl, date=date(2026, 10, 22), close=Decimal("150"))
        PriceDaily.objects.create(security=self.msft, date=date(2026, 10, 22), close=Decimal("50"))

        self.add()  # 10주 @ 100, 환율 1300 (자동)
        self.add(quantity="10", price="200", fx_rate="1350", traded_at="2026-03-02")  # 평균 150
        self.add(side="SELL", quantity="5", price="180", traded_at="2026-04-01")  # 실현 +150
        self.add(ticker="MSFT", quantity="4", price="50", traded_at="2026-05-01", fx_rate="1400")

        data = self.client.get("/api/portfolio/summary/").data
        self.assertEqual(data["fx_rate"], 1400.0)
        aapl = next(h for h in data["holdings"] if h["ticker"] == "AAPL")
        self.assertEqual(aapl["quantity"], 15.0)
        self.assertEqual(aapl["avg_price"], 150.0)
        self.assertEqual(aapl["value_usd"], 2250.0)
        self.assertEqual(aapl["pnl_usd"], 0.0)
        # 원가(원) = 1000*1300 + 2000*1350 = 4,000,000 → 3/4 남음 = 3,000,000
        self.assertEqual(aapl["avg_fx"], 1333.33)
        self.assertEqual(aapl["value_krw"], 3150000.0)
        self.assertEqual(aapl["pnl_krw"], 150000.0)
        self.assertEqual(aapl["fx_pnl_krw"], 150000.0)
        self.assertEqual(aapl["weight"], 91.84)
        self.assertEqual(data["totals"]["realized_usd"], 150.0)
        self.assertEqual(data["totals"]["value_usd"], 2450.0)
        self.assertEqual(data["totals"]["pnl_krw"], 150000)
        self.assertEqual(data["holdings"][0]["ticker"], "AAPL")

    def test_summary_without_prices(self, delay):
        self.add()
        data = self.client.get("/api/portfolio/summary/").data
        self.assertEqual(data["totals"]["unpriced"], ["AAPL"])
        self.assertIsNone(data["holdings"][0]["value_usd"])

    def test_fully_sold_hidden(self, delay):
        self.add()
        self.add(side="SELL", quantity="10", price="120", traded_at="2026-02-01")
        data = self.client.get("/api/portfolio/summary/").data
        self.assertEqual(data["holdings"], [])
        self.assertEqual(data["totals"]["realized_usd"], 200.0)

    def test_accounts(self, delay):
        res = self.client.post("/api/portfolio/accounts/", {"name": "토스", "broker": "토스증권"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.add(account=res.data["id"])
        other = User.objects.create_user("y@example.com", "s3cure-pass-123")
        self.client.force_authenticate(other)
        self.assertEqual(self.add(account=res.data["id"]).status_code, 400)
