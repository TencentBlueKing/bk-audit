# -*- coding: utf-8 -*-
"""
为存量场景补建 IAM 用户组

对所有 iam_manager_group_id 或 iam_viewer_group_id 为空的场景，
调用 IAMGroupManager.create_scene_groups_with_members 创建用户组并回写 ID。
"""
import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def backfill_scene_iam_groups(apps, schema_editor):
    """为缺少 IAM 用户组 ID 的存量场景补建用户组"""
    from django.db.models import Q

    from apps.meta.handlers.iam_group import IAMGroupManager

    Scene = apps.get_model("scene", "Scene")
    scenes = Scene.objects.filter(Q(iam_manager_group_id__isnull=True) | Q(iam_viewer_group_id__isnull=True))

    if not scenes.exists():
        logger.info("[backfill_scene_iam_groups] 没有需要补建用户组的场景，跳过")
        return

    logger.info("[backfill_scene_iam_groups] 发现 %d 个场景需要补建 IAM 用户组", scenes.count())

    success_count = 0
    fail_count = 0

    for scene in scenes:
        try:
            group_ids = IAMGroupManager.create_scene_groups_with_members(
                scene_id=str(scene.scene_id),
                scene_name=scene.name,
                manager_members=([{"type": "user", "id": m} for m in scene.managers] if scene.managers else None),
                viewer_members=([{"type": "user", "id": u} for u in scene.users] if scene.users else None),
            )
            scene.iam_manager_group_id = group_ids["iam_manager_group_id"]
            scene.iam_viewer_group_id = group_ids["iam_viewer_group_id"]
            scene.save(update_fields=["iam_manager_group_id", "iam_viewer_group_id"])
            success_count += 1
            logger.info(
                "[backfill_scene_iam_groups] 场景 %s(%s) 补建成功, " "iam_manager_group_id=%s, iam_viewer_group_id=%s",
                scene.name,
                scene.scene_id,
                scene.iam_manager_group_id,
                scene.iam_viewer_group_id,
            )
        except Exception as e:
            fail_count += 1
            logger.error(
                "[backfill_scene_iam_groups] 场景 %s(%s) 补建失败: %s",
                scene.name,
                scene.scene_id,
                e,
            )

    logger.info(
        "[backfill_scene_iam_groups] 补建完成, 成功=%d, 失败=%d",
        success_count,
        fail_count,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("scene", "0008_scene_iam_manager_group_id_scene_iam_viewer_group_id"),
    ]

    operations = [
        migrations.RunPython(
            backfill_scene_iam_groups,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
