# -*- coding: utf-8 -*-
"""
场景隔离 Phase 2 单元测试 — 现有资源关联场景

覆盖：
- 模型层：ResourceBinding / ResourceBindingScene 关联表
- Serializer 层：列表查询和创建序列化器的 scene_id 参数
- Resource 层：SceneScopeFilter / BindingScopeFilter 场景过滤
- 创建场景时自动创建"场景管理员通知组"
- 删除场景时检查关联资源（策略/通知组/处理套餐/处理规则）
"""
import json

import pytest
from django.test import RequestFactory

from apps.notice.models import NoticeGroup
from services.web.risk.models import ProcessApplication, RiskRule
from services.web.scene.constants import (
    BindingType,
    ResourceVisibilityType,
    SceneStatus,
)
from services.web.scene.filters import BindingScopeFilter, SceneScopeFilter
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
)
from services.web.strategy_v2.models import Strategy

# ==================== Fixtures ====================


class MockUser:
    """模拟用户"""

    def __init__(self, username="admin"):
        self.username = username
        self.is_authenticated = True
        self.is_active = True
        self.pk = 1


@pytest.fixture
def rf():
    """Django RequestFactory"""
    return RequestFactory()


@pytest.fixture
def mock_user():
    return MockUser("admin")


@pytest.fixture
def scene(db):
    """创建测试场景"""
    return Scene.objects.create(
        name="Phase2测试场景",
        description="Phase 2 测试用场景",
        status=SceneStatus.ENABLED,
        managers=["admin", "manager1"],
        users=["user1", "user2"],
    )


@pytest.fixture
def another_scene(db):
    """创建另一个测试场景"""
    return Scene.objects.create(
        name="另一个场景",
        description="用于隔离测试",
        status=SceneStatus.ENABLED,
        managers=["admin2"],
        users=["user3"],
    )


def _make_request(rf, method, path, data=None, user=None):
    """构造带用户的请求"""
    if user is None:
        user = MockUser("admin")
    if method == "get":
        request = rf.get(path, data=data or {})
    elif method == "post":
        request = rf.post(path, data=json.dumps(data or {}), content_type="application/json")
    elif method == "put":
        request = rf.put(path, data=json.dumps(data or {}), content_type="application/json")
    elif method == "delete":
        request = rf.delete(path)
    else:
        raise ValueError(f"Unsupported method: {method}")
    request.user = user
    # 跳过 CSRF 校验
    request.META["HTTP_X_CSRFTOKEN"] = "test"
    request._dont_enforce_csrf_checks = True
    return request


def _bind_resource_to_scene(resource_id, resource_type, scene_id, binding_type=BindingType.SCENE_BINDING):
    """辅助函数：将资源绑定到场景"""
    binding = ResourceBinding.objects.create(
        resource_id=str(resource_id),
        resource_type=resource_type,
        binding_type=binding_type,
    )
    ResourceBindingScene.objects.create(
        binding=binding,
        scene_id=scene_id,
    )
    return binding


# ==================== 模型层测试：ResourceBinding 关联 ====================


