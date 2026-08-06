# -*- coding: utf-8 -*-
from datetime import timedelta

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.utils.logger import logger_celery
from blueapps.utils.logger import logger_celery as logger
from celery.schedules import crontab
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.lock import lock
from services.web.scene.constants import (
    SCENE_PERMISSION_GRANT_MAX_RETRY,
    SYNC_SCENE_PERMISSION_PERIODIC_TASK_MINUTE,
    ApplicationStatus,
    GrantStatus,
    ITSMV4TicketStatus,
)
from services.web.scene.models import Scene, ScenePermissionApplication
from services.web.scene.permission import (
    _extract_reject_reason_from_logs,
    apply_ticket_result,
    do_grant,
    parse_itsm_ticket_from_logs,
)
from services.web.scene.resources import SceneResource


@periodic_task(run_every=crontab(minute="*/10"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(load_lock_name=lambda **kwargs: "celery:sync_scene_members_from_iam")
def sync_scene_members_from_iam():
    """定时同步场景成员"""

    success_count = 0
    fail_count = 0

    for scene in Scene.objects.all().only(
        "scene_id",
        "name",
        "managers",
        "users",
        "iam_manager_group_id",
        "iam_viewer_group_id",
    ):
        try:
            SceneResource._refresh_scene_members_from_iam(scene)
            success_count += 1
        except Exception as err:  # NOCC:broad-except
            fail_count += 1
            logger.exception(
                "[sync_scene_members_from_iam] 同步场景成员失败, scene_id=%s, error=%s",
                scene.scene_id,
                err,
            )

    logger.info(
        "[sync_scene_members_from_iam] finished, success_count=%s, fail_count=%s",
        success_count,
        fail_count,
    )


@periodic_task(
    run_every=crontab(minute=SYNC_SCENE_PERMISSION_PERIODIC_TASK_MINUTE),
    queue="default",
    time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT,
)
@lock(lock_name="celery:sync_scene_permission_status")
def sync_scene_permission_status():
    """轮询 ITSM V4 审批状态 + 重试 GRANT_FAILED 授权。
    阶段一：同步 PENDING 单的 ITSM 状态（审批通过则触发授权）
    阶段二：重试 GRANT_FAILED（审批已通过、仅授权失败），retry_count < MAX 才重试
    """
    operator = bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
    one_year_ago = timezone.now() - timedelta(days=365)

    # 阶段一：同步 PENDING
    pending_qs = ScenePermissionApplication.objects.select_related("scene").filter(
        status=ApplicationStatus.PENDING,
        created_at__gte=one_year_ago,
    )
    for application in pending_qs:
        try:
            # 1. 先在锁外调用 ITSM API（避免长锁）
            if not application.itsm_ticket_id:
                logger_celery.warning("[sync_scene_permission_status] PENDING 单 %s 无 itsm_ticket_id，跳过", application.id)
                continue
            logs_data = api.bk_itsm_v4.ticket_logs(ticket_id=application.itsm_ticket_id)
            if not logs_data:
                continue  # 查不到，跳过等下次

            # 2. 从日志推断工单状态
            parsed = parse_itsm_ticket_from_logs(logs_data)

            # 3. 提取拒绝理由（审批未通过且已终态时需要）
            reject_reason = ""
            if not parsed["approve_result"] and parsed["status"] == ITSMV4TicketStatus.FINISHED:
                reject_reason = _extract_reject_reason_from_logs(logs_data)

            # 4. 加锁 + 更新状态（仅数据库操作）
            with transaction.atomic():
                application = (
                    ScenePermissionApplication.objects.select_for_update()
                    .select_related("scene")
                    .get(id=application.id)
                )
                if application.status != ApplicationStatus.PENDING:
                    continue  # 并发已被处理
                apply_ticket_result(application, parsed, operator=operator, reject_reason=reject_reason)
                application.save()
        except Exception as err:  # pylint: disable=broad-except
            logger_celery.exception("[sync_scene_permission_status] PENDING 单 %s 失败: %s", application.id, err)

    # 阶段二：重试授权失败（审批已通过、仅授权失败），retry_count < MAX 才重试
    failed_qs = ScenePermissionApplication.objects.select_related("scene").filter(
        status=ApplicationStatus.APPROVED,
        grant_status=GrantStatus.FAILED,
        retry_count__lt=SCENE_PERMISSION_GRANT_MAX_RETRY,
        created_at__gte=one_year_ago,
    )
    for application in failed_qs:
        try:
            with transaction.atomic():
                application = (
                    ScenePermissionApplication.objects.select_for_update()
                    .select_related("scene")
                    .get(id=application.id)
                )
                if application.grant_status != GrantStatus.FAILED:
                    continue
                do_grant(application, operator=operator)
                application.save()
        except Exception as err:  # pylint: disable=broad-except
            logger_celery.exception("[sync_scene_permission_status] 授权失败重试 %s 失败: %s", application.id, err)
