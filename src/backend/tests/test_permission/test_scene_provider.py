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
