from django.conf import settings
from django.db import models

from apps.securities.models import Security


class Account(models.Model):
    """증권 계좌. 여러 계좌를 나눠 보고 싶을 때만 쓴다."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField("이름", max_length=50)
    broker = models.CharField("증권사", max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.name


class Transaction(models.Model):
    """매수·매도 한 건. 보유 현황은 거래 내역에서 계산한다."""

    class Side(models.TextChoices):
        BUY = "BUY", "매수"
        SELL = "SELL", "매도"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions"
    )
    security = models.ForeignKey(Security, on_delete=models.PROTECT, related_name="transactions")
    side = models.CharField("구분", max_length=4, choices=Side.choices)
    quantity = models.DecimalField("수량", max_digits=20, decimal_places=6)
    price = models.DecimalField("단가(USD)", max_digits=18, decimal_places=6)
    # 비워두면 거래일의 ECB 환율로 계산한다
    fx_rate = models.DecimalField("환율(원/달러)", max_digits=12, decimal_places=4, null=True, blank=True)
    traded_at = models.DateField("거래일")
    memo = models.CharField("메모", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-traded_at", "-id"]

    def __str__(self):
        return f"{self.traded_at} {self.get_side_display()} {self.security.ticker} {self.quantity}"


class Watch(models.Model):
    """관심 종목. 보유하지 않아도 시세·뉴스·일정을 받아온다."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watches")
    security = models.ForeignKey(Security, on_delete=models.CASCADE, related_name="watchers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "security"], name="uniq_watch")]
        ordering = ["created_at"]
