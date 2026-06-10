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
- ScopeInstancePermission 列表接口直接通过
- ScopePermission.check_resource_permission（不传 scope）
- ScopePermission 的 binding_type 过滤与校验
- System.get_managed_system_ids / System.is_manager 便捷方法
"""

from unittest.mock import MagicMock, patch

import pytest
from django.db.models import Q
from django.test import RequestFactory

from apps.meta.models import System
from apps.permission.handlers.actions.action import ActionEnum
from core.exceptions import PermissionException, ValidationError
from services.web.common.constants import (
    BindingResourceType,
    ScopeQueryField,
    ScopeType,
)
from services.web.common.scope_permission import (
    ScopeContext,
    ScopeInstancePermission,
    ScopePermission,
    _is_scene_action,
    _is_system_action,
)
from services.web.scene.constants import BindingType, SceneStatus, VisibilityScope
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
    SceneSystem,
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

    def test_is_scene_action(self):
        """VIEW_SCENE 的 related_resource_types 包含 scene"""
        assert _is_scene_action(ActionEnum.VIEW_SCENE) is True

    def test_is_system_action(self):
        """VIEW_SYSTEM 的 related_resource_types 包含 system"""
        assert _is_system_action(ActionEnum.VIEW_SYSTEM) is True

    def test_list_strategy_is_scene_action(self):
        """LIST_STRATEGY 的 related_resource_types 包含 scene"""
        assert _is_scene_action(ActionEnum.LIST_STRATEGY) is True

    def test_search_regular_event_is_system_action(self):
        """SEARCH_REGULAR_EVENT 的 related_resource_types 包含 system"""
        assert _is_system_action(ActionEnum.SEARCH_REGULAR_EVENT) is True

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

    def test_from_request_scene_invalid_scope_id(self):
        """scene scope_id 必须是合法场景 ID"""
        request = _make_request(
            self.rf,
            self.user,
            {ScopeQueryField.SCOPE_TYPE: "scene", ScopeQueryField.SCOPE_ID: "abc"},
        )
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


class TestScopeContextDirectConstruction(TestCase):
    """测试 ScopeContext 直接构造时的校验与归一化"""

    # --- 枚举值构造 ---

    def test_construct_cross_scene_enum(self):
        """枚举值 CROSS_SCENE，scope_id 归一化为 None"""
        ctx = ScopeContext(ScopeType.CROSS_SCENE)
        assert ctx.scope_type == ScopeType.CROSS_SCENE
        assert ctx.scope_id is None

    def test_construct_cross_system_enum(self):
        """枚举值 CROSS_SYSTEM，scope_id 归一化为 None"""
        ctx = ScopeContext(ScopeType.CROSS_SYSTEM)
        assert ctx.scope_type == ScopeType.CROSS_SYSTEM
        assert ctx.scope_id is None

    def test_construct_scene_enum_with_scope_id(self):
        """枚举值 SCENE + scope_id"""
        ctx = ScopeContext(ScopeType.SCENE, "123")
        assert ctx.scope_type == ScopeType.SCENE
        assert ctx.scope_id == "123"

    def test_construct_system_enum_with_scope_id(self):
        """枚举值 SYSTEM + scope_id"""
        ctx = ScopeContext(ScopeType.SYSTEM, "bk_monitor")
        assert ctx.scope_type == ScopeType.SYSTEM
        assert ctx.scope_id == "bk_monitor"

    # --- 字符串值构造（自动转枚举） ---

    def test_construct_cross_scene_str(self):
        """字符串 'cross_scene' 自动转 ScopeType 枚举"""
        ctx = ScopeContext("cross_scene")
        assert ctx.scope_type == ScopeType.CROSS_SCENE
        assert isinstance(ctx.scope_type, ScopeType)
        assert ctx.scope_id is None

    def test_construct_scene_str_with_scope_id(self):
        """字符串 'scene' + scope_id"""
        ctx = ScopeContext("scene", "456")
        assert ctx.scope_type == ScopeType.SCENE
        assert isinstance(ctx.scope_type, ScopeType)
        assert ctx.scope_id == "456"

    def test_construct_system_str_with_scope_id(self):
        """字符串 'system' + scope_id"""
        ctx = ScopeContext("system", "bk_log")
        assert ctx.scope_type == ScopeType.SYSTEM
        assert isinstance(ctx.scope_type, ScopeType)
        assert ctx.scope_id == "bk_log"

    # --- 校验：不合法 scope_type ---

    def test_construct_invalid_scope_type_str(self):
        """非法字符串 scope_type 应抛 ValidationError"""
        with pytest.raises(ValidationError):
            ScopeContext("invalid_type")

    # --- 校验：scene/system 缺少 scope_id ---

    def test_construct_scene_missing_scope_id(self):
        """SCENE 不传 scope_id 应抛 ValidationError"""
        with pytest.raises(ValidationError):
            ScopeContext(ScopeType.SCENE)

    def test_construct_scene_invalid_scope_id(self):
        """SCENE 传入非数字 scope_id 应抛 ValidationError"""
        with pytest.raises(ValidationError):
            ScopeContext(ScopeType.SCENE, "abc")

    def test_construct_system_missing_scope_id(self):
        """SYSTEM 不传 scope_id 应抛 ValidationError"""
        with pytest.raises(ValidationError):
            ScopeContext(ScopeType.SYSTEM)

    def test_construct_scene_str_missing_scope_id(self):
        """字符串 'scene' 不传 scope_id 应抛 ValidationError"""
        with pytest.raises(ValidationError):
            ScopeContext("scene")

    # --- 归一化：cross 类型传了 scope_id 会被忽略 ---

    def test_construct_cross_scene_ignores_scope_id(self):
        """CROSS_SCENE 传了 scope_id 也归一化为 None"""
        ctx = ScopeContext(ScopeType.CROSS_SCENE, "999")
        assert ctx.scope_id is None

    def test_construct_cross_system_ignores_scope_id(self):
        """CROSS_SYSTEM 传了 scope_id 也归一化为 None"""
        ctx = ScopeContext(ScopeType.CROSS_SYSTEM, "bk_monitor")
        assert ctx.scope_id is None

    # --- 属性正确性 ---

    def test_properties_scene_str(self):
        """字符串构造后 property 正确"""
        ctx = ScopeContext("scene", "1")
        assert ctx.is_scene_scope is True
        assert ctx.is_system_scope is False
        assert ctx.is_cross_scope is False

    def test_properties_cross_system_str(self):
        """字符串构造 cross_system 后 property 正确"""
        ctx = ScopeContext("cross_system")
        assert ctx.is_scene_scope is False
        assert ctx.is_system_scope is True
        assert ctx.is_cross_scope is True

    # --- frozen 不可变 ---

    def test_frozen_after_direct_construct(self):
        """直接构造的实例也不可变"""
        ctx = ScopeContext("cross_scene")
        with pytest.raises(AttributeError):
            ctx.scope_type = ScopeType.SCENE  # type: ignore


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

    @patch("services.web.common.scope_permission.Permission")
    def test_get_scene_ids_with_single_scene_denied_returns_empty(self, mock_perm_cls):
        """get_scene_ids 只负责回收过滤范围，单场景无权限返回空列表"""
        mock_instance = MagicMock()
        mock_instance.is_allowed.return_value = False
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        result = sp.get_scene_ids(ScopeContext(ScopeType.SCENE, "1"), ActionEnum.VIEW_SCENE)

        assert result == []

    @patch("services.web.common.scope_permission.Permission")
    def test_get_scene_ids_with_disabled_single_scene_returns_empty(self, mock_perm_cls):
        """单场景 scope 过滤停用场景"""
        scene = Scene.objects.create(name="停用单场景", status=SceneStatus.DISABLED)
        mock_instance = MagicMock()
        mock_instance.is_allowed.return_value = True
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        result = sp.get_scene_ids(ScopeContext(ScopeType.SCENE, scene.scene_id), ActionEnum.VIEW_SCENE)

        assert result == []

    @patch("services.web.common.scope_permission.SceneDjangoQuerySetConverter")
    @patch("services.web.common.scope_permission.Permission")
    def test_get_scene_ids_with_cross_scene_filters_disabled_scene(self, mock_perm_cls, mock_converter_cls):
        """跨场景 scope 过滤停用场景"""
        enabled_scene = Scene.objects.create(name="启用跨场景", status=SceneStatus.ENABLED)
        disabled_scene = Scene.objects.create(name="停用跨场景", status=SceneStatus.DISABLED)
        mock_instance = MagicMock()
        mock_instance.get_policies_for_action.return_value = {"any": "policy"}
        mock_perm_cls.return_value = mock_instance
        mock_converter = MagicMock()
        mock_converter.convert.return_value = Q(scene_id__in=[enabled_scene.scene_id, disabled_scene.scene_id])
        mock_converter_cls.return_value = mock_converter

        sp = ScopePermission("admin")
        result = sp.get_scene_ids(ScopeContext(ScopeType.CROSS_SCENE), ActionEnum.VIEW_SCENE)

        assert result == [enabled_scene.scene_id]

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

    @patch("services.web.common.scope_permission.System.is_manager", return_value=False)
    @patch("services.web.common.scope_permission.Permission")
    def test_get_system_ids_with_single_system_denied_returns_empty(self, mock_perm_cls, mock_is_manager):
        """get_system_ids 只负责回收过滤范围，单系统无权限返回空列表"""
        mock_instance = MagicMock()
        mock_instance.is_allowed.return_value = False
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        result = sp.get_system_ids(ScopeContext(ScopeType.SYSTEM, "bk_monitor"), ActionEnum.VIEW_SYSTEM)

        assert result == []

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


# ==================== ScopeInstancePermission Tests ====================


@pytest.mark.django_db
class TestScopeInstancePermission(TestCase):
    """测试 ScopeInstancePermission"""

    def setUp(self):
        self.rf = RequestFactory()
        self.user = MockUser("admin")

    @patch("services.web.common.scope_permission.get_request_username", return_value="admin")
    @patch("services.web.common.scope_permission.ScopePermission")
    def test_list_view_without_resource_id_raises_assertion(self, mock_scope_perm_cls, mock_get_username):
        """无实例 ID 的列表接口，父类 _get_instance_id 抛 AssertionError"""

        mock_scope_perm_cls.return_value = MagicMock()

        perm = ScopeInstancePermission(resource_type=BindingResourceType.PANEL)
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})
        view = MagicMock()
        view.kwargs = {}
        view.lookup_url_kwarg = None
        view.lookup_field = "pk"

        with pytest.raises(AssertionError):
            perm.has_permission(request, view)

    @patch("services.web.common.scope_permission.get_request_username", return_value="admin")
    @patch("services.web.common.scope_permission.ScopePermission")
    def test_default_lookup_field_resolves_pk(self, mock_scope_perm_cls, mock_get_username):
        """默认 lookup_field=pk 时，从 view.kwargs 中取实例 ID"""

        mock_scope_perm = MagicMock()
        mock_scope_perm.check_resource_permission.return_value = True
        mock_scope_perm_cls.return_value = mock_scope_perm

        perm = ScopeInstancePermission(resource_type=BindingResourceType.PANEL)
        request = _make_request(self.rf, self.user, {ScopeQueryField.SCOPE_TYPE: "cross_scene"})
        view = MagicMock()
        view.kwargs = {"pk": "panel_1"}
        view.lookup_url_kwarg = None
        view.lookup_field = "pk"

        result = perm.has_permission(request, view)
        assert result is True
        mock_scope_perm.check_resource_permission.assert_called_with(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_1",
            raise_exception=True,
        )

    def test_resource_type_is_enum(self):
        """resource_type 应为 BindingResourceType 枚举"""

        perm = ScopeInstancePermission(resource_type=BindingResourceType.PANEL)
        assert isinstance(perm.resource_type, BindingResourceType)

    @patch("services.web.common.scope_permission.get_request_username", return_value="admin")
    @patch("services.web.common.scope_permission.Permission")
    @patch("services.web.common.scope_permission.ScopePermission")
    def test_disabled_scene_binding_rejects_before_manager_exception(
        self,
        mock_scope_perm_cls,
        mock_permission_cls,
        mock_get_username,
    ):
        """停用场景下的场景级资源即使是场景管理员也不能使用"""

        scene = Scene.objects.create(name="停用场景", status=SceneStatus.DISABLED)
        binding = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="disabled_panel",
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=scene.scene_id)
        mock_permission = MagicMock()
        mock_permission.is_allowed.return_value = True
        mock_permission_cls.return_value = mock_permission

        perm = ScopeInstancePermission(resource_type=BindingResourceType.PANEL)
        request = _make_request(self.rf, self.user, {})
        view = MagicMock()
        view.kwargs = {"pk": "disabled_panel"}
        view.lookup_url_kwarg = None
        view.lookup_field = "pk"

        result = perm.has_permission(request, view)

        assert result is False
        mock_permission.is_allowed.assert_not_called()
        mock_scope_perm_cls.assert_not_called()


# ==================== check_resource_permission Tests ====================


@pytest.mark.django_db
class TestCheckResourcePermission(TestCase):
    """测试 check_resource_permission（不传 scope，遍历用户全部权限做 any 匹配）"""

    def setUp(self):
        self.scene = Scene.objects.create(
            name="测试场景",
            status="enabled",
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
    def test_all_visible_without_scope_returns_false(self, mock_perm_cls):
        """all_visible 资源在无 scene/system scope 时不可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(BindingResourceType.PANEL, "panel_1", scene_ids=[], system_ids=[])
        assert result is False

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
    def test_specific_scenes_ignores_soft_deleted_scene_binding(self, mock_perm_cls):
        """specific_scenes 不把软删除场景的残留绑定视为可见"""
        mock_perm_cls.return_value = MagicMock()
        self.scene.delete()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_2",
            scene_ids=[self.scene.scene_id],
            system_ids=[],
        )
        assert result is False

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


