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
import logging
import uuid
from typing import List, Optional

from bk_resource import api
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from core.models import get_request_username
from services.web.risk.bksec.config import BkSecConfig
from services.web.risk.bksec.constants import (
    BKSEC_CACHE_TIMEOUT,
    BKSEC_PARAM_OPERATOR,
    BKSEC_PARAM_RISK_TYPE_EXTRA,
    BKSEC_PARAM_TARGET,
    BKSEC_PARAM_TARGET_TYPE,
    BKSEC_PRESET_PA_NAME,
    BKSEC_RISK_ACCESS_MAX_PAGES,
    BKSEC_RISK_ACCESS_ORDERING,
    BKSEC_RISK_ACCESS_PAGE_SIZE,
    BKSEC_RISK_TYPES_CACHE_KEY,
)
from services.web.risk.bksec.contract import build_plugin_constants
from services.web.risk.constants import BkSecPushStatus
from services.web.risk.models import ProcessApplication, Risk
from services.web.strategy_v2.models import Strategy

logger = logging.getLogger("celery")


def preset_template_id() -> Optional[int]:
    """环境变量 BKAPP_BKSEC_SOPS_TEMPLATE_ID。未配置或不是整数时返回 None。"""
    raw = getattr(settings, "BKSEC_SOPS_TEMPLATE_ID", None)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def find_preset_pa() -> Optional[ProcessApplication]:
    """
    查找 BKSEC 预置发单套餐（is_builtin=True 且 sops_template_id=BKSEC_SOPS_TEMPLATE_ID）
    """
    template_id = preset_template_id()
    if template_id is None:
        return None
    return ProcessApplication.objects.filter(is_builtin=True, sops_template_id=template_id).order_by("-id").first()


def _ensure_preset_pa_platform_binding(pa: ProcessApplication) -> None:
    """内置套餐固定为平台级绑定，全部场景可见。"""

    from services.web.scene.constants import (
        BindingType,
        ResourceVisibilityType,
        VisibilityScope,
    )
    from services.web.scene.models import ResourceBinding

    binding, _created = ResourceBinding.objects.get_or_create(
        resource_type=ResourceVisibilityType.PROCESS_APPLICATION.value,
        resource_id=str(pa.id),
        defaults={
            "binding_type": BindingType.PLATFORM_BINDING.value,
            "visibility_type": VisibilityScope.ALL_SCENES.value,
        },
    )
    if (
        binding.binding_type != BindingType.PLATFORM_BINDING.value
        or binding.visibility_type != VisibilityScope.ALL_SCENES.value
    ):
        binding.binding_type = BindingType.PLATFORM_BINDING.value
        binding.visibility_type = VisibilityScope.ALL_SCENES.value
        binding.save(update_fields=["binding_type", "visibility_type"])


def _builtin_pa_uniq_id(template_id: int) -> str:
    """同一模板的内置套餐固定 uniq_id，并发插入会撞上已有唯一约束。"""

    return uuid.uuid5(uuid.NAMESPACE_OID, "bksec-builtin-pa:{}".format(template_id)).hex


def ensure_preset_pa() -> Optional[ProcessApplication]:
    """
    按当前模板 ID 幂等补齐内置套餐。

    没有对应的内置套餐才插入一条。已有同模板 ID 的内置套餐保持原样，
    其他套餐的模板 ID 也不改。环境变量以后换成新模板 ID 时，再插入一条新的内置套餐。
    未配置模板 ID 时不创建，返回 None。
    两个请求同时查空时，后插入的请求撞上 uniq_id 唯一约束，再查回先插入的那条。
    补齐或再次命中时，把套餐绑成平台级、全部场景可见。
    """
    template_id = preset_template_id()
    if template_id is None:
        return None
    existing = find_preset_pa()
    if existing is not None:
        _ensure_preset_pa_platform_binding(existing)
        return existing
    try:
        # 规则同步包在外层事务里。嵌套事务把唯一冲突限制在这次插入，不回滚外层。
        with transaction.atomic():
            pa = ProcessApplication.objects.create(
                uniq_id=_builtin_pa_uniq_id(template_id),
                name=BKSEC_PRESET_PA_NAME,
                sops_template_id=template_id,
                need_approve=False,
                is_enabled=True,
                is_builtin=True,
            )
    except IntegrityError:
        pa = find_preset_pa()
        if pa is None:
            raise
    _ensure_preset_pa_platform_binding(pa)
    return pa


def _risk_access_cache_identity(as_platform: bool) -> str:
    """缓存身份维度：平台同步固定 platform；前端按请求用户隔离，防止跨身份缓存污染"""
    if as_platform:
        return "platform"
    return get_request_username() or "anonymous"


