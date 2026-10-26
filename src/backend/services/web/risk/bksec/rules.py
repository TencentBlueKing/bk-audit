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
from typing import Optional

from django.db import transaction
from django.utils.translation import gettext

from api.domains import BKSEC_PLUGIN_CONFIG_API_URL
from services.web.risk.bksec.config import BkSecConfig
from services.web.risk.bksec.constants import (
    BKSEC_AUTO_RULE_NAME,
    BKSEC_RULE_PRIORITY_BASE,
    BkSecConfigSyncFailReason,
    BkSecConfigSyncStage,
)
from services.web.risk.bksec.contract import build_pa_params
from services.web.risk.models import ProcessApplication, RiskRule
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.filters import BindingMetadataHelper
from services.web.scene.models import ResourceBindingScene
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy

logger = logging.getLogger("celery")

# 处理规则的生命周期管理


def load_bksec_config(strategy: Optional[Strategy]) -> Optional[BkSecConfig]:
    """
    解析策略的 BKSEC 配置
    """
    if not strategy:
        return None
    raw = strategy.bksec_config
    if not raw:
        return None
    try:
        return BkSecConfig.model_validate(raw)
    except Exception as err:  # NOCC:broad-except(配置解析降级)
        logger.exception("[BkSecRule] Invalid bksec_config, strategy_id=%s err=%s", strategy.strategy_id, err)
        return None


def _load_strategy_scene_id(strategy: Strategy) -> Optional[int]:
    """
    返回策略归属场景（处理规则需要绑定到策略所在场景）
    """
    return (
        ResourceBindingScene.objects.filter(
            scene__is_deleted=False,
            binding__resource_type=ResourceVisibilityType.STRATEGY,
            binding__resource_id=str(strategy.strategy_id),
        )
        .values_list("scene_id", flat=True)
        .first()
    )


def _top_priority() -> int:
    """
    自动规则优先级：保留段内取值（结构性最高，手动规则恒低于本段）
    """
    latest = RiskRule.objects.filter(priority_index__gte=BKSEC_RULE_PRIORITY_BASE).order_by("-priority_index").first()
    return (latest.priority_index + 1) if latest else BKSEC_RULE_PRIORITY_BASE


def _latest_auto_rule(strategy_id: int) -> Optional[RiskRule]:
    return RiskRule.objects.filter(auto_strategy_id=strategy_id).order_by("-version").first()


def _build_rule_fields(strategy: Strategy, config: BkSecConfig, pa_id: int) -> dict:
    # 构造处理规则参数
    return {
        "name": str(BKSEC_AUTO_RULE_NAME) % strategy.strategy_id,
        "scope": [{"field": "strategy_id", "operator": "=", "value": [strategy.strategy_id]}],
        "pa_id": pa_id,
        "pa_params": build_pa_params(config),
        "auto_close_risk": False,
    }


def _create_rule_version(strategy: Strategy, fields: dict, rule_id: Optional[int] = None) -> RiskRule:
    """
    创建启用的规则新版本（仅内容变更时调用）。
    """
    if rule_id:
        latest = RiskRule.objects.filter(rule_id=rule_id).order_by("-version").first()
        instance = RiskRule.objects.create(
            **fields,
            rule_id=rule_id,
            version=(latest.version + 1) if latest else 1,
            priority_index=_top_priority(),
            created_at=latest.created_at if latest else None,
            created_by=latest.created_by if latest else "",
            auto_strategy_id=strategy.strategy_id,
            is_enabled=True,
        )
        _sync_rule_scene_binding(strategy, instance)
        return instance
    with transaction.atomic():
        instance = RiskRule.objects.create(
            **fields,
            version=1,
            is_enabled=True,
            auto_strategy_id=strategy.strategy_id,
        )
        # 第一版：rule_id = id（与手动创建规则一致）
        instance.rule_id = instance.id
        instance.priority_index = _top_priority()
        instance.save(update_fields=["rule_id", "priority_index"])
        # 绑定到策略所在场景
        _sync_rule_scene_binding(strategy, instance)
    return instance


def _toggle_rule(rule: Optional[RiskRule], is_enabled: bool) -> None:
    """
    原地切换启停
    """
    if rule and rule.is_enabled != is_enabled:
        rule.is_enabled = is_enabled
        rule.save(update_fields=["is_enabled"])
        logger.info("[BkSecRule] Auto rule toggled, rule_id=%s enabled=%s", rule.rule_id, is_enabled)


