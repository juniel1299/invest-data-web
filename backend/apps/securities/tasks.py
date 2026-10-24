from dataclasses import asdict

from celery import shared_task

from .services import sync_securities


@shared_task
def sync_securities_task():
    return asdict(sync_securities())
