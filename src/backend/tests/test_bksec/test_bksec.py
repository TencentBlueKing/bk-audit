# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import json
from unittest import mock

import pytest
from bk_resource import resource
from django.conf import settings
from rest_framework import serializers

from services.web.risk.bksec import sync_bksec_rule
from services.web.risk.bksec.config import BkSecConfig
from services.web.risk.bksec.constants import BKSEC_RULE_PRIORITY_BASE
from services.web.risk.bksec.contract import (
    build_event_payload,
    build_pa_params,
    build_plugin_constants,
    coerce_operator_constant,
)
from services.web.risk.bksec.render import build_render_context, render_value
from services.web.risk.bksec.service import (
    has_bksec_ticket_sent,
    validate_bksec_test_target,
)
from services.web.risk.models import ProcessApplication, RiskRule
from tests.test_risk.test_tickets.base import RiskContext
from tests.test_risk.test_tickets.constants import RISK_INFO

# 内置发单套餐的约定名称（仅测试 fixture 用）：生产由运维手动创建内置套餐，
# 匹配靠 is_builtin=True + sops_template_id，与名称无关
BKSEC_PRESET_PA_NAME = "【内置】BKSEC安全工单发单"

BKSEC_CONFIG_DATA = {
    "enabled": True,
    "project_id": "17",
    "risk_type_id": "cloud-account-no-mfa",
    "risk_type_name": "云安全-云账号未启用MFA",
    "field_mappings": [
        {"key": "target", "name": "风险资产信息", "value": "风险单 {{ risk.risk_id }} 的资产信息", "required": True},
        {"key": "target_type", "name": "目标资产类型", "value": "tencentcloud_sub_user", "required": True},
        {"key": "operator", "name": "初始责任人", "value": "{{ risk.operator }}", "required": True},
        {"key": "description", "name": "描述", "value": "{{ risk.event_content }}"},
    ],
}


class TestRiskAccessFetch:
    """risk_access 列表翻页取全量：单页截断会 token 漏匹配、启用保存被误阻断"""

    def test_find_token_on_later_page(self):
        """目标类型不在首页：循环翻页取到 token，命中即停不多翻"""
        from services.web.risk.bksec.service import find_risk_access_item

        pages = {
            1: {"count": 3, "results": [{"id": 1, "token": "t1"}, {"id": 2, "token": "t2"}]},
            2: {"count": 3, "results": [{"id": 159, "token": "t-target"}]},
        }

        def fake_list(**kwargs):
            return pages.get(kwargs.get("page", 1), {"count": 3, "results": []})

        with mock.patch(
            "services.web.risk.bksec.service.api.bk_sec.risk_access_list_as_platform", side_effect=fake_list
        ) as fake_fetch:
            item = find_risk_access_item("159")
        assert item and item["token"] == "t-target"
        assert fake_fetch.call_count == 2

    def test_find_token_fallback_non_formal(self):
        """is_formal=true 找不到时用 false 兜底（存量测试类型）"""
        from services.web.risk.bksec.service import find_risk_access_item

        def fake_list(**kwargs):
            if kwargs.get("is_formal") == "true":
                return {"count": 1, "results": [{"id": 1, "token": "t1"}]}
            return {"count": 1, "results": [{"id": 159, "token": "t-test"}]}

        with mock.patch(
            "services.web.risk.bksec.service.api.bk_sec.risk_access_list_as_platform", side_effect=fake_list
        ):
            item = find_risk_access_item("159")
        assert item and item["token"] == "t-test"

    def test_fetch_stops_on_short_page(self):
        """接口不返回 count / 短页时也能终止，不空转"""
        from services.web.risk.bksec.service import fetch_risk_access_items

        calls = []

        def fake_list(**kwargs):
            calls.append(kwargs.get("page"))
            return {"results": [{"id": 1, "token": "t1"}]}

        with mock.patch("services.web.risk.bksec.service.api.bk_sec.risk_access_list", side_effect=fake_list):
            items = fetch_risk_access_items(use_cache=False)
        assert len(items) == 1
        assert calls == [1]

    def test_fetch_cache_by_is_formal(self):
        """下拉展示走缓存（按 is_formal + 身份维度）：同身份二次调用不再打接口"""
        from django.core.cache import cache

        from services.web.risk.bksec.service import fetch_risk_access_items

        cache.clear()
        with mock.patch(
            "services.web.risk.bksec.service.api.bk_sec.risk_access_list",
            mock.Mock(return_value={"count": 1, "results": [{"id": 1, "token": "t1"}]}),
        ) as fake_fetch:
            first = fetch_risk_access_items(is_formal="true", use_cache=True)
            second = fetch_risk_access_items(is_formal="true", use_cache=True)
        assert first == second
        assert fake_fetch.call_count == 1
        cache.clear()

    def test_platform_result_never_cached(self):
        """平台身份结果含 token：一律不落缓存（key 恒为 platform，写入即对全站可见）"""
        from django.core.cache import cache

        from services.web.risk.bksec.constants import BKSEC_RISK_TYPES_CACHE_KEY
        from services.web.risk.bksec.service import fetch_risk_access_items

        cache.clear()
        with mock.patch(
            "services.web.risk.bksec.service.api.bk_sec.risk_access_list_as_platform",
            mock.Mock(return_value={"count": 1, "results": [{"id": 159, "token": "t-secret"}]}),
        ):
            fetch_risk_access_items(project_id="17", is_formal="true", use_cache=True, as_platform=True)
        assert cache.get("{}:platform:17:true".format(BKSEC_RISK_TYPES_CACHE_KEY)) is None
        cache.clear()

    def test_cache_isolated_by_project(self):
        """多项目：缓存按项目隔离，项目 A 的结果不得被项目 B 读到"""
        from django.core.cache import cache

        from services.web.risk.bksec.service import fetch_risk_access_items

        cache.clear()
        with mock.patch(
            "services.web.risk.bksec.service.api.bk_sec.risk_access_list",
            side_effect=lambda **kwargs: {
                "count": 1,
                "results": [{"id": 1, "name": "P{}".format(kwargs.get("project_id"))}],
            },
        ):
            assert fetch_risk_access_items(project_id="17", use_cache=True)[0]["name"] == "P17"
            assert fetch_risk_access_items(project_id="18", use_cache=True)[0]["name"] == "P18"
            assert fetch_risk_access_items(project_id="17", use_cache=True)[0]["name"] == "P17"
        cache.clear()


