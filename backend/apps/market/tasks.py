import logging
from datetime import date, timedelta

from celery import shared_task

from apps.securities.models import Security

from . import services
from .models import CalendarEvent

logger = logging.getLogger(__name__)


def _each_tracked(fn, label):
    """추적 종목마다 fn을 실행한다. 한 종목이 실패해도 나머지는 계속한다."""
    done, errors = {}, {}
    for security in services.tracked_securities():
        try:
            done[security.ticker] = fn(security)
        except Exception as exc:  # noqa: BLE001 - 출처 오류를 기록하고 다음 종목으로
            logger.warning("%s %s 실패: %s", security.ticker, label, exc)
            errors[security.ticker] = str(exc)[:200]
    return {"done": done, "errors": errors}


@shared_task
def update_market_data_task():
    """장 마감 후: 환율과 보유·관심 종목 종가를 갱신한다."""
    result = _each_tracked(services.update_prices, "종가")
    return {"fx": services.update_fx(), "prices": result["done"], "errors": result["errors"]}


@shared_task
def update_macro_task():
    return services.update_macro()


@shared_task
def update_news_task():
    return _each_tracked(services.update_news, "뉴스")


@shared_task
def update_fundamentals_task():
    result = _each_tracked(services.update_fundamentals, "재무")
    result["done"] = {k: bool(v) for k, v in result["done"].items()}
    return result


@shared_task
def update_calendar_task():
    """실적 발표일(Finnhub)과 배당(Alpha Vantage). 키가 없으면 그 항목은 건너뛴다."""
    from django.conf import settings

    result = {}
    if settings.FINNHUB_API_KEY:
        result["earnings"] = _each_tracked(services.update_earnings, "실적 일정")
    if settings.ALPHA_VANTAGE_API_KEY:
        result["dividends"] = _each_tracked(services.update_dividends, "배당")
    # 지난 일정은 1년 지나면 정리한다
    CalendarEvent.objects.filter(date__lt=date.today() - timedelta(days=365)).delete()
    return result


@shared_task
def backfill_security_task(security_id):
    """새로 보유하거나 관심 종목에 담은 종목의 데이터를 바로 채운다."""
    security = Security.objects.get(pk=security_id)
    result = {"fx": services.update_fx()}
    steps = [("prices", services.update_prices), ("fundamentals", services.update_fundamentals), ("news", services.update_news)]
    for name, fn in steps:
        try:
            result[name] = bool(fn(security))
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s %s 채우기 실패: %s", security.ticker, name, exc)
            result[name] = f"error: {exc}"[:200]
    return result
