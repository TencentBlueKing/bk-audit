# -*- coding: utf-8 -*-
"""
风险表软删除改造专项测试

覆盖范围：
1. 软删除基础行为（delete 标记、objects 过滤、_objects 可查、批量软删、updated_at 更新）
2. 查询隔离（get/filter 自动过滤软删除）
3. generate_risk_id 用 _objects 检查主键冲突（不与软删除记录冲突）
4. 订阅 SQL 包含 is_deleted='false' 过滤 + 字段配置含 is_deleted
5. 资产同步 fetch_instance_list 用 _objects（含已删除记录）
"""

import datetime

from django.conf import settings
from django.utils import timezone

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    DORIS_EVENT_BKBASE_RT_ID_KEY,
)
from services.web.risk.constants import RiskStatus
from services.web.risk.handlers.subscription_sql import RiskEventSubscriptionSQLBuilder
from services.web.risk.models import Risk, generate_risk_id
from services.web.risk.provider import RiskResourceProvider
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


def _make_strategy(name: str = "soft-delete-test-strategy") -> Strategy:
    return Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name=name)


def _make_risk(
    *,
    risk_id: str,
    raw_event_id: str,
    strategy: Strategy,
    status: str = RiskStatus.NEW,
    event_time: datetime.datetime | None = None,
) -> Risk:
    return Risk.objects.create(
        risk_id=risk_id,
        raw_event_id=raw_event_id,
        strategy=strategy,
        status=status,
        event_time=event_time or timezone.now(),
    )


# ───────────────────────── 软删除基础行为 ─────────────────────────


class TestSoftDeleteBasic(TestCase):
    """软删除基础测试"""

    def setUp(self):
        super().setUp()
        self.strategy = _make_strategy()
        self.risk = _make_risk(risk_id="soft-delete-001", raw_event_id="raw-001", strategy=self.strategy)

    def test_delete_marks_is_deleted(self):
        """删除后 is_deleted=True，objects 查不到，_objects 能查到"""
        risk_id = self.risk.risk_id
        self.risk.delete()

        self.assertFalse(Risk.objects.filter(risk_id=risk_id).exists())
        self.assertTrue(Risk._objects.filter(risk_id=risk_id, is_deleted=True).exists())

    def test_objects_excludes_deleted(self):
        """objects 自动过滤软删除记录"""
        r1 = _make_risk(risk_id="soft-delete-002", raw_event_id="raw-002", strategy=self.strategy)
        r2 = _make_risk(risk_id="soft-delete-003", raw_event_id="raw-003", strategy=self.strategy)
        r1.delete()

        risk_ids = list(Risk.objects.all().values_list("risk_id", flat=True))
        self.assertIn(r2.risk_id, risk_ids)
        self.assertNotIn(r1.risk_id, risk_ids)

    def test_bulk_delete_is_soft(self):
        """批量删除也是软删除（UPDATE is_deleted=True，而非 DELETE FROM）"""
        _make_risk(risk_id="soft-delete-004", raw_event_id="raw-004", strategy=self.strategy)
        _make_risk(risk_id="soft-delete-005", raw_event_id="raw-005", strategy=self.strategy)

        # 删除前数据库里的总记录数（含可能的历史软删除）
        before_total = Risk._objects.all().count()
        Risk.objects.filter(risk_id__in=["soft-delete-004", "soft-delete-005"]).delete()

        # 软删除后 _objects 总数不变（记录仍在），且这两条标记为已删除
        after_total = Risk._objects.all().count()
        self.assertEqual(before_total, after_total)
        self.assertEqual(
            Risk._objects.filter(risk_id__in=["soft-delete-004", "soft-delete-005"], is_deleted=True).count(), 2
        )

    def test_delete_updates_timestamp(self):
        """删除时 updated_at 被刷新（update_fields=["is_deleted"] + 自动追加 updated_at/updated_by）"""
        risk = _make_risk(risk_id="soft-delete-006", raw_event_id="raw-006", strategy=self.strategy)
        old_updated_at = risk.updated_at
        # 确保时间向前推进
        risk.delete()

        fresh = Risk._objects.get(risk_id="soft-delete-006")
        self.assertIsNotNone(fresh.updated_at)
        self.assertTrue(fresh.is_deleted)
        if old_updated_at:
            self.assertGreaterEqual(fresh.updated_at, old_updated_at)


