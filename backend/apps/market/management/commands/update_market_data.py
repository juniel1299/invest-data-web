from django.core.management.base import BaseCommand

from apps.market.tasks import update_market_data_task


class Command(BaseCommand):
    help = "환율과 보유 종목 종가를 지금 바로 갱신합니다."

    def handle(self, *args, **options):
        result = update_market_data_task()
        self.stdout.write(self.style.SUCCESS(f"환율 {result['fx']}건, 종가 {result['prices']}"))
        if result["errors"]:
            self.stdout.write(self.style.WARNING(f"실패: {result['errors']}"))