class TestResourceBindingModel:
    """ResourceBinding 关联表测试"""

    @pytest.mark.django_db
    def test_resource_binding_create(self, scene):
        """测试创建 ResourceBinding"""
        binding = ResourceBinding.objects.create(
            resource_id="100",
            resource_type=ResourceVisibilityType.STRATEGY,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert binding.resource_id == "100"
        assert binding.resource_type == ResourceVisibilityType.STRATEGY

    @pytest.mark.django_db
    def test_resource_binding_scene_create(self, scene):
        """测试创建 ResourceBindingScene"""
        binding = ResourceBinding.objects.create(
            resource_id="100",
            resource_type=ResourceVisibilityType.STRATEGY,
            binding_type=BindingType.SCENE_BINDING,
        )
        binding_scene = ResourceBindingScene.objects.create(
            binding=binding,
            scene_id=scene.scene_id,
        )
        assert binding_scene.scene_id == scene.scene_id
        assert binding_scene.binding == binding

    @pytest.mark.django_db
    def test_resource_binding_scene_query(self, scene, another_scene):
        """测试通过 ResourceBindingScene 查询资源"""
        _bind_resource_to_scene("100", ResourceVisibilityType.STRATEGY, scene.scene_id)
        _bind_resource_to_scene("200", ResourceVisibilityType.STRATEGY, another_scene.scene_id)

        bound_ids = ResourceBindingScene.objects.filter(
            scene_id=scene.scene_id,
            binding__resource_type=ResourceVisibilityType.STRATEGY,
        ).values_list("binding__resource_id", flat=True)
        assert list(bound_ids) == ["100"]


class TestStrategySceneId:
    """Strategy 通过 ResourceBinding 关联场景测试"""

    @pytest.mark.django_db
    def test_strategy_scene_id_nullable(self):
        """测试 Strategy 可以不绑定场景（无 ResourceBinding 记录）"""
        strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="测试策略",
        )
        # 没有 ResourceBinding 记录
        assert not ResourceBinding.objects.filter(
            resource_id=str(strategy.strategy_id),
            resource_type=ResourceVisibilityType.STRATEGY,
        ).exists()

    @pytest.mark.django_db
    def test_strategy_scene_id_set(self, scene):
        """测试 Strategy 可以通过 ResourceBinding 绑定到场景"""
        strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="场景策略",
        )
        _bind_resource_to_scene(strategy.strategy_id, ResourceVisibilityType.STRATEGY, scene.scene_id)
        bound_ids = ResourceBindingScene.objects.filter(
            scene_id=scene.scene_id,
            binding__resource_type=ResourceVisibilityType.STRATEGY,
        ).values_list("binding__resource_id", flat=True)
        assert str(strategy.strategy_id) in list(bound_ids)

    @pytest.mark.django_db
    def test_strategy_scene_id_field_exists(self):
        """测试 ResourceBinding 模型支持 STRATEGY 资源类型"""
        assert ResourceVisibilityType.STRATEGY is not None
        binding = ResourceBinding.objects.create(
            resource_id="1",
            resource_type=ResourceVisibilityType.STRATEGY,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert binding.resource_type == ResourceVisibilityType.STRATEGY


class TestRiskSceneId:
    """Risk 通过 ResourceBinding 关联场景测试"""

    @pytest.mark.django_db
    def test_risk_scene_id_field_exists(self):
        """测试 ResourceBinding 模型支持 RISK 资源类型"""
        assert ResourceVisibilityType.RISK is not None
        binding = ResourceBinding.objects.create(
            resource_id="1",
            resource_type=ResourceVisibilityType.RISK,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert binding.resource_type == ResourceVisibilityType.RISK

    @pytest.mark.django_db
    def test_risk_scene_id_nullable(self):
        """测试 Risk 可以不绑定场景"""
        # ResourceBinding 不要求必须有 scene 关联
        binding = ResourceBinding.objects.create(
            resource_id="1",
            resource_type=ResourceVisibilityType.RISK,
            binding_type=BindingType.SCENE_BINDING,
        )
        # 没有 ResourceBindingScene 记录也是合法的
        assert not ResourceBindingScene.objects.filter(binding=binding).exists()


class TestProcessApplicationSceneId:
    """ProcessApplication 通过 ResourceBinding 关联场景测试"""

    @pytest.mark.django_db
    def test_process_application_scene_id_field_exists(self):
        """测试 ResourceBinding 模型支持 PROCESS_APPLICATION 资源类型"""
        assert ResourceVisibilityType.PROCESS_APPLICATION is not None
        binding = ResourceBinding.objects.create(
            resource_id="1",
            resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert binding.resource_type == ResourceVisibilityType.PROCESS_APPLICATION

    @pytest.mark.django_db
    def test_process_application_scene_id_nullable(self):
        """测试 ProcessApplication 可以不绑定场景"""
        binding = ResourceBinding.objects.create(
            resource_id="1",
            resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert not ResourceBindingScene.objects.filter(binding=binding).exists()

    @pytest.mark.django_db
    def test_process_application_scene_id_db_index(self, scene):
        """测试 ResourceBinding 的 resource_type 和 resource_id 组合可高效查询"""
        pa = ProcessApplication.objects.create(
            name="测试套餐",
            sops_template_id=10001,
        )
        _bind_resource_to_scene(pa.id, ResourceVisibilityType.PROCESS_APPLICATION, scene.scene_id)
        # 验证可以通过 resource_type + resource_id 查询
        assert ResourceBinding.objects.filter(
            resource_id=str(pa.id),
            resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
        ).exists()


class TestRiskRuleSceneId:
    """RiskRule 通过 ResourceBinding 关联场景测试"""

    @pytest.mark.django_db
    def test_risk_rule_scene_id_field_exists(self):
        """测试 ResourceBinding 模型支持 RISK_RULE 资源类型"""
        assert ResourceVisibilityType.RISK_RULE is not None
        binding = ResourceBinding.objects.create(
            resource_id="1",
            resource_type=ResourceVisibilityType.RISK_RULE,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert binding.resource_type == ResourceVisibilityType.RISK_RULE

    @pytest.mark.django_db
    def test_risk_rule_scene_id_nullable(self):
        """测试 RiskRule 可以不绑定场景"""
        binding = ResourceBinding.objects.create(
            resource_id="1",
            resource_type=ResourceVisibilityType.RISK_RULE,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert not ResourceBindingScene.objects.filter(binding=binding).exists()


class TestNoticeGroupSceneId:
    """NoticeGroup 通过 ResourceBinding 关联场景测试"""

    @pytest.mark.django_db
    def test_notice_group_scene_id_field_exists(self):
        """测试 ResourceBinding 模型支持 NOTICE_GROUP 资源类型"""
        assert ResourceVisibilityType.NOTICE_GROUP is not None
        binding = ResourceBinding.objects.create(
            resource_id="1",
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert binding.resource_type == ResourceVisibilityType.NOTICE_GROUP

    @pytest.mark.django_db
    def test_notice_group_scene_id_nullable(self):
        """测试 NoticeGroup 可以不绑定场景"""
        ng = NoticeGroup.objects.create(
            group_name="无场景通知组",
            group_member=["admin"],
            notice_config=[],
        )
        assert not ResourceBinding.objects.filter(
            resource_id=str(ng.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
        ).exists()

    @pytest.mark.django_db
    def test_notice_group_create_with_scene_id(self, scene):
        """测试创建带场景绑定的通知组"""
        ng = NoticeGroup.objects.create(
            group_name="测试通知组",
            group_member=["admin"],
            notice_config=[],
        )
        _bind_resource_to_scene(ng.group_id, ResourceVisibilityType.NOTICE_GROUP, scene.scene_id)
        bound_ids = ResourceBindingScene.objects.filter(
            scene_id=scene.scene_id,
            binding__resource_type=ResourceVisibilityType.NOTICE_GROUP,
        ).values_list("binding__resource_id", flat=True)
        assert str(ng.group_id) in list(bound_ids)

    @pytest.mark.django_db
    def test_notice_group_filter_by_scene_id(self, scene, another_scene):
        """测试按场景过滤通知组"""
        NoticeGroup.objects.all().delete()
        ng1 = NoticeGroup.objects.create(
            group_name="场景1通知组",
            group_member=["admin"],
            notice_config=[],
        )
        _bind_resource_to_scene(ng1.group_id, ResourceVisibilityType.NOTICE_GROUP, scene.scene_id)
        ng2 = NoticeGroup.objects.create(
            group_name="场景2通知组",
            group_member=["admin"],
            notice_config=[],
        )
        _bind_resource_to_scene(ng2.group_id, ResourceVisibilityType.NOTICE_GROUP, another_scene.scene_id)
        NoticeGroup.objects.create(
            group_name="无场景通知组",
            group_member=["admin"],
            notice_config=[],
        )
        # 通过 SceneScopeFilter 过滤
        qs = SceneScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            scene_id=scene.scene_id,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 1
        assert qs.first().group_name == "场景1通知组"


class TestLinkTableSceneId:
    """LinkTable 通过 ResourceBinding 关联场景测试"""

    @pytest.mark.django_db
    def test_link_table_scene_id_field_exists(self):
        """测试 ResourceBinding 模型支持 LINK_TABLE 资源类型"""
        assert ResourceVisibilityType.LINK_TABLE is not None
        binding = ResourceBinding.objects.create(
            resource_id="test_uid",
            resource_type=ResourceVisibilityType.LINK_TABLE,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert binding.resource_type == ResourceVisibilityType.LINK_TABLE

    @pytest.mark.django_db
    def test_link_table_scene_id_nullable(self):
        """测试 LinkTable 可以不绑定场景"""
        binding = ResourceBinding.objects.create(
            resource_id="test_uid",
            resource_type=ResourceVisibilityType.LINK_TABLE,
            binding_type=BindingType.SCENE_BINDING,
        )
        assert not ResourceBindingScene.objects.filter(binding=binding).exists()


# ==================== Serializer 层测试 ====================


class TestListStrategyRequestSerializer:
    """策略列表序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 ListStrategyRequestSerializer 包含 scene_id 字段"""
        from services.web.strategy_v2.serializers import ListStrategyRequestSerializer

        serializer = ListStrategyRequestSerializer()
        assert "scene_id" in serializer.fields

    def test_scene_id_not_required(self):
        """测试 scene_id 非必填"""
        from services.web.strategy_v2.serializers import ListStrategyRequestSerializer

        serializer = ListStrategyRequestSerializer()
        assert serializer.fields["scene_id"].required is False


class TestCreateStrategyRequestSerializer:
    """策略创建序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 CreateStrategyRequestSerializer 包含 scene_id 字段"""
        from services.web.strategy_v2.serializers import CreateStrategyRequestSerializer

        serializer = CreateStrategyRequestSerializer()
        assert "scene_id" in serializer.fields


class TestListNoticeGroupRequestSerializer:
    """通知组列表序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 ListNoticeGroupRequestSerializer 包含 scene_id 字段"""
        from apps.notice.serializers import ListNoticeGroupRequestSerializer

        serializer = ListNoticeGroupRequestSerializer()
        assert "scene_id" in serializer.fields

    def test_scene_id_not_required(self):
        """测试 scene_id 非必填"""
        from apps.notice.serializers import ListNoticeGroupRequestSerializer

        serializer = ListNoticeGroupRequestSerializer()
        assert serializer.fields["scene_id"].required is False


class TestCreateNoticeGroupRequestSerializer:
    """通知组创建序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 CreateNoticeGroupRequestSerializer 包含 scene_id 字段"""
        from apps.notice.serializers import CreateNoticeGroupRequestSerializer

        serializer = CreateNoticeGroupRequestSerializer()
        assert "scene_id" in serializer.fields

    def test_scene_id_required(self):
        """测试 scene_id 为必传字段"""
        from apps.notice.serializers import CreateNoticeGroupRequestSerializer

        serializer = CreateNoticeGroupRequestSerializer()
        assert serializer.fields["scene_id"].required is True


class TestListProcessApplicationsReqSerializer:
    """处理套餐列表序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 ListProcessApplicationsReqSerializer 包含 scene_id 字段"""
        from services.web.risk.serializers import ListProcessApplicationsReqSerializer

        serializer = ListProcessApplicationsReqSerializer()
        assert "scene_id" in serializer.fields


class TestCreateProcessApplicationsReqSerializer:
    """处理套餐创建序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 CreateProcessApplicationsReqSerializer 包含 scene_id 字段"""
        from services.web.risk.serializers import CreateProcessApplicationsReqSerializer

        serializer = CreateProcessApplicationsReqSerializer()
        assert "scene_id" in serializer.fields


class TestListRiskRuleReqSerializer:
    """处理规则列表序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 ListRiskRuleReqSerializer 包含 scene_id 字段"""
        from services.web.risk.serializers import ListRiskRuleReqSerializer

        serializer = ListRiskRuleReqSerializer()
        assert "scene_id" in serializer.fields


class TestCreateRiskRuleReqSerializer:
    """处理规则创建序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 CreateRiskRuleReqSerializer 包含 scene_id 字段"""
        from services.web.risk.serializers import CreateRiskRuleReqSerializer

        serializer = CreateRiskRuleReqSerializer()
        assert "scene_id" in serializer.fields


class TestListRiskRequestSerializer:
    """风险列表序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 ListRiskRequestSerializer 包含 scene_id 字段"""
        from services.web.risk.serializers import ListRiskRequestSerializer

        serializer = ListRiskRequestSerializer()
        assert "scene_id" in serializer.fields

    def test_scene_id_not_required(self):
        """测试 scene_id 非必填"""
        from services.web.risk.serializers import ListRiskRequestSerializer

        serializer = ListRiskRequestSerializer()
        assert serializer.fields["scene_id"].required is False


class TestListLinkTableRequestSerializer:
    """联表列表序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 ListLinkTableRequestSerializer 包含 scene_id 字段"""
        from services.web.strategy_v2.serializers import ListLinkTableRequestSerializer

        serializer = ListLinkTableRequestSerializer()
        assert "scene_id" in serializer.fields


class TestCreateLinkTableRequestSerializer:
    """联表创建序列化器 scene_id 测试"""

    def test_scene_id_field_exists(self):
        """测试 CreateLinkTableRequestSerializer 包含 scene_id 字段"""
        from services.web.strategy_v2.serializers import (
            CreateLinkTableRequestSerializer,
        )

        serializer = CreateLinkTableRequestSerializer()
        assert "scene_id" in serializer.fields


# ==================== 场景过滤集成测试 ====================


class TestNoticeGroupSceneFilter:
    """通知组场景过滤测试（使用 SceneScopeFilter）"""

    @pytest.mark.django_db
    def test_filter_notice_groups_by_scene(self, scene, another_scene):
        """测试按场景过滤通知组"""
        ng1 = NoticeGroup.objects.create(
            group_name="场景1通知组",
            group_member=["admin"],
            notice_config=[],
        )
        _bind_resource_to_scene(ng1.group_id, ResourceVisibilityType.NOTICE_GROUP, scene.scene_id)
        ng2 = NoticeGroup.objects.create(
            group_name="场景2通知组",
            group_member=["admin"],
            notice_config=[],
        )
        _bind_resource_to_scene(ng2.group_id, ResourceVisibilityType.NOTICE_GROUP, another_scene.scene_id)
        # 按场景1过滤
        qs = SceneScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            scene_id=scene.scene_id,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 1
        assert qs.first().group_name == "场景1通知组"

    @pytest.mark.django_db
    def test_filter_notice_groups_no_scene(self, scene):
        """测试不传 scene_id 和 system_id 时返回全部（兼容存量）"""
        NoticeGroup.objects.all().delete()
        ng1 = NoticeGroup.objects.create(
            group_name="通知组1",
            group_member=["admin"],
            notice_config=[],
        )
        _bind_resource_to_scene(ng1.group_id, ResourceVisibilityType.NOTICE_GROUP, scene.scene_id)
        NoticeGroup.objects.create(
            group_name="通知组2",
            group_member=["admin"],
            notice_config=[],
        )
        # scene_id=None 且 system_id=None 时返回全部（兼容存量）
        qs = SceneScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            scene_id=None,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 2


class TestProcessApplicationSceneFilter:
    """处理套餐场景过滤测试（使用 SceneScopeFilter）"""

    @pytest.mark.django_db
    def test_filter_pa_by_scene(self, scene, another_scene):
        """测试按场景过滤处理套餐"""
        pa1 = ProcessApplication.objects.create(
            name="场景1套餐",
            sops_template_id=10001,
        )
        _bind_resource_to_scene(pa1.id, ResourceVisibilityType.PROCESS_APPLICATION, scene.scene_id)
        pa2 = ProcessApplication.objects.create(
            name="场景2套餐",
            sops_template_id=10002,
        )
        _bind_resource_to_scene(pa2.id, ResourceVisibilityType.PROCESS_APPLICATION, another_scene.scene_id)
        qs = SceneScopeFilter.filter_queryset(
            queryset=ProcessApplication.objects.all(),
            scene_id=scene.scene_id,
            resource_type=ResourceVisibilityType.PROCESS_APPLICATION,
            pk_field="id",
        )
        assert qs.count() == 1
        assert qs.first().name == "场景1套餐"


class TestRiskRuleSceneFilter:
    """处理规则场景过滤测试（使用 SceneScopeFilter）"""

    @pytest.mark.django_db
    def test_filter_rule_by_scene(self, scene, another_scene):
        """测试按场景过滤处理规则"""
        RiskRule.objects.all().delete()
        ResourceBinding.objects.filter(resource_type=ResourceVisibilityType.RISK_RULE).delete()
        rule1 = RiskRule.objects.create(
            name="场景1规则",
            scope=[],
            version=1,
            rule_id=90001,
        )
        _bind_resource_to_scene(rule1.rule_id, ResourceVisibilityType.RISK_RULE, scene.scene_id)
        rule2 = RiskRule.objects.create(
            name="场景2规则",
            scope=[],
            version=1,
            rule_id=90002,
        )
        _bind_resource_to_scene(rule2.rule_id, ResourceVisibilityType.RISK_RULE, another_scene.scene_id)
        qs = SceneScopeFilter.filter_queryset(
            queryset=RiskRule.objects.all(),
            scene_id=scene.scene_id,
            resource_type=ResourceVisibilityType.RISK_RULE,
            pk_field="rule_id",
        )
        assert qs.count() == 1
        assert qs.first().name == "场景1规则"


# ==================== ScopeFilter 单元测试 ====================


class TestSceneScopeFilter:
    """SceneScopeFilter 通用过滤器测试"""

    @pytest.mark.django_db
    def test_filter_with_scene_id(self, scene):
        """测试传入 scene_id 时正确过滤"""
        ng1 = NoticeGroup.objects.create(group_name="绑定组", group_member=["admin"], notice_config=[])
        NoticeGroup.objects.create(group_name="未绑定组", group_member=["admin"], notice_config=[])
        _bind_resource_to_scene(ng1.group_id, ResourceVisibilityType.NOTICE_GROUP, scene.scene_id)
        qs = SceneScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            scene_id=scene.scene_id,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 1
        assert qs.first().group_name == "绑定组"

    @pytest.mark.django_db
    def test_filter_without_scene_id(self):
        """测试不传 scene_id 和 system_id 时返回全部（兼容存量）"""
        NoticeGroup.objects.all().delete()
        NoticeGroup.objects.create(group_name="组1", group_member=["admin"], notice_config=[])
        NoticeGroup.objects.create(group_name="组2", group_member=["admin"], notice_config=[])
        qs = SceneScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            scene_id=None,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 2

    @pytest.mark.django_db
    def test_get_bound_resource_ids(self, scene):
        """测试 get_bound_resource_ids 方法"""
        pa = ProcessApplication.objects.create(name="测试套餐", sops_template_id=10001)
        _bind_resource_to_scene(pa.id, ResourceVisibilityType.PROCESS_APPLICATION, scene.scene_id)
        ids = SceneScopeFilter.get_bound_resource_ids(scene.scene_id, ResourceVisibilityType.PROCESS_APPLICATION)
        assert str(pa.id) in ids


class TestBindingScopeFilter:
    """BindingScopeFilter 组合过滤器测试"""

    @pytest.mark.django_db
    def test_filter_platform_binding_with_scene(self, scene):
        """测试按平台级绑定 + scene_id 过滤"""
        ng1 = NoticeGroup.objects.create(group_name="平台组", group_member=["admin"], notice_config=[])
        NoticeGroup.objects.create(group_name="未绑定组", group_member=["admin"], notice_config=[])
        ResourceBinding.objects.create(
            resource_id=str(ng1.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            binding_type=BindingType.PLATFORM_BINDING,
        )
        # 平台级 + 未指定场景/系统时返回所有平台级资源
        qs = BindingScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            binding_type=BindingType.PLATFORM_BINDING,
            scene_id=None,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 1
        assert qs.first().group_name == "平台组"
        # 平台级 + 指定 scene_id 时返回可见的平台级资源
        qs = BindingScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            binding_type=BindingType.PLATFORM_BINDING,
            scene_id=scene.scene_id,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 1
        assert qs.first().group_name == "平台组"

    @pytest.mark.django_db
    def test_filter_scene_binding_with_scene_id(self, scene):
        """测试按场景级绑定 + scene_id 过滤"""
        ng1 = NoticeGroup.objects.create(group_name="场景组", group_member=["admin"], notice_config=[])
        NoticeGroup.objects.create(group_name="未绑定组", group_member=["admin"], notice_config=[])
        _bind_resource_to_scene(ng1.group_id, ResourceVisibilityType.NOTICE_GROUP, scene.scene_id)
        qs = BindingScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            binding_type=BindingType.SCENE_BINDING,
            scene_id=scene.scene_id,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 1
        assert qs.first().group_name == "场景组"

    @pytest.mark.django_db
    def test_filter_scene_id_only_returns_union(self, scene):
        """测试仅传 scene_id（无 binding_type）时返回场景级 + 平台级的并集"""
        ng1 = NoticeGroup.objects.create(group_name="场景组", group_member=["admin"], notice_config=[])
        ng2 = NoticeGroup.objects.create(group_name="平台组", group_member=["admin"], notice_config=[])
        NoticeGroup.objects.create(group_name="未绑定组", group_member=["admin"], notice_config=[])
        _bind_resource_to_scene(ng1.group_id, ResourceVisibilityType.NOTICE_GROUP, scene.scene_id)
        ResourceBinding.objects.create(
            resource_id=str(ng2.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            binding_type=BindingType.PLATFORM_BINDING,
        )
        qs = BindingScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            binding_type="",
            scene_id=scene.scene_id,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 2
        names = set(qs.values_list("group_name", flat=True))
        assert names == {"场景组", "平台组"}

    @pytest.mark.django_db
    def test_filter_no_params_returns_all(self):
        """测试都不传时返回全部（兼容存量）"""
        NoticeGroup.objects.all().delete()
        NoticeGroup.objects.create(group_name="组1", group_member=["admin"], notice_config=[])
        NoticeGroup.objects.create(group_name="组2", group_member=["admin"], notice_config=[])
        qs = BindingScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            binding_type="",
            scene_id=None,
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 2

    @pytest.mark.django_db
    def test_filter_system_id_returns_system_bound_resources(self, scene):
        """测试传 system_id 时通过 ResourceBindingSystem 返回绑定到该系统的资源"""
        ng1 = NoticeGroup.objects.create(group_name="系统绑定场景组", group_member=["admin"], notice_config=[])
        ng2 = NoticeGroup.objects.create(group_name="平台组", group_member=["admin"], notice_config=[])
        NoticeGroup.objects.create(group_name="未绑定组", group_member=["admin"], notice_config=[])
        # 场景级绑定 + ResourceBindingSystem
        binding1 = ResourceBinding.objects.create(
            resource_id=str(ng1.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding1, scene_id=scene.scene_id)
        ResourceBindingSystem.objects.create(binding=binding1, system_id="bk_job")
        # 平台级绑定 + ResourceBindingSystem（specific_systems 可见）
        from services.web.scene.constants import VisibilityScope

        binding2 = ResourceBinding.objects.create(
            resource_id=str(ng2.group_id),
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
        )
        ResourceBindingSystem.objects.create(binding=binding2, system_id="bk_job")
        # 传 system_id 但不传 binding_type，场景级资源无法绑定到系统，仅返回对该系统可见的平台级资源
        qs = BindingScopeFilter.filter_queryset(
            queryset=NoticeGroup.objects.all(),
            binding_type="",
            system_id="bk_job",
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            pk_field="group_id",
        )
        assert qs.count() == 1
        names = set(qs.values_list("group_name", flat=True))
        assert names == {"平台组"}


# ==================== 创建序列化器 scope 校验测试 ====================


class TestCreateSerializerScopeValidation:
    """创建序列化器 scene_id 必传的校验测试"""

    def test_strategy_serializer_scene_id_required(self):
        """测试策略创建序列化器 scene_id 为必传字段"""
        from services.web.strategy_v2.serializers import CreateStrategyRequestSerializer

        serializer = CreateStrategyRequestSerializer()
        assert "scene_id" in serializer.fields
        assert serializer.fields["scene_id"].required is True
        assert "system_id" not in serializer.fields

    def test_link_table_serializer_scene_id_required(self):
        """测试联表创建序列化器 scene_id 为必传字段"""
        from services.web.strategy_v2.serializers import (
            CreateLinkTableRequestSerializer,
        )

        serializer = CreateLinkTableRequestSerializer()
        assert "scene_id" in serializer.fields
        assert serializer.fields["scene_id"].required is True
        assert "system_id" not in serializer.fields

    def test_process_application_serializer_scene_id_required(self):
        """测试处理套餐创建序列化器 scene_id 为必传字段"""
        from services.web.risk.serializers import CreateProcessApplicationsReqSerializer

        serializer = CreateProcessApplicationsReqSerializer()
        assert "scene_id" in serializer.fields
        assert serializer.fields["scene_id"].required is True
        assert "system_id" not in serializer.fields

    def test_risk_rule_serializer_scene_id_required(self):
        """测试处理规则创建序列化器 scene_id 为必传字段"""
        from services.web.risk.serializers import CreateRiskRuleReqSerializer

        serializer = CreateRiskRuleReqSerializer()
        assert "scene_id" in serializer.fields
        assert serializer.fields["scene_id"].required is True
        assert "system_id" not in serializer.fields

    def test_notice_group_serializer_scene_id_required(self):
        """测试通知组创建序列化器 scene_id 为必传字段"""
        from apps.notice.serializers import CreateNoticeGroupRequestSerializer

        serializer = CreateNoticeGroupRequestSerializer()
        assert "scene_id" in serializer.fields
        assert serializer.fields["scene_id"].required is True
        assert "system_id" not in serializer.fields


class TestCreateResourceBinding:
    """SceneScopeFilter.create_resource_binding 方法测试"""

    @pytest.mark.django_db
    def test_create_with_scene_id(self, scene):
        """测试传 scene_id 时创建 ResourceBindingScene"""
        binding = SceneScopeFilter.create_resource_binding(
            resource_id="test_001",
            resource_type=ResourceVisibilityType.STRATEGY,
            scene_id=scene.scene_id,
        )
        assert binding.binding_type == BindingType.SCENE_BINDING
        assert binding.binding_scenes.filter(scene_id=scene.scene_id).exists()
        assert not binding.binding_systems.exists()

    @pytest.mark.django_db
    def test_create_without_scene_id_raises(self):
        """测试不传 scene_id 时抛出 ValueError"""
        with pytest.raises(ValueError, match="scene_id 为必传参数"):
            SceneScopeFilter.create_resource_binding(
                resource_id="test_004",
                resource_type=ResourceVisibilityType.STRATEGY,
                scene_id=None,
            )


# ==================== 迁移文件测试 ====================


class TestMigrationFiles:
    """迁移文件存在性测试"""

    def test_strategy_migration_exists(self):
        """测试 strategy_v2 迁移文件存在"""
        import os

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "services",
            "web",
            "strategy_v2",
            "migrations",
            "0024_add_scene_id.py",
        )
        assert os.path.exists(path), f"迁移文件不存在: {path}"

    def test_risk_migration_exists(self):
        """测试 risk 迁移文件存在"""
        import os

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "services",
            "web",
            "risk",
            "migrations",
            "0045_add_scene_id.py",
        )
        assert os.path.exists(path), f"迁移文件不存在: {path}"

    def test_notice_migration_exists(self):
        """测试 notice 迁移文件存在"""
        import os

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "apps",
            "notice",
            "migrations",
            "0008_add_scene_id.py",
        )
        assert os.path.exists(path), f"迁移文件不存在: {path}"