class TestBkSecPluginConfigAuth:
    """写路径授权：下拉（用户身份）过滤不等于授权，越权「项目/风险类型」不得借平台身份取 token"""

    # 平台身份数据域更宽：能看到用户看不到的项目 18、类型 159
    PLATFORM_ITEMS = {
        "17": [{"id": 1, "token": "t-visible"}, {"id": 159, "token": "t-secret"}],
        "18": [{"id": 2, "token": "t-other"}],
    }
    # 用户身份：项目 17 只看得到类型 1；项目 18 无权限（空）
    USER_ITEMS = {"17": [{"id": 1, "token": "t-visible"}], "18": []}

    def _sync(self, project_id, risk_type_id, user_items=None):
        from bk_resource import api
        from django.core.cache import cache

        from services.web.risk.bksec.rules import sync_plugin_config

        cache.clear()
        strategy = mock.Mock(strategy_id=1)
        config = BkSecConfig.model_validate(
            {**BKSEC_CONFIG_DATA, "project_id": project_id, "risk_type_id": risk_type_id}
        )

        def fake_fetch(project_id="", is_formal="true", use_cache=True, as_platform=False):
            source = self.PLATFORM_ITEMS if as_platform else (user_items or self.USER_ITEMS)
            return [dict(item, is_formal=True) for item in source.get(str(project_id), [])]

        with mock.patch("services.web.risk.bksec.rules.BKSEC_PLUGIN_CONFIG_API_URL", "http://plugin"), mock.patch(
            "services.web.risk.bksec.service.fetch_risk_access_items", side_effect=fake_fetch
        ), mock.patch.object(api.bk_sec_send_plugin, "config_upsert", return_value={"result": True}) as upsert:
            result = sync_plugin_config(strategy, config)
        cache.clear()
        return result, upsert

    def test_forbidden_risk_type_blocked(self):
        """用户不可见的 risk_type_id：即便平台身份取得到 token，也禁止同步到插件"""
        (success, message), upsert = self._sync("17", "159")
        assert success is False
        assert "无权" in message
        assert upsert.call_count == 0

    def test_forbidden_project_blocked(self):
        """用户无权限的项目：项目 18 用户在下拉里根本看不到，直传不得放行"""
        (success, message), upsert = self._sync("18", "2")
        assert success is False
        assert "无权" in message
        assert upsert.call_count == 0

    def test_visible_risk_type_allowed(self):
        """用户可见的 (项目, 风险类型) 正常同步，写入的是该类型自身的 token"""
        (success, _), upsert = self._sync("17", "1")
        assert success is True
        assert upsert.call_count == 1
        assert upsert.call_args.kwargs["token"] == "t-visible"


