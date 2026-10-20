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

import logging
from typing import List, Optional

from bk_resource import api
from django.conf import settings
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from apps.sops.constants import SOPSTaskStatus
from services.web.risk.bksec.config import BkSecConfig
from services.web.risk.bksec.constants import BKSEC_FIELD_INITIAL_OWNER
from services.web.risk.bksec.contract import build_event_payload, build_plugin_constants
from services.web.risk.bksec.variables import build_risk_data
from services.web.risk.models import Risk, TicketNode
from services.web.strategy_v2.models import Strategy

logger = logging.getLogger("celery")


def ensure_bksec_enabled() -> None:
    """
    后端 feature 硬拦截：BKSEC 未启用（开关关 / 必配环境变量缺失 / 内置套餐未就绪）时，
    阻断一切配置解析、预览、测试发送
    """
    if not FeatureHandler(FeatureTypeChoices.BKSEC).check():
        raise serializers.ValidationError(gettext_lazy("BKSEC 功能未启用或环境未就绪（请确认 BKAPP_FEATURE_BKSEC 开关、必配环境变量与内置发单套餐）"))


def parse_bksec_config(config_dict: dict) -> BkSecConfig:
    """解析并校验 BKSEC 配置（启用态硬拦截 + pydantic 解析）。"""
    ensure_bksec_enabled()
    try:
        return BkSecConfig.model_validate(config_dict)
    except ValueError as err:
        raise serializers.ValidationError(gettext_lazy("BKSEC 配置不合法：%s") % err)


def render_bksec_preview(config: BkSecConfig, risk: Optional[Risk]) -> dict:
    """渲染工单预览（按配置 + 样例风险单渲染报文）"""
    ensure_bksec_enabled()
    try:
        payload = build_event_payload(config, risk=risk)
    except Exception as err:  # NOCC:broad-except(预览即时报错，区别于正式发送的失败重试链路)
        raise serializers.ValidationError(gettext_lazy("字段模板渲染失败，请检查变量语法：%s") % err)
    risk_data = build_risk_data(risk)
    warnings = []
    if risk is not None and not (payload.get("fields", {}).get(BKSEC_FIELD_INITIAL_OWNER) or "").strip():
        warnings.append(gettext_lazy("初始责任人为空（该风险单无责任人且未配置安全接口人兜底），工单可能被 BKSEC 拒收，请到系统配置设置安全接口人或调整映射"))
    # 工单头（BKSEC 侧生成，发单前不存在）：后端 mock 占位，仅用于前端预览工单外观，
    # 非审计中心上报内容、不进入真实报文。发单后由 BKSEC 生成真实值。
    ticket_header = _build_mock_ticket_header(risk, risk_data)
    return {
        "risk_type_id": config.risk_type_id,
        "risk_type_name": config.risk_type_name,
        "has_sample_risk": risk is not None,
        "ticket": payload,
        "ticket_header": ticket_header,
        "risk": risk_data,
        "risk_context_keys": list(risk_data.keys()),
        "warnings": warnings,
    }


def _build_mock_ticket_header(risk: Optional[Risk], risk_data: dict) -> dict:
    """
    后端 mock 的 BKSEC 工单头占位（发单前这些字段尚不存在，由 BKSEC 侧生成）。

    模拟真实工单结构，让预览效果更真实。
    """
    risk_id = getattr(risk, "risk_id", "") or ""
    return {
        "ticket_id": risk_id,
        "title": "{}（安全工单）".format(risk_data.get("title", "")),
        "submit_time": risk_data.get("event_time", ""),
        "deadline": risk_data.get("event_time", ""),
        "status": "待受理",
        "current_operator_org": "",
    }


def sync_bksec_test_config(strategy: Strategy, config: BkSecConfig) -> None:
    """
    如果策略未保存，就要测试发送，则同步插件侧 Config。
    用独立测试 key（{strategy_id}_test），不影响正式配置。
    """
    try:
        config.validate_for_submit()
    except ValueError as err:
        raise serializers.ValidationError(gettext_lazy("BKSEC 配置不合法：%s") % err)
    from services.web.risk.bksec.rules import sync_plugin_config

    success, message = sync_plugin_config(strategy, config, is_test=True)
    if not success:
        raise serializers.ValidationError(gettext_lazy("测试前插件配置同步失败，无法发送测试工单：%s") % message)