# ==================== SCENES_AND_SYSTEMS Binding Tests ====================


@pytest.mark.django_db
class TestScenesAndSystemsBinding(TestCase):
    """测试 SCENES_AND_SYSTEMS 绑定类型的权限消费逻辑"""

    def setUp(self):
        self.scene_1 = Scene.objects.create(name="场景1", status="enabled")
        self.scene_2 = Scene.objects.create(name="场景2", status="enabled")

        # 创建 SCENES_AND_SYSTEMS 绑定 - 只绑定场景
        self.binding_scene_only = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_scene_only",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SCENES_AND_SYSTEMS,
        )
        ResourceBindingScene.objects.create(binding=self.binding_scene_only, scene=self.scene_1)

        # 创建 SCENES_AND_SYSTEMS 绑定 - 只绑定系统
        self.binding_system_only = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_system_only",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SCENES_AND_SYSTEMS,
        )
        ResourceBindingSystem.objects.create(binding=self.binding_system_only, system_id="bk_monitor")

        # 创建 SCENES_AND_SYSTEMS 绑定 - 同时绑定场景和系统
        self.binding_both = ResourceBinding.objects.create(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_both",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.SCENES_AND_SYSTEMS,
        )
        ResourceBindingScene.objects.create(binding=self.binding_both, scene=self.scene_1)
        ResourceBindingSystem.objects.create(binding=self.binding_both, system_id="bk_monitor")

    @patch("services.web.common.scope_permission.Permission")
    def test_scene_only_binding_with_scene_access(self, mock_perm_cls):
        """只绑定场景：用户有对应场景权限时可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_scene_only",
            scene_ids=[self.scene_1.scene_id],
            system_ids=[],
        )
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_scene_only_binding_without_scene_access(self, mock_perm_cls):
        """只绑定场景：用户无对应场景权限时不可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_scene_only",
            scene_ids=[self.scene_2.scene_id],  # 无权限的场景
            system_ids=[],
        )
        assert result is False

    @patch("services.web.common.scope_permission.Permission")
    def test_scene_only_binding_with_system_access_returns_false(self, mock_perm_cls):
        """只绑定场景：用户有系统权限但无场景权限时不可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_scene_only",
            scene_ids=[],  # 无场景权限
            system_ids=["bk_monitor"],  # 有系统权限
        )
        assert result is False

    @patch("services.web.common.scope_permission.Permission")
    def test_system_only_binding_with_system_access(self, mock_perm_cls):
        """只绑定系统：用户有对应系统权限时可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_system_only",
            scene_ids=[],
            system_ids=["bk_monitor"],
        )
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_system_only_binding_without_system_access(self, mock_perm_cls):
        """只绑定系统：用户无对应系统权限时不可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_system_only",
            scene_ids=[],
            system_ids=["bk_other"],  # 无权限的系统
        )
        assert result is False

    @patch("services.web.common.scope_permission.Permission")
    def test_system_only_binding_with_scene_access_returns_false(self, mock_perm_cls):
        """只绑定系统：用户有场景权限但无系统权限时不可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_system_only",
            scene_ids=[self.scene_1.scene_id],  # 有场景权限
            system_ids=[],  # 无系统权限
        )
        assert result is False

    @patch("services.web.common.scope_permission.Permission")
    def test_both_binding_with_scene_access(self, mock_perm_cls):
        """同时绑定场景和系统：用户有场景权限时可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_both",
            scene_ids=[self.scene_1.scene_id],
            system_ids=[],
        )
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_both_binding_with_system_access(self, mock_perm_cls):
        """同时绑定场景和系统：用户有系统权限时可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_both",
            scene_ids=[],
            system_ids=["bk_monitor"],
        )
        assert result is True

    @patch("services.web.common.scope_permission.Permission")
    def test_both_binding_without_access(self, mock_perm_cls):
        """同时绑定场景和系统：用户无任何权限时不可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.PANEL,
            "panel_both",
            scene_ids=[self.scene_2.scene_id],  # 无权限的场景
            system_ids=["bk_other"],  # 无权限的系统
        )
        assert result is False

    @patch("services.web.common.scope_permission.Permission")
    def test_check_resource_permission_with_scenes_and_systems(self, mock_perm_cls):
        """测试 check_resource_permission 对 SCENES_AND_SYSTEMS 绑定的集成测试"""
        mock_instance = MagicMock()
        mock_instance.get_policies_for_action.return_value = {}
        mock_perm_cls.return_value = mock_instance

        sp = ScopePermission("admin")
        # 注入缓存，模拟用户有场景1和bk_monitor系统权限
        cache_key = (ScopeType.CROSS_SCENE, None, ActionEnum.VIEW_SCENE.id)
        sp._scene_ids_cache[cache_key] = [self.scene_1.scene_id]
        cache_key_sys = (ScopeType.CROSS_SYSTEM, None, ActionEnum.VIEW_SYSTEM.id)
        sp._system_ids_cache[cache_key_sys] = ["bk_monitor"]

        # 测试同时绑定场景和系统的资源
        result = sp.check_resource_permission(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_both",
            raise_exception=False,
        )
        assert result is True

        # 测试只绑定场景的资源
        result = sp.check_resource_permission(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_scene_only",
            raise_exception=False,
        )
        assert result is True

        # 测试只绑定系统的资源
        result = sp.check_resource_permission(
            resource_type=BindingResourceType.PANEL,
            resource_id="panel_system_only",
            raise_exception=False,
        )
        assert result is True


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
        self.binding_all_systems = ResourceBinding.objects.create(
            resource_type=BindingResourceType.TOOL,
            resource_id="tool_2",
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_SYSTEMS,
        )

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

    @patch("services.web.common.scope_permission.Permission")
    def test_all_systems_matches(self, mock_perm_cls):
        """all_systems 绑定用户有任意系统权限时可见"""
        mock_perm_cls.return_value = MagicMock()

        sp = ScopePermission("admin")
        result = sp._check_visibility_intersection(
            BindingResourceType.TOOL,
            "tool_2",
            scene_ids=[],
            system_ids=["bk_monitor"],
        )
        assert result is True


@pytest.mark.django_db
class TestGetSystemIdsForScope(TestCase):
    """测试 get_system_ids_for_scope 的场景视角系统展开语义"""

    @patch("services.web.common.scope_permission.Permission")
    def test_scene_scope_with_all_systems_returns_all_system_ids(self, mock_perm_cls):
        mock_perm_cls.return_value = MagicMock()
        scene = Scene.objects.create(name="全系统场景", status="enabled")
        SceneSystem.objects.create(scene=scene, system_id="", is_all_systems=True)
        System.objects.create(system_id="bk_monitor", namespace="bklog", name="监控", instance_id="bk_monitor")
        System.objects.create(system_id="bk_iam", namespace="bklog", name="权限", instance_id="bk_iam")

        sp = ScopePermission("admin")
        sp._scene_ids_cache[(ScopeType.CROSS_SCENE, None, ActionEnum.VIEW_SCENE.id)] = [scene.scene_id]

        result = sp.get_system_ids_for_scope(ScopeContext(ScopeType.CROSS_SCENE))
        assert set(result) == {"bk_monitor", "bk_iam"}

    @patch("services.web.common.scope_permission.Permission")
    def test_scene_scope_filters_blank_system_ids(self, mock_perm_cls):
        mock_perm_cls.return_value = MagicMock()
        scene = Scene.objects.create(name="普通场景", status="enabled")
        SceneSystem.objects.create(scene=scene, system_id="bk_monitor", is_all_systems=False)
        SceneSystem.objects.create(scene=scene, system_id="", is_all_systems=False)

        sp = ScopePermission("admin")
        sp._scene_ids_cache[(ScopeType.CROSS_SCENE, None, ActionEnum.VIEW_SCENE.id)] = [scene.scene_id]

        result = sp.get_system_ids_for_scope(ScopeContext(ScopeType.CROSS_SCENE))
        assert result == ["bk_monitor"]

    @patch("services.web.common.scope_permission.Permission")
    def test_scene_scope_deleted_scene_returns_empty_scene_ids(self, mock_perm_cls):
        scene = Scene.objects.create(name="已删除显式场景", status="enabled")
        scene.delete()
        permission = MagicMock()
        permission.is_allowed.return_value = True
        mock_perm_cls.return_value = permission

        sp = ScopePermission("admin")

        result = sp.get_scene_ids(ScopeContext(ScopeType.SCENE, scene.scene_id), ActionEnum.VIEW_SCENE)
        assert result == []

    @patch("services.web.common.scope_permission.Permission")
    def test_scene_scope_deleted_scene_systems_do_not_expand_all_systems(self, mock_perm_cls):
        mock_perm_cls.return_value = MagicMock()
        scene = Scene.objects.create(name="已删除全系统场景", status="enabled")
        SceneSystem.objects.create(scene=scene, system_id="", is_all_systems=True)
        System.objects.create(system_id="bk_monitor", namespace="bklog", name="监控", instance_id="bk_monitor")
        scene.delete()

        sp = ScopePermission("admin")
        sp._scene_ids_cache[(ScopeType.SCENE, scene.scene_id, ActionEnum.VIEW_SCENE.id)] = [scene.scene_id]

        result = sp.get_system_ids_for_scope(ScopeContext(ScopeType.SCENE, scene.scene_id))
        assert result == []


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
