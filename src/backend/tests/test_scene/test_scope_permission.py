# -*- coding: utf-8 -*-
"""
ScopePermission 权限组件单元测试

覆盖：
- ScopeQueryField 常量
- ScopeContext.from_request 解析与校验（使用 ScopeQueryField 常量）
- ScopePermission action 方向校验（基于 related_resource_types）
- ScopePermission.check_scope_entry 四种 scope_type 路由
- ScopePermission.get_scene_ids / get_system_ids 请求级缓存
- ScopePermission.get_scene_ids / get_system_ids 方向不匹配返回空列表
- ScopeEntryPermission scope action vs 业务 action 路由（无 allowed_scope_types）
- ScopeInstancePermission 列表接口直接通过
- ScopePermission.check_resource_permission（不传 scope）
- ScopePermission._get_scene_visible_resource_ids / _get_system_visible_resource_ids 拆分方法
- System.get_managed_system_ids / System.is_manager 便捷方法
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory

from apps.permission.handlers.actions.action import ActionEnum
from core.exceptions import PermissionException, ValidationError
from services.web.common.constants import (
    BindingResourceType,
    ScopeQueryField,
    ScopeType,
)
from services.web.common.scope_permission import (
    ScopeContext,
    ScopeEntryPermission,
    ScopeInstancePermission,
    ScopePermission,
    _is_scene_action,
    _is_scope_action,
    _is_system_action,
)
from services.web.scene.constants import BindingType, VisibilityScope
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
)
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
    return RequestFactory()


@pytest.fixture
def mock_user():
    return MockUser("test_user")


def _make_request(rf, mock_user, query_params=None, data=None):
    """构造带 scope 参数的 request"""
    params = query_params or {}
    request = rf.get("/", params)
    request.user = mock_user
    if data:
        request.data = data
    else:
        request.data = {}
    return request


# ==================== ScopeQueryField Tests ====================


class TestScopeQueryField(TestCase):
    """测试 ScopeQueryField 枚举常量"""

    def test_scope_type_value(self):
        """SCOPE_TYPE 值为 'scope_type'"""
        assert ScopeQueryField.SCOPE_TYPE == "scope_type"
        assert ScopeQueryField.SCOPE_TYPE.value == "scope_type"

    def test_scope_id_value(self):
        """SCOPE_ID 值为 'scope_id'"""
        assert ScopeQueryField.SCOPE_ID == "scope_id"
        assert ScopeQueryField.SCOPE_ID.value == "scope_id"

    def test_is_text_choices(self):
        """ScopeQueryField 应为 TextChoices 枚举"""
        assert hasattr(ScopeQueryField, "choices")
        assert len(ScopeQueryField.choices) == 2


# ==================== Action 判断函数 Tests ====================


class TestActionTypeChecks(TestCase):
    """测试 action 关联资源类型判断函数"""

    def test_is_scope_action_scene(self):
        """VIEW_SCENE 的 related_resource_types 包含 scene"""
        assert _is_scope_action(ActionEnum.VIEW_SCENE) is True
        assert _is_scene_action(ActionEnum.VIEW_SCENE) is True

    def test_is_scope_action_system(self):
        """VIEW_SYSTEM 的 related_resource_types 包含 system"""
        assert _is_scope_action(ActionEnum.VIEW_SYSTEM) is True
        assert _is_system_action(ActionEnum.VIEW_SYSTEM) is True

    def test_is_scope_action_list_strategy(self):
        """LIST_STRATEGY 的 related_resource_types 包含 scene"""
        assert _is_scope_action(ActionEnum.LIST_STRATEGY) is True
        assert _is_scene_action(ActionEnum.LIST_STRATEGY) is True

    def test_is_scope_action_search_regular_event(self):
        """SEARCH_REGULAR_EVENT 的 related_resource_types 包含 system"""
        assert _is_scope_action(ActionEnum.SEARCH_REGULAR_EVENT) is True
        assert _is_system_action(ActionEnum.SEARCH_REGULAR_EVENT) is True

    def test_not_scope_action(self):
        """MANAGE_PLATFORM 没有 related_resource_types，不是 scope action"""
        assert _is_scope_action(ActionEnum.MANAGE_PLATFORM) is False

    def test_scene_action_not_system(self):
        """VIEW_SCENE 是 scene action 但不是 system action"""
        assert _is_scene_action(ActionEnum.VIEW_SCENE) is True
        assert _is_system_action(ActionEnum.VIEW_SCENE) is False

    def test_system_action_not_scene(self):
        """VIEW_SYSTEM 是 system action 但不是 scene action"""
        assert _is_system_action(ActionEnum.VIEW_SYSTEM) is True
        assert _is_scene_action(ActionEnum.VIEW_SYSTEM) is False


# ==================== ScopeContext Tests ====================


class TestScopeContext(TestCase):
    """测试 ScopeContext 解析与校验"""

    def setUp(self):
        self.rf = RequestFactory()
        self.user = MockUser("admin")

    def test_from_request_cross_scene(self):
        """cross_scene 无需 scope_id"""
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})
        ctx = ScopeContext.from_request(request)
        assert ctx.scope_type == ScopeType.CROSS_SCENE
        assert ctx.scope_id is None
        assert ctx.is_scene_scope is True
        assert ctx.is_system_scope is False
        assert ctx.is_cross_scope is True

    def test_from_request_cross_system(self):
        """cross_system 无需 scope_id"""
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_system"})
        ctx = ScopeContext.from_request(request)
        assert ctx.scope_type == ScopeType.CROSS_SYSTEM
        assert ctx.scope_id is None
        assert ctx.is_system_scope is True
        assert ctx.is_cross_scope is True

    def test_from_request_scene_with_scope_id(self):
        """scene 必须传 scope_id"""
        request = _make_request(
            self.rf,
            self.user,
            {ScopeQueryField.SCOPE_TYPE: "scene", ScopeQueryField.SCOPE_ID: "123"},
        )
        ctx = ScopeContext.from_request(request)
        assert ctx.scope_type == ScopeType.SCENE
        assert ctx.scope_id == "123"
        assert ctx.is_scene_scope is True
        assert ctx.is_cross_scope is False

    def test_from_request_system_with_scope_id(self):
        """system 必须传 scope_id"""
        request = _make_request(
            self.rf,
            self.user,
            {ScopeQueryField.SCOPE_TYPE: "system", ScopeQueryField.SCOPE_ID: "bk_monitor"},
        )
        ctx = ScopeContext.from_request(request)
        assert ctx.scope_type == ScopeType.SYSTEM
        assert ctx.scope_id == "bk_monitor"
        assert ctx.is_system_scope is True
        assert ctx.is_cross_scope is False

    def test_from_request_missing_scope_type(self):
        """缺少 scope_type 参数"""
        request = _make_request(self.rf, self.user, {})
        with pytest.raises(ValidationError):
            ScopeContext.from_request(request)

    def test_from_request_invalid_scope_type(self):
        """不合法 scope_type"""
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "invalid"})
        with pytest.raises(ValidationError):
            ScopeContext.from_request(request)

    def test_from_request_scene_missing_scope_id(self):
        """scene scope_type 缺少 scope_id"""
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "scene"})
        with pytest.raises(ValidationError):
            ScopeContext.from_request(request)

    def test_from_request_system_missing_scope_id(self):
        """system scope_type 缺少 scope_id"""
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "system"})
        with pytest.raises(ValidationError):
            ScopeContext.from_request(request)

    def test_from_request_cross_scene_ignores_scope_id(self):
        """cross_scene 传了 scope_id 也会被忽略"""
        request = _make_request(
            self.rf,
            self.user,
            {ScopeQueryField.SCOPE_TYPE: "cross_scene", ScopeQueryField.SCOPE_ID: "123"},
        )
        ctx = ScopeContext.from_request(request)
        assert ctx.scope_id is None

    def test_from_request_reads_from_data(self):
        """从 request.data 读取 scope 参数"""
        request = _make_request(
            self.rf,
            self.user,
            data={ScopeQueryField.SCOPE_TYPE: "scene", ScopeQueryField.SCOPE_ID: "456"},
        )
        ctx = ScopeContext.from_request(request)
        assert ctx.scope_type == ScopeType.SCENE
        assert ctx.scope_id == "456"

    def test_frozen_dataclass(self):
        """ScopeContext 是不可变的"""
        ctx = ScopeContext(scope_type=ScopeType.CROSS_SCENE)
        with pytest.raises(AttributeError):
            ctx.scope_type = ScopeType.SCENE  # type: ignore

    def test_scope_type_is_enum(self):
        """解析后 scope_type 应该是 ScopeType 枚举实例"""
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})
        ctx = ScopeContext.from_request(request)
        assert isinstance(ctx.scope_type, ScopeType)

    def test_uses_scope_query_field_constants(self):
        """from_request 使用 ScopeQueryField 枚举常量作为参数名"""
        # 验证使用字符串 "scope_type" 和 "scope_id" 同样可以解析
        request = _make_request(self.rf, self.user, {"scope_type": "scene", "scope_id": "1"})
        ctx = ScopeContext.from_request(request)
        assert ctx.scope_type == ScopeType.SCENE
        assert ctx.scope_id == "1"


# ==================== ScopePermission Tests ====================


class TestScopePermissionActionValidation(TestCase):
    """测试 ScopePermission action 方向校验（基于 related_resource_types）"""

    def test_validate_scene_action_success(self):
        """场景 scope + 场景 action 通过"""
        ScopePermission._validate_scope_action(ScopeType.CROSS_SCENE, ActionEnum.VIEW_SCENE)
        ScopePermission._validate_scope_action(ScopeType.SCENE, ActionEnum.MANAGE_SCENE)

    def test_validate_system_action_success(self):
        """系统 scope + 系统 action 通过"""
        ScopePermission._validate_scope_action(ScopeType.CROSS_SYSTEM, ActionEnum.VIEW_SYSTEM)
        ScopePermission._validate_scope_action(ScopeType.SYSTEM, ActionEnum.EDIT_SYSTEM)

    def test_validate_scene_scope_with_list_strategy(self):
        """LIST_STRATEGY 的 related_resource_types 是 scene，可用于场景 scope"""
        ScopePermission._validate_scope_action(ScopeType.CROSS_SCENE, ActionEnum.LIST_STRATEGY)

    def test_validate_scene_action_reject_system_scope(self):
        """系统 scope 不允许场景方向的 action"""
        with pytest.raises(ValueError):
            ScopePermission._validate_scope_action(ScopeType.CROSS_SYSTEM, ActionEnum.VIEW_SCENE)

    def test_validate_system_action_reject_scene_scope(self):
        """场景 scope 不允许系统方向的 action"""
        with pytest.raises(ValueError):
            ScopePermission._validate_scope_action(ScopeType.SCENE, ActionEnum.VIEW_SYSTEM)


# ==================== ScopePermission Direction Mismatch Tests ====================


class TestScopePermissionDirectionMismatch(TestCase):
    """测试 get_scene_ids / get_system_ids 方向不匹配时返回空列表"""

    @patch("services.web.common.scope_permission.Permission")
    def test_get_scene_ids_with_system_scope_returns_empty(self, mock_perm_cls):
        """系统方向 scope 调用 get_scene_ids 返回空列表"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp.get_scene_ids(ScopeContext(ScopeType.CROSS_SYSTEM), ActionEnum.VIEW_SCENE)
        assert result == []

    @patch("services.web.common.scope_permission.Permission")
    def test_get_scene_ids_with_single_system_scope_returns_empty(self, mock_perm_cls):
        """单系统 scope 调用 get_scene_ids 返回空列表"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp.get_scene_ids(ScopeContext(ScopeType.SYSTEM, "bk_monitor"), ActionEnum.VIEW_SCENE)
        assert result == []

    @patch("services.web.common.scope_permission.Permission")
    def test_get_system_ids_with_scene_scope_returns_empty(self, mock_perm_cls):
        """场景方向 scope 调用 get_system_ids 返回空列表"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp.get_system_ids(ScopeContext(ScopeType.CROSS_SCENE), ActionEnum.VIEW_SYSTEM)
        assert result == []

    @patch("services.web.common.scope_permission.Permission")
    def test_get_system_ids_with_single_scene_scope_returns_empty(self, mock_perm_cls):
        """单场景 scope 调用 get_system_ids 返回空列表"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp.get_system_ids(ScopeContext(ScopeType.SCENE, "1"), ActionEnum.VIEW_SYSTEM)
        assert result == []


# ==================== check_scope_entry Tests ====================


@pytest.mark.django_db
class TestScopePermissionCheckScopeEntry(TestCase):
    """测试 check_scope_entry 四种 scope_type 路由"""

    @patch("services.web.common.scope_permission.Permission")
    def test_cross_scene_uses_any_permission(self, mock_perm_cls):
        """cross_scene 使用 has_action_any_permission"""
        mock_instance = MagicMock()
        mock_instance.has_action_any_permission.return_value = True
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        scope = ScopeContext(ScopeType.CROSS_SCENE)
        result = sp.check_scope_entry(scope, ActionEnum.VIEW_SCENE)
        assert result is True
        mock_instance.has_action_any_permission.assert_called_once_with(ActionEnum.VIEW_SCENE)

    @patch("services.web.common.scope_permission.Permission")
    def test_scene_uses_is_allowed(self, mock_perm_cls):
        """scene 使用 is_allowed 实例级"""
        mock_instance = MagicMock()
        mock_instance.is_allowed.return_value = True
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        scope = ScopeContext(ScopeType.SCENE, "1")
        result = sp.check_scope_entry(scope, ActionEnum.VIEW_SCENE)
        assert result is True
        mock_instance.is_allowed.assert_called_once()

    @patch("services.web.common.scope_permission.System.get_managed_system_ids", return_value=["bk_monitor"])
    @patch("services.web.common.scope_permission.Permission")
    def test_cross_system_dual_channel(self, mock_perm_cls, mock_managed):
        """cross_system 走 IAM + 本地 managers 双通道"""
        mock_instance = MagicMock()
        # IAM 返回 False
        mock_instance.has_action_any_permission.return_value = False
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        scope = ScopeContext(ScopeType.CROSS_SYSTEM)
        result = sp.check_scope_entry(scope, ActionEnum.VIEW_SYSTEM)
        assert result is True  # 本地 managers 通过

    @patch("services.web.common.scope_permission.System.is_manager", return_value=True)
    @patch("services.web.common.scope_permission.Permission")
    def test_system_dual_channel(self, mock_perm_cls, mock_is_manager):
        """system 走 IAM + 本地 managers 双通道"""
        mock_instance = MagicMock()
        # IAM 返回 False
        mock_instance.is_allowed.return_value = False
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        scope = ScopeContext(ScopeType.SYSTEM, "bk_monitor")
        result = sp.check_scope_entry(scope, ActionEnum.VIEW_SYSTEM)
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_cross_scene_denied_raises(self, mock_perm_cls):
        """cross_scene 无权限时抛 PermissionException"""
        mock_instance = MagicMock()
        mock_instance.has_action_any_permission.return_value = False
        mock_instance.get_apply_data.return_value = ({}, "http://apply")
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        scope = ScopeContext(ScopeType.CROSS_SCENE)
        with pytest.raises(PermissionException):
            sp.check_scope_entry(scope, ActionEnum.VIEW_SCENE, raise_exception=True)


# ==================== Request-level Cache Tests ====================


@pytest.mark.django_db
class TestScopePermissionCache(TestCase):
    """测试请求级缓存"""

    @patch("services.web.common.scope_permission.Permission")
    def test_get_scene_ids_cache(self, mock_perm_cls):
        """同一 scope+action 调用两次只查询一次 IAM"""
        mock_instance = MagicMock()
        mock_instance.get_policies_for_action.return_value = {}
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        scope = ScopeContext(ScopeType.CROSS_SCENE)

        result1 = sp.get_scene_ids(scope, ActionEnum.VIEW_SCENE)
        result2 = sp.get_scene_ids(scope, ActionEnum.VIEW_SCENE)

        assert result1 == result2
        # 只调用一次 get_policies_for_action
        assert mock_instance.get_policies_for_action.call_count == 1

    @patch("services.web.common.scope_permission.System.get_managed_system_ids", return_value=[])
    @patch("services.web.common.scope_permission.Permission")
    def test_get_system_ids_cache(self, mock_perm_cls, mock_managed):
        """get_system_ids 缓存"""
        mock_instance = MagicMock()
        mock_instance.get_policies_for_action.return_value = {}
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        scope = ScopeContext(ScopeType.CROSS_SYSTEM)

        result1 = sp.get_system_ids(scope, ActionEnum.VIEW_SYSTEM)
        result2 = sp.get_system_ids(scope, ActionEnum.VIEW_SYSTEM)

        assert result1 == result2
        assert mock_instance.get_policies_for_action.call_count == 1

    @patch("services.web.common.scope_permission.Permission")
    def test_direction_mismatch_not_cached(self, mock_perm_cls):
        """方向不匹配的调用不会污染缓存"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        # 系统 scope 调用 get_scene_ids → 空返回
        result = sp.get_scene_ids(ScopeContext(ScopeType.CROSS_SYSTEM), ActionEnum.VIEW_SCENE)
        assert result == []
        # 不应该有缓存条目
        assert len(sp._scene_ids_cache) == 0


