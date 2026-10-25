from datetime import date, datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.digest import builder, mailer, services, tasks
from apps.digest.models import DailySummary
from apps.market import calendar_us
from apps.market.models import CalendarEvent, FxRate, MacroPoint, NewsItem, PriceDaily
from apps.portfolio.models import Transaction, Watch
from apps.securities.models import Security
from apps.trades.models import DisclosedTrade, Filing, Person

User = get_user_model()
FRI = date(2026, 10, 23)
THU = date(2026, 10, 22)
MON = date(2026, 10, 26)


class CalendarTests(TestCase):
    def test_holidays(self):
        h = calendar_us.holidays(2026)
        self.assertIn(date(2026, 1, 1), h)
        self.assertIn(date(2026, 4, 3), h)  # 성금요일
        self.assertIn(date(2026, 6, 19), h)
        self.assertIn(date(2026, 7, 3), h)  # 독립기념일이 토요일이라 금요일 휴장
        self.assertIn(date(2026, 11, 26), h)
        self.assertIn(date(2027, 12, 24), calendar_us.holidays(2027))  # 성탄절 토요일 → 금요일
        self.assertNotIn(date(2021, 12, 31), calendar_us.holidays(2021))  # 신정 토요일은 전날 쉬지 않는다
        self.assertFalse(calendar_us.is_trading_day(date(2026, 10, 24)))

    def test_early_close_and_neighbors(self):
        self.assertTrue(calendar_us.is_early_close(date(2026, 11, 27)))
        self.assertTrue(calendar_us.is_early_close(date(2026, 12, 24)))
        self.assertFalse(calendar_us.is_early_close(date(2026, 7, 3)))  # 그날은 휴장
        self.assertTrue(calendar_us.is_early_close(date(2025, 7, 3)))
        self.assertEqual(calendar_us.next_trading_day(FRI), MON)
        self.assertEqual(calendar_us.previous_trading_day(MON), FRI)
        self.assertEqual(calendar_us.next_trading_day(date(2026, 11, 25)), date(2026, 11, 27))

    def test_should_run(self):
        self.assertTrue(services.should_run(FRI, "regular"))
        self.assertFalse(services.should_run(FRI, "early"))
        self.assertFalse(services.should_run(date(2026, 11, 26), "regular"))
        self.assertTrue(services.should_run(date(2026, 11, 27), "early"))
        self.assertFalse(services.should_run(date(2026, 11, 27), "regular"))

    def test_latest_day(self):
        et = builder.ET
        self.assertEqual(services.latest_day(datetime(2026, 10, 23, 15, 0, tzinfo=et)), THU)
        self.assertEqual(services.latest_day(datetime(2026, 10, 23, 16, 5, tzinfo=et)), FRI)
        self.assertEqual(services.latest_day(datetime(2026, 10, 25, 9, 0, tzinfo=et)), FRI)
        self.assertEqual(services.latest_day(datetime(2026, 11, 27, 13, 30, tzinfo=et)), date(2026, 11, 27))


class DigestFixture:
    def make_data(self):
        self.user = User.objects.create_user("me@example.com", "s3cure-pass-123")
        self.aapl = Security.objects.create(ticker="AAPL", name="Apple Inc.", name_ko="애플", exchange="Nasdaq")
        self.ko = Security.objects.create(ticker="KO", name="Coca-Cola", exchange="NYSE")
        self.nvda = Security.objects.create(ticker="NVDA", name="NVIDIA", exchange="Nasdaq")
        Transaction.objects.create(user=self.user, security=self.aapl, side="BUY", quantity=10, price=100, traded_at=FRI - timedelta(days=60))
        Transaction.objects.create(user=self.user, security=self.ko, side="BUY", quantity=20, price=50, traded_at=FRI - timedelta(days=60))
        Watch.objects.create(user=self.user, security=self.nvda)
        for sec, before, now in [(self.aapl, 200, 210), (self.ko, 60, 57)]:
            PriceDaily.objects.create(security=sec, date=THU, close=before)
            PriceDaily.objects.create(security=sec, date=FRI, close=now)
        FxRate.objects.create(date=THU, usd_krw=1380)
        FxRate.objects.create(date=FRI, usd_krw=1400)
        MacroPoint.objects.create(series="SP500", date=THU, value=6000)
        MacroPoint.objects.create(series="SP500", date=FRI, value=6060)
        pelosi = Person.objects.create(slug="pelosi", name="Nancy Pelosi", name_ko="낸시 펠로시", kind="HOUSE")
        buffett = Person.objects.create(slug="buffett", name="Warren Buffett", name_ko="워런 버핏", kind="INVESTOR")
        for i, (person, sec, filed) in enumerate([
            (buffett, self.ko, FRI), (pelosi, self.nvda, FRI), (pelosi, self.ko, THU),
        ]):
            f = Filing.objects.create(source="HOUSE", key=f"k{i}", person=person, filed_at=filed, url="https://example.gov/x.pdf")
            DisclosedTrade.objects.create(filing=f, person=person, security=sec, ticker=sec.ticker, action="BUY", filed_at=filed)
        # 내 종목과 겹치지 않는 거래
        other = Security.objects.create(ticker="XOM", name="Exxon", exchange="NYSE")
        f = Filing.objects.create(source="HOUSE", key="k9", person=pelosi, filed_at=FRI, url="https://example.gov/y.pdf")
        DisclosedTrade.objects.create(filing=f, person=pelosi, security=other, ticker="XOM", action="SELL", filed_at=FRI)
        NewsItem.objects.create(security=self.aapl, title="애플 신제품", url="https://news.example/a", source="Example",
                                published_at=datetime(2026, 10, 23, 10, 0, tzinfo=builder.ET))
        NewsItem.objects.create(security=self.aapl, title="오래된 기사", url="https://news.example/b",
                                published_at=datetime(2026, 10, 20, 10, 0, tzinfo=builder.ET))
        CalendarEvent.objects.create(kind="EARNINGS", security=self.nvda, date=MON, title="")
        CalendarEvent.objects.create(kind="FOMC", date=MON + timedelta(days=2), title="FOMC")


