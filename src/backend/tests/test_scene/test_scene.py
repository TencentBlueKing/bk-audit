# -*- coding: utf-8 -*-
"""
场景隔离功能单元测试

覆盖：
- 场景 CRUD
- 场景启用/停用
- 场景选择器 & 用户场景列表
- 平台级/场景级报表 CRUD（通过 ResourceBinding 关联）
- 平台级/场景级工具 CRUD（通过 ResourceBinding 关联）
- 资源绑定关系
- 数据过滤规则引擎（ORM Q 对象 & ES DSL）
- 权限校验占位函数
- 菜单 & 权限引导
"""
import json
from unittest import mock

import pytest
from bk_resource import resource
from bk_resource.exceptions import ValidateException
from django.db.models import Q
from django.test import RequestFactory
from django.utils import timezone
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.meta.models import System
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
from services.web.risk.models import Risk
from services.web.scene.constants import (
    BindingType,
    PanelCategory,
    PanelStatus,
    PlatformToolType,
    ResourceScopeType,
    ResourceVisibilityType,
    SceneStatus,
    SceneToolType,
    VisibilityScope,
)
from services.web.scene.data_filter import SceneDataFilter, _parse_list_value
from services.web.scene.exceptions import SceneHasRelatedResources
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
    SceneDataTable,
    SceneSystem,
)
from services.web.scene.views import SceneViewSet
from services.web.strategy_v2.models import Strategy
from services.web.tool.models import Tool
from services.web.vision.constants import ReportGroupType
from services.web.vision.models import SceneReportGroup, VisionPanel
from tests.base import TestCase

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
        name="主机安全审计",
        description="主机安全相关的审计场景",
        status=SceneStatus.ENABLED,
        managers=["admin", "manager1"],
        users=["user1", "user2"],
    )


@pytest.fixture
def scene_with_systems(scene):
    """创建带系统关联的场景"""
    SceneSystem.objects.create(
        scene=scene,
        system_id="bk_cmdb",
        filter_rules=[
            {"field": "extend_data.host.bk_os_type", "operator": "in", "value": "linux,windows"},
        ],
    )
    SceneSystem.objects.create(
        scene=scene,
        system_id="bk_nodeman",
        filter_rules=[
            {"field": "action_id", "operator": "=", "value": "install_agent"},
        ],
    )
    return scene


@pytest.fixture
def scene_with_tables(scene):
    """创建带数据表关联的场景"""
    SceneDataTable.objects.create(
        scene=scene,
        table_id="audit_log_table",
        filter_rules=[
            {"field": "log_level", "operator": "=", "value": "error"},
        ],
    )
    return scene


@pytest.fixture
def platform_panel(db):
    """创建平台级报表（通过 ResourceBinding 关联）"""
    from core.utils.data import unique_id

    panel = VisionPanel.objects.create(
        id=unique_id(),
        name="安全总览报表",
        category=PanelCategory.SECURITY_OVERVIEW,
        description="全局安全总览",
        status=PanelStatus.UNPUBLISHED,
    )
    binding = ResourceBinding.objects.create(  # noqa: F841
        resource_type=ResourceVisibilityType.PANEL,
        resource_id=str(panel.pk),
        binding_type=BindingType.PLATFORM_BINDING,
        visibility_type=VisibilityScope.ALL_VISIBLE,
    )
    return panel


@pytest.fixture
def scene_panel(scene):
    """创建场景级报表（通过 ResourceBinding 关联）"""
    from core.utils.data import unique_id

    panel = VisionPanel.objects.create(
        id=unique_id(),
        name="场景报表",
        category=PanelCategory.BEHAVIOR_ANALYSIS,
        description="场景级报表",
    )
    binding = ResourceBinding.objects.create(
        resource_type=ResourceVisibilityType.PANEL,
        resource_id=str(panel.pk),
        binding_type=BindingType.SCENE_BINDING,
    )
    ResourceBindingScene.objects.create(binding=binding, scene_id=scene.scene_id)
    return panel


@pytest.fixture
def platform_tool(db):
    """创建平台级工具（通过 ResourceBinding 关联）"""
    from core.utils.data import unique_id

    tool = Tool.objects.create(
        name="查询工具",
        uid=unique_id(),
        version=1,
        namespace="default",
        tool_type="data_search",
        config={},
        permission_owner="admin",
        description="平台级查询工具",
        status=PanelStatus.UNPUBLISHED,
    )
    ResourceBinding.objects.create(
        resource_type=ResourceVisibilityType.TOOL,
        resource_id=tool.uid,
        binding_type=BindingType.PLATFORM_BINDING,
        visibility_type=VisibilityScope.ALL_VISIBLE,
    )
    return tool


@pytest.fixture
def scene_tool(scene):
    """创建场景级工具（通过 ResourceBinding 关联）"""
    from core.utils.data import unique_id

    tool = Tool.objects.create(
        name="场景工具",
        uid=unique_id(),
        version=1,
        namespace="default",
        tool_type="data_search",
        config={},
        permission_owner="admin",
        description="场景级工具",
    )
    binding = ResourceBinding.objects.create(
        resource_type=ResourceVisibilityType.TOOL,
        resource_id=tool.uid,
        binding_type=BindingType.SCENE_BINDING,
    )
    ResourceBindingScene.objects.create(binding=binding, scene_id=scene.scene_id)
    return tool


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
    elif method == "patch":
        request = rf.patch(path, data=json.dumps(data or {}), content_type="application/json")
    elif method == "delete":
        request = rf.delete(path)
    else:
        raise ValueError(f"Unsupported method: {method}")
    request.user = user
    # 跳过 CSRF 校验
    request.META["HTTP_X_CSRFTOKEN"] = "test"
    request._dont_enforce_csrf_checks = True
    return request


# ==================== 场景模型测试 ====================


class TestSceneModel:
    """场景模型测试"""

    @pytest.mark.django_db
    def test_create_scene(self):
        """测试创建场景"""
        scene = Scene.objects.create(
            name="测试场景",
            description="测试描述",
            managers=["admin"],
            users=["user1"],
        )
        assert scene.scene_id is not None
        assert scene.name == "测试场景"
        assert scene.status == SceneStatus.ENABLED
        assert scene.managers == ["admin"]
        assert scene.users == ["user1"]

    @pytest.mark.django_db
    def test_scene_str(self, scene):
        """测试场景字符串表示"""
        assert "主机安全审计" in str(scene)

    @pytest.mark.django_db
    def test_scene_ordering(self, db):
        """测试场景排序（按 scene_id 倒序）"""
        Scene.objects.create(name="场景1", managers=["admin"])
        Scene.objects.create(name="场景2", managers=["admin"])
        scenes = list(Scene.objects.all())
        assert scenes[0].scene_id > scenes[1].scene_id

    @pytest.mark.django_db
    def test_scene_default_status(self):
        """测试场景默认状态为启用"""
        scene = Scene.objects.create(name="默认状态场景", managers=["admin"])
        assert scene.status == SceneStatus.ENABLED