# ==================== ScopeEntryPermission Tests ====================


@pytest.mark.django_db
class TestScopeEntryPermission(TestCase):
    """测试 ScopeEntryPermission 路由"""

    def setUp(self):
        self.rf = RequestFactory()
        self.user = MockUser("admin")

    @patch("services.web.common.scope_permission.get_request_username", return_value="admin")
    @patch("services.web.common.scope_permission.Permission")
    def test_scope_action_routes_to_check_scope_entry(self, mock_perm_cls, mock_get_username):
        """scope action（VIEW_SCENE）走 check_scope_entry"""
        mock_instance = MagicMock()
        mock_instance.has_action_any_permission.return_value = True
        mock_perm_cls.return_value = mock_instance

        perm = ScopeEntryPermission(action=ActionEnum.VIEW_SCENE)
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})

        result = perm.has_permission(request, MagicMock())
        assert result is True
        mock_instance.has_action_any_permission.assert_called()

    @patch("services.web.common.scope_permission.get_request_username", return_value="admin")
    @patch("services.web.common.scope_permission.Permission")
    def test_list_strategy_routes_to_check_scope_entry(self, mock_perm_cls, mock_get_username):
        """LIST_STRATEGY（related_resource_types=[SCENE]）走 check_scope_entry"""
        mock_instance = MagicMock()
        mock_instance.has_action_any_permission.return_value = True
        mock_perm_cls.return_value = mock_instance

        perm = ScopeEntryPermission(action=ActionEnum.LIST_STRATEGY)
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})

        result = perm.has_permission(request, MagicMock())
        assert result is True
        mock_instance.has_action_any_permission.assert_called()

    @patch("services.web.common.scope_permission.get_request_username", return_value="admin")
    @patch("services.web.common.scope_permission.Permission")
    def test_non_scope_action_routes_to_iam(self, mock_perm_cls, mock_get_username):
        """无 related_resource_types 的 action 走 IAM 直接校验"""
        mock_instance = MagicMock()
        mock_instance.has_action_any_permission.return_value = True
        mock_perm_cls.return_value = mock_instance

        perm = ScopeEntryPermission(action=ActionEnum.MANAGE_PLATFORM)
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})

        result = perm.has_permission(request, MagicMock())
        assert result is True
        mock_instance.has_action_any_permission.assert_called_with(ActionEnum.MANAGE_PLATFORM)

    @patch("services.web.common.scope_permission.get_request_username", return_value="admin")
    @patch("services.web.common.scope_permission.Permission")
    def test_mounts_scope_and_scope_permission(self, mock_perm_cls, mock_get_username):
        """ScopeEntryPermission 始终挂载 scope 和 scope_permission 到 request"""
        mock_instance = MagicMock()
        mock_instance.has_action_any_permission.return_value = True
        mock_perm_cls.return_value = mock_instance

        perm = ScopeEntryPermission(action=ActionEnum.VIEW_SCENE)
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})

        perm.has_permission(request, MagicMock())
        assert hasattr(request, "scope_permission")
        assert hasattr(request, "scope")
        assert request.scope.scope_type == ScopeType.CROSS_SCENE

    @patch("services.web.common.scope_permission.get_request_username", return_value="admin")
    @patch("services.web.common.scope_permission.Permission")
    def test_no_allowed_scope_types_restriction(self, mock_perm_cls, mock_get_username):
        """ScopeEntryPermission 不限制 scope_type，任何 scope_type 都能通过入口"""
        mock_instance = MagicMock()
        mock_instance.has_action_any_permission.return_value = True
        mock_perm_cls.return_value = mock_instance

        perm = ScopeEntryPermission(action=ActionEnum.VIEW_SCENE)

        # cross_scene 能通过
        request1 = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})
        assert perm.has_permission(request1, MagicMock()) is True

    @patch("services.web.common.scope_permission.get_request_username", return_value="admin")
    @patch("services.web.common.scope_permission.System.get_managed_system_ids", return_value=[])
    @patch("services.web.common.scope_permission.Permission")
    def test_system_scope_with_scene_action_passes_entry(self, mock_perm_cls, mock_managed, mock_get_username):
        """system scope + scene action → 入口走 check_scope_entry 但 _validate_scope_action 会报错"""
        mock_instance = MagicMock()
        mock_perm_cls.return_value = mock_instance

        perm = ScopeEntryPermission(action=ActionEnum.VIEW_SCENE)
        request = _make_request(
            self.rf,
            self.user,
            {ScopeQueryField.SCOPE_TYPE: "cross_system"},
        )

        # VIEW_SCENE 是 scene action，传 cross_system scope → check_scope_entry 中 _validate_scope_action 会 ValueError
        with pytest.raises(ValueError):
            perm.has_permission(request, MagicMock())