def _sync_rule_scene_binding(strategy: Strategy, rule: RiskRule) -> None:
    """
    规则场景归属跟随策略：策略改绑场景后同步规则的场景绑定（保持单一场景）
    """
    scene_id = _load_strategy_scene_id(strategy)
    if scene_id is None:
        return
    current_scene_id = (
        ResourceBindingScene.objects.filter(
            binding__resource_type=ResourceVisibilityType.RISK_RULE,
            binding__resource_id=str(rule.rule_id),
        )
        .values_list("scene_id", flat=True)
        .first()
    )
    if current_scene_id == scene_id:
        return
    BindingMetadataHelper.delete_resource_binding(
        resource_id=str(rule.rule_id), resource_type=ResourceVisibilityType.RISK_RULE
    )
    BindingMetadataHelper.create_resource_binding(
        resource_id=str(rule.rule_id),
        resource_type=ResourceVisibilityType.RISK_RULE,
        scene_id=scene_id,
    )
    logger.info("[BkSecRule] Rule scene binding synced, rule_id=%s scene_id=%s", rule.rule_id, scene_id)


@transaction.atomic
def sync_bksec_rule(strategy: Strategy, strategy_alive: Optional[bool] = None) -> Optional[RiskRule]:
    """
    策略保存后自动同步处理规则：
        1. 无处理规则时新建
        2. 有处理规则时
            2.1 启停状态有变更：根据策略的bksec配置状态更新处理规则的启停状态
            2.2 内容有变更：创建启用的新版本

    规则生效条件 = bksec_config.enabled AND 策略启用态。
    """
    config = load_bksec_config(strategy)
    latest = _latest_auto_rule(strategy.strategy_id)
    if strategy_alive is None:
        alive = strategy.status not in (StrategyStatusChoices.DISABLED, StrategyStatusChoices.DRAFT)
    else:
        alive = strategy_alive
    # 未启用（配置关 或 策略停用）→ 原地停用已有规则
    if not (config and config.enabled and alive):
        _toggle_rule(latest, is_enabled=False)
        return None
    # 启用 → 平台策略不支持，跳过并告警
    from services.web.scene.constants import BindingType
    from services.web.scene.models import ResourceBinding

    is_platform = ResourceBinding.objects.filter(
        resource_type=ResourceVisibilityType.STRATEGY,
        resource_id=str(strategy.strategy_id),
        binding_type=BindingType.PLATFORM_BINDING,
    ).exists()
    if is_platform:
        logger.warning(
            "[BkSecRule] Platform strategy is out of BKSEC scope, skip rule sync, strategy_id=%s",
            strategy.strategy_id,
        )
        return None
    # 启用 → 确保预置套餐存在
    from django.conf import settings

    template_id = settings.BKSEC_SOPS_TEMPLATE_ID
    pa = None
    if template_id:
        try:
            pa = (
                ProcessApplication.objects.filter(is_builtin=True, sops_template_id=int(template_id))
                .order_by("-id")
                .first()
            )
        except (TypeError, ValueError):
            pass
    if pa is None:
        logger.warning(
            "[BkSecRule] Preset process application missing (BKSEC_SOPS_TEMPLATE_ID unset?), "
            "skip rule sync, strategy_id=%s",
            strategy.strategy_id,
        )
        return None
    fields = _build_rule_fields(strategy, config, pa.id)
    # 幂等：内容一致 → 仅原地确保启用
    if latest and all(getattr(latest, k) == v for k, v in fields.items()):
        _toggle_rule(latest, is_enabled=True)
        # 场景归属跟随策略（策略改绑场景后规则可见性同步，内容未变不产生新版本）
        _sync_rule_scene_binding(strategy, latest)
        # Config 同步：即使规则内容未变，插件侧凭证/配方可能更新（如用户改了 target_type）
        # 启用路径为保存前置强校验：同步失败则阻断策略保存，避免“假启用”（规则在、插件无 Config、发不出单）
        _ensure_plugin_config_synced(strategy, config)
        return latest
    # 内容变化/首次 → 创建启用的新版本
    instance = _create_rule_version(strategy, fields, rule_id=latest.rule_id if latest else None)
    logger.info(
        "[BkSecRule] Auto rule synced, strategy_id=%s rule_id=%s version=%s",
        strategy.strategy_id,
        instance.rule_id,
        instance.version,
    )
    # 启用路径同步插件 Config，失败阻断保存
    _ensure_plugin_config_synced(strategy, config)
    return instance


def disable_bksec_rule(strategy_id: int) -> None:
    """
    停用策略的自动发单规则
    """
    _toggle_rule(_latest_auto_rule(strategy_id), is_enabled=False)