class TestSceneSystemModel:
    """场景-系统关联模型测试"""

    @pytest.mark.django_db
    def test_create_scene_system(self, scene):
        """测试创建场景系统关联"""
        ss = SceneSystem.objects.create(
            scene=scene,
            system_id="bk_cmdb",
            filter_rules=[{"field": "action_id", "operator": "=", "value": "view"}],
        )
        assert ss.scene_id == scene.scene_id
        assert ss.system_id == "bk_cmdb"
        assert len(ss.filter_rules) == 1

    @pytest.mark.django_db
    def test_scene_system_unique_together(self, scene):
        """测试场景-系统唯一约束"""
        SceneSystem.objects.create(scene=scene, system_id="bk_cmdb")
        with pytest.raises(Exception):
            SceneSystem.objects.create(scene=scene, system_id="bk_cmdb")

    @pytest.mark.django_db
    def test_scene_system_cascade_delete(self, scene):
        """测试场景删除时级联删除系统关联"""
        SceneSystem.objects.create(scene=scene, system_id="bk_cmdb")
        scene_id = scene.scene_id
        scene.delete()
        assert SceneSystem.objects.filter(scene_id=scene_id).count() == 0


class TestSceneDataTableModel:
    """场景-数据表关联模型测试"""

    @pytest.mark.django_db
    def test_create_scene_data_table(self, scene):
        """测试创建场景数据表关联"""
        sdt = SceneDataTable.objects.create(
            scene=scene,
            table_id="audit_log",
            filter_rules=[{"field": "level", "operator": "=", "value": "error"}],
        )
        assert sdt.scene_id == scene.scene_id
        assert sdt.table_id == "audit_log"

    @pytest.mark.django_db
    def test_scene_data_table_unique_together(self, scene):
        """测试场景-数据表唯一约束"""
        SceneDataTable.objects.create(scene=scene, table_id="audit_log")
        with pytest.raises(Exception):
            SceneDataTable.objects.create(scene=scene, table_id="audit_log")


# ==================== 资源绑定关系测试 ====================


class TestResourceBinding:
    """资源绑定关系测试"""

    @pytest.mark.django_db
    def test_unique_together(self, db):
        """测试资源绑定唯一约束"""
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id="100",
            binding_type=BindingType.PLATFORM_BINDING,
        )
        with pytest.raises(Exception):
            ResourceBinding.objects.create(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id="100",
                binding_type=BindingType.SCENE_BINDING,
            )

    @pytest.mark.django_db
    def test_cascade_delete(self, scene):
        """测试绑定删除时级联删除关联的场景和系统"""
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id="200",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SPECIFIC_SCENES,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=scene.scene_id)
        ResourceBindingSystem.objects.create(binding=binding, system_id="bk_cmdb")
        binding_id = binding.pk
        binding.delete()
        assert ResourceBindingScene.objects.filter(binding_id=binding_id).count() == 0
        assert ResourceBindingSystem.objects.filter(binding_id=binding_id).count() == 0


# ==================== 报表模型测试 ====================


class TestScenePanelModel:
    """场景报表模型测试（通过 ResourceBinding 关联）"""

    @pytest.mark.django_db
    def test_create_platform_panel(self):
        """测试创建平台级报表"""
        from core.utils.data import unique_id

        panel = VisionPanel.objects.create(
            id=unique_id(),
            name="平台报表",
        )
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(panel.pk),
            binding_type=BindingType.PLATFORM_BINDING,
        )
        assert binding.binding_type == BindingType.PLATFORM_BINDING

    @pytest.mark.django_db
    def test_create_scene_panel(self, scene):
        """测试创建场景级报表"""
        from core.utils.data import unique_id

        panel = VisionPanel.objects.create(
            id=unique_id(),
            name="场景报表",
        )
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(panel.pk),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=scene.scene_id)
        assert binding.binding_type == BindingType.SCENE_BINDING
        assert binding.binding_scenes.filter(scene_id=scene.scene_id).exists()


# ==================== 工具模型测试 ====================


class TestSceneToolModel:
    """场景工具模型测试（通过 ResourceBinding 关联）"""

    @pytest.mark.django_db
    def test_create_platform_tool(self):
        """测试创建平台级工具"""
        from core.utils.data import unique_id

        tool = Tool.objects.create(
            name="平台工具",
            uid=unique_id(),
            version=1,
            namespace="default",
            tool_type="data_search",
            config={},
            permission_owner="admin",
        )
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=tool.uid,
            binding_type=BindingType.PLATFORM_BINDING,
        )
        assert binding.binding_type == BindingType.PLATFORM_BINDING

    @pytest.mark.django_db
    def test_create_scene_tool(self, scene):
        """测试创建场景级工具"""
        from core.utils.data import unique_id

        tool = Tool.objects.create(
            name="场景工具",
            uid=unique_id(),
            version=1,
            namespace="default",
            tool_type="data_search",
            config={},
            permission_owner="admin",
        )
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=tool.uid,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=scene.scene_id)
        assert binding.binding_type == BindingType.SCENE_BINDING
        assert binding.binding_scenes.filter(scene_id=scene.scene_id).exists()


# ==================== 数据过滤规则引擎测试 ====================


class TestSceneDataFilter:
    """Django ORM 数据过滤规则引擎测试"""

    @pytest.mark.django_db
    def test_build_filter_empty(self, scene):
        """测试无过滤规则时返回空 Q"""
        q = SceneDataFilter.build_filter(scene.scene_id)
        assert str(q) == str(Q())

    @pytest.mark.django_db
    def test_build_filter_with_system_rules(self, scene_with_systems):
        """测试系统级过滤规则"""
        q = SceneDataFilter.build_filter(scene_with_systems.scene_id)
        assert q is not None
        assert str(q) != str(Q())

    @pytest.mark.django_db
    def test_build_filter_with_table_rules(self, scene_with_tables):
        """测试数据表级过滤规则"""
        q = SceneDataFilter.build_filter(scene_with_tables.scene_id)
        assert q is not None
        assert str(q) != str(Q())

    def test_build_rules_q_equal(self):
        """测试等于操作符"""
        rules = [{"field": "status", "operator": "=", "value": "active"}]
        q = SceneDataFilter._build_rules_q(rules)
        assert q is not None
        assert str(q) == str(Q(status="active"))

    def test_build_rules_q_not_equal(self):
        """测试不等于操作符"""
        rules = [{"field": "status", "operator": "!=", "value": "deleted"}]
        q = SceneDataFilter._build_rules_q(rules)
        assert q is not None
        assert str(q) == str(~Q(status="deleted"))

    def test_build_rules_q_in(self):
        """测试 in 操作符"""
        rules = [{"field": "os_type", "operator": "in", "value": "linux,windows"}]
        q = SceneDataFilter._build_rules_q(rules)
        assert q is not None
        assert str(q) == str(Q(os_type__in=["linux", "windows"]))

    def test_build_rules_q_contains(self):
        """测试 contains 操作符"""
        rules = [{"field": "name", "operator": "contains", "value": "test"}]
        q = SceneDataFilter._build_rules_q(rules)
        assert q is not None
        assert str(q) == str(Q(name__contains="test"))

    def test_build_rules_q_comparison(self):
        """测试比较操作符"""
        rules = [
            {"field": "count", "operator": "gt", "value": 10},
            {"field": "count", "operator": "lt", "value": 100},
        ]
        q = SceneDataFilter._build_rules_q(rules)
        assert q is not None
        expected = Q(count__gt=10) & Q(count__lt=100)
        assert str(q) == str(expected)

    def test_build_rules_q_empty(self):
        """测试空规则"""
        q = SceneDataFilter._build_rules_q([])
        assert q is None

    def test_build_rules_q_invalid_operator(self):
        """测试无效操作符"""
        rules = [{"field": "status", "operator": "invalid_op", "value": "test"}]
        q = SceneDataFilter._build_rules_q(rules)
        assert q is None

    @pytest.mark.django_db
    def test_get_system_ids(self, scene_with_systems):
        """测试获取场景关联系统 ID"""
        system_ids = SceneDataFilter.get_system_ids(scene_with_systems.scene_id)
        assert set(system_ids) == {"bk_cmdb", "bk_nodeman"}

    @pytest.mark.django_db
    def test_get_system_ids_all_systems(self, scene):
        """测试全部系统时返回空列表"""
        SceneSystem.objects.create(scene=scene, system_id="", is_all_systems=True)
        system_ids = SceneDataFilter.get_system_ids(scene.scene_id)
        assert system_ids == []

    @pytest.mark.django_db
    def test_get_table_ids(self, scene_with_tables):
        """测试获取场景关联数据表 ID"""
        table_ids = SceneDataFilter.get_table_ids(scene_with_tables.scene_id)
        assert table_ids == ["audit_log_table"]


