# -*- coding: utf-8 -*-
"""
场景隔离功能单元测试

覆盖：
- 场景 CRUD
- 场景启用/停用
- 场景选择器 & 用户场景列表
- 平台级/场景级报表 CRUD
- 平台级/场景级工具 CRUD
- 资源可见范围
- 数据过滤规则引擎（ORM Q 对象 & ES DSL）
- 权限校验占位函数
- 菜单 & 权限引导
"""
import json

import pytest
from bk_resource import resource
from django.db.models import Q
from django.test import RequestFactory

from services.web.scene.constants import (
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
from services.web.scene.models import (
    ResourceVisibility,
    Scene,
    SceneDataTable,
    SceneSystem,
)
from services.web.scene.permissions import check_scene_permission
from services.web.tool.models import Tool
from services.web.vision.models import VisionPanel
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
    """创建平台级报表"""
    from core.utils.data import unique_id

    return VisionPanel.objects.create(
        id=unique_id(),
        name="安全总览报表",
        category=PanelCategory.SECURITY_OVERVIEW,
        description="全局安全总览",
        status=PanelStatus.UNPUBLISHED,
        scope_type=ResourceScopeType.PLATFORM,
    )


@pytest.fixture
def scene_panel(scene):
    """创建场景级报表"""
    from core.utils.data import unique_id

    return VisionPanel.objects.create(
        id=unique_id(),
        name="场景报表",
        category=PanelCategory.BEHAVIOR_ANALYSIS,
        description="场景级报表",
        scope_type=ResourceScopeType.SCENE,
        scene_id=scene.scene_id,
    )


@pytest.fixture
def platform_tool(db):
    """创建平台级工具"""
    from core.utils.data import unique_id

    return Tool.objects.create(
        name="查询工具",
        uid=unique_id(),
        version=1,
        namespace="default",
        tool_type="data_search",
        config={},
        permission_owner="admin",
        description="平台级查询工具",
        status=PanelStatus.UNPUBLISHED,
        scope_type=ResourceScopeType.PLATFORM,
    )


@pytest.fixture
def scene_tool(scene):
    """创建场景级工具"""
    from core.utils.data import unique_id

    return Tool.objects.create(
        name="场景工具",
        uid=unique_id(),
        version=1,
        namespace="default",
        tool_type="data_search",
        config={},
        permission_owner="admin",
        description="场景级工具",
        scope_type=ResourceScopeType.SCENE,
        scene_id=scene.scene_id,
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


# ==================== 资源可见范围测试 ====================


class TestResourceVisibility:
    """资源可见范围测试"""

    @pytest.mark.django_db
    def test_all_visible(self, scene):
        """测试全部可见"""
        rv = ResourceVisibility.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id="1",
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )
        assert rv.is_visible_to_scene(scene.scene_id) is True

    @pytest.mark.django_db
    def test_all_scenes(self, scene):
        """测试全部场景可见"""
        rv = ResourceVisibility.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id="2",
            visibility_type=VisibilityScope.ALL_SCENES,
        )
        assert rv.is_visible_to_scene(scene.scene_id) is True

    @pytest.mark.django_db
    def test_specific_scenes_visible(self, scene):
        """测试指定场景可见"""
        rv = ResourceVisibility.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id="3",
            visibility_type=VisibilityScope.SPECIFIC_SCENES,
            scene_ids=[scene.scene_id],
        )
        assert rv.is_visible_to_scene(scene.scene_id) is True

    @pytest.mark.django_db
    def test_specific_scenes_not_visible(self, scene):
        """测试指定场景不可见"""
        rv = ResourceVisibility.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id="4",
            visibility_type=VisibilityScope.SPECIFIC_SCENES,
            scene_ids=[999999],
        )
        assert rv.is_visible_to_scene(scene.scene_id) is False

    @pytest.mark.django_db
    def test_specific_systems_visible(self, scene_with_systems):
        """测试指定系统可见"""
        rv = ResourceVisibility.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id="5",
            visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
            system_ids=["bk_cmdb"],
        )
        assert rv.is_visible_to_scene(scene_with_systems.scene_id) is True

    @pytest.mark.django_db
    def test_specific_systems_not_visible(self, scene_with_systems):
        """测试指定系统不可见"""
        rv = ResourceVisibility.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id="6",
            visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
            system_ids=["unknown_system"],
        )
        assert rv.is_visible_to_scene(scene_with_systems.scene_id) is False

    @pytest.mark.django_db
    def test_unique_together(self, db):
        """测试资源可见范围唯一约束"""
        ResourceVisibility.objects.create(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id="100",
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )
        with pytest.raises(Exception):
            ResourceVisibility.objects.create(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id="100",
                visibility_type=VisibilityScope.ALL_SCENES,
            )


