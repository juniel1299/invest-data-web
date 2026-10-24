from django.core.management.base import BaseCommand

from apps.market import tasks


class Command(BaseCommand):
    help = "시세·환율·지표·재무·뉴스·일정을 지금 바로 갱신합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            choices=["prices", "macro", "fundamentals", "news", "calendar"],
            help="하나만 갱신",
        )

    def handle(self, *args, only=None, **options):
        jobs = {
            "prices": tasks.update_market_data_task,
            "macro": tasks.update_macro_task,
            "fundamentals": tasks.update_fundamentals_task,
            "news": tasks.update_news_task,
            "calendar": tasks.update_calendar_task,
        }
        for name, job in jobs.items():
            if only and name != only:
                continue
            self.stdout.write(f"{name}: {job()}")