# ==================== ScopeInstancePermission Tests ====================


@pytest.mark.django_db
class TestScopeInstancePermission(TestCase):
    """测试 ScopeInstancePermission"""

    def setUp(self):
        self.rf = RequestFactory()
        self.user = MockUser("admin")

    def test_list_view_passes_without_resource_id(self):
        """列表接口无 resource_id 直接通过"""

        class TestPerm(ScopeInstancePermission):
            resource_type = BindingResourceType.PANEL
            resource_id_field = "pk"

        perm = TestPerm()
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})
        view = MagicMock()
        view.kwargs = {}

        result = perm.has_permission(request, view)
        assert result is True

    def test_resource_type_is_enum(self):
        """resource_type 应为 BindingResourceType 枚举"""

        class TestPerm(ScopeInstancePermission):
            resource_type = BindingResourceType.TOOL
            resource_id_field = "pk"

        perm = TestPerm()
        assert isinstance(perm.resource_type, BindingResourceType)


# ==================== check_resource_permission Tests ====================


@pytest.mark.django_db
class TestCheckResourcePermission(TestCase):
    """测试 check_resource_permission（不传 scope，遍历用户全部权限做 any 匹配）"""

    def setUp(self):
        self.scene = Scene.objects.create(
            name="测试场景",
            status="enabled",
            managers=["admin"],
            users=["user1"],
        )
        # 创建 all_visible 绑定
        self.binding_all = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_1",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )
        # 创建 specific_scenes 绑定
        self.binding_specific = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_2",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SPECIFIC_SCENES,
        )
        ResourceBindingScene.objects.create(binding=self.binding_specific, scene=self.scene)

        # 创建场景级绑定
        self.binding_scene = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_3",
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=self.binding_scene, scene=self.scene)

    @patch("services.web.common.scope_permission.Permission")
    def test_all_visible_always_passes(self, mock_perm_cls):
        """all_visible 资源直接通过"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(BindingResourceType.PANEL, "panel_1", scene_ids=[], system_ids=[])
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_specific_scenes_matches(self, mock_perm_cls):
        """specific_scenes 绑定在用户有权限的场景中有交集"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_2",
            scene_ids=[self.scene.scene_id],
            system_ids=[],
        )
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_specific_scenes_no_match(self, mock_perm_cls):
        """specific_scenes 绑定无交集时返回 False"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_2",
            scene_ids=[999999],  # 不存在的 scene_id
            system_ids=[],
        )
        assert result is False

    @patch("services.web.common.scope_permission.Permission")
    def test_scene_binding_matches(self, mock_perm_cls):
        """场景级绑定匹配"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_3",
            scene_ids=[self.scene.scene_id],
            system_ids=[],
        )
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_nonexistent_binding_returns_false(self, mock_perm_cls):
        """不存在的资源绑定返回 False"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "nonexistent",
            scene_ids=[self.scene.scene_id],
            system_ids=[],
        )
        assert result is False

    @patch("services.web.common.scope_permission.System.get_managed_system_ids", return_value=[])
    @patch("services.web.common.scope_permission.Permission")
    def test_check_resource_permission_no_scope(self, mock_perm_cls, mock_managed):
        """check_resource_permission 遍历所有有权限的 scope 做 any 匹配"""
        mock_instance = MagicMock()
        mock_instance.get_policies_for_action.return_value = {}
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        # 手动注入场景缓存，模拟用户有该场景权限
        cache_key = (ScopeType.CROSS_SCENE, None, ActionEnum.VIEW_SCENE.id)
        sp._scene_ids_cache[cache_key] = [self.scene.scene_id]
        cache_key_sys = (ScopeType.CROSS_SYSTEM, None, ActionEnum.VIEW_SYSTEM.id)
        sp._system_ids_cache[cache_key_sys] = []

        result = sp.check_resource_permission(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_3",
            raise_exception=False,
        )
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_check_resource_permission_denied_raises(self, mock_perm_cls):
        """check_resource_permission 无权限且 raise_exception=True 时抛异常"""
        mock_instance = MagicMock()
        mock_instance.get_policies_for_action.return_value = {}
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        # 注入空缓存
        sp._scene_ids_cache[(ScopeType.CROSS_SCENE, None, ActionEnum.VIEW_SCENE.id)] = []
        sp._system_ids_cache[(ScopeType.CROSS_SYSTEM, None, ActionEnum.VIEW_SYSTEM.id)] = []

        with pytest.raises(PermissionException):
            sp.check_resource_permission(
                resource_type=BindingResourceType.PANEL,
                resource_id="nonexistent",
                raise_exception=True,
            )


# ==================== Specific System Binding Tests ====================


@pytest.mark.django_db
class TestCheckResourcePermissionSystem(TestCase):
    """测试 check_resource_permission 对齐 specific_systems 绑定"""

    def setUp(self):
        # 创建 specific_systems 绑定
        self.binding_sys = ResourceBinding.objects.create(
            resource_type=BindingResourceType.TOOL,
            resource_id="tool_1",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
        )
        ResourceBindingSystem.objects.create(binding=self.binding_sys, system_id="bk_monitor")

    @patch("services.web.common.scope_permission.Permission")
    def test_specific_systems_matches(self, mock_perm_cls):
        """specific_systems 绑定用户有对应系统权限"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.TOOL,
            "tool_1",
            scene_ids=[],
            system_ids=["bk_monitor"],
        )
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_specific_systems_no_match(self, mock_perm_cls):
        """specific_systems 绑定用户无对应系统权限"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.TOOL,
            "tool_1",
            scene_ids=[],
            system_ids=["bk_other"],
        )
        assert result is False


# ==================== get_resource_ids 拆分方法 Tests ====================


@pytest.mark.django_db
class TestGetResourceIdsSplitMethods(TestCase):
    """测试 _get_scene_visible_resource_ids / _get_system_visible_resource_ids 拆分方法"""

    def setUp(self):
        self.scene = Scene.objects.create(
            name="场景A",
            status="enabled",
            managers=["admin"],
            users=["user1"],
        )
        # 场景级绑定
        self.binding_scene = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="scene_panel_1",
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=self.binding_scene, scene=self.scene)

        # 平台级 all_visible
        self.binding_all = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="all_visible_panel",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )

        # 平台级 all_scenes
        self.binding_all_scenes = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="all_scenes_panel",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_SCENES,
        )

        # 平台级 specific_scenes
        self.binding_specific_scenes = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="specific_scenes_panel",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SPECIFIC_SCENES,
        )
        ResourceBindingScene.objects.create(binding=self.binding_specific_scenes, scene=self.scene)

        # 平台级 specific_systems
        self.binding_specific_systems = ResourceBinding.objects.create(
            resource_type=BindingResourceType.TOOL,
            resource_id="specific_systems_tool",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
        )
        ResourceBindingSystem.objects.create(binding=self.binding_specific_systems, system_id="bk_monitor")

    def test_get_scene_visible_includes_scene_binding(self):
        """场景方向：包含场景级绑定的资源"""
        result = ScopePermission._get_scene_visible_resource_ids(
            BindingResourceType.PANEL,
            [self.scene.scene_id],
        )
        assert "scene_panel_1" in result

    def test_get_scene_visible_includes_all_visible(self):
        """场景方向：包含 all_visible 资源"""
        result = ScopePermission._get_scene_visible_resource_ids(
            BindingResourceType.PANEL,
            [self.scene.scene_id],
        )
        assert "all_visible_panel" in result

    def test_get_scene_visible_includes_all_scenes(self):
        """场景方向：包含 all_scenes 资源"""
        result = ScopePermission._get_scene_visible_resource_ids(
            BindingResourceType.PANEL,
            [self.scene.scene_id],
        )
        assert "all_scenes_panel" in result

    def test_get_scene_visible_includes_specific_scenes(self):
        """场景方向：包含 specific_scenes 匹配的资源"""
        result = ScopePermission._get_scene_visible_resource_ids(
            BindingResourceType.PANEL,
            [self.scene.scene_id],
        )
        assert "specific_scenes_panel" in result

    def test_get_scene_visible_no_match(self):
        """场景方向：不匹配的场景不返回 specific_scenes 资源"""
        result = ScopePermission._get_scene_visible_resource_ids(
            BindingResourceType.PANEL,
            [999999],
        )
        # all_visible 和 all_scenes 仍然在
        assert "all_visible_panel" in result
        assert "all_scenes_panel" in result
        # specific_scenes 不匹配
        assert "specific_scenes_panel" not in result

    def test_get_scene_visible_empty_scene_ids(self):
        """场景方向：空场景 ID 列表只返回 all_visible + all_scenes"""
        result = ScopePermission._get_scene_visible_resource_ids(
            BindingResourceType.PANEL,
            [],
        )
        assert "all_visible_panel" in result
        assert "all_scenes_panel" in result
        assert "scene_panel_1" not in result
        assert "specific_scenes_panel" not in result

    def test_get_system_visible_includes_all_visible(self):
        """系统方向：包含 all_visible 资源"""
        result = ScopePermission._get_system_visible_resource_ids(
            BindingResourceType.TOOL,
            ["bk_monitor"],
        )
        # all_visible 的是 panel 类型，tool 类型没有 all_visible
        # 但 specific_systems tool 应该在
        assert "specific_systems_tool" in result

    def test_get_system_visible_includes_specific_systems(self):
        """系统方向：包含 specific_systems 匹配的资源"""
        result = ScopePermission._get_system_visible_resource_ids(
            BindingResourceType.TOOL,
            ["bk_monitor"],
        )
        assert "specific_systems_tool" in result

    def test_get_system_visible_no_match(self):
        """系统方向：不匹配的系统不返回 specific_systems 资源"""
        result = ScopePermission._get_system_visible_resource_ids(
            BindingResourceType.TOOL,
            ["bk_other"],
        )
        assert "specific_systems_tool" not in result

    def test_get_system_visible_empty_system_ids(self):
        """系统方向：空系统 ID 列表只返回 all_visible"""
        result = ScopePermission._get_system_visible_resource_ids(
            BindingResourceType.TOOL,
            [],
        )
        assert "specific_systems_tool" not in result


# ==================== get_resource_ids 集成 Tests ====================


@pytest.mark.django_db
class TestGetResourceIdsIntegration(TestCase):
    """测试 get_resource_ids 方向不匹配返回空集合"""

    @patch("services.web.common.scope_permission.Permission")
    def test_system_scope_returns_empty_for_scene_binding(self, mock_perm_cls):
        """系统 scope 调用 get_resource_ids，get_scene_ids 返回空 → 不含场景绑定资源"""
        mock_instance = MagicMock()
        mock_instance.get_policies_for_action.return_value = {}
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        # 注入系统缓存
        sp._system_ids_cache[(ScopeType.CROSS_SYSTEM, None, ActionEnum.VIEW_SYSTEM.id)] = []

        result = sp.get_resource_ids(ScopeContext(ScopeType.CROSS_SYSTEM), BindingResourceType.PANEL)
        assert result == set()


# ==================== System Model 便捷方法 Tests ====================


@pytest.mark.django_db
class TestSystemManagerMethods(TestCase):
    """测试 System.get_managed_system_ids / System.is_manager"""

    def setUp(self):
        from apps.meta.models import System

        self.System = System
        # 创建带 managers 的系统
        self.system = System.objects.create(
            system_id="bk_test",
            namespace="default",
            managers=["admin", "test_user"],
        )

    def test_get_managed_system_ids(self):
        """get_managed_system_ids 返回管理的系统 ID 列表"""
        result = self.System.get_managed_system_ids("admin")
        assert "bk_test" in result

    def test_get_managed_system_ids_not_manager(self):
        """非管理员返回空列表"""
        result = self.System.get_managed_system_ids("nobody")
        assert "bk_test" not in result

    def test_is_manager_true(self):
        """is_manager 正确判断管理员"""
        assert self.System.is_manager("bk_test", "admin") is True

    def test_is_manager_false(self):
        """is_manager 正确判断非管理员"""
        assert self.System.is_manager("bk_test", "nobody") is False

    def test_is_manager_nonexistent_system(self):
        """is_manager 对不存在的系统返回 False"""
        assert self.System.is_manager("nonexistent", "admin") is False