class TestParseListValue:
    """_parse_list_value 辅助函数测试"""

    def test_parse_string(self):
        assert _parse_list_value("a,b,c") == ["a", "b", "c"]

    def test_parse_string_with_spaces(self):
        assert _parse_list_value("a, b, c") == ["a", "b", "c"]

    def test_parse_list(self):
        assert _parse_list_value(["a", "b"]) == ["a", "b"]

    def test_parse_single_value(self):
        assert _parse_list_value(42) == ["42"]

    def test_parse_empty_string(self):
        assert _parse_list_value("") == []


# ==================== 场景 ViewSet 测试 ====================


class TestSceneResource(TestCase):
    """场景管理 Resource 测试"""

    def setUp(self):
        super().setUp()
        self.scene = Scene.objects.create(
            name="主机安全审计",
            description="主机安全相关的审计场景",
            status=SceneStatus.ENABLED,
            managers=["admin", "manager1"],
            users=["user1", "user2"],
        )

    def test_scene_list(self):
        """测试场景列表"""
        result = self.resource.scene.list_scene({})
        self.assertGreaterEqual(len(result), 1)

    def test_scene_list_contains_related_strategy_ids_and_risk_count(self):
        """测试场景列表返回关联策略ID和风险数量"""
        strategy = Strategy.objects.create(strategy_name="场景策略")
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=self.scene.scene_id)
        Risk.objects.create(
            raw_event_id="raw-scene-list-1",
            strategy=strategy,
            event_time=timezone.now(),
            event_end_time=timezone.now(),
        )

        result = self.resource.scene.list_scene({})
        target = next(item for item in result if item["scene_id"] == self.scene.scene_id)
        self.assertIn(strategy.strategy_id, target["strategy_ids"])
        self.assertEqual(target["risk_count"], 1)

    def test_scene_list_contains_system_count_and_table_count(self):
        """测试场景列表返回系统和数据表数量"""
        SceneSystem.objects.create(scene=self.scene, system_id="bk_cmdb", is_all_systems=False, filter_rules=[])
        SceneSystem.objects.create(scene=self.scene, system_id="bk_iam", is_all_systems=False, filter_rules=[])
        SceneDataTable.objects.create(scene=self.scene, table_id="table_1", filter_rules=[])

        result = self.resource.scene.list_scene({})
        target = next(item for item in result if item["scene_id"] == self.scene.scene_id)
        self.assertEqual(target["system_count"], 2)
        self.assertEqual(target["table_count"], 1)

    def test_scene_list_ignores_deleted_strategy_binding(self):
        """测试场景列表忽略已删除策略的残留绑定"""
        strategy = Strategy.objects.create(strategy_name="已删除场景策略")
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=self.scene.scene_id)
        strategy.delete()

        result = self.resource.scene.list_scene({})
        target = next(item for item in result if item["scene_id"] == self.scene.scene_id)
        self.assertNotIn(strategy.strategy_id, target["strategy_ids"])
        self.assertEqual(target["risk_count"], 0)

    def test_scene_list_filter_by_status(self):
        """测试按状态过滤场景列表"""
        result = self.resource.scene.list_scene({"status": "enabled"})
        self.assertTrue(all(s["status"] == SceneStatus.ENABLED for s in result))

    def test_scene_list_filter_by_keyword(self):
        """测试按关键词过滤场景列表"""
        result = self.resource.scene.list_scene({"keyword": "主机"})
        self.assertGreaterEqual(len(result), 1)

    def test_scene_list_all(self):
        """测试场景精简列表返回字段"""
        result = self.resource.scene.list_all_scene({})
        self.assertGreaterEqual(len(result), 1)
        self.assertSetEqual(set(result[0].keys()), {"scene_id", "name", "status"})

    def test_scene_list_all_filter_by_status(self):
        """测试场景精简列表支持 status 过滤"""
        Scene.objects.create(name="停用场景", status=SceneStatus.DISABLED, managers=["admin"])
        result = self.resource.scene.list_all_scene({"status": SceneStatus.DISABLED})
        self.assertTrue(result)
        self.assertTrue(all(item["status"] == SceneStatus.DISABLED for item in result))

    def test_scene_retrieve(self):
        """测试场景详情"""
        result = self.resource.scene.retrieve_scene({"scene_id": self.scene.scene_id})
        self.assertEqual(result["name"], "主机安全审计")

    def test_scene_retrieve_contains_related_strategy_ids_and_risk_count(self):
        """测试场景详情返回关联策略ID和风险数量"""
        strategy = Strategy.objects.create(strategy_name="详情场景策略")
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=self.scene.scene_id)
        Risk.objects.create(
            raw_event_id="raw-scene-detail-1",
            strategy=strategy,
            event_time=timezone.now(),
            event_end_time=timezone.now(),
        )

        result = self.resource.scene.retrieve_scene({"scene_id": self.scene.scene_id})
        self.assertEqual(result["strategy_ids"], [strategy.strategy_id])
        self.assertEqual(result["risk_count"], 1)

    def test_create_scene_all_systems_without_system_id(self):
        """创建场景选择全系统时允许不传 system_id"""
        with mock.patch(
            "services.web.scene.resources.IAMGroupManager.create_scene_groups_with_members",
            return_value={"iam_manager_group_id": 1, "iam_viewer_group_id": 2},
        ):
            self.resource.scene.create_scene(
                {"name": "systems-全系统", "managers": ["admin"], "systems": [{"is_all_systems": True}]}
            )

        scene = Scene.objects.get(name="systems-全系统")
        scene_system = SceneSystem.objects.get(scene=scene)
        self.assertEqual(scene_system.system_id, "")
        self.assertTrue(scene_system.is_all_systems)

    def test_create_scene_validate_tables_schema(self):
        """测试创建场景时 tables 子序列化器校验生效"""
        with self.assertRaises(ValidateException):
            self.resource.scene.create_scene(
                {
                    "name": "tables-校验",
                    "managers": ["admin"],
                    "tables": [{"filter_rules": []}],
                }
            )

    def test_scene_retrieve_not_found(self):
        """测试场景不存在"""
        from services.web.scene.exceptions import SceneNotExist

        with self.assertRaises(SceneNotExist):
            self.resource.scene.retrieve_scene({"scene_id": 999999})

    def test_scene_retrieve_with_iam_members(self):
        """测试场景详情 - IAM 成员覆盖"""
        self.scene.iam_manager_group_id = 1001
        self.scene.iam_viewer_group_id = 1002
        self.scene.save(update_fields=["iam_manager_group_id", "iam_viewer_group_id"])

        mock_manager_members = [
            {"type": "user", "id": "iam_admin"},
            {"type": "user", "id": "iam_manager1"},
        ]
        mock_viewer_members = [
            {"type": "user", "id": "iam_user1"},
        ]

        with mock.patch(
            "apps.meta.handlers.iam_group.IAMGroupManager.get_all_group_members",
            side_effect=[mock_manager_members, mock_viewer_members],
        ):
            result = self.resource.scene.retrieve_scene({"scene_id": self.scene.scene_id})
            # 验证返回的是 IAM 实时成员（字符串列表），而非 DB 中的原始值
            self.assertEqual(result["managers"], ["iam_admin", "iam_manager1"])
            self.assertEqual(result["users"], ["iam_user1"])

    def test_scene_info_get_with_iam_members(self):
        """测试获取场景信息 - IAM 成员覆盖"""
        self.scene.iam_manager_group_id = 2001
        self.scene.iam_viewer_group_id = 2002
        self.scene.save(update_fields=["iam_manager_group_id", "iam_viewer_group_id"])

        mock_manager_members = [
            {"type": "user", "id": "scene_admin"},
        ]
        mock_viewer_members = [
            {"type": "user", "id": "scene_user1"},
            {"type": "user", "id": "scene_user2"},
        ]

        with mock.patch(
            "apps.meta.handlers.iam_group.IAMGroupManager.get_all_group_members",
            side_effect=[mock_manager_members, mock_viewer_members],
        ):
            result = self.resource.scene.get_scene_info({"scene_id": self.scene.scene_id})
            self.assertEqual(result["managers"], ["scene_admin"])
            self.assertEqual(result["users"], ["scene_user1", "scene_user2"])

    def test_update_scene_all_systems_without_system_id(self):
        """更新场景选择全系统时允许不传 system_id"""
        self.resource.scene.update_scene({"scene_id": self.scene.scene_id, "systems": [{"is_all_systems": True}]})

        scene_system = SceneSystem.objects.get(scene=self.scene)
        self.assertEqual(scene_system.system_id, "")
        self.assertTrue(scene_system.is_all_systems)

    def test_update_scene_validate_tables_schema(self):
        """测试更新场景时 tables 子序列化器校验生效"""
        with self.assertRaises(ValidateException):
            self.resource.scene.update_scene(
                {
                    "scene_id": self.scene.scene_id,
                    "tables": [{"filter_rules": []}],
                }
            )

    def test_delete_scene_ignores_deleted_strategy_binding(self):
        """测试删除场景时会清理已删除策略的残留绑定"""
        strategy = Strategy.objects.create(strategy_name="待删除策略")
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=self.scene.scene_id)
        strategy.delete()

        result = self.resource.scene.delete_scene({"scene_id": self.scene.scene_id})
        self.assertEqual(result["message"], "success")
        self.assertFalse(Scene.objects.filter(scene_id=self.scene.scene_id).exists())

    def test_delete_scene_reports_related_resource_details(self):
        """测试删除场景存在关联资源时提示资源类型和 ID"""
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            resource_id="1001",
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=self.scene.scene_id)

        with self.assertRaises(SceneHasRelatedResources) as ctx:
            self.resource.scene.delete_scene({"scene_id": self.scene.scene_id})

        self.assertIn("通知组", ctx.exception.message)
        self.assertIn("1001", ctx.exception.message)
        self.assertEqual(
            ctx.exception.data,
            {
                "related_resources": [
                    {
                        "resource_type": ResourceVisibilityType.NOTICE_GROUP,
                        "resource_type_name": "通知组",
                        "resource_id": "1001",
                    }
                ]
            },
        )

    def test_scene_disable(self):
        """测试停用场景"""
        result = self.resource.scene.disable_scene({"scene_id": self.scene.scene_id})
        self.assertEqual(result["status"], SceneStatus.DISABLED)

    def test_scene_enable(self):
        """测试启用场景"""
        self.scene.status = SceneStatus.DISABLED
        self.scene.save()
        result = self.resource.scene.enable_scene({"scene_id": self.scene.scene_id})
        self.assertEqual(result["status"], SceneStatus.ENABLED)

    def test_scene_info_get(self):
        """测试获取场景信息"""
        result = self.resource.scene.get_scene_info({"scene_id": self.scene.scene_id})
        self.assertEqual(result["name"], "主机安全审计")

    def test_scene_info_patch(self):
        """测试编辑场景基础信息"""
        result = self.resource.scene.update_scene_info(
            {
                "scene_id": self.scene.scene_id,
                "name": "修改后的名称",
            }
        )
        self.assertEqual(result["name"], "修改后的名称")


