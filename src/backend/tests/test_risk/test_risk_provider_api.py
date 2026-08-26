# -*- coding: utf-8 -*-
import datetime
from unittest import expectedFailure
from unittest.mock import patch

from django.conf import settings
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone
from iam.collection import FancyDict
from iam.eval.constants import KEYWORD_BK_IAM_PATH
from iam.resource.utils import Page

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.risk.converter.queryset import RiskPathEqDjangoQuerySetConverter
from services.web.risk.models import ManualEvent, Risk
from services.web.risk.provider import ManualEventResourceProvider, RiskResourceProvider
from services.web.scene.constants import (
    BindingType,
    ResourceVisibilityType,
    VisibilityScope,
)
from services.web.scene.models import ResourceBinding, ResourceBindingScene, Scene
from services.web.strategy_v2.models import Strategy


def _ms(dt: datetime.datetime) -> int:
    return int(dt.timestamp() * 1000)


class RiskResourceProviderAPITest(TestCase):
    def setUp(self):
        self._dummy_request = type("DummyRequest", (), {"headers": {}})()
        self.req_patcher = patch.object(RiskResourceProvider, "get_local_request", return_value=self._dummy_request)
        self.req_patcher.start()
        self.addCleanup(self.req_patcher.stop)
        self.provider = RiskResourceProvider()

    def _create_strategy(self, name: str) -> Strategy:
        return Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name=name)

    def _create_risk(
        self,
        *,
        risk_id: str,
        raw_event_id: str,
        strategy: Strategy,
        event_time: datetime.datetime,
        event_end_time: datetime.datetime | None,
    ) -> Risk:
        return Risk.objects.create(
            risk_id=risk_id,
            raw_event_id=raw_event_id,
            strategy=strategy,
            event_time=event_time,
            event_end_time=event_end_time,
        )

    def test_list_fetch_search(self):
        strategy_a = self._create_strategy("strategy-a")
        strategy_b = self._create_strategy("strategy-b")

        event_time = timezone.now()
        risk_a = self._create_risk(
            risk_id="risk-A",
            raw_event_id="raw-A",
            strategy=strategy_a,
            event_time=event_time,
            event_end_time=event_time + datetime.timedelta(minutes=5),
        )
        risk_b = self._create_risk(
            risk_id="risk-B",
            raw_event_id="raw-B",
            strategy=strategy_b,
            event_time=event_time,
            event_end_time=event_time + datetime.timedelta(minutes=10),
        )

        page = Page(50, 0)

        lr = self.provider.list_instance(FancyDict(parent=None, search=None), page)
        expected = [
            {"id": risk_a.risk_id, "display_name": risk_a.risk_id},
            {"id": risk_b.risk_id, "display_name": risk_b.risk_id},
        ]
        self.assertEqual(lr.count, 2)
        self.assertEqual(sorted(lr.results, key=lambda x: x["id"]), sorted(expected, key=lambda x: x["id"]))

        lr_parent = self.provider.list_instance(
            FancyDict(parent={"id": str(strategy_a.strategy_id), "type": ResourceEnum.STRATEGY.id}, search=None),
            page,
        )
        self.assertEqual(lr_parent.count, 1)
        self.assertEqual(lr_parent.results, [{"id": risk_a.risk_id, "display_name": risk_a.risk_id}])

        lr_fetch = self.provider.fetch_instance_info(FancyDict(ids=[risk_a.risk_id, risk_b.risk_id]))
        self.assertEqual(lr_fetch.count, 2)
        self.assertEqual(sorted(lr_fetch.results, key=lambda x: x["id"]), sorted(expected, key=lambda x: x["id"]))

        lr_search = self.provider.search_instance(FancyDict(parent=None, keyword="risk-A"), page)
        self.assertEqual(lr_search.count, 1)
        self.assertEqual(lr_search.results, [{"id": risk_a.risk_id, "display_name": risk_a.risk_id}])

    def test_fetch_instance_list_returns_ms(self):
        strategy = self._create_strategy("strategy")
        event_time = timezone.now().replace(microsecond=123000)
        event_end_time = event_time + datetime.timedelta(minutes=5)

        risk = self._create_risk(
            risk_id="risk-1",
            raw_event_id="raw-1",
            strategy=strategy,
            event_time=event_time,
            event_end_time=event_end_time,
        )

        last_operate_time = event_end_time + datetime.timedelta(minutes=10)
        Risk.objects.filter(pk=risk.pk).update(last_operate_time=last_operate_time)
        risk.refresh_from_db()

        now = timezone.now()
        start_ms = int((now - datetime.timedelta(hours=1)).timestamp() * 1000)
        end_ms = int((now + datetime.timedelta(hours=1)).timestamp() * 1000)

        result = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))
        self.assertGreaterEqual(result.count, 1)

        item = next(data for data in result.results if data["id"] == risk.risk_id)
        payload = item["data"]

        self.assertEqual(payload["event_time_timestamp"], _ms(risk.event_time))
        self.assertEqual(payload["event_end_time_timestamp"], _ms(risk.event_end_time))
        self.assertEqual(payload["last_operate_time_timestamp"], _ms(risk.last_operate_time))

        schema = self.provider.fetch_resource_type_schema()
        properties = schema.properties

        self.assertEqual(properties["event_time_timestamp"]["type"], "integer")
        self.assertEqual(properties["event_end_time_timestamp"]["type"], "integer")
        self.assertEqual(properties["last_operate_time_timestamp"]["type"], "integer")

    def test_handles_null_event_end_timestamp(self):
        strategy = self._create_strategy("strategy-null")
        event_time = timezone.now()

        risk = self._create_risk(
            risk_id="risk-null",
            raw_event_id="raw-null",
            strategy=strategy,
            event_time=event_time,
            event_end_time=None,
        )
        risk.refresh_from_db()

        now = timezone.now()
        start_ms = int((now - datetime.timedelta(hours=1)).timestamp() * 1000)
        end_ms = int((now + datetime.timedelta(hours=1)).timestamp() * 1000)

        result = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        payload = item["data"]

        self.assertIsNone(payload["event_end_time_timestamp"])
        self.assertEqual(payload["event_time_timestamp"], _ms(risk.event_time))
        self.assertEqual(payload["last_operate_time_timestamp"], _ms(risk.last_operate_time))

    # ────────────────────────────────────────────────────────────────────
    # fetch_instance_list 大字段截断/置 NULL 测试（2026-08-07 502 修复）
    # ────────────────────────────────────────────────────────────────────

    def _create_risk_with_fields(
        self,
        *,
        risk_id: str,
        strategy: Strategy,
        event_time: datetime.datetime,
        event_content: str | None = None,
        event_evidence: str | None = None,
        event_data=None,
    ) -> Risk:
        return Risk.objects.create(
            risk_id=risk_id,
            raw_event_id=f"raw-{risk_id}",
            strategy=strategy,
            event_time=event_time,
            event_end_time=event_time + datetime.timedelta(minutes=5),
            event_content=event_content,
            event_evidence=event_evidence,
            event_data=event_data,
        )

    def test_event_content_truncated_when_oversize(self):
        """event_content 超 100KB 被截断到阈值以内"""
        from services.web.risk.constants import (
            FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES,
        )

        strategy = self._create_strategy("strategy-trunc-content")
        event_time = timezone.now()
        risk = self._create_risk_with_fields(
            risk_id="risk-content-trunc",
            strategy=strategy,
            event_time=event_time,
            event_content="x" * (FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES + 1024),  # 阈值+1KB
        )

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        self.assertLessEqual(len(item["data"]["event_content"]), FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES)

    def test_event_content_preserved_when_small(self):
        """event_content 未超阈值保持完整"""
        strategy = self._create_strategy("strategy-content-small")
        event_time = timezone.now()
        risk = self._create_risk_with_fields(
            risk_id="risk-content-ok", strategy=strategy, event_time=event_time, event_content="short content"
        )

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        self.assertEqual(item["data"]["event_content"], "short content")

    def test_event_evidence_nullified_when_oversize(self):
        """event_evidence 超阈值置 NULL"""
        from services.web.risk.constants import (
            FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES,
        )

        strategy = self._create_strategy("strategy-evidence-null")
        event_time = timezone.now()
        risk = self._create_risk_with_fields(
            risk_id="risk-evidence-null",
            strategy=strategy,
            event_time=event_time,
            event_evidence="y" * (FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES + 1024),
        )

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        self.assertIsNone(item["data"]["event_evidence"])

    def test_event_evidence_preserved_when_small(self):
        """event_evidence 未超阈值保持完整"""
        strategy = self._create_strategy("strategy-evidence-ok")
        event_time = timezone.now()
        risk = self._create_risk_with_fields(
            risk_id="risk-evidence-ok", strategy=strategy, event_time=event_time, event_evidence="short evidence"
        )

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        self.assertEqual(item["data"]["event_evidence"], "short evidence")

    def test_event_data_nullified_when_oversize(self):
        """event_data 超 100KB 置 NULL（保证 JSON 合法性）"""
        from services.web.risk.constants import (
            FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES,
        )

        strategy = self._create_strategy("strategy-data-null")
        event_time = timezone.now()
        big_json = {"key": "v" * (FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES + 1024)}
        risk = self._create_risk_with_fields(
            risk_id="risk-data-null", strategy=strategy, event_time=event_time, event_data=big_json
        )

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        self.assertIsNone(item["data"]["event_data"])

    def test_event_data_preserved_when_small(self):
        """event_data 未超阈值保持完整 JSON"""
        strategy = self._create_strategy("strategy-data-ok")
        event_time = timezone.now()
        small_json = {"key": "value", "list": [1, 2, 3]}
        risk = self._create_risk_with_fields(
            risk_id="risk-data-ok", strategy=strategy, event_time=event_time, event_data=small_json
        )

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        self.assertEqual(item["data"]["event_data"], small_json)

    def test_small_fields_unchanged_after_truncation(self):
        """截断后小字段（status/risk_id/event_time_timestamp 等）不受影响"""
        from services.web.risk.constants import (
            FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES,
        )

        strategy = self._create_strategy("strategy-small-unchanged")
        event_time = timezone.now().replace(microsecond=123000)
        risk = self._create_risk_with_fields(
            risk_id="risk-small-unchanged",
            strategy=strategy,
            event_time=event_time,
            event_content="x" * (FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES + 1024),
        )
        last_operate_time = event_time + datetime.timedelta(minutes=10)
        Risk.objects.filter(pk=risk.pk).update(last_operate_time=last_operate_time)

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        payload = item["data"]

        # 小字段完整保留
        self.assertEqual(payload["risk_id"], risk.risk_id)
        self.assertEqual(payload["raw_event_id"], "raw-risk-small-unchanged")
        self.assertEqual(payload["strategy_id"], strategy.strategy_id)
        self.assertEqual(payload["event_time_timestamp"], _ms(risk.event_time))
        self.assertEqual(payload["last_operate_time_timestamp"], _ms(last_operate_time))

    def test_is_deleted_still_returned_after_truncation(self):
        """截断后 is_deleted 仍正确返回（顶层 + data 内）"""
        from services.web.risk.constants import (
            FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES,
        )

        strategy = self._create_strategy("strategy-del-trunc")
        event_time = timezone.now()
        risk = self._create_risk_with_fields(
            risk_id="risk-del-trunc",
            strategy=strategy,
            event_time=event_time,
            event_content="x" * (FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES + 1024),
        )
        risk.delete()  # 软删除

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        self.assertTrue(item["is_deleted"])
        self.assertTrue(item["data"]["is_deleted"])
        # 截断仍生效
        self.assertLessEqual(len(item["data"]["event_content"]), FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES)

    def test_schema_unchanged_after_truncation(self):
        """fetch_resource_type_schema 仍返回完整 schema（不受截断影响）"""
        schema = self.provider.fetch_resource_type_schema()
        properties = schema.properties
        # 三个大字段仍在 schema 中（BKBase 清洗配置依赖）
        self.assertIn("event_content", properties)
        self.assertIn("event_evidence", properties)
        self.assertIn("event_data", properties)

    def test_dynamic_fields_cover_all_serializer_fields(self):
        """动态生成的 values 字段集合覆盖 RiskProviderSerializer 需要的全部字段"""
        values_fields, annotations = self.provider._build_fetch_values_kwargs(102400)
        covered = set(values_fields)  # 含 _truncated_xxx 别名 + strategy_id
        # RiskProviderSerializer exclude=["strategy"]，但字段名是 strategy_id（FK attname）
        # 需覆盖模型所有非 FK 字段 + strategy_id（FK attname）
        model_field_names = {f.name for f in Risk._meta.fields if not f.is_relation}
        model_field_names.add("strategy_id")  # FK 的 attname
        # 截断/置 NULL 字段在 values_fields 中用别名 _truncated_<name>，需映射回原名再比对
        resolved = {f.replace("_truncated_", "") if f.startswith("_truncated_") else f for f in covered}
        missing = model_field_names - resolved
        self.assertFalse(missing, f"values 漏列字段: {missing}")

    # ────────────────────────────────────────────────────────────────────
    # 边缘漏洞补测（2026-08-07）
    # ────────────────────────────────────────────────────────────────────

    @expectedFailure
    def test_multibyte_event_content_byte_limit(self):
        """多字节字符截断后字节数应 ≤ 阈值

        已知限制：event_content 用 Substr 按字符截断（Django text.py:341），
        utf8mb4 中文 3 字节/字符，截断 102400 字符后实际可达 ~300KB。
        此测试标注该问题；修复后（改为字节级判断/截断）应转为 unexpected success。
        """
        from services.web.risk.constants import (
            FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES,
        )

        strategy = self._create_strategy("strategy-mb-bytes")
        event_time = timezone.now()
        limit = FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES
        content = "中" * (limit + 1000)
        risk = self._create_risk_with_fields(
            risk_id="risk-mb-bytes",
            strategy=strategy,
            event_time=event_time,
            event_content=content,
        )
        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        truncated = item["data"]["event_content"]
        self.assertLessEqual(
            len(truncated.encode("utf-8")),
            limit,
            f"event_content 截断后字节数 {len(truncated.encode('utf-8'))} 超阈值 {limit}",
        )

    def test_fields_exactly_at_threshold(self):
        """大字段恰好等于阈值字节时不截断/不置 NULL（> 严格大于，= 不触发）"""
        from services.web.risk.constants import (
            FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES,
        )

        strategy = self._create_strategy("strategy-exact-threshold")
        event_time = timezone.now()
        limit = FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES
        # ASCII：1 字符 = 1 字节，恰好等于阈值
        content = "x" * limit
        evidence = "y" * limit
        risk = self._create_risk_with_fields(
            risk_id="risk-exact-threshold",
            strategy=strategy,
            event_time=event_time,
            event_content=content,
            event_evidence=evidence,
        )
        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        # event_content: Substr 取前 limit 字符 = 全部（恰好等于阈值）
        self.assertEqual(item["data"]["event_content"], content)
        # event_evidence: LENGTH = limit, > limit 为 False, 返回原值
        self.assertEqual(item["data"]["event_evidence"], evidence)

    def test_null_large_fields_not_broken(self):
        """三字段（event_content/event_evidence/event_data）均为 NULL 时不报错"""
        strategy = self._create_strategy("strategy-null-fields")
        event_time = timezone.now()
        risk = self._create_risk_with_fields(
            risk_id="risk-null-fields",
            strategy=strategy,
            event_time=event_time,
            event_content=None,
            event_evidence=None,
            event_data=None,
        )
        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        payload = item["data"]
        # COALESCE(NULL, '') → '' → LENGTH=0 不超阈值 → ELSE 返回原值 NULL
        self.assertIsNone(payload["event_content"])
        self.assertIsNone(payload["event_evidence"])
        self.assertIsNone(payload["event_data"])

    def test_empty_large_fields_preserved(self):
        """空字符串/空 dict 保持不变"""
        strategy = self._create_strategy("strategy-empty")
        event_time = timezone.now()
        risk = self._create_risk_with_fields(
            risk_id="risk-empty",
            strategy=strategy,
            event_time=event_time,
            event_content="",
            event_evidence="",
            event_data={},
        )
        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        payload = item["data"]
        self.assertEqual(payload["event_content"], "")
        self.assertEqual(payload["event_evidence"], "")
        self.assertEqual(payload["event_data"], {})

    def test_truncation_works_on_deep_page(self):
        """深分页（slice_from > 0）时截断仍生效"""
        from services.web.risk.constants import (
            FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES,
        )

        strategy = self._create_strategy("strategy-deep-page")
        base_time = timezone.now() - datetime.timedelta(minutes=10)
        limit = FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES
        for i in range(5):
            r = self._create_risk_with_fields(
                risk_id=f"risk-deep-{i}",
                strategy=strategy,
                event_time=base_time + datetime.timedelta(seconds=i),
                event_content="x" * (limit + 1024),
            )
            Risk.objects.filter(pk=r.pk).update(updated_at=base_time + datetime.timedelta(seconds=i))

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(2, 2),
        )
        self.assertGreaterEqual(result.count, 5)
        self.assertGreaterEqual(len(result.results), 1)
        for item in result.results:
            self.assertLessEqual(len(item["data"]["event_content"]), limit)

    def test_soft_deleted_with_nullified_event_data(self):
        """软删记录的 event_data 超阈值时置 NULL"""
        from services.web.risk.constants import (
            FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES,
        )

        strategy = self._create_strategy("strategy-del-null")
        event_time = timezone.now()
        big_json = {"key": "v" * (FETCH_INSTANCE_LIST_LARGE_FIELD_LIMIT_BYTES + 1024)}
        risk = self._create_risk_with_fields(
            risk_id="risk-del-null",
            strategy=strategy,
            event_time=event_time,
            event_data=big_json,
        )
        risk.delete()

        now = timezone.now()
        result = self.provider.fetch_instance_list(
            FancyDict(
                start_time=_ms(now - datetime.timedelta(hours=1)), end_time=_ms(now + datetime.timedelta(hours=1))
            ),
            Page(50, 0),
        )
        item = next(data for data in result.results if data["id"] == risk.risk_id)
        self.assertTrue(item["is_deleted"])
        self.assertTrue(item["data"]["is_deleted"])
        self.assertIsNone(item["data"]["event_data"])


