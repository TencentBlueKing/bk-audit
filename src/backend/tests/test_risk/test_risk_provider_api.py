# -*- coding: utf-8 -*-
import datetime
from unittest.mock import patch

from django.conf import settings
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone
from iam.collection import FancyDict
from iam.resource.utils import Page

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