class TestBkSecProjectsAggregate:
    """项目 + 风险类型聚合接口（一次返回两级）"""

    @pytest.fixture(autouse=True)
    def _enable_bksec(self):
        """resources 侧在函数内 import FeatureHandler，需 mock 源模块"""
        with mock.patch(
            "apps.feature.handlers.FeatureHandler",
            return_value=mock.Mock(check=mock.Mock(return_value=True)),
        ):
            yield

    def _call(self, projects, fetcher):
        from bk_resource import resource

        with mock.patch(
            "services.web.risk.resources.bksec.api.bk_sec.project_choices", return_value=projects
        ), mock.patch("services.web.risk.resources.bksec.fetch_risk_access_items", side_effect=fetcher):
            return resource.risk.list_bk_sec_projects.perform_request({})

    def test_projects_carry_their_risk_types(self):
        """一次返回两级：每个项目下挂各自项目的风险类型"""
        projects = [{"id": 17, "name": "应用运维安全"}, {"id": 18, "name": "其它项目"}]

        def fetcher(project_id="", is_formal="true", use_cache=True, as_platform=False):
            if project_id == "17":
                return [{"id": 159, "name": "云账号未启用MFA", "is_formal": True, "risk_access_fields": []}]
            return [{"id": 2, "name": "其它类型", "is_formal": True, "risk_access_fields": []}]

        result = self._call(projects, fetcher)
        assert [p["id"] for p in result] == ["17", "18"]
        assert result[0]["name"] == "应用运维安全"
        assert result[0]["risk_types"][0]["risk_type_id"] == "159"
        assert result[1]["risk_types"][0]["risk_type_name"] == "其它类型"

    def test_single_project_failure_degrades(self):
        """单个项目拉取失败：该项目 risk_types 为空，其他项目照常返回"""
        projects = [{"id": 17, "name": "应用运维安全"}, {"id": 18, "name": "其它项目"}]

        def fetcher(project_id="", is_formal="true", use_cache=True, as_platform=False):
            if project_id == "17":
                raise Exception("boom")
            return [{"id": 2, "name": "其它类型", "is_formal": True, "risk_access_fields": []}]

        result = self._call(projects, fetcher)
        assert result[0]["risk_types"] == []
        assert result[1]["risk_types"][0]["risk_type_id"] == "2"

    def test_keyword_filters_risk_types(self):
        """名称搜索只过滤风险类型，不影响项目返回"""
        projects = [{"id": 17, "name": "应用运维安全"}]
        items = [
            {"id": 1, "name": "云账号未启用MFA", "is_formal": True, "risk_access_fields": []},
            {"id": 2, "name": "主机高危端口", "is_formal": True, "risk_access_fields": []},
        ]

        from bk_resource import resource

        with mock.patch(
            "services.web.risk.resources.bksec.api.bk_sec.project_choices", return_value=projects
        ), mock.patch("services.web.risk.resources.bksec.fetch_risk_access_items", return_value=items):
            result = resource.risk.list_bk_sec_projects.perform_request({"name__icontains": "MFA"})
        assert len(result) == 1
        assert [rt["risk_type_id"] for rt in result[0]["risk_types"]] == ["1"]


class TestBkSecRiskTypeFields:
    """风险类型字段 schema：必填前置排序"""

    def test_required_fields_first(self):
        """必填字段前置：target/target_type/operator 按声明顺序排最前，可选字段保持接口原序"""
        from services.web.risk.resources.bksec import _normalize_risk_type

        item = {
            "id": 159,
            "name": "云账号未启用MFA",
            "is_formal": True,
            "risk_access_fields": [
                {"key": "submitter", "name": "提单人", "storage_type": "STRING"},
                {"key": "operator", "name": "初始责任人", "storage_type": "STRING"},
                {"key": "desc", "name": "描述", "storage_type": "STRING"},
                {"key": "target_type", "name": "目标资产类型", "storage_type": "STRING"},
                {"key": "target", "name": "风险资产信息", "storage_type": "STRING"},
            ],
        }
        fields = _normalize_risk_type(item)["fields"]
        assert [f["key"] for f in fields] == ["target", "target_type", "operator", "submitter", "desc"]
        assert [f["required"] for f in fields] == [True, True, True, False, False]

    def test_without_required_fields_keeps_original_order(self):
        """无必填字段时不重排：可选字段保持接口返回顺序"""
        from services.web.risk.resources.bksec import _normalize_risk_type

        item = {
            "id": 1,
            "name": "普通类型",
            "risk_access_fields": [
                {"key": "submitter", "name": "提单人", "storage_type": "STRING"},
                {"key": "desc", "name": "描述", "storage_type": "STRING"},
            ],
        }
        assert [f["key"] for f in _normalize_risk_type(item)["fields"]] == ["submitter", "desc"]


