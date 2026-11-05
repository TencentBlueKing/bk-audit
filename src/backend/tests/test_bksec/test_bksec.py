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
from django.http import Http404
from rest_framework import serializers

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import InstanceActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException, ValidationError
from services.web.risk.bksec import sync_bksec_rule
from services.web.risk.bksec.config import BkSecConfig
from services.web.risk.bksec.constants import BKSEC_RULE_PRIORITY_BASE
from services.web.risk.bksec.contract import (
    build_event_payload,
    build_pa_params,
    build_plugin_constants,
)
from services.web.risk.bksec.render import build_render_context, render_value
from services.web.risk.bksec.service import (
    has_bksec_ticket_sent,
    validate_bksec_test_target,
)
from services.web.risk.constants import TicketNodeStatus
from services.web.risk.models import ProcessApplication, RiskRule, TicketNode
from services.web.risk.permissions import BkSecTestTaskStatusPermission
from services.web.risk.views import TicketViewSet
from tests.test_risk.test_tickets.base import RiskContext
from tests.test_risk.test_tickets.constants import RISK_INFO

# 内置发单套餐的约定名称（仅测试 fixture 用）：生产由运维手动创建内置套餐，
# 匹配靠 is_builtin=True + sops_template_id，与名称无关
BKSEC_PRESET_PA_NAME = "【内置】BKSEC安全工单发单"

# 预置发单套餐模板变量（入参显示名 + 用户入参标记）
BKSEC_SOPS_TEMPLATE_INFO = {
    "pipeline_tree": {
        "constants": {
            key: {"key": key, "name": name, "source_type": "custom", "show_type": "show"}
            for key, name in [
                ("${event_content}", "风险描述"),
                ("${event_evidence}", "风险证据"),
                ("${event_type}", "风险类型"),
                ("${operator}", "初始责任人"),
                ("${risk_type_extra}", "风险类型扩展字段"),
                ("${target}", "风险资产信息"),
            ]
        }
    }
}

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


