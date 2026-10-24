import logging

from celery import shared_task

from apps.market.services import tracked_securities

from . import alerts, services
from .models import Person

logger = logging.getLogger(__name__)


def _run(label, jobs):
    """(이름, 함수) 목록을 실행한다. 하나가 실패해도 나머지는 계속하고, 새 거래는 알린다."""
    done, errors, trades = {}, {}, []
    with services.http_client() as client:
        for name, fn in jobs:
            try:
                new = fn(client)
                trades += new
                done[name] = len(new)
            except Exception as exc:  # noqa: BLE001 - 출처 하나의 오류가 전체를 멈추지 않게
                logger.warning("%s %s 실패: %s", label, name, exc)
                errors[name] = str(exc)[:200]
    return {"done": done, "errors": errors, "notified": alerts.dispatch(trades)}


def _people(**flags):
    return Person.objects.filter(active=True, cik__isnull=False, **flags)


@shared_task
def update_13f_task():
    jobs = [(p.slug, lambda c, p=p: services.update_13f(p, c)) for p in _people(track_13f=True)]
    jobs += [(f"{p.slug}-form4", lambda c, p=p: services.update_form4_person(p, c)) for p in _people(track_form4=True)]
    return _run("13F·Form 4", jobs)


@shared_task
def update_ark_task():
    people = Person.objects.filter(active=True, track_ark=True)
    return _run("ARK", [(p.slug, lambda c, p=p: services.update_ark(p, c)) for p in people])


@shared_task
def update_insiders_task():
    secs = tracked_securities().filter(cik__isnull=False)
    return _run("내부자", [(s.ticker, lambda c, s=s: services.update_insiders(s, c)) for s in secs])


@shared_task
def update_congress_task():
    return _run("의회", [("house", services.update_house), ("senate", services.update_senate)])
