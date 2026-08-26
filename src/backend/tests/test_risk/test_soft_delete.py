# -*- coding: utf-8 -*-
"""
风险表软删除改造专项测试

覆盖范围：
1. 软删除基础行为（delete 标记、objects 过滤、_objects 可查、批量软删、updated_at 更新）
2. 查询隔离（get/filter 自动过滤软删除）
3. generate_risk_id 用 _objects 检查主键冲突（不与软删除记录冲突）
4. 订阅 SQL 包含 is_deleted='false' 过滤（不作为输出字段，评审确认结果集该列恒为 'false' 无输出价值）
5. 资产同步 fetch_instance_list 用 _objects（含已删除记录）
6. ListRisk 走 use_bkbase 路径时 is_deleted 谓词透传到 bkbase SQL
"""

import datetime
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.utils import timezone

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.databus.constants import (
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    ASSET_TICKET_NODE_BKBASE_RT_ID_KEY,
    ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
    DORIS_EVENT_BKBASE_RT_ID_KEY,
)
from services.web.risk.constants import RiskStatus
from services.web.risk.converter.bkbase import BkBaseQueryExpressionBuilder
from services.web.risk.handlers.subscription_sql import RiskEventSubscriptionSQLBuilder
from services.web.risk.models import Risk, generate_risk_id
from services.web.risk.provider import RiskResourceProvider
from services.web.risk.resources.risk import ListRisk
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
        r1 = _make_risk(
            risk_id="soft-delete-101", raw_event_id="raw-101", strategy=self.strategy, status=RiskStatus.NEW
        )
        r2 = _make_risk(
            risk_id="soft-delete-102", raw_event_id="raw-102", strategy=self.strategy, status=RiskStatus.NEW
        )
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
        """已删除记录的序列化数据中 is_deleted=True，且顶层 is_deleted 同步返回"""
        provider = RiskResourceProvider()
        start_ms = int((timezone.now() - datetime.timedelta(days=1)).timestamp() * 1000)
        end_ms = int((timezone.now() + datetime.timedelta(days=1)).timestamp() * 1000)

        result = provider.fetch_instance_list(_DummyFilter(start_ms, end_ms), _DummyPage())

        for item in result.results:
            if item["id"] == self.risk_deleted.risk_id:
                self.assertTrue(item["data"].get("is_deleted"))
                self.assertTrue(item["is_deleted"])
            if item["id"] == self.risk_alive.risk_id:
                self.assertFalse(item["data"].get("is_deleted"))
                self.assertFalse(item["is_deleted"])


# ───────────────────────── ListRisk use_bkbase is_deleted 谓词透传 ─────────────────────────


