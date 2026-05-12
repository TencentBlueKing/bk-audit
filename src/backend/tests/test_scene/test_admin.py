# -*- coding: utf-8 -*-

import pytest
from django.contrib import admin
from django.test import RequestFactory

from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
    SceneDataTable,
    SceneSystem,
)


class TestSceneAdminRegistration:
    def test_scene_models_are_registered(self):
        for model in [Scene, SceneSystem, SceneDataTable, ResourceBinding, ResourceBindingScene, ResourceBindingSystem]:
            assert model in admin.site._registry

    def test_scene_admin_configuration(self):
        scene_admin = admin.site._registry[Scene]
        assert scene_admin.list_display == [
            "scene_id",
            "name",
            "status",
            "iam_manager_group_id",
            "iam_viewer_group_id",
            "is_deleted",
            "updated_at",
        ]
        assert scene_admin.list_filter == ["status", "is_deleted"]
        assert scene_admin.search_fields == ["name", "description"]

    @pytest.mark.django_db
    def test_scene_admin_queryset_includes_soft_deleted_scene(self):
        scene = Scene.objects.create(name="admin 可恢复场景")
        scene.delete()

        scene_admin = admin.site._registry[Scene]
        request = RequestFactory().get("/admin/scene/scene/")

        assert scene.scene_id in scene_admin.get_queryset(request).values_list("scene_id", flat=True)

    @pytest.mark.django_db
    def test_scene_admin_delete_model_uses_soft_delete(self):
        scene = Scene.objects.create(name="admin 单个删除场景")
        SceneSystem.objects.create(scene=scene, system_id="bk_cmdb")
        scene_id = scene.scene_id

        scene_admin = admin.site._registry[Scene]
        request = RequestFactory().post("/admin/scene/scene/")
        scene_admin.delete_model(request, scene)

        assert not Scene.objects.filter(scene_id=scene_id).exists()
        assert Scene._objects.filter(scene_id=scene_id, is_deleted=True).exists()
        assert SceneSystem.objects.filter(scene_id=scene_id).exists()

    @pytest.mark.django_db
    def test_scene_admin_delete_queryset_uses_soft_delete(self):
        scene = Scene.objects.create(name="admin 批量删除场景")
        SceneSystem.objects.create(scene=scene, system_id="bk_cmdb")
        scene_id = scene.scene_id

        scene_admin = admin.site._registry[Scene]
        request = RequestFactory().post("/admin/scene/scene/")
        scene_admin.delete_queryset(request, Scene._objects.filter(scene_id=scene_id))

        assert not Scene.objects.filter(scene_id=scene_id).exists()
        assert Scene._objects.filter(scene_id=scene_id, is_deleted=True).exists()
        assert SceneSystem.objects.filter(scene_id=scene_id).exists()
