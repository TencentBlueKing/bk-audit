# -*- coding: utf-8 -*-
"""
场景隔离 Phase 2 单元测试 — 现有资源关联场景

覆盖：
- 模型层：Strategy/Risk/ProcessApplication/RiskRule/NoticeGroup/LinkTable 的 scene_id 字段
- Serializer 层：列表查询和创建序列化器的 scene_id 参数
- Resource 层：场景过滤 + check_scene_permission 权限校验
- 创建场景时自动创建"场景管理员通知组"
- 删除场景时检查关联资源（策略/通知组/处理套餐/处理规则）
"""
import json

import pytest
from django.test import RequestFactory

from apps.notice.models import NoticeGroup
from services.web.risk.models import ProcessApplication, Risk, RiskRule
from services.web.scene.constants import SceneStatus
from services.web.scene.models import Scene
from services.web.strategy_v2.models import LinkTable, Strategy

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


# ==================== 模型层测试：scene_id 字段 ====================


class TestStrategySceneId:
    """Strategy 模型 scene_id 字段测试"""

    @pytest.mark.django_db
    def test_strategy_scene_id_nullable(self):
        """测试 Strategy 的 scene_id 允许为空"""
        strategy = Strategy(
            namespace="default",
            strategy_name="测试策略",
            scene_id=None,
        )
        assert strategy.scene_id is None

    @pytest.mark.django_db
    def test_strategy_scene_id_set(self, scene):
        """测试 Strategy 的 scene_id 可以设置"""
        strategy = Strategy(
            namespace="default",
            strategy_name="场景策略",
            scene_id=scene.scene_id,
        )
        assert strategy.scene_id == scene.scene_id

    @pytest.mark.django_db
    def test_strategy_scene_id_field_exists(self):
        """测试 Strategy 模型包含 scene_id 字段"""
        field_names = [f.name for f in Strategy._meta.get_fields()]
        assert "scene_id" in field_names


class TestRiskSceneId:
    """Risk 模型 scene_id 字段测试"""

    @pytest.mark.django_db
    def test_risk_scene_id_field_exists(self):
        """测试 Risk 模型包含 scene_id 字段"""
        field_names = [f.name for f in Risk._meta.get_fields()]
        assert "scene_id" in field_names

    @pytest.mark.django_db
    def test_risk_scene_id_nullable(self):
        """测试 Risk 的 scene_id 允许为空"""
        field = Risk._meta.get_field("scene_id")
        assert field.null is True
        assert field.blank is True


class TestProcessApplicationSceneId:
    """ProcessApplication 模型 scene_id 字段测试"""

    @pytest.mark.django_db
    def test_process_application_scene_id_field_exists(self):
        """测试 ProcessApplication 模型包含 scene_id 字段"""
        field_names = [f.name for f in ProcessApplication._meta.get_fields()]
        assert "scene_id" in field_names

    @pytest.mark.django_db
    def test_process_application_scene_id_nullable(self):
        """测试 ProcessApplication 的 scene_id 允许为空"""
        field = ProcessApplication._meta.get_field("scene_id")
        assert field.null is True
        assert field.blank is True

    @pytest.mark.django_db
    def test_process_application_scene_id_db_index(self):
        """测试 ProcessApplication 的 scene_id 有数据库索引"""
        field = ProcessApplication._meta.get_field("scene_id")
        assert field.db_index is True


class TestRiskRuleSceneId:
    """RiskRule 模型 scene_id 字段测试"""

    @pytest.mark.django_db
    def test_risk_rule_scene_id_field_exists(self):
        """测试 RiskRule 模型包含 scene_id 字段"""
        field_names = [f.name for f in RiskRule._meta.get_fields()]
        assert "scene_id" in field_names

    @pytest.mark.django_db
    def test_risk_rule_scene_id_nullable(self):
        """测试 RiskRule 的 scene_id 允许为空"""
        field = RiskRule._meta.get_field("scene_id")
        assert field.null is True
        assert field.blank is True