def sync_plugin_config(strategy: Strategy, config: BkSecConfig, is_test: bool = False) -> tuple:
    """
    同步插件 Config：传业务参数给插件，插件内部构造完整 Config 并存储。

    审计中心传 strategy_id + risk_type_id + source_type + token
    is_test=True 时用 {strategy_id}_test 作为 key，不影响正式配置（测试发送用）。
    返回 (success: bool, message: str)：
        - success=True  → 插件已成功建立/更新 Config
        - success=False → 失败原因（含插件返回的 message 或网络异常信息）

    监控上报（BkSecConfigSyncFailedEvent）保留，供可观测；调用方据此决定是否阻断。
    """
    from services.web.common.monitor import BkSecConfigSyncFailedEvent

    # 同步场景：测试发送（is_test=True）与策略保存走同一同步逻辑，但失败影响不同，需区分上报
    stage = BkSecConfigSyncStage.TEST_SEND if is_test else BkSecConfigSyncStage.STRATEGY_SAVE

    def _report_fail(reason: BkSecConfigSyncFailReason, error: str) -> None:
        """失败上报：维度只放低基数的 stage/fail_reason，错误明细走事件正文"""
        BkSecConfigSyncFailedEvent(
            context={
                "strategy_id": str(strategy.strategy_id),
                "stage": stage.value,
                "fail_reason": reason.value,
            },
            extra={"error": error},
        ).report()

    if not BKSEC_PLUGIN_CONFIG_API_URL:
        message = "BKSEC_PLUGIN_CONFIG_API_URL 未配置，无法同步插件配置"
        logger.warning("[BkSecPluginConfig] %s, strategy_id=%s", message, strategy.strategy_id)
        _report_fail(BkSecConfigSyncFailReason.API_URL_MISSING, message)
        return (False, message)

    # 获取 token（risk_access 列表翻页查找：单页取会截断漏匹配；is_formal=true 优先、false 兜底）
    try:
        from services.web.risk.bksec.service import find_risk_access_item

        # 凭证查找不走缓存（use_cache=False），避免 token 轮换后向插件写入旧值
        item = find_risk_access_item(config.risk_type_id)
        token = (item or {}).get("token", "")
        if not token:
            message = "risk_access 列表接口未返回 risk_type_id=%s 的 token" % config.risk_type_id
            logger.warning(
                "[BkSecPluginConfig] %s, strategy_id=%s risk_type_id=%s",
                message,
                strategy.strategy_id,
                config.risk_type_id,
            )
            _report_fail(BkSecConfigSyncFailReason.TOKEN_MISSING, message)
            return (False, message)
    except Exception as err:
        message = "获取 token 失败：%s" % err
        logger.warning(
            "[BkSecPluginConfig] %s, strategy_id=%s risk_type_id=%s", message, strategy.strategy_id, config.risk_type_id
        )
        _report_fail(BkSecConfigSyncFailReason.TOKEN_FETCH_FAILED, message)
        return (False, message)

    # 测试发送用独立 key，不影响正式配置
    plugin_strategy_id = f"{strategy.strategy_id}_test" if is_test else str(strategy.strategy_id)

    # 调用插件 Config 同步 API
    try:
        from bk_resource import api

        result = api.bk_sec_send_plugin.config_upsert(
            strategy_id=plugin_strategy_id,
            risk_type_id=config.risk_type_id,
            source_type=config.source_type,
            token=token,
        )
        if result.get("result"):
            logger.info(
                "[BkSecPluginConfig] Synced, strategy_id=%s risk_type_id=%s is_test=%s",
                strategy.strategy_id,
                config.risk_type_id,
                is_test,
            )
            return (True, "ok")
        message = str(result.get("message", "插件拒绝写入 Config"))
        logger.warning("[BkSecPluginConfig] Upsert rejected: %s", message)
        _report_fail(BkSecConfigSyncFailReason.UPSERT_REJECTED, message)
        return (False, message)
    except Exception as err:  # NOCC:broad-except(插件不可达上报监控)
        message = "插件配置同步接口不可达：%s" % err
        logger.warning("[BkSecPluginConfig] Sync failed, strategy_id=%s err=%s", strategy.strategy_id, err)
        _report_fail(BkSecConfigSyncFailReason.API_UNREACHABLE, str(err))
        return (False, message)


def _ensure_plugin_config_synced(strategy: Strategy, config: BkSecConfig) -> None:
    """
    启用路径的插件 Config 同步：失败阻断保存，带重试。

    阻断保证配置正确性；重试解决短暂抖动（插件服务不可用/网络异常等）。
    失败后用户重新保存即可（手动补偿）。
    """
    import time

    from rest_framework import serializers

    max_retries = 3
    message = ""
    for attempt in range(max_retries):
        success, message = sync_plugin_config(strategy, config)
        if success:
            return
        if attempt < max_retries - 1:
            time.sleep(1)  # 重试间隔
    raise serializers.ValidationError(gettext("BKSEC 安全工单已启用但插件配置同步失败，策略保存被阻断：%s") % message)
