from celery import shared_task

from . import services


@shared_task
def send_daily_summaries_task(kind="regular"):
    """평소엔 17:00, 조기 마감일엔 14:00(미국 동부)에 실행된다. 휴장일과 맞지 않는 쪽은 건너뛴다."""
    day = services.today_et()
    if not services.should_run(day, kind):
        return {"date": day.isoformat(), "skipped": True}
    return services.run_day(day)
