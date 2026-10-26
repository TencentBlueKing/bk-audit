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
from django.core.cache import cache
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from apps.sops.constants import SOPSTaskStatus
from services.web.risk.bksec.config import BkSecConfig
from services.web.risk.bksec.constants import (
    BKSEC_CACHE_TIMEOUT,
    BKSEC_FIELD_INITIAL_OWNER,
    BKSEC_RISK_ACCESS_MAX_PAGES,
    BKSEC_RISK_ACCESS_PAGE_SIZE,
    BKSEC_RISK_TYPES_CACHE_KEY,
)
from services.web.risk.bksec.contract import build_event_payload, build_plugin_constants
from services.web.risk.bksec.render import build_risk_data
from services.web.risk.models import Risk, TicketNode
from services.web.strategy_v2.models import Strategy

logger = logging.getLogger("celery")


def fetch_risk_access_items(is_formal: str = "true", use_cache: bool = True) -> List[dict]:
    """
    拉取风险类型列表（循环翻页取全量）

    risk_access_list 响应为分页结构（count/results），默认页容量未知且可能截断，
    单页取会导致 token 漏匹配（启用保存被误阻断）、下拉缺项，故统一翻页取全量；
    短页 / 空页 / 达 count / 翻页上限即停，防止异常接口空转。

    use_cache=True 时按 is_formal 维度缓存 BKSEC_CACHE_TIMEOUT 秒（下拉等只读展示，
    容忍短暂陈旧）；token 等凭证查找须传 use_cache=False 保证新鲜，避免轮换后写旧值。
    """
    cache_key = "{}:{}".format(BKSEC_RISK_TYPES_CACHE_KEY, is_formal or "true")
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    items: List[dict] = []
    for page in range(1, BKSEC_RISK_ACCESS_MAX_PAGES + 1):
        result = (
            api.bk_sec.risk_access_list(
                project_id=settings.BKSEC_PROJECT_ID or "",
                is_formal=is_formal or "true",
                page=page,
                page_size=BKSEC_RISK_ACCESS_PAGE_SIZE,
            )
            or {}
        )
        batch = result.get("results") or []
        items.extend(item for item in batch if isinstance(item, dict))
        total = result.get("count")
        # 终止：空页 / 达 count / 短页（兼容接口不返回 count）
        if not batch or (isinstance(total, int) and len(items) >= total) or len(batch) < BKSEC_RISK_ACCESS_PAGE_SIZE:
            break
    if use_cache:
        cache.set(cache_key, items, timeout=BKSEC_CACHE_TIMEOUT)
    return items


def find_risk_access_item(risk_type_id: str, use_cache: bool = False) -> Optional[dict]:
    """
    按 risk_type_id 查找风险类型（取 token 用）

    is_formal=true 优先，找不到再用 false 兜底（存量测试类型也可能配了 token）。
    默认不走缓存：token 为凭证，须保证新鲜。
    """
    for is_formal in ("true", "false"):
        for item in fetch_risk_access_items(is_formal=is_formal, use_cache=use_cache):
            if str(item.get("id")) == str(risk_type_id):
                return item
    return None


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


def build_ticket_preview(config: BkSecConfig, risk: Optional[Risk]) -> dict:
    """
    组装工单预览（按配置 + 样例风险单渲染报文，不实际发送，支持保存前预览）
    """
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
    risk_id = getattr(risk, "risk_id", "") or ""
    ticket_header = {
        "ticket_id": risk_id,
        "title": "{}（安全工单）".format(risk_data.get("title", "")),
        "submit_time": risk_data.get("event_time", ""),
        "deadline": risk_data.get("event_time", ""),
        "status": "待受理",
        "current_operator_org": "",
    }
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


def build_test_constants(config: BkSecConfig, risk: Risk, test_receivers: List[str]) -> dict:
    """组装测试发送的插件入参常量（按样例风险单渲染成终值）。"""
    try:
        config.validate_for_submit()
    except ValueError as err:
        raise serializers.ValidationError(gettext_lazy("BKSEC 配置不合法：%s") % err)
    # 测试接收人：BKSEC push_event 发单仅支持单人，取首个作为测试处理人（契约兼容单值 operator）
    test_operator = test_receivers[0] if test_receivers else ""
    try:
        return build_plugin_constants(config, risk=risk, test_operator=test_operator)
    except Exception as err:  # NOCC:broad-except(测试发送即时报错，便于定位配置问题)
        raise serializers.ValidationError(gettext_lazy("字段模板渲染失败，请检查变量语法：%s") % err)


