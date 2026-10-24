import json
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import httpx
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.market.models import Fundamentals, MacroPoint, PriceDaily
from apps.portfolio.models import Transaction, Watch
from apps.securities.models import Security
from apps.trades import alerts, principles
from apps.trades.models import DisclosedTrade, Filing, Follow, HoldingSnapshot, Notification, Person

User = get_user_model()
TODAY = date.today()


def make_trade(person, security, action="BUY", filed=TODAY, key=None, **kw):
    filing = Filing.objects.create(source=kw.pop("source", "HOUSE"), key=key or f"k{Filing.objects.count()}",
                                   person=person, filed_at=filed, url="https://example.gov/doc.pdf")
    return DisclosedTrade.objects.create(filing=filing, person=person, security=security,
                                         ticker=security.ticker if security else "", action=action,
                                         filed_at=filed, **kw)


class TradesApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("me@example.com", "s3cure-pass-123")
        self.client.force_authenticate(self.user)
        self.aapl = Security.objects.create(ticker="AAPL", name="Apple Inc.", name_ko="애플", exchange="Nasdaq")
        self.ko = Security.objects.create(ticker="KO", name="Coca-Cola", exchange="NYSE")
        self.nvda = Security.objects.create(ticker="NVDA", name="NVIDIA", exchange="Nasdaq")
        self.pelosi = Person.objects.create(slug="pelosi", name="Nancy Pelosi", name_ko="낸시 펠로시", kind="HOUSE")
        self.buffett = Person.objects.create(slug="buffett", name="Warren Buffett", name_ko="워런 버핏", kind="INVESTOR", track_13f=True)
        Person.objects.create(slug="hidden", name="Hidden", name_ko="숨김", kind="HOUSE", active=False)
        Transaction.objects.create(user=self.user, security=self.aapl, side="BUY", quantity=10, price=100, traded_at=TODAY - timedelta(days=30))

    def test_people_and_follow(self):
        make_trade(self.pelosi, self.nvda, amount_min=1001, amount_max=15000)
        res = self.client.get("/api/trades/people/")
        self.assertEqual([p["slug"] for p in res.data], ["pelosi", "buffett"])
        self.assertEqual(res.data[0]["recent_trades"], 1)
        self.assertEqual(res.data[0]["last_filed_at"], TODAY.isoformat())
        self.assertEqual(self.client.post("/api/trades/people/pelosi/follow/").status_code, 201)
        self.assertTrue(self.client.get("/api/trades/people/?kind=HOUSE").data[0]["is_following"])
        self.assertEqual(self.client.delete("/api/trades/people/pelosi/follow/").status_code, 204)
        self.assertEqual(self.client.post("/api/trades/people/hidden/follow/").status_code, 404)

    def test_feed_scopes(self):
        Follow.objects.create(user=self.user, person=self.pelosi)
        a = make_trade(self.pelosi, self.nvda, traded_at=TODAY - timedelta(days=20), amount_min=1001, amount_max=15000, owner="배우자")
        b = make_trade(self.buffett, self.aapl, action="REDUCE", source="13F", shares=100)
        insider_filing = Filing.objects.create(source="FORM4", key="f4", security=self.aapl, filed_at=TODAY)
        c = DisclosedTrade.objects.create(filing=insider_filing, security=self.aapl, ticker="AAPL", action="SELL",
                                          filed_at=TODAY, shares=10, price=200, actor_name="Cook Timothy D", actor_title="CEO")

        all_ = self.client.get("/api/trades/feed/").data
        self.assertEqual({t["id"] for t in all_}, {a.id, b.id})  # 내부자는 기본 피드에서 빠진다
        first = next(t for t in all_ if t["id"] == a.id)
        self.assertEqual((first["delay_days"], first["owner"], first["is_buy"], first["overlap"]), (20, "배우자", True, False))
        mine = self.client.get("/api/trades/feed/?scope=mine").data
        self.assertEqual({t["id"] for t in mine}, {b.id, c.id})
        self.assertTrue(all(t["overlap"] for t in mine))
        self.assertEqual([t["id"] for t in self.client.get("/api/trades/feed/?scope=following").data], [a.id])
        self.assertEqual([t["id"] for t in self.client.get("/api/trades/feed/?kind=INSIDER").data], [c.id])
        self.assertEqual([t["id"] for t in self.client.get("/api/trades/feed/?kind=INVESTOR").data], [b.id])

    def test_person_detail_holdings_and_overlap(self):
        q1, q2 = date(2026, 3, 31), date(2026, 6, 30)
        for as_of, rows in ((q1, [("AAPL", 100, 1000), ("KO", 50, 500)]), (q2, [("AAPL", 80, 900), ("KO", 50, 600), ("NVDA", 10, 500)])):
            for t, shares, value in rows:
                HoldingSnapshot.objects.create(person=self.buffett, source="13F", as_of=as_of, key=t, ticker=t,
                                               security=Security.objects.get(ticker=t), name=t, shares=shares, value_usd=value)
        d = self.client.get("/api/trades/people/buffett/").data
        self.assertEqual(d["holdings_as_of"], "2026-06-30")
        self.assertEqual([(h["ticker"], h["weight"], h["change_pct"]) for h in d["holdings"]],
                         [("AAPL", 45.0, -20.0), ("KO", 30.0, 0.0), ("NVDA", 25.0, "NEW")])
        self.assertEqual(d["overlap"], {"tickers": ["AAPL"], "weight": 45.0})
        self.assertIn("13F", d["sources"])

    def test_security_detail_has_trades_holders_principles(self):
        HoldingSnapshot.objects.create(person=self.buffett, source="13F", as_of=date(2026, 6, 30), key="AAPL", ticker="AAPL",
                                       security=self.aapl, name="APPLE", shares=10, value_usd=1000)
        make_trade(self.pelosi, self.aapl, amount_min=1001, amount_max=15000)
        with mock.patch("apps.market.services.update_prices"), mock.patch("apps.market.services.update_fundamentals"):
            d = self.client.get("/api/securities/AAPL/").data
        self.assertEqual(d["trades"][0]["person"]["slug"], "pelosi")
        self.assertEqual(d["holders"][0]["slug"], "buffett")
        self.assertEqual(d["holders"][0]["weight"], 100.0)
        self.assertEqual(len(d["principles"]["graham"]), 6)

    def test_notifications(self):
        t = make_trade(self.pelosi, self.aapl, amount_min=1001, amount_max=15000)
        Notification.objects.create(user=self.user, trade=t, reason="OVERLAP", title="x", body="y")
        d = self.client.get("/api/trades/notifications/").data
        self.assertEqual(d["unread"], 1)
        self.assertEqual(d["items"][0]["trade"]["ticker"], "AAPL")
        self.assertEqual(self.client.post("/api/trades/notifications/read/").status_code, 204)
        self.assertEqual(self.client.get("/api/trades/notifications/").data["unread"], 0)

    def test_principles_endpoint(self):
        Watch.objects.create(user=self.user, security=self.ko)
        d = self.client.get("/api/trades/principles/").data
        self.assertEqual([s["ticker"] for s in d["securities"]], ["AAPL", "KO"])
        self.assertTrue(d["securities"][0]["held"])
        self.assertIn("checks", d["bogle"])

    def test_alert_settings_on_me(self):
        res = self.client.patch("/api/auth/me/", {"ntfy_topic": "my-secret-topic", "notify_insider": False}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["ntfy_topic"], "my-secret-topic")
        self.assertFalse(res.data["notify_insider"])