# ==================== 报表模型测试 ====================


class TestScenePanelModel:
    """场景报表模型测试（复用 VisionPanel 模型）"""

    @pytest.mark.django_db
    def test_create_platform_panel(self):
        """测试创建平台级报表"""
        from core.utils.data import unique_id

        panel = VisionPanel.objects.create(
            id=unique_id(),
            name="平台报表",
            scope_type=ResourceScopeType.PLATFORM,
        )
        assert panel.scope_type == ResourceScopeType.PLATFORM
        assert panel.scene_id is None

    @pytest.mark.django_db
    def test_create_scene_panel(self, scene):
        """测试创建场景级报表"""
        from core.utils.data import unique_id

        panel = VisionPanel.objects.create(
            id=unique_id(),
            name="场景报表",
            scope_type=ResourceScopeType.SCENE,
            scene_id=scene.scene_id,
        )
        assert panel.scope_type == ResourceScopeType.SCENE
        assert panel.scene_id == scene.scene_id


# ==================== 工具模型测试 ====================


class TestSceneToolModel:
    """场景工具模型测试（复用 Tool 模型）"""

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
            scope_type=ResourceScopeType.PLATFORM,
        )
        assert tool.scope_type == ResourceScopeType.PLATFORM
        assert tool.scene_id is None

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
            scope_type=ResourceScopeType.SCENE,
            scene_id=scene.scene_id,
        )
        assert tool.scope_type == ResourceScopeType.SCENE
        assert tool.scene_id == scene.scene_id


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


# ==================== 权限校验测试 ====================


class TestCheckScenePermission:
    """权限校验占位函数测试"""

    def test_check_scene_permission_pass(self, rf):
        """测试权限校验占位函数不抛异常（空实现）"""
        request = rf.get("/")
        request.user = MockUser("admin")
        check_scene_permission(request, 100001, require_role="user")
        check_scene_permission(request, 100001, require_role="manager")
        check_scene_permission(request, 100001, require_role="admin")


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

    def test_scene_list_filter_by_status(self):
        """测试按状态过滤场景列表"""
        result = self.resource.scene.list_scene({"status": "enabled"})
        self.assertTrue(all(s["status"] == SceneStatus.ENABLED for s in result))

    def test_scene_list_filter_by_keyword(self):
        """测试按关键词过滤场景列表"""
        result = self.resource.scene.list_scene({"keyword": "主机"})
        self.assertGreaterEqual(len(result), 1)

    def test_scene_retrieve(self):
        """测试场景详情"""
        result = self.resource.scene.retrieve_scene({"scene_id": self.scene.scene_id})
        self.assertEqual(result["name"], "主机安全审计")

    def test_scene_retrieve_not_found(self):
        """测试场景不存在"""
        from services.web.scene.exceptions import SceneNotExist

        with self.assertRaises(SceneNotExist):
            self.resource.scene.retrieve_scene({"scene_id": 999999})

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

    def test_scene_my_scenes(self):
        """测试用户场景列表"""
        result = self.resource.scene.list_my_scenes({})
        # 注意：perform_request 中使用 get_request_username()，在测试环境中可能返回空
        # 这里只验证不抛异常
        self.assertIsInstance(result, list)

    def test_scene_selector(self):
        """测试场景选择器"""
        result = self.resource.scene.get_scene_selector({})
        self.assertIn("scenes", result)


