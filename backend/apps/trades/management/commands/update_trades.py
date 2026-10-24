from django.core.management.base import BaseCommand

from apps.trades import tasks


class Command(BaseCommand):
    help = "유명인·의원·내부자 매매 공시를 지금 바로 수집합니다."

    def add_arguments(self, parser):
        parser.add_argument("--only", choices=["13f", "ark", "insiders", "congress"], help="하나만 수집")

    def handle(self, *args, only=None, **options):
        jobs = {
            "13f": tasks.update_13f_task,
            "ark": tasks.update_ark_task,
            "insiders": tasks.update_insiders_task,
            "congress": tasks.update_congress_task,
        }
        for name, job in jobs.items():
            if not only or name == only:
                self.stdout.write(f"{name}: {job()}")