class TestBkSecConfig:
    def test_parse_and_dedupe(self):
        data = {
            **BKSEC_CONFIG_DATA,
            "field_mappings": BKSEC_CONFIG_DATA["field_mappings"] + [BKSEC_CONFIG_DATA["field_mappings"][0]],
        }
        config = BkSecConfig.model_validate(data)
        assert len(config.field_mappings) == 4

    def test_project_id_fallback_to_global(self, settings):
        """前端未传 project_id：回退全局配置，不阻断保存（改造期过渡兼容）"""
        settings.BKSEC_PROJECT_ID = "17"
        data = {k: v for k, v in BKSEC_CONFIG_DATA.items() if k != "project_id"}
        config = BkSecConfig.model_validate(data)
        assert config.project_id == "17"
        config.validate_for_submit()

    def test_project_id_fallback_missing_still_blocks(self, settings):
        """既未传 project_id 又未配置全局项目：仍然拦截"""
        settings.BKSEC_PROJECT_ID = None
        data = {k: v for k, v in BKSEC_CONFIG_DATA.items() if k != "project_id"}
        config = BkSecConfig.model_validate(data)
        assert config.project_id == ""
        with pytest.raises(ValueError):
            config.validate_for_submit()

    def test_validate_for_submit_missing_type(self):
        config = BkSecConfig.model_validate({**BKSEC_CONFIG_DATA, "risk_type_id": ""})
        with pytest.raises(ValueError):
            config.validate_for_submit()

    def test_validate_for_submit_missing_required_field(self):
        mappings = [m for m in BKSEC_CONFIG_DATA["field_mappings"] if m["key"] != "operator"]
        config = BkSecConfig.model_validate({**BKSEC_CONFIG_DATA, "field_mappings": mappings})
        with pytest.raises(ValueError):
            config.validate_for_submit()

    def test_validate_disabled_skip(self):
        config = BkSecConfig.model_validate({"enabled": False})
        config.validate_for_submit()

    def test_serializer_allows_blank_values(self):
        """显式空串合法（可选字段不填值）：field_mappings[].value 传空不再被 DRF blank 校验拦截"""
        from services.web.strategy_v2.serializers import BkSecConfigSerializer

        serializer = BkSecConfigSerializer(
            data={
                "enabled": True,
                "risk_type_id": "",
                "risk_type_name": "",
                "field_mappings": [{"key": "description", "name": "描述", "value": "", "required": False}],
            }
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["field_mappings"][0]["value"] == ""

    def test_serializer_type_errors_still_rejected(self):
        """放行空串不降校验强度：类型错误仍拦截"""
        from services.web.strategy_v2.serializers import BkSecConfigSerializer

        serializer = BkSecConfigSerializer(data={"enabled": "not-a-bool", "field_mappings": [{"required": "x"}]})
        assert not serializer.is_valid()
        assert "enabled" in serializer.errors

    def test_risk_access_list_registered(self):
        """回归：sync_plugin_config 依赖该资源取 token，缺失会导致启用 BKSEC 的策略保存全部被阻断
        （2026-10-16 db4f1a9ba 起取 token 改用 risk_access_list 按 risk_type_id 匹配，RiskAccessRetrieve 已删除）
        """
        from bk_resource import api

        assert callable(api.bk_sec.risk_access_list)


@pytest.mark.django_db
class TestRenderer:
    def test_render_risk_variables(self):
        with RiskContext() as risk:
            context = build_render_context(risk=risk, events=[])
            assert render_value("{{ risk.risk_id }}", context) == risk.risk_id
            assert render_value("{{ risk.operator }}", context) == "admin"
            assert render_value("static text", context) == "static text"
            assert render_value("{{ risk.not_exist }}", context) == ""

    def test_render_flat_variables(self):
        """裸变量：风险字段优先，风险无该字段时补充最后一条事件的字段"""
        events = [{"username": "alice"}, {"username": "bob"}]
        with RiskContext() as risk:
            context = build_render_context(risk=risk, events=events)
            assert render_value("{{ risk_id }}", context) == risk.risk_id
            assert render_value("{{ operator }}", context) == "admin"
            assert render_value("{{ username }}", context) == "bob"

    def test_render_event_data_subscript(self):
        """event_data 下标取值（对齐风险单标题渲染口径），兼容 JSON 字符串形态"""
        events = [
            {"event_data": {"username": "alice", "asset": "127.0.0.1"}},
            {"event_data": '{"username": "bob", "asset": "10.0.0.1"}'},
        ]
        with RiskContext() as risk:
            context = build_render_context(risk=risk, events=events)
            assert render_value("{{ event_data['username'] }}", context) == "bob"
            assert render_value("{{ event_data['asset'] }}", context) == "10.0.0.1"
            assert render_value("{{ risk.event_data['username'] }}", context) == "admin"
            # 下标不命中：渲染为空，不抛未定义错误
            assert render_value("{{ event_data['not_exist'] }}", context) == ""
            # 无事件：回落到风险单 event_data，仍不抛错
            empty_context = build_render_context(risk=risk, events=[])
            assert render_value("{{ event_data['username'] }}", empty_context) == "admin"
            assert render_value("{{ event_data['not_exist'] }}", empty_context) == ""
            # 扁平变量不影响命名空间取值
            assert render_value("{{ risk.operator }}", context) == "admin"
            assert render_value("{{ event.username }}", context) == "bob"


@pytest.mark.django_db
class TestContract:
    def test_build_event_payload_with_fallback(self):
        config = BkSecConfig.model_validate(BKSEC_CONFIG_DATA)
        # 无责任人 → 初始责任人兜底为安全接口人
        with RiskContext(risk_info={"operator": []}) as risk:
            with mock.patch(
                "services.web.risk.bksec.contract.load_security_person", mock.Mock(return_value=["sec_admin"])
            ):
                payload = build_event_payload(config, risk=risk, events=[])
        assert payload["risk_type"] == "cloud-account-no-mfa"
        assert payload["fields"]["operator"] == "sec_admin"
        assert risk.risk_id in payload["fields"]["target"]

    def test_build_pa_params_and_plugin_constants(self):
        config = BkSecConfig.model_validate(BKSEC_CONFIG_DATA)
        pa_params = build_pa_params(config)
        # 字段级契约：标准入参（含 event_type/event_data）走 field 映射，action 由 SOPS 模板节点输入决定（审计侧不传）
        assert pa_params["${risk_id}"] == {"field": "risk_id", "value": ""}
        assert pa_params["${strategy_id}"] == {"field": "strategy_id", "value": ""}
        assert pa_params["${event_type}"] == {"field": "event_type", "value": ""}
        assert pa_params["${operator}"] == {
            "field": "",
            "value": "{{ risk.operator }}",
        }
        # target/target_type/operator 三个独立入参模板（从 field_mappings 派生到 config 独立字段）
        assert pa_params["${target_type}"] == {"field": "", "value": "tencentcloud_sub_user"}
        # event_data 还原为标准字段；risk_type_extra 承载扩展字段
        assert pa_params["${event_data}"] == {"field": "event_data", "value": ""}
        assert "${risk_type_extra}" in pa_params and "${once_task}" in pa_params and "${action}" not in pa_params
        # 渲染后的插件常量（测试发送用）
        with RiskContext() as risk:
            with mock.patch(
                "services.web.risk.bksec.render.load_risk_events", mock.Mock(return_value=[{"event_id": "e1"}])
            ):
                constants = build_plugin_constants(config, risk=risk, test_operator="tester")
        assert constants["${risk_id}"] == risk.risk_id
        assert constants["${event_type}"] == '["SuperPermission"]'  # event_type 从 risk.event_type 序列化
        assert constants["${operator}"] == '["tester"]'  # 数组串，满足插件 json.loads 契约
        # event_data 还原为事件拓展数据
        assert json.loads(constants["${event_data}"]) == {"username": "admin"}
        # risk_type_extra 承载全部字段映射（含 target/target_type/operator，与独立入参重复但语义独立）
        extra = json.loads(constants["${risk_type_extra}"])
        assert "description" in extra and "operator" in extra and "target_type" in extra
        # target 独立入参模板已渲染
        assert risk.risk_id in constants["${target}"]

    def test_render_bksec_constant_dispatch(self):
        """派单值加工收口：标量模板 / risk_type_extra JSON 重组 / operator 契约，各走各的分支"""
        from services.web.risk.bksec.contract import render_bksec_constant

        with RiskContext() as risk:
            context = build_render_context(risk=risk, events=[])
            # 标量模板：文字+变量混排渲染
            assert render_bksec_constant("${target}", "云账号 {{ risk.risk_id }}", context, risk) == (
                "云账号 {}".format(risk.risk_id)
            )
            # risk_type_extra：JSON 模板串 → 逐字段渲染重组（值内引号不破结构）
            extra = json.loads(
                render_bksec_constant(
                    "${risk_type_extra}", json.dumps({"operator": "{{ risk.operator }}"}), context, risk
                )
            )
            assert extra["operator"] == "admin"
            # operator：先渲染再过数组串契约
            assert json.loads(render_bksec_constant("${operator}", "{{ risk.operator }}", context, risk)) == ["admin"]


@pytest.mark.django_db
class TestBkSecRules:
    @pytest.fixture(autouse=True)
    def _mock_plugin_config_sync(self):
        """启用路径的插件 Config 同步强校验在单测环境（无 URL）会阻断，mock 掉。"""
        with mock.patch("services.web.risk.bksec.rules.sync_plugin_config", mock.Mock(return_value=(True, "ok"))):
            yield

    def _strategy(self, bksec_config=None):
        from services.web.strategy_v2.models import Strategy

        strategy, _ = Strategy.objects.get_or_create(
            strategy_id=RISK_INFO["strategy_id"],
            defaults={
                "strategy_name": f"test_strategy_{RISK_INFO['strategy_id']}",
                "bksec_config": bksec_config or {},
            },
        )
        if bksec_config is not None:
            strategy.bksec_config = bksec_config
            strategy.save(update_fields=["bksec_config"])
        return strategy

    def test_sync_rule_create_and_idempotent(self, settings):
        from services.web.risk.bksec.rules import sync_bksec_rule

        settings.BKSEC_SOPS_TEMPLATE_ID = "10001"
        RiskRule.objects.all().delete()
        ProcessApplication.objects.all().delete()
        ProcessApplication.objects.create(
            name=str(BKSEC_PRESET_PA_NAME), sops_template_id=10001, need_approve=False, is_enabled=True, is_builtin=True
        )
        strategy = self._strategy(BKSEC_CONFIG_DATA)
        rule = sync_bksec_rule(strategy)
        assert rule is not None and rule.is_enabled and rule.auto_strategy_id == strategy.strategy_id
        assert rule.scope == [{"field": "strategy_id", "operator": "=", "value": [strategy.strategy_id]}]
        # 闭环定论：工单办结（标准运维任务成功）即关闭审计风险，
        # 之后新事件按聚合规则生成新风险单 → 新任务 → 首次发单，不再需要"工单办结后重新开单"
        assert rule.auto_close_risk is True
        assert "${event_data}" in rule.pa_params and "${event_type}" in rule.pa_params
        # 保留优先级段：自动规则结构性最高（段基址 9000），手动规则恒低于段
        manual = RiskRule.objects.create(name="manual", scope=[], pa_id=rule.pa_id, version=1, priority_index=1)
        assert rule.priority_index >= BKSEC_RULE_PRIORITY_BASE > manual.priority_index
        # 幂等：内容未变不产生新版本
        again = sync_bksec_rule(strategy)
        assert again.version == rule.version

    def test_sync_rule_disable_and_update(self, settings):
        from services.web.risk.bksec.rules import sync_bksec_rule

        settings.BKSEC_SOPS_TEMPLATE_ID = "10001"
        RiskRule.objects.all().delete()
        ProcessApplication.objects.all().delete()
        ProcessApplication.objects.create(
            name=str(BKSEC_PRESET_PA_NAME), sops_template_id=10001, need_approve=False, is_enabled=True, is_builtin=True
        )
        strategy = self._strategy(BKSEC_CONFIG_DATA)
        rule = sync_bksec_rule(strategy)
        # 关闭开关 → 原地停用（不产生新版本，对齐 ToggleRiskRule）
        strategy.bksec_config = {"enabled": False}
        strategy.save(update_fields=["bksec_config"])
        assert sync_bksec_rule(strategy) is None
        latest = RiskRule.objects.filter(auto_strategy_id=strategy.strategy_id).order_by("-version").first()
        assert not latest.is_enabled
        assert latest.version == rule.version
        assert RiskRule.objects.filter(auto_strategy_id=strategy.strategy_id).count() == 1
        # 重新启用（内容未变）→ 原地启用，仍不产生新版本
        strategy.bksec_config = BKSEC_CONFIG_DATA
        strategy.save(update_fields=["bksec_config"])
        reenabled = sync_bksec_rule(strategy)
        assert reenabled.is_enabled
        assert reenabled.version == rule.version
        assert RiskRule.objects.filter(auto_strategy_id=strategy.strategy_id).count() == 1
        # 内容变更（换风险类型）→ 产生启用的新版本，旧版本保留供在途风险单引用
        strategy.bksec_config = {**BKSEC_CONFIG_DATA, "risk_type_id": "host-highrisk-port"}
        strategy.save(update_fields=["bksec_config"])
        updated = sync_bksec_rule(strategy)
        assert updated.is_enabled
        assert updated.version == rule.version + 1
        assert RiskRule.objects.filter(rule_id=rule.rule_id, version=rule.version).exists()
        # 策略停用（评审定论：停用策略须禁用自动规则）——Toggle 经 celery 异步落库，
        # 调用方显式传方向；即便配置仍启用，规则也停
        stopped = sync_bksec_rule(strategy, strategy_alive=False)
        assert stopped is None
        latest = RiskRule.objects.filter(auto_strategy_id=strategy.strategy_id).order_by("-version").first()
        assert not latest.is_enabled
        assert latest.version == updated.version  # 原地切换不产生新版本
        # 策略重新启用 → 原地恢复
        resumed = sync_bksec_rule(strategy, strategy_alive=True)
        assert resumed.is_enabled and resumed.version == updated.version
        # 状态推导路径：strategy.status=disabled（已落库）时不传覆盖 → 同样停用
        strategy.status = "disabled"
        strategy.save(update_fields=["status"])
        assert sync_bksec_rule(strategy) is None
        assert (
            not RiskRule.objects.filter(auto_strategy_id=strategy.strategy_id).order_by("-version").first().is_enabled
        )
        strategy.status = "running"
        strategy.save(update_fields=["status"])

    def test_auto_rule_edit_guard(self):
        """自动规则禁人工维护：Update/Toggle/Delete/批量调整一律拒绝"""
        settings.BKSEC_SOPS_TEMPLATE_ID = "10001"
        RiskRule.objects.all().delete()
        ProcessApplication.objects.all().delete()
        ProcessApplication.objects.create(
            name=str(BKSEC_PRESET_PA_NAME), sops_template_id=10001, need_approve=False, is_enabled=True, is_builtin=True
        )
        strategy = self._strategy(BKSEC_CONFIG_DATA)
        rule = sync_bksec_rule(strategy)
        with pytest.raises(Exception) as err:
            resource.risk.toggle_risk_rule.perform_request({"rule_id": rule.rule_id, "is_enabled": False})
        assert "自动发单规则" in str(err.value.args)
        with pytest.raises(Exception) as err:
            resource.risk.delete_risk_rule.perform_request({"rule_id": rule.rule_id})
        assert "自动发单规则" in str(err.value.args)
        # 守卫生效：规则未被人工改动
        latest = RiskRule.objects.filter(auto_strategy_id=strategy.strategy_id).order_by("-version").first()
        assert latest.is_enabled and latest.version == rule.version

    def test_sync_rule_without_preset_pa(self, settings):
        from services.web.risk.bksec.rules import sync_bksec_rule

        settings.BKSEC_SOPS_TEMPLATE_ID = None
        RiskRule.objects.all().delete()
        ProcessApplication.objects.all().delete()
        strategy = self._strategy(BKSEC_CONFIG_DATA)
        assert sync_bksec_rule(strategy) is None

    def test_sync_rule_scene_binding_follows_strategy(self, settings):
        """规则场景归属跟随策略：策略改绑场景后规则可见性同步更新"""
        from services.web.scene.constants import ResourceVisibilityType
        from services.web.scene.filters import BindingMetadataHelper
        from services.web.scene.models import ResourceBindingScene, Scene

        settings.BKSEC_SOPS_TEMPLATE_ID = "10001"
        RiskRule.objects.all().delete()
        ProcessApplication.objects.all().delete()
        ProcessApplication.objects.create(
            name=str(BKSEC_PRESET_PA_NAME), sops_template_id=10001, need_approve=False, is_enabled=True, is_builtin=True
        )
        strategy = self._strategy(BKSEC_CONFIG_DATA)
        scene_a = Scene.objects.create(name="bksec-scene-a")
        scene_b = Scene.objects.create(name="bksec-scene-b")
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(strategy.strategy_id),
            resource_type=ResourceVisibilityType.STRATEGY,
            scene_id=scene_a.scene_id,
        )

        def _rule_scenes(rule_id):
            return list(
                ResourceBindingScene.objects.filter(
                    binding__resource_type=ResourceVisibilityType.RISK_RULE,
                    binding__resource_id=str(rule_id),
                ).values_list("scene_id", flat=True)
            )

        rule = sync_bksec_rule(strategy)
        assert _rule_scenes(rule.rule_id) == [scene_a.scene_id]
        # 策略改绑场景（内容未变走幂等路径）→ 规则绑定跟随，不产生新版本
        BindingMetadataHelper.delete_resource_binding(
            resource_id=str(strategy.strategy_id), resource_type=ResourceVisibilityType.STRATEGY
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(strategy.strategy_id),
            resource_type=ResourceVisibilityType.STRATEGY,
            scene_id=scene_b.scene_id,
        )
        again = sync_bksec_rule(strategy)
        assert again.version == rule.version
        assert _rule_scenes(rule.rule_id) == [scene_b.scene_id]
        # 内容变更产生新版本 → 新版本绑定当前场景
        strategy.bksec_config = {**BKSEC_CONFIG_DATA, "risk_type_id": "host-highrisk-port"}
        strategy.save(update_fields=["bksec_config"])
        updated = sync_bksec_rule(strategy)
        assert updated.version == rule.version + 1
        assert _rule_scenes(updated.rule_id) == [scene_b.scene_id]


