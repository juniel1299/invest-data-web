"""거래 내역으로 보유 현황을 계산한다 (이동평균법)."""

from dataclasses import dataclass, field
from decimal import Decimal

from apps.market.services import fx_on

ZERO = Decimal("0")


class OversellError(ValueError):
    def __init__(self, ticker, traded_at):
        self.ticker, self.traded_at = ticker, traded_at
        super().__init__(f"{traded_at}에 보유 수량보다 많은 {ticker}를 매도합니다.")


@dataclass
class Position:
    security: object
    quantity: Decimal = ZERO
    cost_usd: Decimal = ZERO
    cost_krw: Decimal = ZERO
    realized_usd: Decimal = ZERO
    # 환율을 모르는 매수가 하나라도 있으면 원화 원가를 믿을 수 없다
    krw_known: bool = True
    transactions: list = field(default_factory=list)

    @property
    def avg_price(self):
        return self.cost_usd / self.quantity if self.quantity else ZERO

    @property
    def avg_fx(self):
        return self.cost_krw / self.cost_usd if self.cost_usd and self.krw_known else None


def build_positions(transactions, fx_lookup=fx_on):
    """transactions: 한 사용자의 거래 목록. 종목별 Position을 돌려준다."""
    positions = {}
    ordered = sorted(transactions, key=lambda t: (t.traded_at, t.side != "BUY", t.id or 0))
    for t in ordered:
        pos = positions.setdefault(t.security_id, Position(security=t.security))
        pos.transactions.append(t)
        if t.side == "BUY":
            fx = t.fx_rate or fx_lookup(t.traded_at)
            amount = t.quantity * t.price
            pos.quantity += t.quantity
            pos.cost_usd += amount
            if fx:
                pos.cost_krw += amount * fx
            else:
                pos.krw_known = False
        else:
            if t.quantity > pos.quantity:
                raise OversellError(t.security.ticker, t.traded_at)
            ratio = t.quantity / pos.quantity
            avg = pos.avg_price
            pos.realized_usd += t.quantity * (t.price - avg)
            pos.cost_usd -= pos.cost_usd * ratio
            pos.cost_krw -= pos.cost_krw * ratio
            pos.quantity -= t.quantity
    return positions