# ==================== 报表 ViewSet 测试 ====================


class TestSceneViewSetPermission(TestCase):
    def test_list_requires_manage_platform(self):
        from apps.permission.handlers.actions import ActionEnum
        from apps.permission.handlers.drf import IAMPermission

        view = SceneViewSet()
        view.action = "list"
        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], IAMPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_PLATFORM])

    def test_list_all_no_permission(self):
        view = SceneViewSet()
        view.action = "all"

        self.assertEqual(view.get_permissions(), [])

    def test_my_role_permissions_no_permission(self):
        view = SceneViewSet()
        view.action = "my_role_permissions"

        self.assertEqual(view.get_permissions(), [])

    def test_info_get_requires_view_scene(self):
        from apps.permission.handlers.actions import ActionEnum
        from apps.permission.handlers.drf import InstanceActionPermission

        view = SceneViewSet()
        view.action = "get_scene_info"
        view.kwargs = {"scene_id": 1001}
        view.request = RequestFactory().get("/api/v1/scenes/1001/info/")
        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.VIEW_SCENE])

    def test_info_patch_requires_manage_scene(self):
        from apps.permission.handlers.actions import ActionEnum
        from apps.permission.handlers.drf import InstanceActionPermission

        view = SceneViewSet()
        view.action = "update_scene_info"
        view.kwargs = {"scene_id": 1001}
        view.request = RequestFactory().patch("/api/v1/scenes/1001/info/")
        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_SCENE])

    def test_resource_routes_have_unique_endpoints(self):
        endpoints = [(route.endpoint, route.pk_field) for route in SceneViewSet.resource_routes if route.endpoint]
        self.assertEqual(len(endpoints), len(set(endpoints)))


class TestGetMyRolePermissions(TestCase):
    def _make_drf_request(self, username="admin"):
        factory = APIRequestFactory()
        django_request = factory.get("/api/v1/scenes/my_role_permissions/")
        django_request.user = MockUser(username)
        return Request(django_request)

    def test_returns_iam_permissions(self):
        drf_request = self._make_drf_request()

        with mock.patch.object(System, "get_managed_system_ids", return_value=[]), mock.patch.object(
            Permission,
            "has_action_any_permission",
            side_effect=lambda action: {
                ActionEnum.MANAGE_PLATFORM: True,
                ActionEnum.MANAGE_SCENE: False,
                ActionEnum.VIEW_SCENE: True,
                ActionEnum.EDIT_SYSTEM: False,
                ActionEnum.VIEW_SYSTEM: True,
            }[action],
        ):
            result = self.resource.scene.get_my_role_permissions.request({}, _request=drf_request)

        self.assertEqual(
            result,
            {
                "manage_platform": True,
                "manage_scene": False,
                "view_scene": True,
                "edit_system": False,
                "view_system": True,
            },
        )

    def test_local_system_manager_grants_system_permissions(self):
        drf_request = self._make_drf_request()

        with mock.patch.object(System, "get_managed_system_ids", return_value=["bk_test"]), mock.patch.object(
            Permission,
            "has_action_any_permission",
            side_effect=lambda action: {
                ActionEnum.MANAGE_PLATFORM: False,
                ActionEnum.MANAGE_SCENE: False,
                ActionEnum.VIEW_SCENE: False,
                ActionEnum.EDIT_SYSTEM: False,
                ActionEnum.VIEW_SYSTEM: False,
            }[action],
        ):
            result = self.resource.scene.get_my_role_permissions.request({}, _request=drf_request)

        self.assertEqual(result["edit_system"], True)
        self.assertEqual(result["view_system"], True)


