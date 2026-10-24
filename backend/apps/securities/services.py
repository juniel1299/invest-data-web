"""SEC 공개 티커 목록으로 종목 마스터를 동기화한다."""

from dataclasses import dataclass

import httpx
from django.conf import settings
from django.db import transaction

from .models import Security

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
# 장외(OTC) 종목은 제외하고 주요 거래소만 담는다
SUPPORTED_EXCHANGES = {"NYSE", "Nasdaq", "CBOE"}


@dataclass
class SyncResult:
    created: int
    updated: int
    deactivated: int


def fetch_sec_tickers(client=None):
    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        res = client.get(SEC_TICKERS_URL, headers={"User-Agent": settings.SEC_USER_AGENT})
        res.raise_for_status()
        payload = res.json()
    finally:
        if owns_client:
            client.close()

    fields = payload["fields"]
    rows = [dict(zip(fields, row)) for row in payload["data"]]
    return [r for r in rows if r.get("exchange") in SUPPORTED_EXCHANGES and r.get("ticker")]


@transaction.atomic
def sync_securities(client=None):
    rows = fetch_sec_tickers(client)
    # 한 회사가 여러 티커를 가질 수 있어 티커 기준으로 맞춘다
    incoming = {r["ticker"].upper(): r for r in rows}
    existing = {s.ticker: s for s in Security.objects.all()}

    to_create, to_update = [], []
    for ticker, row in incoming.items():
        sec = existing.get(ticker)
        if sec is None:
            to_create.append(
                Security(ticker=ticker, name=row["name"], exchange=row["exchange"], cik=row["cik"])
            )
        elif (sec.name, sec.exchange, sec.cik, sec.is_active) != (
            row["name"],
            row["exchange"],
            row["cik"],
            True,
        ):
            sec.name, sec.exchange, sec.cik, sec.is_active = (
                row["name"],
                row["exchange"],
                row["cik"],
                True,
            )
            to_update.append(sec)

    Security.objects.bulk_create(to_create, batch_size=1000)
    Security.objects.bulk_update(to_update, ["name", "exchange", "cik", "is_active"], batch_size=1000)
    # 목록에서 사라진 종목은 지우지 않고 비활성화한다 (나중에 보유 내역이 참조할 수 있음)
    deactivated = (
        Security.objects.filter(is_active=True).exclude(ticker__in=incoming).update(is_active=False)
    )
    return SyncResult(created=len(to_create), updated=len(to_update), deactivated=deactivated)