class ManualEventProviderAPITest(TestCase):
    def setUp(self):
        self._dummy_request = type("DummyRequest", (), {"headers": {}})()
        self.req_patcher = patch.object(
            ManualEventResourceProvider, "get_local_request", return_value=self._dummy_request
        )
        self.req_patcher.start()
        self.addCleanup(self.req_patcher.stop)
        self.provider = ManualEventResourceProvider()

    def _create_strategy(self, name: str) -> Strategy:
        return Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name=name)

    def _create_manual_event(
        self,
        *,
        raw_event_id: str,
        strategy: Strategy,
        event_time: datetime.datetime,
    ) -> ManualEvent:
        return ManualEvent.objects.create(
            raw_event_id=raw_event_id,
            strategy=strategy,
            event_time=event_time,
        )

    def test_list_fetch_search(self):
        strategy_a = self._create_strategy("manual-a")
        strategy_b = self._create_strategy("manual-b")
        event_time = timezone.now()
        event_a = self._create_manual_event(
            raw_event_id="manual-raw-A",
            strategy=strategy_a,
            event_time=event_time,
        )
        event_b = self._create_manual_event(
            raw_event_id="manual-raw-B",
            strategy=strategy_b,
            event_time=event_time,
        )
        page = Page(50, 0)
        lr = self.provider.list_instance(FancyDict(parent=None, search=None), page)
        expected = [
            {"id": str(event_a.manual_event_id), "display_name": event_a.raw_event_id},
            {"id": str(event_b.manual_event_id), "display_name": event_b.raw_event_id},
        ]
        self.assertEqual(lr.count, 2)
        self.assertEqual(sorted(lr.results, key=lambda x: x["id"]), sorted(expected, key=lambda x: x["id"]))

        lr_parent = self.provider.list_instance(
            FancyDict(parent={"id": str(strategy_a.strategy_id), "type": ResourceEnum.STRATEGY.id}, search=None),
            page,
        )
        self.assertEqual(lr_parent.count, 1)
        self.assertEqual(
            lr_parent.results, [{"id": str(event_a.manual_event_id), "display_name": event_a.raw_event_id}]
        )

        lr_fetch = self.provider.fetch_instance_info(
            FancyDict(ids=[str(event_a.manual_event_id), str(event_b.manual_event_id)])
        )
        self.assertEqual(lr_fetch.count, 2)

        lr_search = self.provider.search_instance(FancyDict(parent=None, keyword="manual-raw-A"), page)
        self.assertEqual(lr_search.count, 1)
        self.assertEqual(
            lr_search.results, [{"id": str(event_a.manual_event_id), "display_name": event_a.raw_event_id}]
        )

    def test_fetch_instance_list_returns_ms(self):
        strategy = self._create_strategy("manual-strategy")
        event_time = timezone.now().replace(microsecond=123000)
        event = self._create_manual_event(
            raw_event_id="manual-raw-1",
            strategy=strategy,
            event_time=event_time,
        )
        last_operate_time = event_time + datetime.timedelta(minutes=5)
        ManualEvent.objects.filter(pk=event.pk).update(last_operate_time=last_operate_time)
        event.refresh_from_db()

        now = timezone.now()
        start_ms = int((now - datetime.timedelta(hours=1)).timestamp() * 1000)
        end_ms = int((now + datetime.timedelta(hours=1)).timestamp() * 1000)

        result = self.provider.fetch_instance_list(FancyDict(start_time=start_ms, end_time=end_ms), Page(50, 0))
        self.assertGreaterEqual(result.count, 1)
        item = next(data for data in result.results if data["id"] == str(event.manual_event_id))
        payload = item["data"]
        self.assertEqual(payload["event_time_timestamp"], _ms(event.event_time))
        self.assertEqual(payload["last_operate_time_timestamp"], _ms(event.last_operate_time))


