from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("이메일은 필수입니다.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """이메일로 로그인하는 사용자."""

    class Currency(models.TextChoices):
        KRW = "KRW", "원화"
        USD = "USD", "달러"

    username = None
    email = models.EmailField("이메일", unique=True)
    display_currency = models.CharField(
        "표시 통화", max_length=3, choices=Currency.choices, default=Currency.KRW
    )
    # 푸시는 ntfy(무료, 앱 설치 후 주제 구독)로 보낸다. 비워두면 앱 안 알림함에만 쌓인다
    ntfy_topic = models.CharField("ntfy 주제", max_length=64, blank=True)
    notify_follow = models.BooleanField("팔로우한 인물의 새 거래", default=True)
    notify_overlap = models.BooleanField("내 보유·관심 종목을 누가 거래", default=True)
    notify_insider = models.BooleanField("보유 종목 내부자 대량 매매", default=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
