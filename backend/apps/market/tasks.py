import logging

from celery import shared_task

from apps.securities.models import Security

from . import services

logger = logging.getLogger(__name__)


@shared_task
def update_market_data_task():
    """장 마감 후: 환율과 보유 종목 종가를 갱신한다. 한 종목이 실패해도 나머지는 계속한다."""
    result = {"fx": services.update_fx(), "prices": {}, "errors": {}}
    for security in services.held_securities():
        try:
            result["prices"][security.ticker] = services.update_prices(security)
        except Exception as exc:  # noqa: BLE001 - 출처 오류를 기록하고 다음 종목으로
            logger.warning("%s 종가 수집 실패: %s", security.ticker, exc)
            result["errors"][security.ticker] = str(exc)
    return result


@shared_task
def backfill_security_task(security_id):
    """포트폴리오에 새 종목이 들어오면 바로 종가와 환율을 채운다."""
    security = Security.objects.get(pk=security_id)
    return {"fx": services.update_fx(), "prices": services.update_prices(security)}
