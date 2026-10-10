# -*- coding: utf-8 -*-
import importlib

import pytest

from services.web.scene.constants import SceneStatus
from services.web.scene.models import Scene

migration_0006 = importlib.import_module("services.web.scene.migrations.0006_backfill_system_default_scene")


@pytest.mark.django_db
def test_ensure_default_scene_create_reserved_scene():
    """不存在 system_default 时，创建迁移保留场景。"""
    Scene.objects.filter(name=migration_0006.DEFAULT_SCENE_NAME).delete()

    scene = migration_0006._ensure_default_scene(Scene)

    assert scene.name == migration_0006.DEFAULT_SCENE_NAME
    assert scene.description == migration_0006.DEFAULT_SCENE_DESCRIPTION
    assert scene.status == SceneStatus.ENABLED


@pytest.mark.django_db
def test_ensure_default_scene_reuse_reserved_scene():
    """存在迁移保留场景时允许复用，并校正状态。"""
    # 事务测试清库后不会重跑数据迁移，复用场景由本例自行准备。
    Scene.objects.filter(name=migration_0006.DEFAULT_SCENE_NAME).delete()
    scene = Scene.objects.create(
        name=migration_0006.DEFAULT_SCENE_NAME,
        description=migration_0006.DEFAULT_SCENE_DESCRIPTION,
        status=SceneStatus.DISABLED,
    )

    reused = migration_0006._ensure_default_scene(Scene)
    scene.refresh_from_db()

    assert reused.scene_id == scene.scene_id
    assert scene.status == SceneStatus.ENABLED


@pytest.mark.django_db
def test_ensure_default_scene_reject_user_managed_conflict():
    """存在同名用户场景时拒绝复用，避免权限扩大。"""
    Scene.objects.filter(name=migration_0006.DEFAULT_SCENE_NAME).delete()
    Scene.objects.create(name=migration_0006.DEFAULT_SCENE_NAME, description="用户自定义场景")

    with pytest.raises(RuntimeError, match="Reserved scene name conflict"):
        migration_0006._ensure_default_scene(Scene)