class AlertTests(APITestCase):
    def setUp(self):
        self.aapl = Security.objects.create(ticker="AAPL", name="Apple", exchange="Nasdaq")
        self.nvda = Security.objects.create(ticker="NVDA", name="NVIDIA", exchange="Nasdaq")
        self.pelosi = Person.objects.create(slug="pelosi", name="Pelosi", name_ko="펠로시", kind="HOUSE")
        self.holder = User.objects.create_user("holder@example.com", "s3cure-pass-123", ntfy_topic="topic-a")
        self.fan = User.objects.create_user("fan@example.com", "s3cure-pass-123")
        self.quiet = User.objects.create_user("quiet@example.com", "s3cure-pass-123", notify_overlap=False)
        for u in (self.holder, self.quiet):
            Transaction.objects.create(user=u, security=self.aapl, side="BUY", quantity=1, price=1, traded_at=TODAY)
        Follow.objects.create(user=self.fan, person=self.pelosi)
        self.pushed = []

        def handler(req):
            self.pushed.append(json.loads(req.content))
            return httpx.Response(200, json={})

        real = httpx.Client
        patcher = mock.patch("apps.trades.alerts.httpx.Client", lambda **kw: real(transport=httpx.MockTransport(handler)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_follow_and_overlap(self):
        t = make_trade(self.pelosi, self.aapl, amount_min=Decimal(1001), amount_max=Decimal(15000), traded_at=TODAY - timedelta(days=10))
        self.assertEqual(alerts.dispatch([t]), 2)
        n = {x.user: x for x in Notification.objects.all()}
        self.assertEqual((n[self.holder].reason, n[self.fan].reason), ("OVERLAP", "FOLLOW"))
        self.assertNotIn(self.quiet, n)
        self.assertEqual(n[self.holder].title, "펠로시 · AAPL 매수")
        self.assertIn("$1,001 ~ $15,000", n[self.holder].body)
        # ntfy 주제를 정한 사용자에게만 푸시한다
        self.assertEqual([p["topic"] for p in self.pushed], ["topic-a"])
        self.assertEqual(self.pushed[0]["click"], "https://example.gov/doc.pdf")
        self.assertIsNotNone(Notification.objects.get(user=self.holder).pushed_at)
        # 같은 거래로 다시 알리지 않는다
        self.assertEqual(alerts.dispatch([t]), 0)

    def test_old_filings_are_not_alerted(self):
        t = make_trade(self.pelosi, self.aapl, filed=TODAY - timedelta(days=30))
        self.assertEqual(alerts.dispatch([t]), 0)

    def test_insider_only_when_large(self):
        f = Filing.objects.create(source="FORM4", key="f4", security=self.aapl, filed_at=TODAY)
        small = DisclosedTrade.objects.create(filing=f, row=0, security=self.aapl, ticker="AAPL", action="SELL", filed_at=TODAY, shares=10, price=200, actor_name="A")
        big = DisclosedTrade.objects.create(filing=f, row=1, security=self.aapl, ticker="AAPL", action="SELL", filed_at=TODAY, shares=10000, price=200, actor_name="Cook", actor_title="CEO")
        # 내부자 알림은 '내 종목 거래' 설정과 따로 켜고 끈다 (quiet 사용자도 받는다)
        self.assertEqual(alerts.dispatch([small, big]), 2)
        self.assertEqual({n.user for n in Notification.objects.all()}, {self.holder, self.quiet})
        n = Notification.objects.get(user=self.holder)
        self.assertEqual((n.reason, n.trade), ("INSIDER", big))
        self.assertEqual(n.title, "Cook (CEO) · AAPL 매도")


class PrincipleTests(APITestCase):
    def test_graham_and_lynch(self):
        sec = Security.objects.create(ticker="KO", name="Coca-Cola", exchange="NYSE")
        PriceDaily.objects.create(security=sec, date=TODAY, close=60)
        Fundamentals.objects.create(
            security=sec, shares_outstanding=100, eps_ttm=5, equity=3000,
            annual=[{"year": 2021, "eps": 2.0, "net_income": 1}, {"year": 2023, "eps": 2.5, "net_income": 2}, {"year": 2025, "eps": 4.0, "net_income": 3}],
        )
        r = principles.check_security(sec)
        g = {c["label"]: c for c in r["graham"]}
        self.assertEqual(g["PER 15배 이하"]["value"], "12.0배")
        self.assertTrue(g["PER 15배 이하"]["pass"])
        self.assertEqual(g["PBR 1.5배 이하"]["value"], "2.0배")
        self.assertFalse(g["PBR 1.5배 이하"]["pass"])
        # 그레이엄 넘버 = √(22.5 × 5 × 30) ≈ 58.09 < 60
        self.assertFalse(g["주가가 그레이엄 넘버 이하"]["pass"])
        self.assertIsNone(g["배당 지급"]["pass"])  # 배당 키가 없으면 판단하지 않는다
        lynch = {c["label"]: c for c in r["lynch"]}
        self.assertEqual(lynch["EPS 연평균 성장률"]["value"], "18.9%")
        self.assertEqual(lynch["PEG 1 이하 (PER ÷ 성장률)"]["value"], "0.63")
        self.assertEqual(r["graham_score"], {"passed": 2, "checked": 5})

    def test_bogle_mirrors_cash_flows(self):
        user = User.objects.create_user("b@example.com", "s3cure-pass-123")
        sec = Security.objects.create(ticker="AAPL", name="Apple", exchange="Nasdaq")
        d1, d2 = TODAY - timedelta(days=100), TODAY - timedelta(days=50)
        for d, v in ((d1, 100), (d2, 120), (TODAY, 150)):
            MacroPoint.objects.create(series="SP500", date=d, value=v)
        PriceDaily.objects.create(security=sec, date=TODAY, close=30)
        Transaction.objects.create(user=user, security=sec, side="BUY", quantity=100, price=10, traded_at=d1)  # $1000 → 지수 10단위
        Transaction.objects.create(user=user, security=sec, side="SELL", quantity=40, price=15, traded_at=d2)  # $600 → 지수 5단위 매도
        self.client.force_authenticate(user)
        b = self.client.get("/api/trades/principles/").data["bogle"]
        self.assertEqual(b["my_value_usd"], 1800.0)  # 60주 × $30
        self.assertEqual(b["index_value_usd"], 750.0)  # 5단위 × 150
        self.assertEqual(b["difference_usd"], 1050.0)
        self.assertTrue(b["checks"][2]["pass"])