@pytest.mark.django_db
class TestBkSecResources:
    @pytest.fixture(autouse=True)
    def _enable_bksec(self):
        """接口测试依赖 feature 开关放行（BKSEC 环境变量/内置套餐在单测环境通常缺失）。"""
        with mock.patch(
            "services.web.risk.bksec.service.FeatureHandler",
            return_value=mock.Mock(check=mock.Mock(return_value=True)),
        ):
            yield

    def test_preview_ticket(self):
        config = BkSecConfig.model_validate(BKSEC_CONFIG_DATA)
        with RiskContext() as risk:
            result = resource.risk.preview_ticket.perform_request(
                {"bksec_config": config.model_dump(), "risk_id": risk.risk_id}
            )
        assert result["has_sample_risk"] is True
        assert result["ticket"]["fields"]["operator"] == "admin"
        assert risk.risk_id in result["ticket"]["fields"]["target"]

    def test_send_test_ticket(self, settings):
        """测试发送经 SOPS 真实通道（create_task + start_task），事件常量含测试标记与处理人覆盖"""
        from services.web.strategy_v2.models import Strategy
        from tests.test_risk.test_tickets.constants import SOPS_FLOW_INFO

        config = BkSecConfig.model_validate(BKSEC_CONFIG_DATA)
        settings.BKSEC_SOPS_TEMPLATE_ID = "10001"
        ProcessApplication.objects.filter(is_builtin=True).delete()
        ProcessApplication.objects.create(
            name=str(BKSEC_PRESET_PA_NAME), sops_template_id=10001, need_approve=False, is_builtin=True
        )
        with RiskContext() as risk:
            strategy = Strategy.objects.get(strategy_id=risk.strategy_id)
            strategy.bksec_config = config.model_dump()
            strategy.save(update_fields=["bksec_config"])
            with mock.patch(
                "services.web.risk.bksec.rules.sync_plugin_config", mock.Mock(return_value=(True, "ok"))
            ), mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.create_task", mock.Mock(return_value=SOPS_FLOW_INFO)
            ) as create_task, mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.start_task", mock.Mock(return_value=None)
            ) as start_task, mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_task_status",
                mock.Mock(return_value={"state": "RUNNING"}),
            ):
                result = resource.risk.send_test_ticket.perform_request(
                    {
                        "test_receivers": ["tester"],
                        "risk_id": risk.risk_id,
                        "bksec_config": config.model_dump(),
                    }
                )
        assert result["task"]["task_id"] == SOPS_FLOW_INFO["task_id"]
        start_task.assert_called_once()
        constants = create_task.call_args.kwargs["constants"]
        # 字段级插件契约（P1 确认后结构）
        assert constants["${event_type}"] == '["SuperPermission"]'  # event_type 从 risk.event_type 序列化
        # risk_type_extra 承载全部字段映射（含 target/target_type/operator，与独立入参重复但语义独立）
        extra = json.loads(constants["${risk_type_extra}"])
        assert "description" in extra and "operator" in extra
        # Bug1 修复锁定：测试发送必须以指定处理人覆盖初始责任人，保证隔离
        assert constants["${operator}"] == '["tester"]'  # 数组串，满足插件 json.loads 契约
        # 决策 A 修复锁定：测试发送必须携带样例风险单，risk 变量按真实数据渲染；
        # target 独立入参模板已渲染
        assert risk.risk_id in constants["${target}"]
        # 测试任务名带【测试】前缀，便于 SOPS 侧区分
        assert create_task.call_args.kwargs["name"].startswith("【测试】")

    def test_send_test_ticket_blocked_by_formal_dispatch(self, settings):
        """回调隔离守卫：风险存在正式派单历史时拒绝测试发送（防插件回调复用污染/静默拦截）"""
        import time as _time

        from services.web.risk.models import TicketNode
        from services.web.strategy_v2.models import Strategy

        config = BkSecConfig.model_validate(BKSEC_CONFIG_DATA)
        settings.BKSEC_SOPS_TEMPLATE_ID = "10001"
        with RiskContext() as risk:
            strategy = Strategy.objects.get(strategy_id=risk.strategy_id)
            strategy.bksec_config = config.model_dump()
            strategy.save(update_fields=["bksec_config"])
            TicketNode.objects.create(
                risk_id=risk.risk_id,
                operator="bk-audit",
                action="AutoProcess",
                timestamp=_time.time(),
                time="2026-09-23 00:00:00",
                process_result={"task": {"task_id": 1}},
                extra={},
            )
            with mock.patch("services.web.risk.resources.bksec.api.bk_sops.create_task") as create_task:
                with pytest.raises(Exception) as err:
                    resource.risk.send_test_ticket.perform_request(
                        {
                            "test_receivers": ["tester"],
                            "risk_id": risk.risk_id,
                            "bksec_config": config.model_dump(),
                        }
                    )
            create_task.assert_not_called()
            assert "正式派单" in str(err.value.args)

    def test_test_task_status_failure_hint(self):
        """任务失败时轮询接口返回失败提示：透出失败节点的原始错误文本，取不到才回退通用提示"""

        def make_failed_status():
            # 每个用例独立 dict：fill_failure_info 会回写 error_message，共享夹具会污染下一用例
            return {
                "state": "FAILED",
                "children": {"node1": {"id": "node1", "name": "发单节点", "state": "FAILED"}},
            }

        with mock.patch(
            "services.web.risk.resources.bksec.api.bk_sops.get_task_status",
            mock.Mock(return_value=make_failed_status()),
        ), mock.patch(
            "services.web.risk.resources.bksec.api.bk_sops.get_node_data",
            mock.Mock(return_value={"ex_data": "plugin execute failed: Config matching query does not exist."}),
        ):
            result = resource.risk.get_task_status.perform_request({"task_id": "1"})
        assert result["state"] == "FAILED"
        assert "Config matching query does not exist" in result["failure_hint"]
        # 节点错误取不到 → 通用指引
        with mock.patch(
            "services.web.risk.resources.bksec.api.bk_sops.get_task_status",
            mock.Mock(return_value=make_failed_status()),
        ), mock.patch(
            "services.web.risk.resources.bksec.api.bk_sops.get_node_data",
            mock.Mock(side_effect=Exception("boom")),
        ):
            result = resource.risk.get_task_status.perform_request({"task_id": "1"})
        assert result["failure_hint"] == resource.risk.get_task_status.GENERIC_HINT
        # 成功状态不附带提示
        with mock.patch(
            "services.web.risk.resources.bksec.api.bk_sops.get_task_status",
            mock.Mock(return_value={"state": "FINISHED"}),
        ):
            result = resource.risk.get_task_status.perform_request({"task_id": "1"})
        assert "failure_hint" not in result

    def test_operator_constant_empty_value_renders_valid_json_array(self):
        """断点1固化：无责任人且无安全接口人时，${operator} 仍为合法 JSON 数组串（插件 json.loads 不崩）"""
        # 分号切分与 JSON 序列化由代码处理，配置页只需按语义写 {{ risk.operator }}
        assert json.loads(coerce_operator_constant("")) == []
        # 分号分隔的多人 → 数组
        assert json.loads(coerce_operator_constant("alice;bob")) == ["alice", "bob"]
        # 脏值 "None" 被剔除
        assert json.loads(coerce_operator_constant("None")) == []
        # 已是数组串时保持数组语义
        assert json.loads(coerce_operator_constant('["alice"]')) == ["alice"]


