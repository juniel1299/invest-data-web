from django.core.management.base import BaseCommand

from apps.securities.services import sync_securities


class Command(BaseCommand):
    help = "SEC 티커 목록으로 종목 마스터를 동기화합니다."

    def handle(self, *args, **options):
        result = sync_securities()
        self.stdout.write(
            self.style.SUCCESS(
                f"추가 {result.created}, 갱신 {result.updated}, 비활성화 {result.deactivated}"
            )
        )