def render_bksec_test_constants(config: BkSecConfig, risk: Risk, test_receivers: List[str]) -> dict:
    """渲染测试发送的插件入参常量。"""
    try:
        config.validate_for_submit()
    except ValueError as err:
        raise serializers.ValidationError(gettext_lazy("BKSEC 配置不合法：%s") % err)
    # 测试接收人：BKSEC 当前仅取首个作为测试处理人（契约兼容单值 operator）
    test_operator = test_receivers[0] if test_receivers else ""
    try:
        return build_plugin_constants(config, risk=risk, test_operator=test_operator)
    except Exception as err:  # NOCC:broad-except(测试发送即时报错，便于定位配置问题)
        raise serializers.ValidationError(gettext_lazy("字段模板渲染失败，请检查变量语法：%s") % err)


def is_auto_process_succeeded(node: TicketNode) -> bool:
    """
    判断该正式派单是否已成功发出工单

    - 终态 FINISHED：视为已成功发出
    - 终态 FAILED/REVOKED/EXPIRED：未真正发出工单，允许在其上测试
    - 非终态（CREATED/RUNNING/...）：保守按已发出处理，避免与进行中的正式单互相干扰
    - 状态不可判定（无 task_id / 查询异常）：保守按已发出处理
    """
    process_result = node.process_result or {}
    state = (process_result.get("status") or {}).get("state") or ""
    if state not in SOPSTaskStatus.get_finished_status():
        task_id = (process_result.get("task") or {}).get("task_id")
        if not task_id:
            return True
        try:
            status = api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        except Exception as err:  # NOCC:broad-except(状态不可判定时保守拦截)
            logger.warning(
                "[BkSec] get sops task status failed, risk_id=%s task_id=%s err=%s", node.risk_id, task_id, err
            )
            return True
        state = (status or {}).get("state") or ""
    return state in SOPSTaskStatus.get_success_status()


def validate_bksec_test_target(risk: Risk) -> None:
    """
    校验该风险单是否已成功发送过正式工单

    仅当正式派单已成功（SOPS 任务 FINISHED）时拒绝测试发送：插件的回调按风险单复用，
    在其上发送测试工单会干扰正式回调或被静默拦截。
    派单失败/被终止/已过期的单据未真正发出工单，允许测试，避免自动派单策略下无样例单可用。
    """
    node = (
        TicketNode.objects.filter(risk_id=risk.risk_id, action="AutoProcess", is_test=False)
        .order_by("-timestamp")
        .first()
    )
    if node is None or not is_auto_process_succeeded(node):
        return
    raise serializers.ValidationError(
        gettext_lazy("该风险单已有成功的正式派单记录：插件的回调按风险单复用，在其上发送测试工单会干扰正式回调或被静默拦截，请选择一张未成功发送过正式工单的风险单进行测试")
    )


FAILURE_HINTS_BY_CHANNEL = {
    FeatureTypeChoices.BKSEC: [
        ("Config matching query does not exist", "插件侧未配置该策略的发单配置（Config 表），请在插件 Admin 为对应 strategy_id 添加后重试"),
        ("业务或执行人校验失败", "插件白名单未放行：请检查插件环境变量 BKAPP_EXECUTOR / BKAPP_BK_BIZ_ID"),
        ("Expecting value", "插件参数格式错误：operator 须为 JSON 数组串、event_type/event_data/event_evidence 须为合法 JSON"),
    ],
}


def translate_failure_hint(channel: str, detail_text: str, generic: str = "任务执行失败") -> str:
    """按渠道将原始错误信息翻译为可操作提示。

    用于写入点（发单 / 测试发单）翻译后落库到 TicketNode.process_result["failure_hint"]，
    查询层（执行记录列表/详情）只读该字段，不感知具体渠道。
    渠道未知或未命中特征时回退原始错误文本；原始错误为空时回退通用提示。
    """
    detail_text = detail_text or ""
    for pattern, hint in FAILURE_HINTS_BY_CHANNEL.get(channel, []):
        if pattern in detail_text:
            return hint
    return detail_text.strip() or generic