def validate_bksec_test_target(risk: Risk) -> None:
    """
    校验该风险单是否已成功发送过正式工单，已成功则拒绝测试发送

    仅当正式派单已成功（SOPS 任务 FINISHED）时拒绝：插件的回调按风险单复用，
    在其上发送测试工单会干扰正式回调或被静默拦截。
    派单失败/被终止/已过期的单据未真正发出工单，允许测试，避免自动派单策略下无样例单可用。

    判定语义（保守拦截，避免与进行中的正式单干扰）：
    - 终态 FINISHED → 拒绝；终态 FAILED/REVOKED/EXPIRED → 放行
    - 非终态（CREATED/RUNNING/...）→ 回查 SOPS 实时状态后按 FINISHED 与否判定
    - 状态不可判定（无 task_id / 回查异常）→ 保守按已发出（拒绝）
    """
    node = (
        TicketNode.objects.filter(risk_id=risk.risk_id, action="AutoProcess", is_test=False)
        .order_by("-timestamp")
        .first()
    )
    if node is None:
        return
    process_result = node.process_result or {}
    state = (process_result.get("status") or {}).get("state") or ""
    succeeded = False
    if state not in SOPSTaskStatus.get_finished_status():
        task_id = (process_result.get("task") or {}).get("task_id")
        if not task_id:
            succeeded = True  # 无从判定：保守按已发出拦截
        else:
            try:
                status = api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
                succeeded = ((status or {}).get("state") or "") in SOPSTaskStatus.get_success_status()
            except Exception as err:  # NOCC:broad-except(状态不可判定时保守拦截)
                logger.warning(
                    "[BkSec] get sops task status failed, risk_id=%s task_id=%s err=%s", risk.risk_id, task_id, err
                )
                succeeded = True  # 无从判定：保守按已发出拦截
    else:
        succeeded = state in SOPSTaskStatus.get_success_status()
    if not succeeded:
        return
    raise serializers.ValidationError(
        gettext_lazy("该风险单已有成功的正式派单记录：插件的回调按风险单复用，在其上发送测试工单会干扰正式回调或被静默拦截，请选择一张未成功发送过正式工单的风险单进行测试")
    )


DEFAULT_FAILURE_HINT = gettext_lazy("任务执行失败")
FAILURE_HINT_MAX_LEN = 200
# 回源取节点错误时最多查询的失败节点数（避免子流程里大量失败节点打爆 SOPS）
MAX_FETCH_ERROR_NODES = 5


def iter_status_nodes(node: dict):
    """深度遍历 SOPS 任务状态树（失败节点可能嵌套在子流程里）"""
    for child in (node.get("children") or {}).values():
        if not isinstance(child, dict):
            continue
        yield child
        yield from iter_status_nodes(child)


def fill_failure_info(status: dict, task_id: str = "", generic=DEFAULT_FAILURE_HINT) -> str:
    """
    补全失败信息：回写逐节点错误 + 返回记录级失败提示（原地修改 status 并返回提示文本）

    一次完成两件事（写入点共用：终态同步 / 重试前快照 / 建单 / 测试轮询）：
    - 写 error_message：SOPS get_task_status 不返回错误文本（只在 get_node_data 的 ex_data 里），
      对失败节点回源取错误并写入 status.children[].error_message，
      供执行记录详情 / 重试快照的 attempts 展示逐节点失败原因；
    - 写 failure_hint：返回第一个取到错误的失败节点文本（截 FAILURE_HINT_MAX_LEN）作记录级摘要，
      由写入点落库 TicketNode.process_result["failure_hint"]，查询层只读该字段。

    语义边界：已回写过 error_message 的节点不再回源（读已存优先）；单节点回源失败静默跳过；
    全部取不到返回 generic；最多回源 MAX_FETCH_ERROR_NODES 个失败节点。
    """

    def _extract_error_texts(node_data: dict) -> List[str]:
        """get_node_data 响应里的错误文本：真实错误在顶层 ex_data / error_message；
        outputs 可能是 [{key, value}] 或 {key: value}，仅取错误类键"""
        texts: List[str] = []
        for key in ("ex_data", "error_message"):
            value = str(node_data.get(key) or "").strip()
            if value:
                texts.append(value)
        outputs = node_data.get("outputs") or {}
        if isinstance(outputs, list):
            items = [(item.get("key"), item.get("value")) for item in outputs if isinstance(item, dict)]
        else:
            items = list(outputs.items())
        for key, value in items:
            value = str(value or "").strip()
            if value and ("error" in str(key).lower() or "ex_data" in str(key).lower()):
                texts.append(value)
        return texts

    if not status:
        return str(generic)
    failed_states = {s.value for s in SOPSTaskStatus.get_failed_status()}
    failed_children = [
        child for child in iter_status_nodes(status) if child.get("state") in failed_states and child.get("id")
    ]
    hint = ""
    fetch_quota = MAX_FETCH_ERROR_NODES
    for child in failed_children:
        error_message = str(child.get("error_message") or "").strip()
        if not error_message and task_id and fetch_quota > 0:
            fetch_quota -= 1
            try:
                node_data = (
                    api.bk_sops.get_node_data(
                        task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID, node_id=str(child["id"])
                    )
                    or {}
                )
            except Exception:  # NOCC:broad-except(单节点取错失败不影响其余节点)
                logger.warning("[FailureHint] Fetch node data failed, task_id=%s node_id=%s", task_id, child["id"])
                node_data = {}
            texts = _extract_error_texts(node_data)
            if texts:
                error_message = "\n".join(dict.fromkeys(texts)).strip()
                child["error_message"] = error_message
        if error_message and not hint:
            hint = error_message
    return hint[:FAILURE_HINT_MAX_LEN] if hint else str(generic)