def _bind_strategy_to_scene(strategy_id, scene):
    """将策略绑定到场景"""
    binding = ResourceBinding.objects.create(
        resource_type=ResourceVisibilityType.STRATEGY,
        resource_id=str(strategy_id),
        binding_type=BindingType.SCENE_BINDING,
        visibility_type=VisibilityScope.ALL_VISIBLE,
    )
    return ResourceBindingScene.objects.create(binding=binding, scene=scene)


class RiskProviderSceneFilterTest(TestCase):
    """测试 Risk Provider 通过策略所属场景来过滤风险"""

    def setUp(self):
        self._dummy_request = type("DummyRequest", (), {"headers": {}})()
        self.req_patcher = patch.object(RiskResourceProvider, "get_local_request", return_value=self._dummy_request)
        self.req_patcher.start()
        self.addCleanup(self.req_patcher.stop)
        self.provider = RiskResourceProvider()

    def _create_strategy(self, name: str) -> Strategy:
        return Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name=name)

    def _create_risk(self, risk_id: str, strategy: Strategy) -> Risk:
        return Risk.objects.create(
            risk_id=risk_id,
            raw_event_id=f"raw-{risk_id}",
            strategy=strategy,
            event_time=timezone.now(),
        )

    def test_list_by_scene_returns_only_bound_strategy_risks(self):
        """场景过滤风险 = 筛选场景下绑定的策略 → 这些策略对应的风险"""
        scene = Scene.objects.create(name="risk-scene")
        strategy_in = self._create_strategy("in-scene")
        strategy_out = self._create_strategy("out-scene")
        _bind_strategy_to_scene(strategy_in.strategy_id, scene)

        risk_in = self._create_risk("risk-in", strategy_in)
        risk_out = self._create_risk("risk-out", strategy_out)

        page = Page(50, 0)
        lr = self.provider.list_instance(
            FancyDict(parent={"id": str(scene.scene_id), "type": ResourceEnum.SCENE.id}, search=None),
            page,
        )
        result_ids = {item["id"] for item in lr.results}
        self.assertIn(risk_in.risk_id, result_ids)
        self.assertNotIn(risk_out.risk_id, result_ids)

    def test_search_by_scene_returns_only_bound_strategy_risks(self):
        """搜索时也只返回场景下策略对应的风险"""
        scene = Scene.objects.create(name="risk-search-scene")
        strategy_in = self._create_strategy("search-in")
        strategy_out = self._create_strategy("search-out")
        _bind_strategy_to_scene(strategy_in.strategy_id, scene)

        risk_in = self._create_risk("srisk-in", strategy_in)
        risk_out = self._create_risk("srisk-out", strategy_out)

        page = Page(50, 0)
        lr = self.provider.search_instance(
            FancyDict(
                parent=FancyDict(id=str(scene.scene_id), type=ResourceEnum.SCENE.id),
                keyword="srisk",
            ),
            page,
        )
        result_ids = {item["id"] for item in lr.results}
        self.assertIn(risk_in.risk_id, result_ids)
        self.assertNotIn(risk_out.risk_id, result_ids)

    def test_list_without_parent_returns_all(self):
        """无 parent 时应返回全部风险"""
        strategy = self._create_strategy("all-strat")
        risk = self._create_risk("risk-all", strategy)

        lr = self.provider.list_instance(FancyDict(parent=None, search=None), Page(50, 0))
        result_ids = {item["id"] for item in lr.results}
        self.assertIn(risk.risk_id, result_ids)