class BuilderTests(DigestFixture, TestCase):
    def setUp(self):
        self.make_data()

    def test_build(self):
        d = builder.build(self.user, FRI)
        p = d["portfolio"]
        self.assertEqual(p["change_usd"], 40.0)  # 10×(+10) + 20×(−3)
        self.assertEqual(p["change_krw"], 56000)
        self.assertAlmostEqual(p["change_pct"], round(40 / (3240 - 40) * 100, 2))
        self.assertEqual([m["ticker"] for m in d["movers"]["up"]], ["AAPL"])
        self.assertEqual([m["ticker"] for m in d["movers"]["down"]], ["KO"])
        sp = next(m for m in d["market"] if m["series"] == "SP500")
        self.assertEqual(sp["change_pct"], 1.0)
        # 목요일 공시는 빠지고, 내 종목과 겹치는 거래가 먼저
        tickers = [t["ticker"] for t in d["trades"]]
        self.assertEqual(set(tickers[:2]), {"KO", "NVDA"})
        self.assertEqual(tickers[2], "XOM")
        self.assertEqual(d["trade_total"], 3)
        self.assertEqual([n["title"] for n in d["news"]], ["애플 신제품"])
        self.assertEqual(d["next_trading_day"], MON.isoformat())
        self.assertEqual([e["ticker"] for e in d["tomorrow"]], ["NVDA"])
        self.assertTrue(builder.has_content(d))

    def test_monday_includes_weekend_filings(self):
        sat = FRI + timedelta(days=1)
        p = Person.objects.get(slug="pelosi")
        f = Filing.objects.create(source="HOUSE", key="sat", person=p, filed_at=sat, url="https://example.gov/z.pdf")
        DisclosedTrade.objects.create(filing=f, person=p, security=self.nvda, ticker="NVDA", action="BUY", filed_at=sat)
        d = builder.build(self.user, MON)
        self.assertEqual(d["trade_total"], 1)

    def test_empty_user(self):
        u = User.objects.create_user("new@example.com", "s3cure-pass-123")
        d = builder.build(u, FRI)
        self.assertIsNone(d["portfolio"])
        self.assertEqual(d["movers"], {"up": [], "down": []})


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", APP_URL="https://app.example")
class MailTests(DigestFixture, TestCase):
    def setUp(self):
        self.make_data()

    def test_subject_and_render(self):
        d = builder.build(self.user, FRI)
        self.assertEqual(mailer.subject(d), f"[미국 주식 모음] 10/23(금) 마감 요약 · 내 포트폴리오 {d['portfolio']['change_pct']:+.2f}%")
        text, html = mailer.render(d)
        self.assertIn("+$40.00", text)
        self.assertIn("₩56,000", text)
        self.assertIn("★ 워런 버핏 · KO", text)
        self.assertIn("10/26(월) 일정", text)
        self.assertIn("https://app.example", html)
        self.assertIn("애플 신제품", html)

    def test_run_day_sends_once(self):
        r = services.run_day(FRI)
        self.assertEqual((r["made"], r["sent"]), (1, 1))
        self.assertEqual(mail.outbox[0].to, ["me@example.com"])
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")
        services.run_day(FRI)
        self.assertEqual(len(mail.outbox), 1)  # 이미 보낸 날은 다시 안 보낸다
        services.run_day(FRI, force=True)
        self.assertEqual(len(mail.outbox), 2)

    def test_opt_out(self):
        self.user.daily_email = False
        self.user.save()
        r = services.run_day(FRI)
        self.assertEqual((r["made"], r["sent"]), (1, 0))
        self.assertTrue(DailySummary.objects.filter(user=self.user, date=FRI).exists())

    def test_task_skips_holiday_and_wrong_kind(self):
        with mock.patch.object(services, "today_et", return_value=date(2026, 11, 26)):
            self.assertTrue(tasks.send_daily_summaries_task()["skipped"])
        with mock.patch.object(services, "today_et", return_value=FRI):
            self.assertTrue(tasks.send_daily_summaries_task(kind="early")["skipped"])
            self.assertEqual(tasks.send_daily_summaries_task()["sent"], 1)


class DigestApiTests(DigestFixture, APITestCase):
    def setUp(self):
        self.make_data()
        self.client.force_authenticate(self.user)

    def test_detail_and_list(self):
        res = self.client.get(f"/api/digest/{FRI.isoformat()}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["portfolio"]["change_usd"], 40.0)
        self.assertIn("마감 요약", res.data["subject"])
        self.assertEqual(self.client.get("/api/digest/2026-10-24/").status_code, 404)
        self.assertEqual(self.client.get("/api/digest/abc/").status_code, 400)
        with mock.patch.object(services, "latest_day", return_value=FRI):
            rows = self.client.get("/api/digest/").data
            self.assertEqual(rows[0]["date"], FRI.isoformat())
            self.assertEqual(rows[0]["trade_total"], 3)
            self.assertEqual(self.client.get("/api/digest/latest/").data["date"], FRI.isoformat())

    def test_daily_email_setting(self):
        res = self.client.patch("/api/auth/me/", {"daily_email": False}, format="json")
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.daily_email)
