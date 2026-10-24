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