def fetch_risk_access_items(
    project_id: str = "", is_formal: str = "", use_cache: bool = True, as_platform: bool = False
) -> List[dict]:
    """
    拉取风险类型列表（循环翻页取全量）

    risk_access_list 响应为分页结构（count/results），默认页容量未知且可能截断，
    单页取会导致 token 漏匹配（启用保存被误阻断）、下拉缺项，故统一翻页取全量；
    短页 / 空页 / 达 count / 翻页上限即停，防止异常接口空转。

    翻页固定带 ordering=created_at：接口默认无序，翻页期间数据增删会让 offset 错位（漏取/重复）。

    project_id：项目维度（risk_access 必传），风险类型归属项目，须与 risk_type_id 联合定位；
    由调用方（策略配置 / 预览 / 测试发送）显式传入，无全局兜底。
    as_platform：认证形态——True 走平台身份（RiskAccessListAsPlatform，同步 config 取 token），
    False 走用户身份（RiskAccessList，前端下拉随请求者凭证，网关按用户数据域出数据）。
    缓存按 项目 + is_formal + 身份维度隔离（项目/身份的数据域不同，混用会互相污染）。
    use_cache=True 时缓存 BKSEC_CACHE_TIMEOUT 秒（下拉等只读展示，容忍短暂陈旧）；
    达翻页上限视为结果不完整，不写缓存，避免把截断结果固化 BKSEC_CACHE_TIMEOUT 秒。

    平台身份（as_platform=True）结果含 token 凭证，一律不落缓存：其缓存 key 恒为 platform，
    任一调用写入即对全站可见，等于把全量 token 明文存进 redis；且 token 轮换后缓存会写旧值。
    """
    # 凭证不落缓存（结构性保证：不依赖调用方自觉传 use_cache=False）
    use_cache = use_cache and not as_platform
    cache_key = "{}:{}:{}:{}".format(
        BKSEC_RISK_TYPES_CACHE_KEY,
        _risk_access_cache_identity(as_platform),
        project_id or "_",
        is_formal or "_",
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
                project_id=project_id or "",
                is_formal=is_formal or None,
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
            is_formal or "_",
            BKSEC_RISK_ACCESS_MAX_PAGES,
            len(items),
        )
        return items
    if use_cache:
        cache.set(cache_key, items, timeout=BKSEC_CACHE_TIMEOUT)
    return items


def find_risk_access_item(
    risk_type_id: str, project_id: str = "", use_cache: bool = False, as_platform: bool = True
) -> Optional[dict]:
    """
    按 项目 + risk_type_id 查找风险类型（取 token 用）

    默认平台身份（同步插件 Config 取 token 的专用路径，不受操作者数据域影响）。
    平台身份结果不落缓存（见 fetch_risk_access_items），保证 token 轮换后写入插件的是新值。
    """
    for is_formal in ("true", "false"):
        for item in fetch_risk_access_items(
            project_id=project_id, is_formal=is_formal, use_cache=use_cache, as_platform=as_platform
        ):
            if str(item.get("id")) == str(risk_type_id):
                return item
    return None


