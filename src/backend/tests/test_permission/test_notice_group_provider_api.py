# -*- coding: utf-8 -*-
import pytest
from iam.collection import FancyDict
from iam.eval.constants import KEYWORD_BK_IAM_PATH
from iam.resource.utils import Page

from apps.notice.models import NoticeGroup
from apps.notice.provider import NoticeGroupResourceProvider
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.scene.constants import (
    BindingType,
    ResourceVisibilityType,
    VisibilityScope,
)
from services.web.scene.models import ResourceBinding, ResourceBindingScene, Scene


def _patch_local_request(provider_cls):
    """为 Provider 注入 dummy request，绕过 get_local_request 依赖"""

    class _R:
        headers = {}

    setattr(provider_cls, "get_local_request", staticmethod(lambda: _R()))


def _create_scene(name: str = "test-scene") -> Scene:
    return Scene.objects.create(name=name)


def _mk_notice_group(name: str) -> NoticeGroup:
    return NoticeGroup.objects.create(group_name=name, group_member=["admin"], notice_config=[])


def _bind_to_scene(resource_type: str, resource_id: str, scene: Scene) -> ResourceBindingScene:
    """创建 ResourceBinding + ResourceBindingScene，将资源绑定到场景"""
    binding = ResourceBinding.objects.create(
        resource_type=resource_type,
        resource_id=str(resource_id),
        binding_type=BindingType.SCENE_BINDING,
        visibility_type=VisibilityScope.ALL_VISIBLE,
    )
    return ResourceBindingScene.objects.create(binding=binding, scene=scene)


@pytest.mark.django_db
class TestNoticeGroupResourceProviderAPI:
    def setup_method(self):
        _patch_local_request(NoticeGroupResourceProvider)
        self.provider = NoticeGroupResourceProvider()

    # ==================== 基础 CRUD 测试 ====================

    def test_list_and_fetch_info_and_search(self):
        a = _mk_notice_group("alpha-group")
        b = _mk_notice_group("beta-group")

        lr = self.provider.list_instance(FancyDict(parent=None, search=None), Page(50, 0))
        assert lr.count >= 2

        result_map = {item["id"]: item["display_name"] for item in lr.results}
        assert result_map.get(a.group_id) == a.group_name
        assert result_map.get(b.group_id) == b.group_name

        lr = self.provider.fetch_instance_info(FancyDict(ids=[a.group_id, b.group_id]))
        assert lr.count == 2

        result_map = {item["id"]: item["display_name"] for item in lr.results}
        assert result_map.get(a.group_id) == a.group_name
        assert result_map.get(b.group_id) == b.group_name

        lr = self.provider.search_instance(FancyDict(keyword="alpha", parent=None), Page(50, 0))
        assert lr.count == 1
        assert lr.results == [{"id": a.group_id, "display_name": a.group_name}]

    def test_list_attr_and_attr_value_empty(self):
        lr = self.provider.list_attr()
        assert lr.count == 0
        assert lr.results == []

        lr = self.provider.list_attr_value(FancyDict(attr="group_name"), Page(50, 0))
        assert lr.count == 0
        assert lr.results == []

    def test_list_instance_by_policy_no_expression(self):
        lr = self.provider.list_instance_by_policy(FancyDict(expression=None), Page(50, 0))
        assert lr.count == 0
        assert lr.results == []

    # ==================== create_instance 路径测试 ====================

    def test_create_instance_without_binding(self):
        """未绑定场景时，iam_path 的 scene_id 为空字符串"""
        ng = _mk_notice_group("ng-no-binding")

        resource = ResourceEnum.NOTICE_GROUP.create_instance(str(ng.group_id))

        assert resource.attribute["id"] == str(ng.group_id)
        assert resource.attribute["name"] == ng.group_name
        assert resource.attribute[KEYWORD_BK_IAM_PATH] == f"/scene,/notice_group,{ng.group_id}/"

    def test_create_instance_with_scene_binding(self):
        """绑定到场景后，iam_path 应包含正确的 scene_id"""
        scene = _create_scene("ng-scene")
        ng = _mk_notice_group("ng-bound")
        _bind_to_scene(ResourceVisibilityType.NOTICE_GROUP, str(ng.group_id), scene)

        resource = ResourceEnum.NOTICE_GROUP.create_instance(str(ng.group_id))

        expected_path = f"/scene,{scene.scene_id}/notice_group,{ng.group_id}/"
        assert resource.attribute[KEYWORD_BK_IAM_PATH] == expected_path
        assert resource.attribute["name"] == ng.group_name

    # ==================== Provider 场景过滤测试 ====================

    def test_list_instance_by_scene_returns_bound_only(self):
        """list_instance 按场景过滤，只返回绑定到该场景的通知组"""
        scene = _create_scene("ng-filter-scene")
        ng_in = _mk_notice_group("in-scene-group")
        ng_out = _mk_notice_group("out-scene-group")
        _bind_to_scene(ResourceVisibilityType.NOTICE_GROUP, str(ng_in.group_id), scene)

        lr = self.provider.list_instance(
            FancyDict(parent=FancyDict(id=str(scene.scene_id), type=ResourceEnum.SCENE.id), search=None),
            Page(50, 0),
        )

        result_ids = {item["id"] for item in lr.results}
        assert ng_in.group_id in result_ids
        assert ng_out.group_id not in result_ids

    def test_search_instance_by_scene_returns_bound_only(self):
        """search_instance 按场景过滤+关键词搜索，只返回绑定到该场景的通知组"""
        scene = _create_scene("ng-search-scene")
        ng_in = _mk_notice_group("findable-ng")
        ng_out = _mk_notice_group("findable-ng-outside")
        _bind_to_scene(ResourceVisibilityType.NOTICE_GROUP, str(ng_in.group_id), scene)

        lr = self.provider.search_instance(
            FancyDict(
                parent=FancyDict(id=str(scene.scene_id), type=ResourceEnum.SCENE.id),
                keyword="findable",
            ),
            Page(50, 0),
        )

        result_ids = {item["id"] for item in lr.results}
        assert ng_in.group_id in result_ids
        assert ng_out.group_id not in result_ids

    def test_list_instance_no_parent_returns_all(self):
        """无 parent 时应返回全部通知组"""
        ng = _mk_notice_group("ng-all-visible")

        lr = self.provider.list_instance(FancyDict(parent=None, search=None), Page(50, 0))

        result_ids = {item["id"] for item in lr.results}
        assert ng.group_id in result_ids

    def test_list_instance_unknown_parent_type_returns_empty(self):
        """parent type 不是 scene 时应返回空"""
        _mk_notice_group("ng-unknown-parent")

        lr = self.provider.list_instance(
            FancyDict(parent=FancyDict(id="999", type="unknown_type"), search=None),
            Page(50, 0),
        )

        assert lr.count == 0
        assert lr.results == []
