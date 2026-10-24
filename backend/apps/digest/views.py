from datetime import date

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.market import calendar_us

from . import services
from .mailer import subject

LIST_LIMIT = 60


def _brief(s):
    p = s.data.get("portfolio")
    return {
        "date": s.date.isoformat(),
        "early_close": s.data.get("early_close", False),
        "change_pct": p["change_pct"] if p else None,
        "change_usd": p["change_usd"] if p else None,
        "trade_total": s.data.get("trade_total", 0),
        "news_count": len(s.data.get("news", [])),
        "emailed": s.emailed_at is not None,
    }


@api_view(["GET"])
def summaries(request):
    """지난 요약 목록. 가장 최근 거래일 요약이 없으면 지금 만든다."""
    latest = services.latest_day()
    if not request.user.summaries.filter(date=latest).exists():
        services.make_summary(request.user, latest)
    rows = request.user.summaries.all()[:LIST_LIMIT]
    return Response([_brief(s) for s in rows])


@api_view(["GET"])
def summary_detail(request, day):
    if day == "latest":
        d = services.latest_day()
    else:
        try:
            d = date.fromisoformat(day)
        except ValueError:
            return Response({"detail": "날짜 형식은 YYYY-MM-DD입니다."}, status=status.HTTP_400_BAD_REQUEST)
    s = request.user.summaries.filter(date=d).first()
    if s is None:
        if not calendar_us.is_trading_day(d) or d > services.latest_day():
            return Response({"detail": "그날은 요약이 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        s = services.make_summary(request.user, d)
    return Response({**s.data, "subject": subject(s.data), "emailed_at": s.emailed_at})