# ==================== 报表 ViewSet 测试 ====================


class TestPanelResources(TestCase):
    """报表 Resource 测试（vision 模块）"""

    def setUp(self):
        super().setUp()
        self.scene = Scene.objects.create(
            name="主机安全审计",
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
            scope_type=ResourceScopeType.PLATFORM,
        )
        self.scene_panel = VisionPanel.objects.create(
            id=unique_id(),
            name="场景报表",
            category=PanelCategory.BEHAVIOR_ANALYSIS,
            description="场景级报表",
            scope_type=ResourceScopeType.SCENE,
            scene_id=self.scene.scene_id,
        )

    def test_panel_list(self):
        """测试报表列表（通过 scope 过滤）"""
        result = self.resource.vision.list_panels({"scenario": "default", "scope_type": "platform"})
        platform_names = [item["name"] for item in result]
        self.assertIn("安全总览报表", platform_names)

    def test_panel_list_filter_platform(self):
        """测试按平台级过滤报表"""
        result = self.resource.vision.list_panels({"scenario": "default", "scope_type": "platform"})
        for item in result:
            self.assertEqual(item["scope_type"], "platform")

    def test_panel_list_filter_scene(self):
        """测试按场景过滤报表"""
        result = self.resource.vision.list_panels(
            {
                "scenario": "default",
                "scope_type": "scene",
                "scene_id": self.scene.scene_id,
            }
        )
        for item in result:
            self.assertEqual(item["scope_type"], "scene")
            self.assertEqual(item["scene_id"], self.scene.scene_id)

    def test_panel_list_filter_scene_with_platform(self):
        """测试传 scene_id 但不传 scope_type，应返回该场景报表 + 平台级报表"""
        result = self.resource.vision.list_panels(
            {
                "scenario": "default",
                "scene_id": self.scene.scene_id,
            }
        )
        scope_types = {item["scope_type"] for item in result}
        names = [item["name"] for item in result]
        self.assertIn("platform", scope_types)
        self.assertIn("scene", scope_types)
        self.assertIn("安全总览报表", names)
        self.assertIn("场景报表", names)

    def test_panel_list_no_scope(self):
        """测试不传 scope 参数，返回全部报表（兼容存量）"""
        result = self.resource.vision.list_panels({"scenario": "default"})
        self.assertGreaterEqual(len(result), 2)

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
        self.assertTrue(
            ResourceVisibility.objects.filter(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(result["id"]),
            ).exists()
        )

    def test_update_platform_panel(self):
        """测试编辑平台级报表"""
        result = self.resource.vision.update_platform_panel(
            {
                "panel_id": self.platform_panel.pk,
                "name": "更新后的报表",
            }
        )
        self.assertEqual(result["name"], "更新后的报表")

    def test_delete_platform_panel(self):
        """测试删除平台级报表"""
        pk = self.platform_panel.pk
        self.resource.vision.delete_platform_panel({"panel_id": pk})
        self.assertFalse(VisionPanel.objects.filter(pk=pk).exists())

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

    def test_create_scene_panel(self):
        """测试创建场景级报表"""
        result = self.resource.vision.create_scene_panel(
            {
                "scene_id": self.scene.scene_id,
                "name": "新场景报表",
                "category": PanelCategory.BEHAVIOR_ANALYSIS,
            }
        )
        self.assertEqual(result["name"], "新场景报表")
        panel = VisionPanel.objects.get(pk=result["id"])
        self.assertEqual(panel.scope_type, ResourceScopeType.SCENE)
        self.assertEqual(panel.scene_id, self.scene.scene_id)

    def test_update_scene_panel(self):
        """测试编辑场景级报表"""
        result = self.resource.vision.update_scene_panel(
            {
                "scene_id": self.scene.scene_id,
                "panel_id": self.scene_panel.pk,
                "name": "更新后的场景报表",
            }
        )
        self.assertEqual(result["name"], "更新后的场景报表")

    def test_delete_scene_panel(self):
        """测试删除场景级报表"""
        pk = self.scene_panel.pk
        self.resource.vision.delete_scene_panel({"scene_id": self.scene.scene_id, "panel_id": pk})
        self.assertFalse(VisionPanel.objects.filter(pk=pk).exists())