@pytest.mark.django_db
class TestBkSecPushStatus:
    """插件推送上报：风险单推送状态 + 测试发送守卫"""

    def test_report_marks_risk_push_success(self):
        """上报把风险单置为推送成功；重复上报幂等（状态不变、updated=False）"""
        from services.web.risk.constants import BkSecPushStatus

        with RiskContext() as risk:
            assert risk.bksec_push_status == BkSecPushStatus.NOT_PUSHED
            first = resource.risk.report_bk_sec_ticket_sent.perform_request(
                {"risk_id": risk.risk_id, "event_id": "evt-1", "trace_id": "trace-1"}
            )
            assert first["push_status"] == BkSecPushStatus.SUCCESS
            assert first["updated"] is True
            risk.refresh_from_db()
            assert risk.bksec_push_status == BkSecPushStatus.SUCCESS
            assert risk.bksec_push_event_id == "evt-1"
            second = resource.risk.report_bk_sec_ticket_sent.perform_request(
                {"risk_id": risk.risk_id, "event_id": "evt-1", "trace_id": "trace-1"}
            )
            assert second["updated"] is False
            assert has_bksec_ticket_sent(risk) is True

    def test_test_send_blocked_when_already_pushed(self):
        """已推送成功的风险单不允许测试发送：回调/轮询节点长驻 RUNNING 不再被误判为「未发单」"""
        from services.web.risk.constants import BkSecPushStatus

        with RiskContext() as risk:
            risk.bksec_push_status = BkSecPushStatus.SUCCESS
            risk.save(update_fields=["bksec_push_status"])
            with pytest.raises(serializers.ValidationError):
                validate_bksec_test_target(risk)

    def test_test_send_allowed_without_any_dispatch(self):
        """未推送过的风险单允许测试发送"""
        with RiskContext() as risk:
            validate_bksec_test_target(risk)