def is_risk_type_visible(risk_type_id: str, project_id: str = "", as_platform: bool = False) -> bool:
    """
    校验 (项目, risk_type_id) 是否在指定身份可见的风险类型范围内（默认用户身份）

    下拉（用户身份）的过滤只是「看不见」，而取 token 走平台身份不受数据域影响：
    若不在写路径显式校验，调用方可绕过前端直传任意 project_id / risk_type_id，借平台身份
    拿到越权 token 并写入插件 Config。故保存/测试等写路径须先过本校验。

    项目越权由本校验天然覆盖：用用户身份查无权项目时网关返回空列表，risk_type_id 必然匹配不上，
    故无需再单独调 project_choices 校验一次项目权限。

    无用户上下文（后台任务）时用户身份请求会被框架降级为平台身份，等价于不裁剪，不会误阻断。
    """
    for is_formal in ("true", "false"):
        # 写路径不走展示缓存。权限收回后，下一次保存或测试必须重新向网关确认。
        for item in fetch_risk_access_items(
            project_id=project_id, is_formal=is_formal, use_cache=False, as_platform=as_platform
        ):
            if str(item.get("id")) == str(risk_type_id):
                return True
    return False


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
    组装工单预览：审计侧渲染最终参数后调用 BKSEC，返回 BKSEC 实际工单字段
    """
    ensure_bksec_enabled()
    if risk is None:
        return {
            "risk_type_id": config.risk_type_id,
            "risk_type_name": config.risk_type_name,
            "has_sample_risk": False,
            "ticket": {
                "risk_type": config.risk_type_id,
                "source": "bk-audit",
                "risk_id": "",
                "fields": {},
            },
            "warnings": [],
        }

    try:
        constants = build_plugin_constants(config, risk=risk)
        operator = constants.get(BKSEC_PARAM_OPERATOR) or "[]"
        operator = ",".join(str(item) for item in json.loads(operator))
        extra = json.loads(constants.get(BKSEC_PARAM_RISK_TYPE_EXTRA) or "{}")
        preview_params = {
            "project_id": config.project_id,
            "risk_type_id": config.risk_type_id,
            "operator": operator,
            "data_source": risk.event_source or "bk-audit",
            "target": constants.get(BKSEC_PARAM_TARGET, ""),
            "target_type": constants.get(BKSEC_PARAM_TARGET_TYPE, ""),
            "source_type": config.source_type or "bk-audit",
            "timestamp": int(risk.event_time.timestamp() * 1000),
            "extra": extra,
        }
    except Exception as err:  # NOCC:broad-except(预览即时报错，区别于正式发送的失败重试链路)
        raise serializers.ValidationError(gettext_lazy("字段模板渲染失败，请检查变量语法：%s") % err)

    try:
        result = api.bk_sec.preview_ticket_fields(preview_params) or {}
    except Exception as err:  # NOCC:broad-except(预览接口异常需转为用户可读错误)
        logger.exception("[BkSecPreview] preview_ticket_fields failed, risk_id=%s", risk.risk_id)
        raise serializers.ValidationError(gettext_lazy("BKSEC 工单字段预览失败：%s") % err)

    fields = {
        str(item.get("key")): item.get("value")
        for item in (result.get("fields") or [])
        if isinstance(item, dict) and item.get("key")
    }
    warnings = []
    if not operator.strip():
        warnings.append(gettext_lazy("初始责任人为空（该风险单无责任人且未配置安全接口人兜底），工单可能被 BKSEC 拒收，请到系统配置设置安全接口人或调整映射"))
    return {
        "risk_type_id": config.risk_type_id,
        "risk_type_name": config.risk_type_name,
        "has_sample_risk": True,
        "ticket": {
            "risk_type": config.risk_type_id,
            "source": "bk-audit",
            "risk_id": risk.risk_id,
            "fields": fields,
        },
        "warnings": warnings,
    }


def prepare_test_constants(strategy: Strategy, config: BkSecConfig, risk: Risk, test_receivers: List[str]) -> dict:
    """
    测试发送前置：必填校验 → 插件 Config 同步 → 渲染终值入参。

    - 必填校验 validate_for_submit 只执行一次；
    - Config 同步用独立测试 key（{strategy_id}_test），不影响正式配置；
      策略未保存时也要先建测试 Config，插件才能接受本次发送；
    - 测试接收人：BKSEC push_event 发单仅支持单人，取首个非空接收人覆盖 ${operator}
      （契约兼容单值 operator，保证测试单隔离）。没有有效接收人则拒绝，避免落到正式责任人。
    - once_task 由 build_plugin_constants 固定为测试模式，不根据接收人是否为空推导。
    """
    try:
        config.validate_for_submit()
    except ValueError as err:
        raise serializers.ValidationError(gettext_lazy("BKSEC 配置不合法：%s") % err)
    receivers = [str(item or "").strip() for item in test_receivers or []]
    receivers = [item for item in receivers if item]
    if not receivers:
        raise serializers.ValidationError(gettext_lazy("至少指定一个测试接收人"))
    from services.web.risk.bksec.rules import sync_plugin_config

    success, message = sync_plugin_config(strategy, config, is_test=True)
    if not success:
        # 下游诊断原文只落服务端日志，避免插件响应/内部地址透传给调用方
        logger.error(
            "[BkSecTestSend] Plugin config sync failed, strategy_id=%s diagnosis=%s",
            strategy.strategy_id,
            message,
        )
        raise serializers.ValidationError(gettext_lazy("测试前插件配置同步失败，请稍后重试；若持续失败请联系管理员"))
    try:
        return build_plugin_constants(config, risk=risk, test_operator=receivers[0])
    except Exception as err:  # NOCC:broad-except(测试发送即时报错，便于定位配置问题)
        raise serializers.ValidationError(gettext_lazy("字段模板渲染失败，请检查变量语法：%s") % err)


def has_bksec_ticket_sent(risk: Risk) -> bool:
    """
    该风险单的 BKSEC 工单是否已推送成功（权威来源：风险单上的推送状态）

    插件在 BKSEC 推单返回 2xx 那一刻主动上报置为「推送成功」，这是唯一可信来源：
    SOPS 侧只能证明「套餐跑了」，不能证明「工单发了」。
    """

    return risk.bksec_push_status == BkSecPushStatus.SUCCESS