# ==================== 工具 ViewSet 测试 ====================


class TestToolResources(TestCase):
    """工具 Resource 测试（tool 模块）"""

    def setUp(self):
        super().setUp()
        self.scene = Scene.objects.create(
            name="主机安全审计",
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
            scope_type=ResourceScopeType.PLATFORM,
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
            scope_type=ResourceScopeType.SCENE,
            scene_id=self.scene.scene_id,
        )
        self.resource = resource

    def _call_list_tool(self, data):
        """调用 ListTool Resource（需要 mock request 和权限）"""
        from unittest.mock import PropertyMock, patch

        from django.db.models import Q
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from services.web.tool.permissions import ToolPermission
        from services.web.tool.resources import ListTool

        factory = APIRequestFactory()
        django_request = factory.get('/fake-url/', data, format='json')
        drf_request = Request(django_request)

        with patch.object(
            ToolPermission, 'authed_tool_filter', new_callable=PropertyMock, return_value=Q()
        ), patch.object(
            ToolPermission,
            'fetch_tool_permission_tags',
            return_value={
                "use_tool_permission_tags": [],
                "manage_tool_permission_tags": [],
            },
        ):
            res = ListTool()
            response = res.request(data, _request=drf_request)
            return response.data.get("results", [])

    def test_tool_list(self):
        """测试工具列表（通过 scope 过滤）"""
        # 不传 scope，返回全部工具（包括有 scope 和无 scope 的）
        result = self._call_list_tool({"page": 1, "page_size": 10})
        tool_names = [item["name"] for item in result]
        self.assertIn("查询工具", tool_names)
        self.assertIn("场景工具", tool_names)

    def test_tool_list_filter_platform(self):
        """测试按平台级过滤工具"""
        result = self._call_list_tool({"scope_type": "platform", "page": 1, "page_size": 10})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "查询工具")

    def test_tool_list_filter_scene(self):
        """测试按场景过滤工具"""
        result = self._call_list_tool(
            {"scope_type": "scene", "scene_id": self.scene.scene_id, "page": 1, "page_size": 10}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "场景工具")

    def test_tool_detail(self):
        """测试工具详情（通过 get_tool_detail）"""
        result = self.resource.tool.get_tool_detail({"uid": self.platform_tool.uid})
        self.assertEqual(result["name"], "查询工具")
        self.assertEqual(result["scope_type"], ResourceScopeType.PLATFORM)

    def test_tool_detail_not_found(self):
        """测试工具不存在"""
        from services.web.tool.exceptions import ToolDoesNotExist

        with self.assertRaises(ToolDoesNotExist):
            self.resource.tool.get_tool_detail({"uid": "nonexistent_uid"})

    def test_tool_list_filter_scene_with_platform(self):
        """测试传 scene_id 但不传 scope_type，应返回该场景工具 + 平台级工具"""
        result = self._call_list_tool({"scene_id": self.scene.scene_id, "page": 1, "page_size": 10})
        tool_names = [item["name"] for item in result]
        self.assertIn("查询工具", tool_names)  # 平台级
        self.assertIn("场景工具", tool_names)  # 场景级
        self.assertEqual(len(result), 2)

    def test_create_platform_tool(self):
        """测试创建平台级工具"""
        data = {
            "name": "新工具",
            "tool_type": "data_search",
            "description": "新工具描述",
            "tags": ["测试"],
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
        self.assertIsNotNone(tool)
        self.assertEqual(tool.scope_type, ResourceScopeType.PLATFORM)

    def test_update_platform_tool(self):
        """测试编辑平台级工具"""
        self.resource.tool.update_platform_scene_tool(
            {
                "uid": self.platform_tool.uid,
                "name": "更新后的工具",
                "tags": ["测试"],
            }
        )
        updated_tool = Tool.last_version_tool(self.platform_tool.uid)
        self.assertEqual(updated_tool.name, "更新后的工具")

    def test_delete_platform_tool(self):
        """测试删除平台级工具"""
        uid = self.platform_tool.uid
        self.resource.tool.delete_platform_scene_tool({"uid": uid})
        self.assertIsNone(Tool.last_version_tool(uid))

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

    def test_create_scene_tool(self):
        """测试创建场景级工具"""
        result = self.resource.tool.create_scene_scope_tool(
            {
                "scene_id": self.scene.scene_id,
                "name": "新场景工具",
                "tool_type": "data_search",
                "tags": ["安全"],
                "data_search_config_type": "sql",
                "config": {
                    "sql": "SELECT * FROM test_table",
                    "referenced_tables": [{"table_name": "test_table"}],
                    "input_variable": [],
                    "output_fields": [],
                },
            }
        )
        tool = Tool.last_version_tool(result["uid"])
        self.assertIsNotNone(tool)
        self.assertEqual(tool.scope_type, ResourceScopeType.SCENE)
        self.assertEqual(tool.scene_id, self.scene.scene_id)

    def test_update_scene_tool(self):
        """测试编辑场景级工具"""
        self.resource.tool.update_scene_scope_tool(
            {
                "scene_id": self.scene.scene_id,
                "uid": self.scene_tool.uid,
                "name": "更新后的场景工具",
                "tags": ["安全"],
            }
        )
        updated_tool = Tool.last_version_tool(self.scene_tool.uid)
        self.assertEqual(updated_tool.name, "更新后的场景工具")

    def test_delete_scene_tool(self):
        """测试删除场景级工具"""
        uid = self.scene_tool.uid
        self.resource.tool.delete_scene_scope_tool({"scene_id": self.scene.scene_id, "uid": uid})
        self.assertIsNone(Tool.last_version_tool(uid))


# ==================== 菜单 & 权限引导测试 ====================


class TestMenuAndGuide(TestCase):
    """菜单和权限引导测试"""

    def test_menu_list(self):
        """测试菜单列表"""
        result = self.resource.scene.list_menus({})
        menu_ids = [m["id"] for m in result]
        self.assertIn("risk", menu_ids)
        self.assertIn("search", menu_ids)
        self.assertIn("scene_config", menu_ids)

    def test_permission_guide(self):
        """测试权限引导"""
        result = self.resource.scene.get_permission_guide({"module": "scene_config"})
        self.assertFalse(result["has_permission"])
        self.assertIn("guide", result)


# ==================== 常量测试 ====================


class TestConstants:
    """常量枚举测试"""

    def test_scene_status_choices(self):
        assert SceneStatus.ENABLED == "enabled"
        assert SceneStatus.DISABLED == "disabled"

    def test_visibility_scope_choices(self):
        assert VisibilityScope.ALL_VISIBLE == "all_visible"
        assert VisibilityScope.SPECIFIC_SCENES == "specific_scenes"

    def test_resource_scope_type_choices(self):
        assert ResourceScopeType.PLATFORM == "platform"
        assert ResourceScopeType.SCENE == "scene"

    def test_panel_category_choices(self):
        assert len(PanelCategory.choices) == 8

    def test_platform_tool_type_choices(self):
        assert len(PlatformToolType.choices) == 4

    def test_scene_tool_type_choices(self):
        assert len(SceneToolType.choices) == 4