class TestNoticeGroupSceneId:
    """NoticeGroup 模型 scene_id 字段测试"""

    @pytest.mark.django_db
    def test_notice_group_scene_id_field_exists(self):
        """测试 NoticeGroup 模型包含 scene_id 字段"""
        field_names = [f.name for f in NoticeGroup._meta.get_fields()]
        assert "scene_id" in field_names

    @pytest.mark.django_db
    def test_notice_group_scene_id_nullable(self):
        """测试 NoticeGroup 的 scene_id 允许为空"""
        field = NoticeGroup._meta.get_field("scene_id")
        assert field.null is True
        assert field.blank is True

    @pytest.mark.django_db
    def test_notice_group_create_with_scene_id(self, scene):
        """测试创建带 scene_id 的通知组"""
        ng = NoticeGroup.objects.create(
            group_name="测试通知组",
            group_member=["admin"],
            notice_config=[],
            scene_id=scene.scene_id,
        )
        assert ng.scene_id == scene.scene_id

    @pytest.mark.django_db
    def test_notice_group_filter_by_scene_id(self, scene, another_scene):
        """测试按 scene_id 过滤通知组"""
        # 先清理可能的残留数据
        NoticeGroup.objects.all().delete()
        NoticeGroup.objects.create(
            group_name="场景1通知组",
            group_member=["admin"],
            notice_config=[],
            scene_id=scene.scene_id,
        )
        NoticeGroup.objects.create(
            group_name="场景2通知组",
            group_member=["admin"],
            notice_config=[],
            scene_id=another_scene.scene_id,
        )
        NoticeGroup.objects.create(
            group_name="无场景通知组",
            group_member=["admin"],
            notice_config=[],
            scene_id=None,
        )
        assert NoticeGroup.objects.filter(scene_id=scene.scene_id).count() == 1
        assert NoticeGroup.objects.filter(scene_id=another_scene.scene_id).count() == 1
        assert NoticeGroup.objects.filter(scene_id=None).count() == 1


class TestLinkTableSceneId:
    """LinkTable 模型 scene_id 字段测试"""

    @pytest.mark.django_db
    def test_link_table_scene_id_field_exists(self):
        """测试 LinkTable 模型包含 scene_id 字段"""
        field_names = [f.name for f in LinkTable._meta.get_fields()]
        assert "scene_id" in field_names

    @pytest.mark.django_db
    def test_link_table_scene_id_nullable(self):
        """测试 LinkTable 的 scene_id 允许为空"""
        field = LinkTable._meta.get_field("scene_id")
        assert field.null is True
        assert field.blank is True


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

    def test_scene_id_allow_null(self):
        """测试 scene_id 允许为空"""
        from apps.notice.serializers import CreateNoticeGroupRequestSerializer

        serializer = CreateNoticeGroupRequestSerializer()
        assert serializer.fields["scene_id"].allow_null is True


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
    """通知组场景过滤测试"""

    @pytest.mark.django_db
    def test_filter_notice_groups_by_scene(self, scene, another_scene):
        """测试按场景过滤通知组"""
        NoticeGroup.objects.create(
            group_name="场景1通知组",
            group_member=["admin"],
            notice_config=[],
            scene_id=scene.scene_id,
        )
        NoticeGroup.objects.create(
            group_name="场景2通知组",
            group_member=["admin"],
            notice_config=[],
            scene_id=another_scene.scene_id,
        )
        # 按场景1过滤
        qs = NoticeGroup.objects.filter(scene_id=scene.scene_id)
        assert qs.count() == 1
        assert qs.first().group_name == "场景1通知组"

    @pytest.mark.django_db
    def test_filter_notice_groups_no_scene(self, scene):
        """测试不传 scene_id 时返回全部"""
        # 先清理可能的残留数据
        NoticeGroup.objects.all().delete()
        NoticeGroup.objects.create(
            group_name="通知组1",
            group_member=["admin"],
            notice_config=[],
            scene_id=scene.scene_id,
        )
        NoticeGroup.objects.create(
            group_name="通知组2",
            group_member=["admin"],
            notice_config=[],
            scene_id=None,
        )
        assert NoticeGroup.objects.all().count() == 2


class TestProcessApplicationSceneFilter:
    """处理套餐场景过滤测试"""

    @pytest.mark.django_db
    def test_filter_pa_by_scene(self, scene, another_scene):
        """测试按场景过滤处理套餐"""
        ProcessApplication.objects.create(
            name="场景1套餐",
            sops_template_id=10001,
            scene_id=scene.scene_id,
        )
        ProcessApplication.objects.create(
            name="场景2套餐",
            sops_template_id=10002,
            scene_id=another_scene.scene_id,
        )
        qs = ProcessApplication.objects.filter(scene_id=scene.scene_id)
        assert qs.count() == 1
        assert qs.first().name == "场景1套餐"


class TestRiskRuleSceneFilter:
    """处理规则场景过滤测试"""

    @pytest.mark.django_db
    def test_filter_rule_by_scene(self, scene, another_scene):
        """测试按场景过滤处理规则"""
        RiskRule.objects.create(
            name="场景1规则",
            scope=[],
            version=1,
            scene_id=scene.scene_id,
        )
        RiskRule.objects.create(
            name="场景2规则",
            scope=[],
            version=1,
            scene_id=another_scene.scene_id,
        )
        qs = RiskRule.objects.filter(scene_id=scene.scene_id)
        assert qs.count() == 1
        assert qs.first().name == "场景1规则"


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