def _create_test_node(risk, task_id, operator="tester"):
    return TicketNode.objects.create(
        risk_id=risk.risk_id,
        operator=operator,
        action="AutoProcess",
        timestamp=1,
        time="2026-01-01 00:00:00",
        process_result={"task": {"task_id": task_id}},
        extra={},
        status=TicketNodeStatus.RUNNING,
        is_test=True,
    )


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
        """未命中项目名时只返回名称匹配的风险类型"""
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

    def test_project_id_missing_always_blocks(self):
        """未传 project_id 直接拦截（多项目：无全局兜底）"""
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
        assert constants["${once_task}"] == "yes"  # 测试发送固定测试模式，不随接收人推导
        # event_data 还原为事件拓展数据
        assert json.loads(constants["${event_data}"]) == {"username": "admin"}
        # risk_type_extra 承载全部字段映射（含 target/target_type/operator，与独立入参重复但语义独立）
        extra = json.loads(constants["${risk_type_extra}"])
        assert "description" in extra and "operator" in extra and "target_type" in extra
        # target 独立入参模板已渲染
        assert risk.risk_id in constants["${target}"]
        # 接收人为空时仍固定测试模式，不回落到正式 once_task=no
        with mock.patch(
            "services.web.risk.bksec.render.load_risk_events", mock.Mock(return_value=[{"event_id": "e1"}])
        ):
            without_receiver = build_plugin_constants(config, risk=risk, test_operator="")
        assert without_receiver["${once_task}"] == "yes"

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
        from rest_framework import serializers

        from services.web.risk.bksec.rules import sync_bksec_rule

        settings.BKSEC_SOPS_TEMPLATE_ID = None
        RiskRule.objects.all().delete()
        ProcessApplication.objects.all().delete()
        strategy = self._strategy(BKSEC_CONFIG_DATA)
        with pytest.raises(serializers.ValidationError):
            sync_bksec_rule(strategy)

    def test_sync_rule_creates_builtin_pa_without_touching_old_pa(self, settings):
        """模板 ID 已配置但没有对应内置套餐时自动补齐，旧套餐的模板 ID 保持不变。"""
        from services.web.risk.bksec.rules import sync_bksec_rule
        from services.web.risk.bksec.service import ensure_preset_pa

        settings.BKSEC_SOPS_TEMPLATE_ID = "20002"
        RiskRule.objects.all().delete()
        ProcessApplication.objects.all().delete()
        old_pa = ProcessApplication.objects.create(
            name="旧发单套餐", sops_template_id=10001, need_approve=False, is_enabled=True, is_builtin=False
        )
        strategy = self._strategy(BKSEC_CONFIG_DATA)
        rule = sync_bksec_rule(strategy)
        from services.web.scene.constants import (
            BindingType,
            ResourceVisibilityType,
            VisibilityScope,
        )
        from services.web.scene.models import ResourceBinding

        def _assert_platform_all_scenes(pa):
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.PROCESS_APPLICATION.value,
                resource_id=str(pa.id),
            )
            assert binding.binding_type == BindingType.PLATFORM_BINDING.value
            assert binding.visibility_type == VisibilityScope.ALL_SCENES.value

        builtin = ProcessApplication.objects.get(is_builtin=True, sops_template_id=20002)
        assert rule.pa_id == builtin.id
        assert builtin.need_approve is False
        _assert_platform_all_scenes(builtin)
        old_pa.refresh_from_db()
        assert old_pa.sops_template_id == 10001
        assert old_pa.is_builtin is False
        # 已有内置套餐缺绑定时，再次补齐会补上平台级、全部场景可见，不另插套餐
        ResourceBinding.objects.filter(resource_id=str(builtin.id)).delete()
        assert ensure_preset_pa().id == builtin.id
        _assert_platform_all_scenes(builtin)
        assert ProcessApplication.objects.filter(is_builtin=True).count() == 1
        settings.BKSEC_SOPS_TEMPLATE_ID = "30003"
        created = ensure_preset_pa()
        assert created.sops_template_id == 30003
        _assert_platform_all_scenes(created)
        builtin.refresh_from_db()
        assert builtin.sops_template_id == 20002
        assert ProcessApplication.objects.filter(is_builtin=True).count() == 2

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

    def test_draft_status_needs_explicit_alive_to_create_rule(self, settings):
        """状态仍是 DRAFT 时，不传 strategy_alive 不建规则；显式启用才会建规则并同步插件配置"""
        from services.web.risk.bksec.rules import sync_bksec_rule
        from services.web.strategy_v2.constants import StrategyStatusChoices

        settings.BKSEC_SOPS_TEMPLATE_ID = "10001"
        RiskRule.objects.all().delete()
        ProcessApplication.objects.all().delete()
        ProcessApplication.objects.create(
            name=str(BKSEC_PRESET_PA_NAME), sops_template_id=10001, need_approve=False, is_enabled=True, is_builtin=True
        )
        strategy = self._strategy(BKSEC_CONFIG_DATA)
        strategy.status = StrategyStatusChoices.DRAFT.value
        strategy.save(update_fields=["status"])
        with mock.patch(
            "services.web.risk.bksec.rules.sync_plugin_config", mock.Mock(return_value=(True, "ok"))
        ) as plugin_sync:
            assert sync_bksec_rule(strategy) is None
            plugin_sync.assert_not_called()
            rule = sync_bksec_rule(strategy, strategy_alive=True)
        assert rule is not None and rule.is_enabled
        assert rule.auto_strategy_id == strategy.strategy_id
        plugin_sync.assert_called_once()
        strategy.status = StrategyStatusChoices.RUNNING.value
        strategy.save(update_fields=["status"])

    def test_draft_submit_syncs_bksec_rule_as_alive(self):
        """草稿以 is_draft=False 提交时，在部署前按启用态同步发单规则"""
        from services.web.strategy_v2.constants import StrategyStatusChoices
        from services.web.strategy_v2.models import Strategy
        from services.web.strategy_v2.resources import UpdateStrategy

        strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="bksec_draft_submit",
            status=StrategyStatusChoices.DRAFT.value,
            bksec_config=BKSEC_CONFIG_DATA,
        )
        updater = UpdateStrategy()
        with mock.patch.object(updater, "ensure_active_scene_binding_or_404"), mock.patch.object(
            updater, "_check_source_type"
        ), mock.patch.object(updater, "update_db", return_value=False) as update_db, mock.patch.object(
            updater, "add_audit_instance_to_context"
        ), mock.patch(
            "services.web.strategy_v2.resources.call_controller"
        ) as controller, mock.patch(
            "services.web.strategy_v2.resources.StrategyInfoSerializer",
            return_value=mock.Mock(data={}),
        ), mock.patch(
            "services.web.risk.bksec.rules.sync_bksec_rule"
        ) as sync:
            updater.perform_request(
                {
                    "strategy_id": strategy.strategy_id,
                    "strategy_type": strategy.strategy_type,
                    "is_draft": False,
                }
            )
        sync.assert_called_once()
        assert sync.call_args.args[0].strategy_id == strategy.strategy_id
        assert sync.call_args.args[0].status == StrategyStatusChoices.DRAFT.value
        assert sync.call_args.kwargs["strategy_alive"] is True
        update_db.assert_called_once()
        controller.assert_called_once()

    def test_running_update_derives_bksec_alive_from_status(self):
        """已提交策略的普通更新不覆盖启用态，仍按当前状态推导"""
        from services.web.strategy_v2.constants import StrategyStatusChoices
        from services.web.strategy_v2.models import Strategy
        from services.web.strategy_v2.resources import UpdateStrategy

        strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="bksec_running_update",
            status=StrategyStatusChoices.RUNNING.value,
            bksec_config=BKSEC_CONFIG_DATA,
        )
        updater = UpdateStrategy()
        with mock.patch.object(updater, "ensure_active_scene_binding_or_404"), mock.patch.object(
            updater, "_check_source_type"
        ), mock.patch.object(updater, "update_db", return_value=False), mock.patch.object(
            updater, "add_audit_instance_to_context"
        ), mock.patch(
            "services.web.strategy_v2.resources.call_controller"
        ) as controller, mock.patch(
            "services.web.strategy_v2.resources.StrategyInfoSerializer",
            return_value=mock.Mock(data={}),
        ), mock.patch(
            "services.web.risk.bksec.rules.sync_bksec_rule"
        ) as sync:
            updater.perform_request({"strategy_id": strategy.strategy_id, "strategy_type": strategy.strategy_type})
        sync.assert_called_once()
        assert sync.call_args.kwargs["strategy_alive"] is None
        controller.assert_not_called()

    def test_plugin_sync_failure_keeps_strategy_and_restores_bksec_config(self, settings):
        """插件拒绝配置时规则回滚，bksec_config 回到保存前，其余字段保留，并给出说明。"""
        from django.db import transaction

        from services.web.risk.bksec.rules import sync_bksec_rule_or_keep_strategy
        from services.web.strategy_v2.models import Strategy
        from services.web.strategy_v2.serializers import (
            CreateStrategyResponseSerializer,
            UpdateStrategyResponseSerializer,
        )

        settings.BKSEC_SOPS_TEMPLATE_ID = "10001"
        RiskRule.objects.all().delete()
        ProcessApplication.objects.all().delete()
        ProcessApplication.objects.create(
            name=str(BKSEC_PRESET_PA_NAME), sops_template_id=10001, need_approve=False, is_enabled=True, is_builtin=True
        )
        previous = {"enabled": False}
        with mock.patch(
            "services.web.risk.bksec.rules.sync_plugin_config", return_value=(False, "plugin down")
        ), mock.patch("time.sleep"):
            with transaction.atomic():
                created = Strategy.objects.create(
                    namespace="default",
                    strategy_name="kept-on-create",
                    description="other-field-saved",
                    bksec_config=BKSEC_CONFIG_DATA,
                )
                sync_bksec_rule_or_keep_strategy(created, {})
            updated = Strategy.objects.create(
                namespace="default",
                strategy_name="before-rename",
                description="before-desc",
                bksec_config=previous,
            )
            updated.strategy_name = "renamed-after-save"
            updated.description = "other-field-saved"
            updated.bksec_config = BKSEC_CONFIG_DATA
            updated.save(update_fields=["strategy_name", "description", "bksec_config"])
            sync_bksec_rule_or_keep_strategy(updated, previous)

        created.refresh_from_db()
        updated.refresh_from_db()
        assert created.strategy_name == "kept-on-create"
        assert created.description == "other-field-saved"
        assert created.bksec_config == {}
        assert updated.strategy_name == "renamed-after-save"
        assert updated.description == "other-field-saved"
        assert updated.bksec_config == previous
        assert not RiskRule.objects.filter(auto_strategy_id__in=[created.strategy_id, updated.strategy_id]).exists()
        created_data = CreateStrategyResponseSerializer(created).data
        updated_data = UpdateStrategyResponseSerializer(updated).data
        assert "未生效" in created_data["bksec_sync_message"]
        assert "plugin down" in created_data["bksec_sync_message"]
        assert created_data["bksec_config"] == {}
        assert updated_data["bksec_config"] == previous
        assert "strategy_id" in created_data and "strategy_name" in created_data

    def test_update_continues_after_plugin_sync_failure(self):
        """更新接口在插件同步失败后仍保存其余字段，并继续后续部署。"""
        from services.web.risk.bksec.rules import BkSecPluginSyncError
        from services.web.strategy_v2.constants import StrategyStatusChoices
        from services.web.strategy_v2.models import Strategy
        from services.web.strategy_v2.resources import UpdateStrategy

        previous = {"enabled": False}
        strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="before-rename",
            status=StrategyStatusChoices.RUNNING.value,
            bksec_config=previous,
        )

        def fake_update_db(strategy, validated_request_data, draft_save):
            strategy.strategy_name = "renamed-after-save"
            strategy.description = "other-field-saved"
            strategy.bksec_config = BKSEC_CONFIG_DATA
            strategy.save(update_fields=["strategy_name", "description", "bksec_config"])
            return True

        updater = UpdateStrategy()
        with mock.patch.object(updater, "ensure_active_scene_binding_or_404"), mock.patch.object(
            updater, "_check_source_type"
        ), mock.patch.object(updater, "update_db", side_effect=fake_update_db), mock.patch.object(
            updater, "update_remote"
        ) as update_remote, mock.patch.object(
            updater, "add_audit_instance_to_context"
        ), mock.patch(
            "services.web.strategy_v2.resources.StrategyInfoSerializer",
            return_value=mock.Mock(data={}),
        ), mock.patch(
            "services.web.risk.bksec.rules.sync_bksec_rule", side_effect=BkSecPluginSyncError("plugin down")
        ):
            result = updater.perform_request(
                {"strategy_id": strategy.strategy_id, "strategy_type": strategy.strategy_type}
            )

        strategy.refresh_from_db()
        assert strategy.strategy_name == "renamed-after-save"
        assert strategy.description == "other-field-saved"
        assert strategy.bksec_config == previous
        assert "未生效" in result.bksec_sync_message
        assert "plugin down" in result.bksec_sync_message
        update_remote.assert_called_once()

    def test_missing_preset_pa_restores_bksec_config_and_update_continues(self, settings):
        """内置套餐补不出来时，更新保留其余字段，bksec_config 回到保存前，并继续部署。"""
        from services.web.strategy_v2.constants import StrategyStatusChoices
        from services.web.strategy_v2.models import Strategy
        from services.web.strategy_v2.resources import UpdateStrategy

        settings.BKSEC_SOPS_TEMPLATE_ID = None
        previous = {"enabled": False}
        strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="before-rename",
            status=StrategyStatusChoices.RUNNING.value,
            bksec_config=previous,
        )

        def fake_update_db(strategy, validated_request_data, draft_save):
            strategy.strategy_name = "renamed-after-save"
            strategy.description = "other-field-saved"
            strategy.bksec_config = BKSEC_CONFIG_DATA
            strategy.save(update_fields=["strategy_name", "description", "bksec_config"])
            return True

        updater = UpdateStrategy()
        with mock.patch.object(updater, "ensure_active_scene_binding_or_404"), mock.patch.object(
            updater, "_check_source_type"
        ), mock.patch.object(updater, "update_db", side_effect=fake_update_db), mock.patch.object(
            updater, "update_remote"
        ) as update_remote, mock.patch.object(
            updater, "add_audit_instance_to_context"
        ), mock.patch(
            "services.web.strategy_v2.resources.StrategyInfoSerializer",
            return_value=mock.Mock(data={}),
        ):
            result = updater.perform_request(
                {"strategy_id": strategy.strategy_id, "strategy_type": strategy.strategy_type}
            )

        strategy.refresh_from_db()
        assert strategy.strategy_name == "renamed-after-save"
        assert strategy.description == "other-field-saved"
        assert strategy.bksec_config == previous
        assert "内置发单套餐未就绪" in result.bksec_sync_message
        assert not RiskRule.objects.filter(auto_strategy_id=strategy.strategy_id).exists()
        update_remote.assert_called_once()


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
        assert "risk" not in result
        assert "risk_context_keys" not in result
        assert result["ticket_header"] == {
            "ticket_id": "",
            "title": "",
            "submit_time": "",
            "deadline": "",
            "status": "",
            "current_operator_org": "",
        }
        assert result["ticket"]["fields"]["operator"] == "admin"
        assert risk.risk_id in result["ticket"]["fields"]["target"]

    def test_list_projects_keyword_matches_project_name(self):
        """项目名命中与风险类型名命中取并集；类型命中时保留所属项目名，只留命中的类型"""
        projects = [{"id": 17, "name": "云安全项目"}, {"id": 18, "name": "主机安全"}]
        items_by_project = {
            "17": [
                {"id": 159, "name": "云账号未启用MFA", "is_formal": True},
                {"id": 161, "name": "密钥泄露", "is_formal": True},
            ],
            "18": [
                {"id": 160, "name": "高危端口开放", "is_formal": True},
                {"id": 162, "name": "云账号异常登录", "is_formal": True},
            ],
        }
        with mock.patch(
            "apps.feature.handlers.FeatureHandler", return_value=mock.Mock(check=mock.Mock(return_value=True))
        ), mock.patch(
            "services.web.risk.resources.bksec.api.bk_sec.project_choices", mock.Mock(return_value=projects)
        ), mock.patch(
            "services.web.risk.resources.bksec.fetch_risk_access_items",
            mock.Mock(side_effect=lambda project_id="", **kwargs: items_by_project.get(str(project_id), [])),
        ):
            # 并集：项目名命中的项目带全部类型；另一个项目只因类型名命中而留下，项目名仍在
            result = resource.risk.list_bk_sec_projects.perform_request({"name__icontains": "云"})
            assert [(p["id"], p["name"]) for p in result] == [("17", "云安全项目"), ("18", "主机安全")]
            assert [rt["risk_type_id"] for rt in result[0]["risk_types"]] == ["159", "161"]
            assert [rt["risk_type_id"] for rt in result[1]["risk_types"]] == ["162"]
            # 只有类型名命中
            result = resource.risk.list_bk_sec_projects.perform_request({"name__icontains": "高危端口"})
            assert [(p["id"], p["name"]) for p in result] == [("18", "主机安全")]
            assert [rt["risk_type_id"] for rt in result[0]["risk_types"]] == ["160"]
            # 项目名和风险类型都不命中：不返回
            assert resource.risk.list_bk_sec_projects.perform_request({"name__icontains": "不存在"}) == []
            # 不传关键字：项目 + 全量风险类型
            result = resource.risk.list_bk_sec_projects.perform_request({})
            risk_types = {p["id"]: [rt["risk_type_id"] for rt in p["risk_types"]] for p in result}
            assert risk_types == {"17": ["159", "161"], "18": ["160", "162"]}

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
            ), mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_template_info",
                mock.Mock(return_value=BKSEC_SOPS_TEMPLATE_INFO),
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
        assert constants["${once_task}"] == "yes"
        # 决策 A 修复锁定：测试发送必须携带样例风险单，risk 变量按真实数据渲染；
        # target 独立入参模板已渲染
        assert risk.risk_id in constants["${target}"]
        # 测试任务名带【测试】前缀，便于 SOPS 侧区分
        assert create_task.call_args.kwargs["name"].startswith("【测试】")
        # 入参快照落库：执行记录详情只读该键，缺失则套餐参数一栏为空
        node = TicketNode.objects.filter(is_test=True, risk_id=risk.risk_id).order_by("-timestamp").first()
        snapshot = {item["key"]: item for item in node.process_result["pa_constants"]}
        assert snapshot["${event_content}"]["name"] == "风险描述"
        assert snapshot["${event_type}"]["value"] == '["SuperPermission"]'
        assert snapshot["${operator}"]["value"] == '["tester"]'

    def test_empty_test_receivers_rejected_before_send(self):
        """空接收人、空白接收人在序列化和 Resource.request 都被拒绝，不生成正式发送参数"""
        from bk_resource.exceptions import ValidateException

        from services.web.risk.serializers import SendTestTicketReqSerializer

        for receivers in ([], [""], ["  "], ["", "  "]):
            serializer = SendTestTicketReqSerializer(
                data={"test_receivers": receivers, "risk_id": "risk-1", "bksec_config": BKSEC_CONFIG_DATA}
            )
            assert serializer.is_valid() is False
            assert "test_receivers" in serializer.errors
        serializer = SendTestTicketReqSerializer(
            data={"test_receivers": ["  tester  ", ""], "risk_id": "risk-1", "bksec_config": BKSEC_CONFIG_DATA}
        )
        assert serializer.is_valid() is True
        assert serializer.validated_data["test_receivers"] == ["tester"]
        with mock.patch("services.web.risk.resources.bksec.api.bk_sops.create_task") as create_task:
            with pytest.raises(ValidateException):
                resource.risk.send_test_ticket.request(
                    {"test_receivers": [], "risk_id": "risk-1", "bksec_config": BKSEC_CONFIG_DATA}
                )
        create_task.assert_not_called()

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

    def test_preview_permission_binds_sample_risk_strategy(self):
        """预览按样例风险所属策略做实例鉴权，而不是任意策略可编辑"""
        with RiskContext() as risk:
            view = TicketViewSet()
            view.action = "preview"
            view.request = mock.Mock(query_params={}, data={"risk_id": risk.risk_id})
            assert view.get_sample_strategy_id() == risk.strategy_id
            permissions = view.get_permissions()
            assert len(permissions) == 1
            permission = permissions[0]
            assert isinstance(permission, InstanceActionPermission)
            assert permission.actions == [ActionEnum.EDIT_STRATEGY]
            assert permission.resource_meta is ResourceEnum.STRATEGY
            assert permission.get_instance_id() == risk.strategy_id

    def test_test_task_status_failure_hint(self):
        """任务失败时轮询接口返回失败提示：透出失败节点的原始错误文本，取不到才回退通用提示"""

        def make_failed_status():
            # 每个用例独立 dict：fill_failure_info 会回写 error_message，共享夹具会污染下一用例
            return {
                "state": "FAILED",
                "children": {"node1": {"id": "node1", "name": "发单节点", "state": "FAILED"}},
            }

        with RiskContext() as risk:
            _create_test_node(risk, task_id=1)
            with mock.patch("services.web.risk.resources.bksec.ensure_strategy_edit_permission"), mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_task_status",
                mock.Mock(return_value=make_failed_status()),
            ), mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_node_data",
                mock.Mock(return_value={"ex_data": "plugin execute failed: Config matching query does not exist."}),
            ):
                result = resource.risk.get_task_status.perform_request({"task_id": "1"})
            assert result["state"] == "FAILED"
            assert "Config matching query does not exist" in result["failure_hint"]
            # 节点错误取不到 → 通用指引。上一次失败已把节点写成终态，换一条仍在运行的测试单。
            _create_test_node(risk, task_id="2")
            with mock.patch("services.web.risk.resources.bksec.ensure_strategy_edit_permission"), mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_task_status",
                mock.Mock(return_value=make_failed_status()),
            ), mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_node_data",
                mock.Mock(side_effect=Exception("boom")),
            ):
                result = resource.risk.get_task_status.perform_request({"task_id": "2"})
            assert result["failure_hint"] == resource.risk.get_task_status.GENERIC_HINT
            # 成功状态不附带提示
            _create_test_node(risk, task_id="3")
            with mock.patch("services.web.risk.resources.bksec.ensure_strategy_edit_permission"), mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_task_status",
                mock.Mock(return_value={"state": "FINISHED"}),
            ):
                result = resource.risk.get_task_status.perform_request({"task_id": "3"})
            assert "failure_hint" not in result

    def test_task_status_unknown_task_does_not_query_sops(self):
        """task_id 对不上测试节点时 404，不回源 SOPS"""
        with mock.patch("services.web.risk.resources.bksec.api.bk_sops.get_task_status") as get_status:
            with pytest.raises(Http404):
                resource.risk.get_task_status.perform_request({"task_id": "999"})
        get_status.assert_not_called()

    def test_task_status_ignores_formal_node(self):
        """正式派单节点即使 task_id 命中，也不能经测试状态接口回源"""
        with RiskContext() as risk:
            TicketNode.objects.create(
                risk_id=risk.risk_id,
                operator="tester",
                action="AutoProcess",
                timestamp=1,
                time="2026-01-01 00:00:00",
                process_result={"task": {"task_id": 9}},
                extra={},
                is_test=False,
            )
            with mock.patch("services.web.risk.resources.bksec.api.bk_sops.get_task_status") as get_status:
                with pytest.raises(Http404):
                    resource.risk.get_task_status.perform_request({"task_id": "9"})
            get_status.assert_not_called()

    def test_task_status_requires_strategy_edit_permission(self):
        """命中测试节点后，无策略编辑权限则拒绝，且不回源 SOPS"""
        with RiskContext() as risk:
            _create_test_node(risk, task_id=42)
            with mock.patch("services.web.risk.permissions.PermissionService") as service_cls, mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_task_status"
            ) as get_status:
                service_cls.return_value.is_allowed.side_effect = PermissionException("编辑策略", {})
                with pytest.raises(PermissionException):
                    resource.risk.get_task_status.perform_request({"task_id": "42"})
            get_status.assert_not_called()

    def test_task_status_matches_integer_task_id(self):
        """task_id 以数字落库时，字符串入参仍能定位测试节点"""
        with RiskContext() as risk:
            _create_test_node(risk, task_id=7)
            with mock.patch("services.web.risk.resources.bksec.ensure_strategy_edit_permission") as ensure, mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_task_status",
                return_value={"state": "RUNNING"},
            ) as get_status:
                result = resource.risk.get_task_status.perform_request({"task_id": "7"})
            assert result["state"] == "RUNNING"
            assert result["task_id"] == "7"
            ensure.assert_called_once_with(risk.strategy_id)
            get_status.assert_called_once()

    def test_task_status_risk_id_without_own_node_returns_empty(self):
        """刷新恢复只定位本人的测试单；没有则空结果，不回源"""
        with RiskContext() as risk:
            _create_test_node(risk, task_id=8, operator="other")
            with mock.patch("services.web.risk.resources.bksec.get_request_username", return_value="me"), mock.patch(
                "services.web.risk.resources.bksec.api.bk_sops.get_task_status"
            ) as get_status:
                assert resource.risk.get_task_status.perform_request({"risk_id": risk.risk_id}) == {}
            get_status.assert_not_called()

    def test_task_status_permission_uses_node_strategy(self):
        """视图层：task_id 定位到测试节点后，按该风险所属策略鉴权"""
        with RiskContext() as risk:
            _create_test_node(risk, task_id=42)
            request = mock.Mock(query_params={"task_id": "42"}, data={})
            permission = BkSecTestTaskStatusPermission()
            with mock.patch("services.web.risk.permissions.IAMPermission.has_permission", return_value=True) as allowed:
                assert permission.has_permission(request, view=None) is True
            allowed.assert_called_once()
            assert str(permission.resources[0].id) == str(risk.strategy_id)

    def test_task_status_permission_missing_node_skips_iam(self):
        """视图层：task_id 没有对应测试节点时不打 IAM，交给资源层 404"""
        request = mock.Mock(query_params={"task_id": "missing"}, data={})
        permission = BkSecTestTaskStatusPermission()
        with mock.patch("services.web.risk.permissions.IAMPermission.has_permission") as allowed:
            assert permission.has_permission(request, view=None) is True
        allowed.assert_not_called()

    def test_task_status_permission_missing_strategy_rejected(self):
        """只传 risk_id 且风险不存在时，视图层拒绝，不把空实例交给 IAM"""
        request = mock.Mock(query_params={"risk_id": "missing-risk"}, data={})
        permission = BkSecTestTaskStatusPermission()
        with pytest.raises(ValidationError):
            permission.has_permission(request, view=None)


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

    def test_push_failure_only_for_builtin_pa_and_keeps_success(self):
        """只有内置发单套餐失败才记推送失败，已成功不被其他套餐失败盖掉。"""
        from apps.sops.constants import SOPSTaskStatus
        from services.web.risk.constants import BkSecPushStatus
        from services.web.risk.handlers.ticket import AutoProcess

        builtin = ProcessApplication.objects.create(
            name="builtin-pa", sops_template_id=10001, need_approve=False, is_enabled=True, is_builtin=True
        )
        other = ProcessApplication.objects.create(
            name="other-pa", sops_template_id=10002, need_approve=False, is_enabled=True, is_builtin=False
        )
        failed = {"state": SOPSTaskStatus.FAILED.value}
        with RiskContext() as risk:
            handler = AutoProcess(risk_id=risk.risk_id, operator="admin")
            handler.update_status(
                {"status": failed, "pa_id": other.id},
                pa_config={"auto_close_risk": False},
            )
            risk.refresh_from_db()
            assert risk.bksec_push_status == BkSecPushStatus.NOT_PUSHED

            handler.update_status(
                {"status": failed, "pa_id": builtin.id},
                pa_config={"auto_close_risk": False},
            )
            risk.refresh_from_db()
            assert risk.bksec_push_status == BkSecPushStatus.FAILED

            risk.bksec_push_status = BkSecPushStatus.SUCCESS
            risk.save(update_fields=["bksec_push_status"])
            handler.risk.refresh_from_db()
            handler._reused_task_node = mock.Mock(process_result={"pa_id": other.id})
            handler.update_status({"status": failed}, pa_config={"auto_close_risk": False})
            risk.refresh_from_db()
            assert risk.bksec_push_status == BkSecPushStatus.SUCCESS
