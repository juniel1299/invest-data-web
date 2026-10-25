import logging
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.market import calendar_us

from . import builder, mailer
from .builder import ET
from .models import DailySummary

logger = logging.getLogger(__name__)


def today_et():
    return datetime.now(ET).date()


def recipients():
    """보유 종목이나 관심 종목이 있는 사용자."""
    User = get_user_model()
    return User.objects.filter(is_active=True).filter(
        Q(transactions__isnull=False) | Q(watches__isnull=False)
    ).distinct()


def make_summary(user, day):
    summary, _ = DailySummary.objects.update_or_create(user=user, date=day, defaults={"data": builder.build(user, day)})
    return summary


def run_day(day, email=True, force=False, users=None):
    """그날 요약을 만들고, 원하는 사용자에게 아직 안 보낸 이메일을 보낸다."""
    made = sent = 0
    errors = {}
    for user in users if users is not None else recipients():
        summary = make_summary(user, day)
        made += 1
        if not (email and user.email and (force or (user.daily_email and summary.emailed_at is None))):
            continue
        if not builder.has_content(summary.data):
            continue
        try:
            mailer.send(summary)
            sent += 1
        except Exception as exc:  # noqa: BLE001 - 한 명 실패가 다른 사람 발송을 막지 않게
            logger.warning("요약 메일 %s 실패: %s", user.email, exc)
            errors[user.email] = str(exc)[:200]
    return {"date": day.isoformat(), "made": made, "sent": sent, "errors": errors}


def should_run(day, kind):
    if not calendar_us.is_trading_day(day):
        return False
    return calendar_us.is_early_close(day) == (kind == "early")


def latest_day(now=None):
    """요약을 볼 수 있는 가장 최근 거래일. 오늘 장이 끝나기 전이면 직전 거래일."""
    now = now or datetime.now(ET)
    day = now.date()
    close_hour = 13 if calendar_us.is_early_close(day) else 16
    if calendar_us.is_trading_day(day) and now.hour >= close_hour:
        return day
    return calendar_us.previous_trading_day(day)
