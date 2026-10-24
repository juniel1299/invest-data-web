from datetime import date

from django.core.management.base import BaseCommand

from apps.market.models import CalendarEvent

# 연준 공식 일정(federalreserve.gov/monetarypolicy/fomccalendars.htm)의 회의 둘째 날 = 금리 결정 발표일.
# 새 해 일정이 나오면 여기에 추가하거나 관리자 화면에서 직접 넣는다.
FOMC_DECISION_DAYS = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
]


class Command(BaseCommand):
    help = "FOMC 금리 결정일을 일정에 넣습니다."

    def handle(self, *args, **options):
        created = 0
        for day in FOMC_DECISION_DAYS:
            _, new = CalendarEvent.objects.get_or_create(
                kind=CalendarEvent.Kind.FOMC, security=None, date=day, defaults={"title": "FOMC 금리 결정"}
            )
            created += new
        self.stdout.write(self.style.SUCCESS(f"FOMC 일정 {created}건 추가"))
