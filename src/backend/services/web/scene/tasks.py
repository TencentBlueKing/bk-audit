# -*- coding: utf-8 -*-
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.utils.logger import logger_celery as logger
from celery.schedules import crontab
from django.conf import settings

from core.lock import lock
from services.web.scene.models import Scene
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
