from django.db import models


class Security(models.Model):
    """종목 마스터. SEC 티커 목록에서 매일 갱신한다."""

    ticker = models.CharField("티커", max_length=16, unique=True)
    name = models.CharField("영문명", max_length=255)
    name_ko = models.CharField("한글명", max_length=255, blank=True)
    exchange = models.CharField("거래소", max_length=32, blank=True)
    cik = models.PositiveIntegerField("SEC CIK", null=True, blank=True, db_index=True)
    is_active = models.BooleanField("상장 중", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ticker"]

    def __str__(self):
        return f"{self.ticker} ({self.name})"
