from django.db import models

from apps.securities.models import Security


class PriceDaily(models.Model):
    """종목별 일간 종가 (USD)."""

    security = models.ForeignKey(Security, on_delete=models.CASCADE, related_name="prices")
    date = models.DateField()
    close = models.DecimalField(max_digits=18, decimal_places=6)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["security", "date"], name="uniq_price_day")]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.security.ticker} {self.date} {self.close}"


class FxRate(models.Model):
    """일간 원/달러 환율 (1 USD = usd_krw 원). 출처: ECB 기준환율."""

    date = models.DateField(unique=True)
    usd_krw = models.DecimalField(max_digits=12, decimal_places=4)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} {self.usd_krw}"


class MacroPoint(models.Model):
    """지수·금리 같은 시장 지표의 일간 값 (FRED)."""

    series = models.CharField(max_length=32)
    date = models.DateField()
    value = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["series", "date"], name="uniq_macro_day")]
        ordering = ["-date"]


class Fundamentals(models.Model):
    """SEC 재무 데이터 요약. 최근 12개월(TTM)과 최근 5개 회계연도."""

    security = models.OneToOneField(Security, on_delete=models.CASCADE, related_name="fundamentals")
    shares_outstanding = models.BigIntegerField(null=True)
    revenue_ttm = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    net_income_ttm = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    eps_ttm = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    # [{"year": 2025, "end": "2025-09-27", "revenue": ..., "net_income": ..., "eps": ...}, ...]
    annual = models.JSONField(default=list)
    as_of = models.DateField(null=True, help_text="TTM 기준일 (가장 최근 보고 기간 끝)")
    updated_at = models.DateTimeField(auto_now=True)


class NewsItem(models.Model):
    security = models.ForeignKey(Security, on_delete=models.CASCADE, related_name="news")
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    source = models.CharField(max_length=200, blank=True)
    published_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["security", "url"], name="uniq_news_url")]
        ordering = ["-published_at"]


class CalendarEvent(models.Model):
    class Kind(models.TextChoices):
        EARNINGS = "EARNINGS", "실적 발표"
        EX_DIVIDEND = "EX_DIVIDEND", "배당락일"
        DIVIDEND_PAY = "DIVIDEND_PAY", "배당 지급일"
        FOMC = "FOMC", "FOMC 금리 결정"
        ECONOMIC = "ECONOMIC", "경제 지표"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    security = models.ForeignKey(
        Security, on_delete=models.CASCADE, null=True, blank=True, related_name="events"
    )
    date = models.DateField()
    title = models.CharField(max_length=200, blank=True)
    # 실적: {"hour": "amc", "eps_estimate": 1.6, "eps_actual": null}, 배당: {"amount": 0.26}
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "security", "date"], name="uniq_event"),
        ]
        ordering = ["date"]

    def __str__(self):
        who = self.security.ticker if self.security else ""
        return f"{self.date} {self.get_kind_display()} {who}"
