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
from core.models import get_request_username
from services.web.risk.bksec.config import BkSecConfig
from services.web.risk.bksec.constants import (
    BKSEC_CACHE_TIMEOUT,
    BKSEC_FIELD_INITIAL_OWNER,
    BKSEC_RISK_ACCESS_MAX_PAGES,
    BKSEC_RISK_ACCESS_ORDERING,
    BKSEC_RISK_ACCESS_PAGE_SIZE,
    BKSEC_RISK_TYPES_CACHE_KEY,
)
from services.web.risk.bksec.contract import build_event_payload, build_plugin_constants
from services.web.risk.bksec.render import build_risk_data
from services.web.risk.models import ProcessApplication, Risk, TicketNode
from services.web.strategy_v2.models import Strategy

logger = logging.getLogger("celery")


def find_preset_pa() -> Optional[ProcessApplication]:
    """
    查找 BKSEC 预置发单套餐（is_builtin=True 且 sops_template_id=BKSEC_SOPS_TEMPLATE_ID）
    """
    template_id = getattr(settings, "BKSEC_SOPS_TEMPLATE_ID", None)
    if not template_id:
        return None
    try:
        return (
            ProcessApplication.objects.filter(is_builtin=True, sops_template_id=int(template_id))
            .order_by("-id")
            .first()
        )
    except (TypeError, ValueError):
        return None


def _risk_access_cache_identity(as_platform: bool) -> str:
    """缓存身份维度：平台同步固定 platform；前端按请求用户隔离，防止跨身份缓存污染"""
    if as_platform:
        return "platform"
    return get_request_username() or "anonymous"


def fetch_risk_access_items(is_formal: str = "true", use_cache: bool = True, as_platform: bool = False) -> List[dict]:
    """
    拉取风险类型列表（循环翻页取全量）

    risk_access_list 响应为分页结构（count/results），默认页容量未知且可能截断，
    单页取会导致 token 漏匹配（启用保存被误阻断）、下拉缺项，故统一翻页取全量；
    短页 / 空页 / 达 count / 翻页上限即停，防止异常接口空转。

    翻页固定带 ordering=created_at：接口默认无序，翻页期间数据增删会让 offset 错位（漏取/重复）。

    as_platform：认证形态——True 走平台身份（RiskAccessListAsPlatform，同步 config 取 token），
    False 走用户身份（RiskAccessList，前端下拉随请求者凭证，网关按用户数据域出数据）。
    缓存按 is_formal + 身份维度隔离（两种身份数据域可能不同，混用会互相污染）。
    use_cache=True 时缓存 BKSEC_CACHE_TIMEOUT 秒（下拉等只读展示，容忍短暂陈旧）；
    token 等凭证查找须传 use_cache=False 保证新鲜，避免轮换后写旧值。
    达翻页上限视为结果不完整，不写缓存，避免把截断结果固化 BKSEC_CACHE_TIMEOUT 秒。
    """
    cache_key = "{}:{}:{}".format(
        BKSEC_RISK_TYPES_CACHE_KEY, _risk_access_cache_identity(as_platform), is_formal or "true"
    )
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    fetcher = api.bk_sec.risk_access_list_as_platform if as_platform else api.bk_sec.risk_access_list
    items: List[dict] = []
    for page in range(1, BKSEC_RISK_ACCESS_MAX_PAGES + 1):
        result = (
            fetcher(
                project_id=settings.BKSEC_PROJECT_ID or "",
                is_formal=is_formal or "true",
                ordering=BKSEC_RISK_ACCESS_ORDERING,
                page=page,
                page_size=BKSEC_RISK_ACCESS_PAGE_SIZE,
            )
            or {}
        )
        batch = result.get("results") or []
        items.extend(item for item in batch if isinstance(item, dict))
        total = result.get("count")
        # 终止：空页 / 达 count（count 存在时以其为准，短页不可信：
        # 服务端可能自行压缩 page_size 或按权限过滤后返回不足一页，此时仍有下一页）
        if not batch or (isinstance(total, int) and len(items) >= total):
            break
        # count 缺失时才退化用短页判定，兼容不返回 count 的接口
        if not isinstance(total, int) and len(batch) < BKSEC_RISK_ACCESS_PAGE_SIZE:
            break
    else:
        logger.warning(
            "[BkSec] risk_access 列表翻页达上限仍未取完, is_formal=%s pages=%s fetched=%s, "
            "结果不完整（下拉缺项 / token 漏匹配），请确认总量或调大 BKSEC_RISK_ACCESS_MAX_PAGES",
            is_formal or "true",
            BKSEC_RISK_ACCESS_MAX_PAGES,
            len(items),
        )
        return items
    if use_cache:
        cache.set(cache_key, items, timeout=BKSEC_CACHE_TIMEOUT)
    return items


def find_risk_access_item(risk_type_id: str, use_cache: bool = False, as_platform: bool = True) -> Optional[dict]:
    """
    按 risk_type_id 查找风险类型（取 token 用）

    默认平台身份（同步插件 Config 取 token 的专用路径，不受操作者数据域影响）。
    """
    for is_formal in ("true", "false"):
        for item in fetch_risk_access_items(is_formal=is_formal, use_cache=use_cache, as_platform=as_platform):
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


def prepare_test_constants(strategy: Strategy, config: BkSecConfig, risk: Risk, test_receivers: List[str]) -> dict:
    """
    测试发送前置：必填校验 → 插件 Config 同步 → 渲染终值入参。

    - 必填校验 validate_for_submit 只执行一次；
    - Config 同步用独立测试 key（{strategy_id}_test），不影响正式配置；
      策略未保存时也要先建测试 Config，插件才能接受本次发送；
    - 测试接收人：BKSEC push_event 发单仅支持单人，取首个覆盖 ${operator}
      （契约兼容单值 operator，保证测试单隔离）。
    """
    try:
        config.validate_for_submit()
    except ValueError as err:
        raise serializers.ValidationError(gettext_lazy("BKSEC 配置不合法：%s") % err)
    from services.web.risk.bksec.rules import sync_plugin_config

    success, message = sync_plugin_config(strategy, config, is_test=True)
    if not success:
        raise serializers.ValidationError(gettext_lazy("测试前插件配置同步失败，无法发送测试工单：%s") % message)
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
