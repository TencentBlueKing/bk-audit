# -*- coding: utf-8 -*-
"""白名单异步建单、审批轮询和到期。"""

from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from celery.schedules import crontab
from django.conf import settings

from services.web.risk.whitelist.service import (
    create_itsm_ticket,
    expire_whitelists,
    sync_pending_whitelists,
)


@celery_app.task(ignore_result=True)
def create_risk_whitelist_ticket(rule_id: int) -> None:
    create_itsm_ticket(rule_id)


@periodic_task(
    run_every=crontab(minute=getattr(settings, "RISK_WHITELIST_SYNC_MINUTE", "*/5")),
    queue="risk",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
def sync_risk_whitelist_approval() -> None:
    sync_pending_whitelists()


@periodic_task(
    run_every=crontab(minute=getattr(settings, "RISK_WHITELIST_EXPIRE_MINUTE", "*/10")),
    queue="risk",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
def expire_risk_whitelists() -> None:
    expire_whitelists()