class TestPanelResources(TestCase):
    """报表 Resource 测试（vision 模块，通过 ResourceBinding 关联）"""

    def setUp(self):
        super().setUp()
        self.scene = Scene.objects.create(
            name="主机安全审计",
            status=SceneStatus.ENABLED,
            managers=["admin"],
        )
        self.another_scene = Scene.objects.create(
            name="容器安全审计",
            status=SceneStatus.ENABLED,
            managers=["admin"],
        )
        from core.utils.data import unique_id

        self.platform_panel = VisionPanel.objects.create(
            id=unique_id(),
            name="安全总览报表",
            category=PanelCategory.SECURITY_OVERVIEW,
            description="全局安全总览",
            status=PanelStatus.UNPUBLISHED,
        )
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(self.platform_panel.pk),
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )

        self.scene_panel = VisionPanel.objects.create(
            id=unique_id(),
            name="场景报表",
            category=PanelCategory.BEHAVIOR_ANALYSIS,
            description="场景级报表",
        )
        scene_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(self.scene_panel.pk),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=scene_binding, scene_id=self.scene.scene_id)

        self.another_scene_panel = VisionPanel.objects.create(
            id=unique_id(),
            name="另一个场景报表",
            category=PanelCategory.ASSET_SECURITY,
            description="另一个场景级报表",
        )
        another_scene_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(self.another_scene_panel.pk),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=another_scene_binding, scene_id=self.another_scene.scene_id)

        self.system_panel = VisionPanel.objects.create(
            id=unique_id(),
            name="系统报表",
            category=PanelCategory.SECURITY_OVERVIEW,
            description="指定系统可见报表",
        )
        system_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(self.system_panel.pk),
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
        )
        ResourceBindingSystem.objects.create(binding=system_binding, system_id="bk_job")
        self.scene_group = SceneReportGroup.objects.create(
            scene=self.scene,
            name="默认分组",
            group_type=ReportGroupType.CUSTOM,
            priority_index=0,
        )

    def _call_list_panels(self, data):
        """调用 list_panels 并 mock ScopePermission，避免真实 IAM 依赖。"""
        from services.web.common.constants import ScopeType
        from services.web.common.scope_permission import ScopePermission

        scope_type = data.get("scope_type")
        scope_id = data.get("scope_id")

        if scope_type == ScopeType.SCENE:
            scene_ids, system_ids = [int(scope_id)], []
        elif scope_type == ScopeType.CROSS_SCENE:
            scene_ids, system_ids = [self.scene.scene_id, self.another_scene.scene_id], []
        elif scope_type == ScopeType.SYSTEM:
            scene_ids, system_ids = [], [scope_id]
        elif scope_type == ScopeType.CROSS_SYSTEM:
            scene_ids, system_ids = [], []
        else:
            scene_ids, system_ids = [], []

        with mock.patch.object(ScopePermission, "get_scene_ids", return_value=scene_ids), mock.patch.object(
            ScopePermission, "get_system_ids", return_value=system_ids
        ):
            return self.resource.vision.list_panels(data)

    def test_panel_list(self):
        """测试报表列表按 scope 返回资源"""
        result = self._call_list_panels({"scope_type": "cross_scene"})
        names = {item["name"] for item in result}
        self.assertEqual(names, {"安全总览报表", "场景报表", "另一个场景报表"})

    def test_panel_list_filter_platform(self):
        """测试按平台级过滤报表"""
        result = self._call_list_panels(
            {
                "scope_type": "cross_scene",
                "binding_type": "platform_binding",
            }
        )
        names = {item["name"] for item in result}
        self.assertEqual(names, {"安全总览报表"})

    def test_panel_list_filter_scene(self):
        """测试按场景过滤报表"""
        result = self._call_list_panels(
            {
                "scope_type": "scene",
                "scope_id": str(self.scene.scene_id),
                "binding_type": "scene_binding",
            }
        )
        panel_ids = [item["id"] for item in result]
        self.assertIn(self.scene_panel.pk, panel_ids)
        self.assertNotIn(self.platform_panel.pk, panel_ids)

    def test_panel_list_filter_scene_with_platform(self):
        """测试 scene scope 不传 binding_type 时返回该场景报表 + 平台级报表"""
        result = self._call_list_panels(
            {
                "scope_type": "scene",
                "scope_id": str(self.scene.scene_id),
            }
        )
        names = [item["name"] for item in result]
        self.assertIn("安全总览报表", names)
        self.assertIn("场景报表", names)

    def test_panel_list_scene_scope_excludes_specific_system_panel(self):
        """测试 scene scope 不应通过场景系统关系返回指定系统可见的平台报表"""
        SceneSystem.objects.create(scene=self.scene, system_id="bk_job")

        result = self._call_list_panels(
            {
                "scope_type": "scene",
                "scope_id": str(self.scene.scene_id),
            }
        )

        names = {item["name"] for item in result}
        self.assertNotIn("系统报表", names)

    def test_panel_list_filter_multiple_scenes(self):
        """测试报表列表支持多场景筛选"""
        result = self._call_list_panels(
            {
                "scope_type": "cross_scene",
                "binding_type": "scene_binding",
            }
        )
        names = {item["name"] for item in result}
        self.assertEqual(names, {"场景报表", "另一个场景报表"})

    def test_panel_list_filter_multiple_scenes_with_platform(self):
        """测试报表列表 cross_scene 时返回场景级与平台级并集"""
        result = self._call_list_panels(
            {
                "scope_type": "cross_scene",
            }
        )
        names = {item["name"] for item in result}
        self.assertEqual(names, {"安全总览报表", "场景报表", "另一个场景报表"})

    def test_panel_list_filter_multiple_systems(self):
        """测试报表列表支持多系统筛选"""
        result = self._call_list_panels(
            {
                "scope_type": "cross_system",
            }
        )
        names = {item["name"] for item in result}
        self.assertEqual(names, set())

    def test_panel_list_no_scope(self):
        """测试不传 scope 参数时校验失败"""
        with self.assertRaises(ValidateException):
            self.resource.vision.list_panels({})

    def test_panel_list_with_scope(self):
        """测试传 scope 参数时按 CompositeScopeFilter 返回场景+平台级报表"""
        result = self._call_list_panels(
            {
                "scope_type": "cross_scene",
            }
        )
        panel_ids = {item["id"] for item in result}
        self.assertEqual(
            panel_ids,
            {
                self.platform_panel.pk,
                self.scene_panel.pk,
                self.another_scene_panel.pk,
            },
        )

    def test_create_platform_panel(self):
        """测试创建平台级报表"""
        data = {
            "name": "新报表",
            "category": PanelCategory.SECURITY_OVERVIEW,
            "description": "新报表描述",
            "visibility": {
                "visibility_type": VisibilityScope.ALL_VISIBLE,
            },
        }
        result = self.resource.vision.create_platform_panel(data)
        self.assertEqual(result["name"], "新报表")
        # 验证 ResourceBinding 已创建
        self.assertTrue(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(result["id"]),
                binding_type=BindingType.PLATFORM_BINDING,
            ).exists()
        )

    def test_create_platform_panel_with_status(self):
        """测试创建平台级报表支持传入上下架状态"""
        result = self.resource.vision.create_platform_panel(
            {
                "name": "已上架报表",
                "status": PanelStatus.PUBLISHED,
            }
        )
        panel = VisionPanel.objects.get(pk=result["id"])
        self.assertEqual(panel.status, PanelStatus.PUBLISHED)

    def test_update_platform_panel(self):
        """测试编辑平台级报表"""
        result = self.resource.vision.update_platform_panel(
            {
                "panel_id": self.platform_panel.pk,
                "name": "更新后的报表",
            }
        )
        self.assertEqual(result["name"], "更新后的报表")

    def test_update_platform_panel_with_status(self):
        """测试编辑平台级报表支持传入上下架状态"""
        self.resource.vision.update_platform_panel(
            {
                "panel_id": self.platform_panel.pk,
                "status": PanelStatus.PUBLISHED,
            }
        )
        self.platform_panel.refresh_from_db()
        self.assertEqual(self.platform_panel.status, PanelStatus.PUBLISHED)

    def test_create_platform_panel_specific_scenes_without_scene_ids_raise(self):
        """测试平台级报表 specific_scenes 未传 scene_ids 时校验失败"""
        with self.assertRaises(ValidateException):
            self.resource.vision.create_platform_panel(
                {
                    "name": "非法报表",
                    "visibility": {
                        "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    },
                }
            )

    def test_update_platform_panel_specific_systems_without_system_ids_raise(self):
        """测试平台级报表 specific_systems 未传 system_ids 时校验失败"""
        with self.assertRaises(ValidateException):
            self.resource.vision.update_platform_panel(
                {
                    "panel_id": self.platform_panel.pk,
                    "visibility": {
                        "visibility_type": VisibilityScope.SPECIFIC_SYSTEMS,
                    },
                }
            )

    def test_delete_platform_panel(self):
        """测试删除平台级报表"""
        pk = self.platform_panel.pk
        self.resource.vision.delete_platform_panel({"panel_id": pk})
        self.assertFalse(VisionPanel.objects.filter(pk=pk).exists())
        # 验证 ResourceBinding 也被删除
        self.assertFalse(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(pk),
            ).exists()
        )

    def test_delete_published_platform_panel(self):
        """测试删除已上架的平台级报表（应失败）"""
        from services.web.vision.exceptions import ScenePanelCannotDelete

        self.platform_panel.status = PanelStatus.PUBLISHED
        self.platform_panel.save()
        with self.assertRaises(ScenePanelCannotDelete):
            self.resource.vision.delete_platform_panel({"panel_id": self.platform_panel.pk})
        self.assertTrue(VisionPanel.objects.filter(pk=self.platform_panel.pk).exists())

    def test_publish_platform_panel(self):
        """测试上架/下架平台级报表"""
        # 上架
        result = self.resource.vision.publish_platform_panel({"panel_id": self.platform_panel.pk})
        self.assertEqual(result["status"], PanelStatus.PUBLISHED)
        # 下架
        result = self.resource.vision.publish_platform_panel({"panel_id": self.platform_panel.pk})
        self.assertEqual(result["status"], PanelStatus.UNPUBLISHED)

    def test_publish_platform_panel_with_status(self):
        """测试平台级报表支持显式传入上下架状态"""
        result = self.resource.vision.publish_platform_panel(
            {"panel_id": self.platform_panel.pk, "status": PanelStatus.UNPUBLISHED}
        )
        self.assertEqual(result["status"], PanelStatus.UNPUBLISHED)

    def test_publish_scene_panel_with_int_scene_id_and_status(self):
        """测试场景级报表上下架支持整型 scene_id 和显式状态"""
        result = self.resource.vision.publish_scene_panel(
            {
                "scene_id": self.scene.scene_id,
                "panel_id": self.scene_panel.pk,
                "status": PanelStatus.UNPUBLISHED,
            }
        )
        self.assertEqual(result["status"], PanelStatus.UNPUBLISHED)

    def test_scene_panel_publish_serializer_scene_id_is_required_int(self):
        """测试场景级报表上下架请求的 scene_id 为必填整数"""
        from services.web.vision.serializers import ScenePanelOperateRequestSerializer

        field = ScenePanelOperateRequestSerializer().fields["scene_id"]
        self.assertIsInstance(field, serializers.IntegerField)
        self.assertTrue(field.required)

    def test_create_scene_panel(self):
        """测试创建场景级报表"""
        result = self.resource.vision.create_scene_panel(
            {
                "scene_id": self.scene.scene_id,
                "group_id": self.scene_group.id,
                "name": "新场景报表",
                "category": PanelCategory.BEHAVIOR_ANALYSIS,
                "status": PanelStatus.PUBLISHED,
            }
        )
        self.assertEqual(result["name"], "新场景报表")
        # 验证 ResourceBinding 已创建
        binding = ResourceBinding.objects.get(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(result["id"]),
        )
        panel = VisionPanel.objects.get(pk=result["id"])
        self.assertEqual(binding.binding_type, BindingType.SCENE_BINDING)
        self.assertTrue(binding.binding_scenes.filter(scene_id=self.scene.scene_id).exists())
        self.assertEqual(panel.status, PanelStatus.PUBLISHED)

    def test_update_scene_panel(self):
        """测试编辑场景级报表"""
        result = self.resource.vision.update_scene_panel(
            {
                "scene_id": self.scene.scene_id,
                "group_id": self.scene_group.id,
                "panel_id": self.scene_panel.pk,
                "name": "更新后的场景报表",
                "status": PanelStatus.PUBLISHED,
            }
        )
        self.assertEqual(result["name"], "更新后的场景报表")
        self.scene_panel.refresh_from_db()
        self.assertEqual(self.scene_panel.status, PanelStatus.PUBLISHED)

    def test_delete_scene_panel(self):
        """测试删除场景级报表"""
        pk = self.scene_panel.pk
        self.resource.vision.delete_scene_panel({"scene_id": self.scene.scene_id, "panel_id": pk})
        self.assertFalse(VisionPanel.objects.filter(pk=pk).exists())
        # 验证 ResourceBinding 也被删除
        self.assertFalse(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(pk),
            ).exists()
        )


