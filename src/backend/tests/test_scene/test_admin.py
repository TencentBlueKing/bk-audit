# -*- coding: utf-8 -*-

from django.contrib import admin

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
            "updated_at",
        ]
        assert scene_admin.list_filter == ["status"]
        assert scene_admin.search_fields == ["name", "description"]
