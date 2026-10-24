"""새 거래를 사용자에게 알린다: 앱 알림함 + ntfy 푸시(주제를 정한 사용자만)."""

import logging
from datetime import date, timedelta
from decimal import Decimal

import httpx
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .models import Follow, Notification

logger = logging.getLogger(__name__)

# 처음 수집할 때 쌓인 옛 공시로 알림이 쏟아지지 않게 최근 공시만 알린다
ALERT_MAX_AGE_DAYS = 3
INSIDER_ALERT_MIN_USD = Decimal("1000000")


def _who(t):
    return t.person.name_ko if t.person else f"{t.actor_name} ({t.actor_title})" if t.actor_title else t.actor_name


def _money(v):
    return f"${v:,.0f}"


def describe(t):
    what = t.ticker or t.asset_name
    title = f"{_who(t)} · {what} {t.get_action_display()}"
    parts = []
    if t.amount_min is not None:
        parts.append(f"{_money(t.amount_min)} ~ {_money(t.amount_max)}" if t.amount_max else f"{_money(t.amount_min)} 이상")
    elif t.value_usd:
        parts.append(f"약 {_money(t.value_usd)}")
    if t.shares and t.amount_min is None:
        parts.append(f"{t.shares:,.0f}주")
    if t.traded_at:
        parts.append(f"거래일 {t.traded_at:%m/%d}")
    parts.append(f"공시일 {t.filed_at:%m/%d}")
    return title, " · ".join(parts)


def _users_with(security):
    User = get_user_model()
    return set(
        User.objects.filter(Q(transactions__security=security) | Q(watches__security=security)).values_list("id", flat=True)
    )


def dispatch(trades, today=None):
    """거래 목록을 보고 알림을 만든다. 만든 알림 수를 돌려준다."""
    today = today or date.today()
    User = get_user_model()
    created = []
    for t in trades:
        if t.filed_at < today - timedelta(days=ALERT_MAX_AGE_DAYS):
            continue
        owners = _users_with(t.security) if t.security else set()
        targets = {}
        if t.person:
            for uid in Follow.objects.filter(person=t.person, user__notify_follow=True).values_list("user_id", flat=True):
                targets[uid] = Notification.Reason.FOLLOW
            for uid in User.objects.filter(id__in=owners, notify_overlap=True).values_list("id", flat=True):
                targets[uid] = Notification.Reason.OVERLAP  # 내 종목과 겹치면 그쪽을 우선 표시
        elif t.value_usd and t.value_usd >= INSIDER_ALERT_MIN_USD:
            for uid in User.objects.filter(id__in=owners, notify_insider=True).values_list("id", flat=True):
                targets[uid] = Notification.Reason.INSIDER
        if not targets:
            continue
        title, body = describe(t)
        for uid, reason in targets.items():
            n, new = Notification.objects.get_or_create(
                user_id=uid, trade=t, defaults={"reason": reason, "title": title, "body": body}
            )
            if new:
                created.append(n)
    push(created)
    return len(created)


def push(notifications):
    sent = [n for n in notifications if n.user.ntfy_topic]
    if not sent:
        return
    with httpx.Client(timeout=10) as client:
        for n in sent:
            try:
                res = client.post(
                    settings.NTFY_SERVER.rstrip("/"),
                    json={
                        "topic": n.user.ntfy_topic,
                        "title": n.title,
                        "message": n.body,
                        "tags": ["chart_with_upwards_trend" if n.trade.is_buy else "chart_with_downwards_trend"],
                        **({"click": n.trade.filing.url} if n.trade.filing.url else {}),
                    },
                )
                res.raise_for_status()
                n.pushed_at = timezone.now()
                n.save(update_fields=["pushed_at"])
            except httpx.HTTPError as exc:
                logger.warning("ntfy 전송 실패 (%s): %s", n.user_id, exc)

