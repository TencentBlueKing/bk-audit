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
    assert scene.managers == []
    assert scene.users == []


@pytest.mark.django_db
def test_ensure_default_scene_reuse_reserved_scene():
    """存在迁移保留场景时允许复用，并校正状态。"""
    scene = Scene.objects.get(name=migration_0006.DEFAULT_SCENE_NAME)
    scene.description = migration_0006.DEFAULT_SCENE_DESCRIPTION
    scene.status = SceneStatus.DISABLED
    scene.managers = []
    scene.users = []
    scene.save(update_fields=["description", "status", "managers", "users"])

    reused = migration_0006._ensure_default_scene(Scene)
    scene.refresh_from_db()

    assert reused.scene_id == scene.scene_id
    assert scene.status == SceneStatus.ENABLED


@pytest.mark.django_db
def test_ensure_default_scene_reject_user_managed_conflict():
    """存在同名用户场景时拒绝复用，避免权限扩大。"""
    scene = Scene.objects.get(name=migration_0006.DEFAULT_SCENE_NAME)
    scene.description = "用户自定义场景"
    scene.managers = ["admin"]
    scene.users = ["user1"]
    scene.save(update_fields=["description", "managers", "users"])

    with pytest.raises(RuntimeError, match="Reserved scene name conflict"):
        migration_0006._ensure_default_scene(Scene)
