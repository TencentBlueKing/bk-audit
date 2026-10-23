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

from services.web.risk.bksec import sync_bksec_rule
from services.web.risk.bksec.config import BkSecConfig
from services.web.risk.bksec.constants import (
    BKSEC_PRESET_PA_NAME,
    BKSEC_RULE_PRIORITY_BASE,
)
from services.web.risk.bksec.contract import (
    build_event_payload,
    build_pa_params,
    build_plugin_constants,
    coerce_operator_constant,
)
from services.web.risk.bksec.render import build_render_context, render_value
from services.web.risk.models import ProcessApplication, RiskRule
from tests.test_risk.test_tickets.base import RiskContext
from tests.test_risk.test_tickets.constants import RISK_INFO

BKSEC_CONFIG_DATA = {
    "enabled": True,
    "risk_type_id": "cloud-account-no-mfa",
    "risk_type_name": "云安全-云账号未启用MFA",
    "field_mappings": [
        {"key": "target", "name": "风险资产信息", "value": "风险单 {{ risk.risk_id }} 的资产信息", "required": True},
        {"key": "target_type", "name": "目标资产类型", "value": "tencentcloud_sub_user", "required": True},
        {"key": "operator", "name": "初始责任人", "value": "{{ risk.operator }}", "required": True},
        {"key": "description", "name": "描述", "value": "{{ risk.event_content }}"},
    ],
}


class TestBkSecConfig:
    def test_parse_and_dedupe(self):
        data = {
            **BKSEC_CONFIG_DATA,
            "field_mappings": BKSEC_CONFIG_DATA["field_mappings"] + [BKSEC_CONFIG_DATA["field_mappings"][0]],
        }
        config = BkSecConfig.model_validate(data)
        assert len(config.field_mappings) == 4

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
        assert rule.auto_close_risk is False  # 评审定论：不自动关审计风险
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
