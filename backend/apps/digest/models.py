from django.conf import settings
from django.db import models


class DailySummary(models.Model):
    """거래일 하루 요약. 이메일로 보내고, 앱 '오늘의 정리'에서 다시 본다."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="summaries")
    date = models.DateField("거래일")
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="uniq_summary_day")]
        ordering = ["-date"]
        verbose_name = verbose_name_plural = "장 마감 요약"
