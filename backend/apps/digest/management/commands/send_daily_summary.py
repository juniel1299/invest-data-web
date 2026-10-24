from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.digest import services
from apps.market import calendar_us


class Command(BaseCommand):
    help = "장 마감 요약을 만들고 이메일로 보낸다. 날짜를 안 주면 가장 최근 거래일."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="YYYY-MM-DD (미국 동부 기준 거래일)")
        parser.add_argument("--user", help="이 이메일의 사용자만")
        parser.add_argument("--no-email", action="store_true", help="요약만 만들고 보내지 않는다")
        parser.add_argument("--force", action="store_true", help="이미 보냈거나 수신을 끈 사용자에게도 보낸다")

    def handle(self, *args, **opts):
        day = date.fromisoformat(opts["date"]) if opts["date"] else services.latest_day()
        if not calendar_us.is_trading_day(day):
            raise CommandError(f"{day}는 미국 증시 휴장일입니다.")
        users = None
        if opts["user"]:
            users = list(get_user_model().objects.filter(email=opts["user"]))
            if not users:
                raise CommandError(f"{opts['user']} 사용자가 없습니다.")
        result = services.run_day(day, email=not opts["no_email"], force=opts["force"], users=users)
        self.stdout.write(self.style.SUCCESS(f"{result['date']}: 요약 {result['made']}건, 메일 {result['sent']}건"))
        for email, err in result["errors"].items():
            self.stderr.write(f"{email}: {err}")