# ───────────────────────── 查询隔离 ─────────────────────────


class TestQueryIsolation(TestCase):
    """查询隔离测试"""

    def setUp(self):
        super().setUp()
        self.strategy = _make_strategy()

    def test_get_raises_for_deleted(self):
        """get 查不到软删除记录，抛 DoesNotExist"""
        risk = _make_risk(risk_id="soft-delete-100", raw_event_id="raw-100", strategy=self.strategy)
        risk.delete()
        with self.assertRaises(Risk.DoesNotExist):
            Risk.objects.get(risk_id="soft-delete-100")

    def test_filter_excludes_deleted(self):
        """filter 自动过滤软删除"""
        r1 = _make_risk(risk_id="soft-delete-101", raw_event_id="raw-101", strategy=self.strategy, status=RiskStatus.NEW)
        r2 = _make_risk(risk_id="soft-delete-102", raw_event_id="raw-102", strategy=self.strategy, status=RiskStatus.NEW)
        r1.delete()

        risks = list(Risk.objects.filter(status=RiskStatus.NEW).values_list("risk_id", flat=True))
        self.assertIn(r2.risk_id, risks)
        self.assertNotIn(r1.risk_id, risks)

    def test_objects_all_with_is_deleted_true_can_query(self):
        """显式传 is_deleted=True 可绕过默认过滤，查到软删除记录"""
        risk = _make_risk(risk_id="soft-delete-103", raw_event_id="raw-103", strategy=self.strategy)
        risk.delete()

        self.assertTrue(Risk.objects.filter(risk_id="soft-delete-103", is_deleted=True).exists())


# ───────────────────────── generate_risk_id ─────────────────────────


class TestGenerateRiskId(TestCase):
    """风险 ID 生成测试"""

    def setUp(self):
        super().setUp()
        self.strategy = _make_strategy()

    def test_generate_risk_id_format(self):
        """generate_risk_id 返回符合格式的 ID（14位时间 + 6位微秒，共20位数字）"""
        new_id = generate_risk_id()
        self.assertEqual(len(new_id), 20)
        self.assertTrue(new_id.isdigit())
        # 校验时间前缀对应当前日期（YYYYMMDD）
        self.assertTrue(new_id.startswith(datetime.datetime.now().strftime("%Y%m%d")))

    def test_no_collision_with_deleted(self):
        """generate_risk_id 用 _objects 检查，不与软删除记录的主键冲突"""
        risk = _make_risk(risk_id="soft-delete-200", raw_event_id="raw-200", strategy=self.strategy)
        risk.delete()
        # 软删除后该 risk_id 仍在数据库（_objects 可查），generate_risk_id 不会生成相同 ID
        new_id = generate_risk_id()
        self.assertFalse(Risk._objects.filter(risk_id=new_id).exists())
        self.assertNotEqual(new_id, "soft-delete-200")


# ───────────────────────── 订阅 SQL ─────────────────────────


