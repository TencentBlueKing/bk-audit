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

from services.web.risk.constants import RiskStatus
from services.web.risk.handlers.ticket import AutoProcess, NewRisk
from services.web.risk.models import ProcessApplication, RiskRule
from tests.test_bksec.test_bksec import BKSEC_CONFIG_DATA
from tests.test_risk.test_tickets.base import RiskContext
from tests.test_risk.test_tickets.constants import (
    RISK_INFO,
    SOPS_FLOW_INFO,
    SOPS_FLOW_STATUS,
)

# 插件契约模板：12 个字段级常量（截取关键项）
SOPS_TEMPLATE_INFO = {
    "pipeline_tree": {
        "constants": {
            key: {"key": key, "show_type": "show", "source_type": "custom"}
            for key in [
                "${risk_id}",
                "${event_content}",
                "${event_evidence}",
                "${event_type}",
                "${event_data}",
                "${event_time}",
                "${event_source}",
                "${operator}",
                "${target_type}",
                "${target}",
                "${strategy_id}",
                "${raw_event_id}",
                "${risk_type_extra}",
                "${once_task}",
            ]
        }
    }
}

# 预置套餐 pa_params（由 build_pa_params 生成的结构，字段级契约）
PA_PARAMS = {
    "${risk_id}": {"field": "risk_id", "value": ""},
    "${event_content}": {"field": "event_content", "value": ""},
    "${event_evidence}": {"field": "event_evidence", "value": ""},
    "${event_data}": {"field": "event_data", "value": ""},
    "${event_time}": {"field": "event_time", "value": ""},
    "${event_source}": {"field": "event_source", "value": ""},
    "${strategy_id}": {"field": "strategy_id", "value": ""},
    "${raw_event_id}": {"field": "raw_event_id", "value": ""},
    "${event_type}": {"field": "event_type", "value": ""},
    "${target_type}": {"field": "", "value": "tencentcloud_sub_user"},
    "${target}": {"field": "", "value": "风险单 {{ risk.risk_id }} 的资产信息"},
    "${risk_type_extra}": {
        "field": "",
        "value": json.dumps(
            {
                "target": "风险单 {{ risk.risk_id }} 的资产信息",
                "target_type": "tencentcloud_sub_user",
                "operator": "{{ risk.operator }}",
                "description": "{{ risk.event_content }}",
            },
            ensure_ascii=False,
        ),
    },
    "${operator}": {"field": "", "value": "{{ risk.operator }}"},
    "${once_task}": {"field": "", "value": "no"},
}


def _prepare_rule(settings, strategy_id: int) -> None:
    """创建预置套餐 + 自动规则（scope=strategy_id）"""
    from services.web.risk.bksec.constants import BKSEC_PRESET_PA_NAME

    settings.BKSEC_SOPS_TEMPLATE_ID = "10001"
    RiskRule.objects.all().delete()
    ProcessApplication.objects.all().delete()
    pa = ProcessApplication.objects.create(
        name=str(BKSEC_PRESET_PA_NAME), sops_template_id=10001, need_approve=False, is_builtin=True
    )
    rule = RiskRule.objects.create(
        name=f"【自动】策略 {strategy_id} BKSEC发单",
        scope=[{"field": "strategy_id", "operator": "=", "value": [strategy_id]}],
        pa_id=pa.id,
        pa_params=PA_PARAMS,
        auto_close_risk=False,
        version=1,
        is_enabled=True,
        auto_strategy_id=strategy_id,
    )
    rule.rule_id = rule.id
    rule.save(update_fields=["rule_id"])


@pytest.mark.django_db
class TestNewRiskBkSecFallback:
    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock())
    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock())
    def test_operatorless_risk_skips_rule_when_bksec_disabled(self):
        """未启用 BKSEC 的策略维持原语义：无责任人不走规则"""
        from services.web.strategy_v2.models import Strategy

        strategy_id = RISK_INFO["strategy_id"]
        strategy, _ = Strategy.objects.get_or_create(
            strategy_id=strategy_id, defaults={"strategy_name": f"test_strategy_{strategy_id}"}
        )
        strategy.bksec_config = {"enabled": False}
        strategy.save(update_fields=["bksec_config"])
        RiskRule.objects.all().delete()
        with RiskContext(risk_info={"operator": []}) as risk:
            NewRisk(risk_id=risk.risk_id, operator="admin").run()
            risk.refresh_from_db()
            assert risk.rule_id is None
            assert risk.status == RiskStatus.AWAIT_PROCESS


@pytest.mark.django_db
class TestAutoProcessBkSecRender:
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_task_status", mock.Mock(return_value=SOPS_FLOW_STATUS)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_template_info", mock.Mock(return_value=SOPS_TEMPLATE_INFO)
    )
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.create_task", mock.Mock(return_value=SOPS_FLOW_INFO))
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.start_task", mock.Mock(return_value=None))
    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock())
    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock())
    def test_auto_process_renders_event_constant(self, settings):
        """正式发送：事件契约常量按风险/事件上下文渲染后传给 SOPS"""
        strategy_id = RISK_INFO["strategy_id"]
        _prepare_rule(settings, strategy_id)
        from services.web.strategy_v2.models import Strategy

        strategy, _ = Strategy.objects.get_or_create(
            strategy_id=strategy_id, defaults={"strategy_name": f"test_strategy_{strategy_id}"}
        )
        strategy.bksec_config = BKSEC_CONFIG_DATA
        strategy.save(update_fields=["bksec_config"])
        with RiskContext() as risk:
            risk.status = RiskStatus.AUTO_PROCESS
            risk.rule_id = RiskRule.objects.get(auto_strategy_id=strategy_id).rule_id
            risk.rule_version = 1
            risk.save(update_fields=["status", "rule_id", "rule_version"])
            with mock.patch(
                "services.web.risk.bksec.render.load_risk_events",
                mock.Mock(return_value=[{"event_id": "e1"}, {"event_id": "e2"}]),
            ):
                AutoProcess(risk_id=risk.risk_id, operator="admin").run()
            risk.refresh_from_db()
            # 校验传给 SOPS 的常量已完成变量渲染
            from services.web.risk.handlers.ticket import api as ticket_api

            call_kwargs = ticket_api.bk_sops.create_task.call_args
            constants = call_kwargs.kwargs["constants"]
            # 字段级契约：标准字段按 field 映射取值（含 event_type）
            assert constants["${risk_id}"] == risk.risk_id
            assert constants["${event_type}"] == '["SuperPermission"]'
            # event_data 还原为事件拓展数据（Risk.event_data，非字段映射）
            assert json.loads(constants["${event_data}"]) == {"username": "admin"}
            # risk_type_extra 承载全部字段映射（含 target/target_type/operator），模板已按风险渲染
            extra = json.loads(constants["${risk_type_extra}"])
            assert "description" in extra and "{{" not in extra["description"]
            # target 独立入参模板已渲染
            assert risk.risk_id in constants["${target}"]
            # operator 兜底模板已渲染（json.loads 校验通过，数组串契约）
            assert constants["${operator}"] == '["admin"]'