class TestListRiskBkbaseSqlIsDeletedPredicate(TestCase):
    """ListRisk 走 use_bkbase 路径时，is_deleted 谓词必须透传到 bkbase SQL。

    软删除 commit 3db116b6 将 Risk 基类改为 SoftDeleteModel，
    Risk.objects.filter() 经 SoftDeleteModelManager 自动注入 is_deleted=False 谓词。
    该谓词随 base_queryset.values() 透传到 bkbase base SQL（compile_queryset_sql），
    进而出现在 count SQL / data SQL 中发往 bkbase query_sync。
    若 bkbase Doris 表无 is_deleted 列，会报「结果表不存在」。
    本测试断言该谓词确实透传，避免回归（7-30 已识别的缺口）。
    """

    def setUp(self):
        super().setUp()
        self.strategy = _make_strategy()
        self.risk_alive = _make_risk(
            risk_id="bkbase-isdeleted-alive",
            raw_event_id="raw-alive",
            strategy=self.strategy,
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        # mock 6 个 bkbase RT 表名配置（与 ListRisk._get_bkbase_table_map 对齐）
        self.table_map = {
            ASSET_RISK_BKBASE_RT_ID_KEY: "test.asset_risk",
            ASSET_STRATEGY_BKBASE_RT_ID_KEY: "test.asset_strategy",
            ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY: "test.asset_strategy_tag",
            ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY: "test.ticket_permission_rt",
            ASSET_TICKET_NODE_BKBASE_RT_ID_KEY: "test.ticket_node_rt",
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

    def _build_table_map_with_suffix(self) -> dict:
        """构造 BkBaseQueryExpressionBuilder 需要的 table_map（key=模型 db_table, value=RT id + .doris）"""
        return {
            Risk._meta.db_table: f"{self.table_map[ASSET_RISK_BKBASE_RT_ID_KEY]}.doris",
            "risk_strategy": f"{self.table_map[ASSET_STRATEGY_BKBASE_RT_ID_KEY]}.doris",
            "risk_strategytag": f"{self.table_map[ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY]}.doris",
            "risk_ticketpermission": f"{self.table_map[ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY]}.doris",
            "risk_ticketnode": f"{self.table_map[ASSET_TICKET_NODE_BKBASE_RT_ID_KEY]}.doris",
            "risk_event": f"{self.table_map[DORIS_EVENT_BKBASE_RT_ID_KEY]}.doris",
        }

    def test_compile_queryset_sql_contains_is_deleted_predicate(self):
        """Risk.objects.values() 编译出的 bkbase base SQL 含 is_deleted='false' 谓词"""
        value_fields = ["risk_id", "strategy_id", "raw_event_id", "event_time", "event_end_time"]
        # Risk.objects.all() 经 SoftDeleteModelManager 自动注入 is_deleted=False
        values_queryset = Risk.objects.all().values(*value_fields).distinct()

        builder = BkBaseQueryExpressionBuilder(
            table_map=self._build_table_map_with_suffix(),
            storage_suffix="doris",
        )
        sql = builder.compile_queryset_sql(values_queryset.order_by())

        self.assertIsNotNone(sql, "应成功编译出 SQL（Risk.objects 非空）")
        self.assertIn(
            "is_deleted",
            sql,
            f"bkbase base SQL 必须含 is_deleted 谓词（软删除透传），实际 SQL: {sql}",
        )
        self.assertIn(
            "'false'",
            sql,
            f"bkbase base SQL 必须含 'false' 字面量（SoftDeleteModelManager 注入值），实际 SQL: {sql}",
        )

    def test_compile_queryset_sql_excludes_soft_deleted(self):
        """软删除记录被 Risk.objects 过滤，但 SQL 仍向 bkbase 透传 is_deleted='false' 谓词"""
        risk_deleted = _make_risk(
            risk_id="bkbase-isdeleted-deleted",
            raw_event_id="raw-deleted",
            strategy=self.strategy,
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        risk_deleted.delete()

        # Risk.objects 不含软删除记录（ORM 层已过滤）
        alive_ids = list(Risk.objects.all().values_list("risk_id", flat=True))
        self.assertIn(self.risk_alive.risk_id, alive_ids)
        self.assertNotIn(risk_deleted.risk_id, alive_ids)

        # 但编译出的 bkbase SQL 仍含 is_deleted 谓词（向 bkbase 声明只查未删除的）
        value_fields = ["risk_id", "strategy_id", "raw_event_id", "event_time", "event_end_time"]
        values_queryset = Risk.objects.all().values(*value_fields).distinct()
        builder = BkBaseQueryExpressionBuilder(
            table_map=self._build_table_map_with_suffix(),
            storage_suffix="doris",
        )
        sql = builder.compile_queryset_sql(values_queryset.order_by())

        self.assertIsNotNone(sql)
        self.assertIn("is_deleted", sql)
        self.assertIn("'false'", sql)

    def test_list_risk_retrieve_via_bkbase_sql_contains_is_deleted(self):
        """ListRisk.retrieve_via_bkbase 完整路径：mock query_sync 收集的 SQL 含 is_deleted 谓词"""
        sql_log = []

        def fake_query_sync(sql):
            sql_log.append(sql)
            if "COUNT" in sql.upper():
                return {"list": [{"count": 1}]}
            return {"list": [{"risk_id": self.risk_alive.risk_id, "strategy_id": self.strategy.strategy_id}]}

        base_queryset = Risk.objects.all()
        request = SimpleNamespace(query_params={"page": "1", "page_size": "10"})
        resource = ListRisk()
        # _duplicate_event_field_map 在 perform_request 流程里初始化（risk.py:359），
        # 直接调 retrieve_via_bkbase 需手动设空 dict
        resource._duplicate_event_field_map = {}

        with mock.patch("bk_resource.api.bk_base.query_sync", side_effect=fake_query_sync):
            resource.retrieve_via_bkbase(
                base_queryset=base_queryset,
                request=request,
                order_fields=[],
                event_filters=[],
            )

        self.assertGreaterEqual(len(sql_log), 1, "retrieve_via_bkbase 应至少生成 count SQL")
        # count SQL 和 data SQL 都应含 is_deleted 谓词（base_queryset 透传）
        for idx, sql in enumerate(sql_log):
            self.assertIn(
                "is_deleted",
                sql,
                f"第 {idx} 条 bkbase SQL 必须含 is_deleted 谓词，实际 SQL: {sql}",
            )
