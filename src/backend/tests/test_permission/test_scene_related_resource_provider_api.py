# -*- coding: utf-8 -*-
import pytest
from iam.collection import FancyDict
from iam.eval.constants import KEYWORD_BK_IAM_PATH
from iam.resource.utils import Page

from apps.permission.handlers.resource_types import ResourceEnum
from services.web.process_application.provider import ProcessApplicationResourceProvider
from services.web.risk.models import ProcessApplication, RiskRule
from services.web.rule.provider import RuleResourceProvider
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
class TestSceneRelatedResourceProviderAPI:
    def setup_method(self):
        _patch_local_request(ProcessApplicationResourceProvider)
        _patch_local_request(RuleResourceProvider)

    # ==================== create_instance 路径测试 ====================

    def test_process_application_create_instance_contains_iam_path(self):
        pa = ProcessApplication.objects.create(name="pa-for-iam", sops_template_id=1001)

        resource = ResourceEnum.PROCESS_APPLICATION.create_instance(str(pa.id))

        assert resource.attribute["id"] == str(pa.id)
        assert resource.attribute["name"] == pa.name
        assert KEYWORD_BK_IAM_PATH in resource.attribute
        assert resource.attribute[KEYWORD_BK_IAM_PATH].endswith(f"/process_application,{pa.id}/")

    def test_process_application_create_instance_with_scene_binding(self):
        """绑定到场景后，iam_path 应包含正确的 scene_id"""
        scene = _create_scene("pa-scene")
        pa = ProcessApplication.objects.create(name="pa-bound", sops_template_id=1002)
        _bind_to_scene(ResourceVisibilityType.PROCESS_APPLICATION, str(pa.id), scene)

        resource = ResourceEnum.PROCESS_APPLICATION.create_instance(str(pa.id))

        expected_path = f"/scene,{scene.scene_id}/process_application,{pa.id}/"
        assert resource.attribute[KEYWORD_BK_IAM_PATH] == expected_path

    def test_rule_create_instance_contains_iam_path(self):
        rule = RiskRule.objects.create(name="rule-for-iam", scope={})

        resource = ResourceEnum.RULE.create_instance(str(rule.id))

        assert resource.attribute["id"] == str(rule.id)
        assert resource.attribute["name"] == rule.name
        assert KEYWORD_BK_IAM_PATH in resource.attribute
        assert resource.attribute[KEYWORD_BK_IAM_PATH].endswith(f"/rule,{rule.id}/")

    def test_rule_create_instance_with_scene_binding(self):
        """绑定到场景后，iam_path 应包含正确的 scene_id"""
        scene = _create_scene("rule-scene")
        rule = RiskRule.objects.create(name="rule-bound", scope={})
        _bind_to_scene(ResourceVisibilityType.RISK_RULE, str(rule.id), scene)

        resource = ResourceEnum.RULE.create_instance(str(rule.id))

        expected_path = f"/scene,{scene.scene_id}/rule,{rule.id}/"
        assert resource.attribute[KEYWORD_BK_IAM_PATH] == expected_path

    # ==================== Provider fetch_instance_info 测试 ====================

    def test_process_application_provider_fetch_instance_info(self):
        pa = ProcessApplication.objects.create(name="pa-fetch", sops_template_id=1002)
        provider = ProcessApplicationResourceProvider()

        lr = provider.fetch_instance_info(FancyDict(ids=[str(pa.id)]))

        assert lr.count == 1
        assert lr.results == [{"id": str(pa.id), "display_name": pa.name}]

    def test_rule_provider_fetch_instance_info(self):
        rule = RiskRule.objects.create(name="rule-fetch", scope={})
        provider = RuleResourceProvider()

        lr = provider.fetch_instance_info(FancyDict(ids=[str(rule.id)]))

        assert lr.count == 1
        assert lr.results == [{"id": str(rule.id), "display_name": rule.name}]

    # ==================== Provider 场景过滤测试 ====================

    def test_process_application_provider_list_by_scene(self):
        """通过 ResourceBindingScene 过滤，只返回绑定到该场景的处理套餐"""
        scene = _create_scene("pa-list-scene")
        pa_in = ProcessApplication.objects.create(name="pa-in-scene", sops_template_id=2001)
        pa_out = ProcessApplication.objects.create(name="pa-out-scene", sops_template_id=2002)
        _bind_to_scene(ResourceVisibilityType.PROCESS_APPLICATION, str(pa_in.id), scene)

        provider = ProcessApplicationResourceProvider()
        page = Page(50, 0)

        # list_instance 带 scene parent
        lr = provider.list_instance(
            FancyDict(parent=FancyDict(id=str(scene.scene_id), type=ResourceEnum.SCENE.id), search=None),
            page,
        )
        result_ids = {item["id"] for item in lr.results}
        assert str(pa_in.id) in result_ids
        assert str(pa_out.id) not in result_ids

    def test_process_application_provider_search_by_scene(self):
        """搜索时只返回该场景下匹配的处理套餐"""
        scene = _create_scene("pa-search-scene")
        pa_in = ProcessApplication.objects.create(name="searchable-pa", sops_template_id=3001)
        pa_out = ProcessApplication.objects.create(name="searchable-pa-outside", sops_template_id=3002)
        _bind_to_scene(ResourceVisibilityType.PROCESS_APPLICATION, str(pa_in.id), scene)

        provider = ProcessApplicationResourceProvider()
        page = Page(50, 0)

        lr = provider.search_instance(
            FancyDict(
                parent=FancyDict(id=str(scene.scene_id), type=ResourceEnum.SCENE.id),
                keyword="searchable",
            ),
            page,
        )
        result_ids = {item["id"] for item in lr.results}
        assert str(pa_in.id) in result_ids
        assert str(pa_out.id) not in result_ids

    def test_rule_provider_list_by_scene(self):
        """通过 ResourceBindingScene 过滤，只返回绑定到该场景的处理规则"""
        scene = _create_scene("rule-list-scene")
        rule_in = RiskRule.objects.create(name="rule-in-scene", scope={})
        rule_out = RiskRule.objects.create(name="rule-out-scene", scope={})
        _bind_to_scene(ResourceVisibilityType.RISK_RULE, str(rule_in.id), scene)

        provider = RuleResourceProvider()
        page = Page(50, 0)

        lr = provider.list_instance(
            FancyDict(parent=FancyDict(id=str(scene.scene_id), type=ResourceEnum.SCENE.id), search=None),
            page,
        )
        result_ids = {item["id"] for item in lr.results}
        assert str(rule_in.id) in result_ids
        assert str(rule_out.id) not in result_ids

    def test_rule_provider_search_by_scene(self):
        """搜索时只返回该场景下匹配的处理规则"""
        scene = _create_scene("rule-search-scene")
        rule_in = RiskRule.objects.create(name="findable-rule", scope={})
        rule_out = RiskRule.objects.create(name="findable-rule-outside", scope={})
        _bind_to_scene(ResourceVisibilityType.RISK_RULE, str(rule_in.id), scene)

        provider = RuleResourceProvider()
        page = Page(50, 0)

        lr = provider.search_instance(
            FancyDict(
                parent=FancyDict(id=str(scene.scene_id), type=ResourceEnum.SCENE.id),
                keyword="findable",
            ),
            page,
        )
        result_ids = {item["id"] for item in lr.results}
        assert str(rule_in.id) in result_ids
        assert str(rule_out.id) not in result_ids

    # ==================== 无 parent 时返回全部 ====================

    def test_process_application_provider_list_all_without_parent(self):
        """无 parent 时应返回全部处理套餐"""
        pa = ProcessApplication.objects.create(name="pa-all", sops_template_id=4001)
        provider = ProcessApplicationResourceProvider()

        lr = provider.list_instance(FancyDict(parent=None, search=None), Page(50, 0))

        result_ids = {item["id"] for item in lr.results}
        assert str(pa.id) in result_ids

    def test_rule_provider_list_all_without_parent(self):
        """无 parent 时应返回全部处理规则"""
        rule = RiskRule.objects.create(name="rule-all", scope={})
        provider = RuleResourceProvider()

        lr = provider.list_instance(FancyDict(parent=None, search=None), Page(50, 0))

        result_ids = {item["id"] for item in lr.results}
        assert str(rule.id) in result_ids
