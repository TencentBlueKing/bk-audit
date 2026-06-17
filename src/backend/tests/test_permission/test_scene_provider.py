# -*- coding: utf-8 -*-

import pytest
from iam.collection import FancyDict
from iam.resource.utils import Page

from services.web.scene.models import Scene
from services.web.scene.provider import SceneResourceProvider


@pytest.mark.django_db
class TestSceneResourceProvider:
    def setup_method(self):
        self.provider = SceneResourceProvider()

    def test_list_instance_by_policy_no_expression(self):
        lr = self.provider.list_instance_by_policy(FancyDict(expression=None), Page(50, 0))
        assert lr.count == 0
        assert lr.results == []

    def test_list_instance_by_policy_eq_scene_id(self):
        scene_in = Scene.objects.create(name="scene-in")
        Scene.objects.create(name="scene-out")

        expression = {
            "op": "eq",
            "field": "scene.id",
            "value": str(scene_in.scene_id),
        }

        lr = self.provider.list_instance_by_policy(FancyDict(expression=expression), Page(50, 0))

        assert lr.count == 1
        assert lr.results == [{"id": str(scene_in.scene_id), "display_name": scene_in.name}]

    def test_list_and_fetch_instance_use_scene_id(self):
        scene = Scene.objects.create(name="scene-id-provider")

        listed, listed_count = self.provider.filter_list_instance_results(None, None, Page(50, 0))
        fetched, fetched_count = self.provider.filter_fetch_instance_results([str(scene.scene_id)])

        assert listed_count >= 1
        assert {"id": str(scene.scene_id), "display_name": scene.name} in listed
        assert fetched_count == 1
        assert fetched == [{"id": str(scene.scene_id), "display_name": scene.name}]

    def test_fetch_instance_list_returns_snapshot_and_schema(self):
        scene = Scene.objects.create(name="scene-snapshot-provider")
        start_ms = int((scene.updated_at.timestamp() - 1) * 1000)
        end_ms = int((scene.updated_at.timestamp() + 1) * 1000)

        result = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))
        schema = self.provider.fetch_resource_type_schema()

        assert result.count == 1
        assert result.results[0]["id"] == str(scene.scene_id)
        assert result.results[0]["display_name"] == scene.name
        assert result.results[0]["data"]["scene_id"] == scene.scene_id
        assert result.results[0]["data"]["is_deleted"] is False
        assert "scene_id" in schema.properties
        assert "name" in schema.properties
        assert "is_deleted" in schema.properties

    def test_fetch_instance_list_returns_deleted_snapshot(self):
        scene = Scene.objects.create(name="scene-deleted-snapshot-provider")
        scene_id = scene.scene_id
        scene.delete()
        deleted_scene = Scene._base_manager.get(scene_id=scene_id)
        start_ms = int((deleted_scene.updated_at.timestamp() - 1) * 1000)
        end_ms = int((deleted_scene.updated_at.timestamp() + 1) * 1000)

        result = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))

        assert result.count == 1
        assert result.results[0]["id"] == str(scene_id)
        assert result.results[0]["is_deleted"] is True
        assert result.results[0]["data"]["is_deleted"] is True