# ==================== 工具 ViewSet 测试 ====================


class TestToolResources(TestCase):
    """工具 Resource 测试（tool 模块，通过 ResourceBinding 关联）"""

    def setUp(self):
        super().setUp()
        self.scene = Scene.objects.create(
            name="主机安全审计",
            status=SceneStatus.ENABLED,
            managers=["admin"],
        )
        self.another_scene = Scene.objects.create(
            name="容器安全审计",
            status=SceneStatus.ENABLED,
            managers=["admin"],
        )
        from core.utils.data import unique_id

        self.platform_tool = Tool.objects.create(
            name="查询工具",
            uid=unique_id(),
            version=1,
            namespace="default",
            tool_type="data_search",
            config={},
            permission_owner="admin",
            description="平台级查询工具",
            status=PanelStatus.UNPUBLISHED,
        )
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=self.platform_tool.uid,
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )

        self.scene_tool = Tool.objects.create(
            name="场景工具",
            uid=unique_id(),
            version=1,
            namespace="default",
            tool_type="data_search",
            config={},
            permission_owner="admin",
            description="场景级工具",
        )
        scene_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=self.scene_tool.uid,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=scene_binding, scene_id=self.scene.scene_id)

        self.another_scene_tool = Tool.objects.create(
            name="另一个场景工具",
            uid=unique_id(),
            version=1,
            namespace="default",
            tool_type="data_search",
            config={},
            permission_owner="admin",
            description="另一个场景级工具",
        )
        another_scene_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=self.another_scene_tool.uid,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=another_scene_binding, scene_id=self.another_scene.scene_id)

        self.system_tool = Tool.objects.create(
            name="系统工具",
            uid=unique_id(),
            version=1,
            namespace="default",
            tool_type="data_search",
            config={},
            permission_owner="admin",
            description="指定系统可见工具",
        )
        system_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=self.system_tool.uid,
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
        )
        ResourceBindingSystem.objects.create(binding=system_binding, system_id="bk_job")

        self.resource = resource

    def _call_list_tool(self, data):
        """调用 ListTool Resource（需要 mock request 和权限）"""
        from unittest.mock import patch

        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from services.web.common.constants import ScopeType
        from services.web.common.scope_permission import ScopePermission
        from services.web.tool.resources import ListTool

        scope_type = data.get("scope_type")
        scope_id = data.get("scope_id")

        if scope_type == ScopeType.SCENE:
            scene_ids, system_ids = [int(scope_id)], []
        elif scope_type == ScopeType.CROSS_SCENE:
            scene_ids, system_ids = [self.scene.scene_id, self.another_scene.scene_id], []
        elif scope_type == ScopeType.SYSTEM:
            scene_ids, system_ids = [], [scope_id]
        elif scope_type == ScopeType.CROSS_SYSTEM:
            scene_ids, system_ids = [], ["bk_job", "bk_cmdb"]
        else:
            scene_ids, system_ids = [], []

        factory = APIRequestFactory()
        django_request = factory.get('/fake-url/', data, format='json')
        drf_request = Request(django_request)

        with patch.object(ScopePermission, "get_scene_ids", return_value=scene_ids), patch.object(
            ScopePermission, "get_system_ids", return_value=system_ids
        ):
            res = ListTool()
            response = res.request(data, _request=drf_request)
            return response.data.get("results", [])

    def test_tool_list(self):
        """测试跨场景视角返回场景工具与平台工具并集"""
        result = self._call_list_tool({"scope_type": "cross_scene", "page": 1, "page_size": 10})
        names = {item["name"] for item in result}
        self.assertEqual(names, {"查询工具", "场景工具", "另一个场景工具"})

    def test_tool_list_filter_platform(self):
        """测试跨场景视角按平台级过滤"""
        result = self._call_list_tool(
            {"scope_type": "cross_scene", "binding_type": "platform_binding", "page": 1, "page_size": 10}
        )
        names = {item["name"] for item in result}
        self.assertEqual(names, {"查询工具"})

    def test_tool_list_filter_scene(self):
        """测试单场景视角按场景级过滤工具"""
        result = self._call_list_tool(
            {
                "scope_type": "scene",
                "scope_id": str(self.scene.scene_id),
                "binding_type": "scene_binding",
                "page": 1,
                "page_size": 10,
            }
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "场景工具")

    def test_tool_detail(self):
        """测试工具详情"""
        result = self.resource.tool.get_tool_detail({"uid": self.platform_tool.uid})
        self.assertEqual(result["name"], "查询工具")

    def test_tool_detail_not_found(self):
        """测试工具不存在"""
        from services.web.tool.exceptions import ToolDoesNotExist

        with self.assertRaises(ToolDoesNotExist):
            self.resource.tool.get_tool_detail({"uid": "nonexistent_uid"})

    def test_tool_list_filter_scene_with_platform(self):
        """测试单场景视角不传 binding_type 时返回场景级 + 平台级工具"""
        result = self._call_list_tool(
            {"scope_type": "scene", "scope_id": str(self.scene.scene_id), "page": 1, "page_size": 10}
        )
        tool_names = [item["name"] for item in result]
        self.assertIn("查询工具", tool_names)  # 平台级
        self.assertIn("场景工具", tool_names)  # 场景级
        self.assertEqual(len(result), 2)

    def test_tool_list_scene_scope_excludes_specific_system_tool(self):
        """测试 scene scope 不应通过场景系统关系返回指定系统可见的平台工具"""
        SceneSystem.objects.create(scene=self.scene, system_id="bk_job")

        result = self._call_list_tool(
            {"scope_type": "scene", "scope_id": str(self.scene.scene_id), "page": 1, "page_size": 10}
        )

        names = {item["name"] for item in result}
        self.assertNotIn("系统工具", names)

    def test_tool_list_filter_multiple_scenes(self):
        """测试跨场景视角按场景级过滤"""
        result = self._call_list_tool(
            {
                "scope_type": "cross_scene",
                "binding_type": "scene_binding",
                "page": 1,
                "page_size": 10,
            }
        )
        names = {item["name"] for item in result}
        self.assertEqual(names, {"场景工具", "另一个场景工具"})

    def test_tool_list_filter_multiple_scenes_with_platform(self):
        """测试跨场景视角返回场景级与平台级并集"""
        result = self._call_list_tool(
            {
                "scope_type": "cross_scene",
                "page": 1,
                "page_size": 10,
            }
        )
        names = {item["name"] for item in result}
        self.assertEqual(names, {"查询工具", "场景工具", "另一个场景工具"})

    def test_tool_list_filter_multiple_systems(self):
        """测试跨系统视角支持系统可见工具"""
        result = self._call_list_tool(
            {
                "scope_type": "cross_system",
                "page": 1,
                "page_size": 10,
            }
        )
        names = {item["name"] for item in result}
        self.assertEqual(names, {"查询工具", "系统工具"})

    def test_create_platform_tool(self):
        """测试创建平台级工具"""
        data = {
            "name": "新工具",
            "tool_type": "data_search",
            "description": "新工具描述",
            "tags": ["测试"],
            "status": PanelStatus.PUBLISHED,
            "data_search_config_type": "sql",
            "config": {
                "sql": "SELECT * FROM test_table",
                "referenced_tables": [{"table_name": "test_table"}],
                "input_variable": [],
                "output_fields": [],
            },
        }
        result = self.resource.tool.create_platform_scene_tool(data)
        tool = Tool.last_version_tool(result["uid"])
        # 验证 ResourceBinding 已创建
        self.assertTrue(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=result["uid"],
                binding_type=BindingType.PLATFORM_BINDING,
            ).exists()
        )
        self.assertEqual(tool.status, PanelStatus.PUBLISHED)

    def test_update_platform_tool(self):
        """测试编辑平台级工具"""
        self.resource.tool.update_platform_scene_tool(
            {
                "uid": self.platform_tool.uid,
                "name": "更新后的工具",
                "tags": ["测试"],
                "status": PanelStatus.PUBLISHED,
            }
        )
        updated_tool = Tool.last_version_tool(self.platform_tool.uid)
        self.assertEqual(updated_tool.name, "更新后的工具")
        self.assertEqual(updated_tool.status, PanelStatus.PUBLISHED)

    def test_create_platform_tool_specific_scenes_without_scene_ids_raise(self):
        """测试平台级工具 specific_scenes 未传 scene_ids 时校验失败"""
        with self.assertRaises(ValidateException):
            self.resource.tool.create_platform_scene_tool(
                {
                    "name": "非法工具",
                    "tool_type": "data_search",
                    "tags": ["测试"],
                    "data_search_config_type": "sql",
                    "config": {
                        "sql": "SELECT * FROM test_table",
                        "referenced_tables": [{"table_name": "test_table"}],
                        "input_variable": [],
                        "output_fields": [],
                    },
                    "visibility": {
                        "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                    },
                }
            )

    def test_update_platform_tool_specific_systems_without_system_ids_raise(self):
        """测试平台级工具 specific_systems 未传 system_ids 时校验失败"""
        with self.assertRaises(ValidateException):
            self.resource.tool.update_platform_scene_tool(
                {
                    "uid": self.platform_tool.uid,
                    "tags": ["测试"],
                    "visibility": {
                        "visibility_type": VisibilityScope.SPECIFIC_SYSTEMS,
                    },
                }
            )

    def test_delete_platform_tool(self):
        """测试删除平台级工具"""
        uid = self.platform_tool.uid
        self.resource.tool.delete_platform_scene_tool({"uid": uid})
        self.assertIsNone(Tool.last_version_tool(uid))
        # 验证 ResourceBinding 也被删除
        self.assertFalse(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=uid,
            ).exists()
        )

    def test_delete_published_platform_tool(self):
        """测试删除已上架的平台级工具（应失败）"""
        from services.web.tool.exceptions import SceneToolCannotDelete

        self.platform_tool.status = PanelStatus.PUBLISHED
        self.platform_tool.save()
        with self.assertRaises(SceneToolCannotDelete):
            self.resource.tool.delete_platform_scene_tool({"uid": self.platform_tool.uid})
        self.assertIsNotNone(Tool.last_version_tool(self.platform_tool.uid))

    def test_publish_platform_tool(self):
        """测试上架/下架平台级工具"""
        self.resource.tool.publish_platform_scene_tool({"uid": self.platform_tool.uid})
        updated_tool = Tool.last_version_tool(self.platform_tool.uid)
        self.assertEqual(updated_tool.status, PanelStatus.PUBLISHED)

    def test_publish_platform_tool_with_status(self):
        """测试平台级工具支持显式传入上下架状态"""
        self.resource.tool.publish_platform_scene_tool(
            {"uid": self.platform_tool.uid, "status": PanelStatus.UNPUBLISHED}
        )
        updated_tool = Tool.last_version_tool(self.platform_tool.uid)
        self.assertEqual(updated_tool.status, PanelStatus.UNPUBLISHED)

    def test_publish_scene_tool(self):
        """测试上架/下架场景级工具"""
        self.resource.tool.publish_scene_scope_tool({"scene_id": self.scene.scene_id, "uid": self.scene_tool.uid})
        updated_tool = Tool.last_version_tool(self.scene_tool.uid)
        self.assertEqual(updated_tool.status, PanelStatus.PUBLISHED)

        self.resource.tool.publish_scene_scope_tool({"scene_id": self.scene.scene_id, "uid": self.scene_tool.uid})
        updated_tool = Tool.last_version_tool(self.scene_tool.uid)
        self.assertEqual(updated_tool.status, PanelStatus.UNPUBLISHED)

    def test_publish_scene_tool_with_int_scene_id_and_status(self):
        """测试场景级工具上下架支持整型 scene_id 和显式状态"""
        self.resource.tool.publish_scene_scope_tool(
            {
                "scene_id": self.scene.scene_id,
                "uid": self.scene_tool.uid,
                "status": PanelStatus.UNPUBLISHED,
            }
        )
        updated_tool = Tool.last_version_tool(self.scene_tool.uid)
        self.assertEqual(updated_tool.status, PanelStatus.UNPUBLISHED)

    def test_publish_scene_tool_request_serializes_response(self):
        """测试场景级工具上下架接口响应可被序列化"""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from services.web.tool.resources import PublishSceneScopeTool

        data = {"scene_id": self.scene.scene_id, "uid": self.scene_tool.uid}
        factory = APIRequestFactory()
        django_request = factory.post("/api/v1/tool/scene/publish/", data, format="json")
        drf_request = Request(django_request)

        response_data = PublishSceneScopeTool().request(data, _request=drf_request)

        self.assertEqual(
            response_data,
            {
                "uid": self.scene_tool.uid,
                "name": self.scene_tool.name,
                "status": PanelStatus.PUBLISHED,
            },
        )

    def test_scene_tool_publish_serializer_scene_id_is_required_int(self):
        """测试场景级工具上下架请求的 scene_id 为必填整数"""
        from services.web.tool.serializers import SceneScopeToolPublishRequestSerializer

        field = SceneScopeToolPublishRequestSerializer().fields["scene_id"]
        self.assertIsInstance(field, serializers.IntegerField)
        self.assertTrue(field.required)

    def test_publish_scene_tool_not_exist(self):
        """测试上架/下架非本场景工具（应失败）"""
        from services.web.tool.exceptions import SceneToolNotExist

        with self.assertRaises(SceneToolNotExist):
            self.resource.tool.publish_scene_scope_tool(
                {"scene_id": self.scene.scene_id, "uid": self.another_scene_tool.uid}
            )

    def test_create_scene_tool(self):
        """测试创建场景级工具"""
        result = self.resource.tool.create_scene_scope_tool(
            {
                "scene_id": self.scene.scene_id,
                "name": "新场景工具",
                "tool_type": "data_search",
                "tags": ["安全"],
                "status": PanelStatus.PUBLISHED,
                "data_search_config_type": "sql",
                "config": {
                    "sql": "SELECT * FROM test_table",
                    "referenced_tables": [{"table_name": "test_table"}],
                    "input_variable": [],
                    "output_fields": [],
                },
            }
        )
        # 验证 ResourceBinding 已创建
        binding = ResourceBinding.objects.get(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=result["uid"],
        )
        tool = Tool.last_version_tool(result["uid"])
        self.assertEqual(binding.binding_type, BindingType.SCENE_BINDING)
        self.assertTrue(binding.binding_scenes.filter(scene_id=self.scene.scene_id).exists())
        self.assertEqual(tool.status, PanelStatus.PUBLISHED)

    def test_update_scene_tool(self):
        """测试编辑场景级工具"""
        self.resource.tool.update_scene_scope_tool(
            {
                "scene_id": self.scene.scene_id,
                "uid": self.scene_tool.uid,
                "name": "更新后的场景工具",
                "tags": ["安全"],
                "status": PanelStatus.PUBLISHED,
            }
        )
        updated_tool = Tool.last_version_tool(self.scene_tool.uid)
        self.assertEqual(updated_tool.name, "更新后的场景工具")
        self.assertEqual(updated_tool.status, PanelStatus.PUBLISHED)

    def test_delete_scene_tool(self):
        """测试删除场景级工具"""
        uid = self.scene_tool.uid
        self.resource.tool.delete_scene_scope_tool({"scene_id": self.scene.scene_id, "uid": uid})
        self.assertIsNone(Tool.last_version_tool(uid))
        # 验证 ResourceBinding 也被删除
        self.assertFalse(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=uid,
            ).exists()
        )


# ==================== 常量测试 ====================


class TestConstants:
    """常量枚举测试"""

    def test_scene_status_choices(self):
        assert SceneStatus.ENABLED == "enabled"
        assert SceneStatus.DISABLED == "disabled"

    def test_visibility_scope_choices(self):
        assert VisibilityScope.ALL_VISIBLE == "all_visible"
        assert VisibilityScope.ALL_SYSTEMS == "all_systems"
        assert VisibilityScope.SPECIFIC_SCENES == "specific_scenes"

    def test_resource_scope_type_choices(self):
        assert ResourceScopeType.PLATFORM == "platform"
        assert ResourceScopeType.SCENE == "scene"

    def test_binding_type_choices(self):
        assert BindingType.SCENE_BINDING == "scene_binding"
        assert BindingType.PLATFORM_BINDING == "platform_binding"

    def test_panel_category_choices(self):
        assert len(PanelCategory.choices) == 8

    def test_platform_tool_type_choices(self):
        assert len(PlatformToolType.choices) == 4

    def test_scene_tool_type_choices(self):
        assert len(SceneToolType.choices) == 4
