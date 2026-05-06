# -*- coding: utf-8 -*-
"""
为存量场景补建 IAM 用户组

对所有 iam_manager_group_id 或 iam_viewer_group_id 为空的场景，
调用 IAMGroupManager.create_single_group_with_members 分别创建管理和使用用户组并回写 ID。
"""
import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def backfill_scene_iam_groups(apps, schema_editor):
    """为缺少 IAM 用户组 ID 的存量场景补建用户组"""
    from django.db.models import Q

    from apps.meta.handlers.iam_group import (
        SCENE_MANAGER_GROUP_ACTIONS,
        SCENE_VIEWER_GROUP_ACTIONS,
        IAMGroupManager,
    )

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
            scene.iam_manager_group_id = IAMGroupManager.create_single_group_with_members(
                group_name=f"{scene.name}-管理用户组",
                group_description=f"{scene.name} 场景管理用户组，拥有查看和管理场景权限",
                group_actions=SCENE_MANAGER_GROUP_ACTIONS,
                members=scene.managers or None,
                scene_id=str(scene.scene_id),
                scene_name=scene.name,
            )
            scene.iam_viewer_group_id = IAMGroupManager.create_single_group_with_members(
                group_name=f"{scene.name}-使用用户组",
                group_description=f"{scene.name} 场景使用用户组，拥有查看场景权限",
                group_actions=SCENE_VIEWER_GROUP_ACTIONS,
                members=scene.users or None,
                scene_id=str(scene.scene_id),
                scene_name=scene.name,
            )
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