class TestSubscriptionSQLSoftDelete(TestCase):
    """订阅 SQL 软删除过滤测试"""

    TIME_RANGE = (1000000000000, 1000000099999)

    def setUp(self):
        super().setUp()
        self.table_map = {
            ASSET_RISK_BKBASE_RT_ID_KEY: "test.asset_risk",
            ASSET_STRATEGY_BKBASE_RT_ID_KEY: "test.asset_strategy",
            ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY: "test.asset_strategy_tag",
            DORIS_EVENT_BKBASE_RT_ID_KEY: "test.event_rt",
        }
        for key, value in self.table_map.items():
            GlobalMetaConfig.set(
                config_key=key,
                config_value=value,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=settings.DEFAULT_NAMESPACE,
            )

    def tearDown(self):
        GlobalMetaConfig.objects.filter(config_key__in=self.table_map.keys()).delete()
        super().tearDown()

    def test_sql_contains_is_deleted_filter(self):
        """生成的内层 SQL 包含 r.is_deleted='false' 过滤"""
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=settings.DEFAULT_NAMESPACE,
            time_range=self.TIME_RANGE,
        )
        inner_sql = builder._base_subquery
        self.assertIn("is_deleted", inner_sql)
        self.assertIn("'false'", inner_sql)

    def test_field_config_includes_is_deleted(self):
        """字段配置包含 is_deleted"""
        field_names = [c.name for c in RiskEventSubscriptionSQLBuilder.INNER_FIELD_CONFIG]
        self.assertIn("is_deleted", field_names)

    def test_is_deleted_field_display_name_prefixed(self):
        """is_deleted 字段展示名带 risk_ 前缀，避免与 event 级字段冲突"""
        config = next(c for c in RiskEventSubscriptionSQLBuilder.INNER_FIELD_CONFIG if c.name == "is_deleted")
        self.assertEqual(config.display_name, "risk_is_deleted")

    def test_build_query_sql_contains_is_deleted(self):
        """完整查询 SQL 包含 is_deleted 过滤条件"""
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=settings.DEFAULT_NAMESPACE,
            time_range=self.TIME_RANGE,
        )
        sql = builder.build_query_sql(limit=10, offset=0)
        self.assertIn("`r`.`is_deleted`='false'", sql)


# ───────────────────────── 资产同步 fetch_instance_list ─────────────────────────


class _DummyFilter:
    """模拟 IAM fetch filter，提供 start_time/end_time 毫秒时间戳"""

    def __init__(self, start_ms: int, end_ms: int):
        self.start_time = start_ms
        self.end_time = end_ms


class _DummyPage:
    """模拟 IAM Page，slice_from/slice_to 控制分页窗口"""

    def __init__(self, slice_from: int = 0, slice_to: int = 1000):
        self.slice_from = slice_from
        self.slice_to = slice_to


class TestFetchInstanceListIncludesDeleted(TestCase):
    """资产同步 fetch_instance_list 用 _objects，已删除记录也同步到 Doris"""

    def setUp(self):
        super().setUp()
        self.strategy = _make_strategy()
        base = timezone.now()
        self.risk_alive = _make_risk(
            risk_id="provider-alive",
            raw_event_id="raw-alive",
            strategy=self.strategy,
            event_time=base,
        )
        self.risk_deleted = _make_risk(
            risk_id="provider-deleted",
            raw_event_id="raw-deleted",
            strategy=self.strategy,
            event_time=base,
        )
        self.risk_deleted.delete()

    def test_fetch_instance_list_includes_deleted_risk(self):
        """fetch_instance_list 结果包含已软删除的 Risk（使 Doris is_deleted 同步为 'true'）"""
        provider = RiskResourceProvider()
        # 时间窗口覆盖 updated_at（软删除会刷新 updated_at）
        start_ms = int((timezone.now() - datetime.timedelta(days=1)).timestamp() * 1000)
        end_ms = int((timezone.now() + datetime.timedelta(days=1)).timestamp() * 1000)

        result = provider.fetch_instance_list(_DummyFilter(start_ms, end_ms), _DummyPage())

        risk_ids = {item["id"] for item in result.results}
        self.assertIn(self.risk_alive.risk_id, risk_ids)
        self.assertIn(self.risk_deleted.risk_id, risk_ids)

    def test_fetch_instance_list_deleted_risk_is_deleted_true(self):
        """已删除记录的序列化数据中 is_deleted=True"""
        provider = RiskResourceProvider()
        start_ms = int((timezone.now() - datetime.timedelta(days=1)).timestamp() * 1000)
        end_ms = int((timezone.now() + datetime.timedelta(days=1)).timestamp() * 1000)

        result = provider.fetch_instance_list(_DummyFilter(start_ms, end_ms), _DummyPage())

        for item in result.results:
            if item["id"] == self.risk_deleted.risk_id:
                self.assertTrue(item["data"].get("is_deleted"))
            if item["id"] == self.risk_alive.risk_id:
                self.assertFalse(item["data"].get("is_deleted"))
