from datetime import date

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

WEEKDAYS = "월화수목금토일"


def day_label(iso):
    d = date.fromisoformat(iso)
    return f"{d.month}/{d.day}({WEEKDAYS[d.weekday()]})"


def subject(data):
    p = data["portfolio"]
    tail = ""
    if p and p["change_pct"] is not None:
        tail = f" · 내 포트폴리오 {p['change_pct']:+.2f}%"
    return f"[미국 주식 모음] {day_label(data['date'])} 마감 요약{tail}"


def _context(data):
    def signed(v, fmt="{:,.2f}"):
        return "-" if v is None else ("+" if v > 0 else "") + fmt.format(v)

    p = data["portfolio"]
    return {
        "d": data,
        "day": day_label(data["date"]),
        "next_day": day_label(data["next_trading_day"]),
        "p": p,
        "p_change": None if not p else f"{signed(p['change_usd'], '${:,.2f}')} ({signed(p['change_pct'])}%)",
        "pnl_text": None if not p else signed(p["pnl_pct"]) + "%",
        "pnl_krw_text": None if not p or p["pnl_krw_pct"] is None else signed(p["pnl_krw_pct"]) + "%",
        "p_change_krw": None if not p or p["change_krw"] is None else signed(p["change_krw"], "₩{:,.0f}"),
        "market": [
            {**m, "change_text": "-" if m["change_pct"] is None else f"{signed(m['change'])} ({signed(m['change_pct'])}%)"}
            for m in data["market"]
        ],
        "app_url": settings.APP_URL,
    }


def render(data):
    ctx = _context(data)
    return render_to_string("digest/email.txt", ctx), render_to_string("digest/email.html", ctx)


def send(summary):
    text, html = render(summary.data)
    msg = EmailMultiAlternatives(subject(summary.data), text, settings.DEFAULT_FROM_EMAIL, [summary.user.email])
    msg.attach_alternative(html, "text/html")
    msg.send()
    summary.emailed_at = timezone.now()
    summary.save(update_fields=["emailed_at"])
