# -*- coding: utf-8 -*-
import pytest
from iam.eval.constants import KEYWORD_BK_IAM_PATH

from apps.permission.handlers.resource_types import ResourceEnum
from services.web.scene.constants import (
    BindingType,
    ResourceVisibilityType,
    VisibilityScope,
)
from services.web.scene.models import ResourceBinding, ResourceBindingScene, Scene
from services.web.strategy_v2.models import LinkTable


def _create_scene(name: str = "test-scene") -> Scene:
    return Scene.objects.create(name=name)


def _bind_to_scene(resource_type: str, resource_id: str, scene: Scene) -> ResourceBindingScene:
    binding = ResourceBinding.objects.create(
        resource_type=resource_type,
        resource_id=str(resource_id),
        binding_type=BindingType.SCENE_BINDING,
        visibility_type=VisibilityScope.ALL_VISIBLE,
    )
    return ResourceBindingScene.objects.create(binding=binding, scene=scene)


@pytest.mark.django_db
class TestSceneRelatedResourceProviderAPI:
    def test_link_table_create_instance_uses_uid_and_latest_version_name(self):
        scene = _create_scene("link-table-logical-id-scene")
        link_table_v1 = LinkTable.objects.create(
            namespace="default",
            uid="lt-logical-id-1",
            version=1,
            name="old-link-table",
            config={"tables": [], "links": []},
        )
        LinkTable.objects.create(
            namespace="default",
            uid=link_table_v1.uid,
            version=2,
            name="new-link-table",
            config={"tables": [], "links": []},
        )
        _bind_to_scene(ResourceVisibilityType.LINK_TABLE, str(link_table_v1.uid), scene)

        resource = ResourceEnum.LINK_TABLE.create_instance(str(link_table_v1.uid))

        assert resource.attribute["id"] == str(link_table_v1.uid)
        assert resource.attribute["name"] == "new-link-table"
        assert resource.attribute[KEYWORD_BK_IAM_PATH] == f"/scene,{scene.scene_id}/link_table,{link_table_v1.uid}/"