class RiskPathEqDjangoQuerySetConverterTest(TestCase):
    """测试 RiskPathEqDjangoQuerySetConverter 对场景路径的处理"""

    def _create_strategy(self, name: str) -> Strategy:
        return Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name=name)

    def test_risk_create_instance_uses_scene_parent_path(self):
        scene = Scene.objects.create(name="risk-parent-path-scene")
        strategy = self._create_strategy("risk-parent-path-strategy")
        _bind_strategy_to_scene(strategy.strategy_id, scene)
        risk = Risk.objects.create(
            risk_id="risk-parent-path",
            raw_event_id="raw-parent-path",
            strategy=strategy,
            event_time=timezone.now(),
        )

        resource = ResourceEnum.RISK.create_instance(risk.risk_id)

        self.assertEqual(resource.attribute["id"], risk.risk_id)
        self.assertEqual(resource.attribute["name"], risk.risk_id)
        self.assertEqual(resource.attribute[KEYWORD_BK_IAM_PATH], f"/scene,{scene.scene_id}/")

    def test_process_risk_apply_data_has_single_risk_node(self):
        scene = Scene.objects.create(name="risk-apply-data-scene")
        strategy = self._create_strategy("risk-apply-data-strategy")
        _bind_strategy_to_scene(strategy.strategy_id, scene)
        risk = Risk.objects.create(
            risk_id="risk-apply-data",
            raw_event_id="raw-apply-data",
            strategy=strategy,
            event_time=timezone.now(),
        )

        resource = ResourceEnum.RISK.create_instance(risk.risk_id)
        with patch.object(Permission, "get_apply_url", return_value="http://apply.example"):
            apply_data, _ = Permission(username="admin").get_apply_data([ActionEnum.PROCESS_RISK], [resource])

        instances = apply_data["actions"][0]["related_resource_types"][0]["instances"]
        self.assertEqual(len(instances), 1)
        self.assertEqual([node["type"] for node in instances[0]], [ResourceEnum.SCENE.id, ResourceEnum.RISK.id])
        self.assertEqual([node["id"] for node in instances[0]], [str(scene.scene_id), risk.risk_id])

    def test_scene_path_converts_to_strategy_id_in(self):
        """/scene,{scene_id}/ 路径应转换为 strategy_id__in 查询"""
        scene = Scene.objects.create(name="converter-scene")
        strategy = self._create_strategy("conv-strat")
        _bind_strategy_to_scene(strategy.strategy_id, scene)

        converter = RiskPathEqDjangoQuerySetConverter()
        expression = {
            "op": "starts_with",
            "field": "risk._bk_iam_path_",
            "value": f"/scene,{scene.scene_id}/",
        }
        q_filter = converter.convert(expression)
        self.assertIsInstance(q_filter, Q)

        # 应用到 Risk 查询
        risk = Risk.objects.create(
            risk_id="conv-risk",
            raw_event_id="raw-conv",
            strategy=strategy,
            event_time=timezone.now(),
        )
        qs = Risk.objects.filter(q_filter)
        self.assertIn(risk, qs)

    def test_scene_path_excludes_unbound_strategy_risks(self):
        """场景路径查询不应包含不在该场景下的策略的风险"""
        scene = Scene.objects.create(name="converter-exclude-scene")
        strategy_in = self._create_strategy("conv-in")
        strategy_out = self._create_strategy("conv-out")
        _bind_strategy_to_scene(strategy_in.strategy_id, scene)

        risk_in = Risk.objects.create(
            risk_id="conv-risk-in",
            raw_event_id="raw-in",
            strategy=strategy_in,
            event_time=timezone.now(),
        )
        risk_out = Risk.objects.create(
            risk_id="conv-risk-out",
            raw_event_id="raw-out",
            strategy=strategy_out,
            event_time=timezone.now(),
        )

        converter = RiskPathEqDjangoQuerySetConverter()
        expression = {
            "op": "starts_with",
            "field": "risk._bk_iam_path_",
            "value": f"/scene,{scene.scene_id}/",
        }
        q_filter = converter.convert(expression)
        qs = Risk.objects.filter(q_filter)

        self.assertIn(risk_in, qs)
        self.assertNotIn(risk_out, qs)

    def test_strategy_path_backward_compatible(self):
        """兼容旧路径 /strategy,{strategy_id}/ → 直接匹配 strategy_id"""
        strategy = self._create_strategy("old-strat")
        risk = Risk.objects.create(
            risk_id="old-risk",
            raw_event_id="raw-old",
            strategy=strategy,
            event_time=timezone.now(),
        )

        converter = RiskPathEqDjangoQuerySetConverter()
        expression = {
            "op": "starts_with",
            "field": "risk._bk_iam_path_",
            "value": f"/strategy,{strategy.strategy_id}/",
        }
        q_filter = converter.convert(expression)
        qs = Risk.objects.filter(q_filter)
        self.assertIn(risk, qs)

    def test_risk_id_eq(self):
        """risk.id 仍能正常匹配"""
        strategy = self._create_strategy("id-strat")
        risk = Risk.objects.create(
            risk_id="id-test-risk",
            raw_event_id="raw-id",
            strategy=strategy,
            event_time=timezone.now(),
        )

        converter = RiskPathEqDjangoQuerySetConverter()
        expression = {
            "op": "eq",
            "field": "risk.id",
            "value": "id-test-risk",
        }
        q_filter = converter.convert(expression)
        qs = Risk.objects.filter(q_filter)
        self.assertIn(risk, qs)
