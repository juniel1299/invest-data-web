"""뉴욕증권거래소 휴장일·조기 마감일 (정규 규칙만).

라이브러리(exchange_calendars)는 pandas까지 끌어와 무거워서 규칙을 직접 계산한다.
대통령 장례 같은 임시 휴장은 EXTRA_CLOSED에 더한다.
"""

from datetime import date, timedelta
from functools import lru_cache

# 지미 카터 전 대통령 국장일
EXTRA_CLOSED = {date(2025, 1, 9)}


def _easter(year):
    # 그레고리력 부활절 (익명 알고리즘)
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year, month, weekday):
    d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d):
    """토요일이면 금요일, 일요일이면 월요일에 쉰다."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=32)
def holidays(year):
    days = {
        _nth_weekday(year, 1, 0, 3),  # 마틴 루서 킹 데이
        _nth_weekday(year, 2, 0, 3),  # 대통령의 날
        _easter(year) - timedelta(days=2),  # 성금요일
        _last_weekday(year, 5, 0),  # 메모리얼 데이
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # 노동절
        _nth_weekday(year, 11, 3, 4),  # 추수감사절
        _observed(date(year, 12, 25)),
    }
    # 새해 첫날이 토요일이면 전년 12월 31일에 쉬지 않는다 (NYSE 규칙)
    new_year = date(year, 1, 1)
    if new_year.weekday() != 5:
        days.add(_observed(new_year))
    if year >= 2022:
        days.add(_observed(date(year, 6, 19)))  # 준틴스
    return frozenset(days)


def is_trading_day(d):
    return d.weekday() < 5 and d not in holidays(d.year) and d not in EXTRA_CLOSED


def is_early_close(d):
    """13:00 조기 마감: 독립기념일 전날, 추수감사절 다음 날, 크리스마스 이브."""
    if not is_trading_day(d):
        return False
    thanksgiving = _nth_weekday(d.year, 11, 3, 4)
    return d in {date(d.year, 7, 3), thanksgiving + timedelta(days=1), date(d.year, 12, 24)}


def next_trading_day(d):
    d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def previous_trading_day(d):
    d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d
