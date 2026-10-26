# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime
import logging

from bk_resource import api
from bk_resource.base import Resource
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy
from rest_framework import serializers
from rest_framework.settings import api_settings

from apps.audit.resources import AuditMixinResource
from apps.sops.constants import SOPSTaskStatus
from core.models import get_request_username
from services.web.risk.bksec.constants import (
    BKSEC_REQUIRED_FIELD_KEYS,
    BKSEC_TEST_NODE_SCAN_LIMIT,
)
from services.web.risk.bksec.service import (
    build_test_constants,
    build_ticket_preview,
    ensure_bksec_enabled,
    fetch_risk_access_items,
    fill_failure_info,
    parse_bksec_config,
    sync_bksec_test_config,
    validate_bksec_test_target,
)
from services.web.risk.constants import TicketNodeStatus
from services.web.risk.models import Risk, TicketNode
from services.web.risk.utils import calc_task_duration
from services.web.strategy_v2.models import Strategy

logger = logging.getLogger("celery")


class BkSecResourceMeta(Resource):
    tags = ["BkSec"]


class TicketResourceMeta(AuditMixinResource):
    tags = ["Ticket"]


class ListBkSecRiskTypes(BkSecResourceMeta):
    """
    查询 BKSEC 风险类型列表（策略页下拉）

    按 BKSEC_PROJECT_ID 项目维度过滤（必填），默认只返回正式（is_formal）类型。
    """

    name = gettext_lazy("查询BKSEC风险类型列表")

    class RequestSerializer(serializers.Serializer):
        name__icontains = serializers.CharField(label=gettext_lazy("名称模糊搜索"), required=False, allow_blank=True)
        is_formal = serializers.CharField(label=gettext_lazy("是否正式"), required=False, allow_blank=True)

    def perform_request(self, validated_request_data):
        from apps.feature.constants import FeatureTypeChoices
        from apps.feature.handlers import FeatureHandler

        if not FeatureHandler(FeatureTypeChoices.BKSEC).check():
            return []
        if not settings.BKSEC_PROJECT_ID:
            raise serializers.ValidationError(gettext_lazy("未配置 BKSEC 项目（BKAPP_BKSEC_PROJECT_ID），无法查询风险类型"))
        # 全量翻页（带缓存）后本地模糊过滤：缓存键只按 is_formal 维度，
        # 名称过滤须在本地做，否则不同关键字互相污染缓存
        items = fetch_risk_access_items(is_formal=validated_request_data.get("is_formal") or "true")
        keyword = (validated_request_data.get("name__icontains") or "").strip().lower()
        if keyword:
            items = [item for item in items if keyword in (item.get("name") or "").lower()]
        return [_normalize_risk_type(item) for item in items if isinstance(item, dict)]


class PreviewTicket(TicketResourceMeta):
    """
    预览工单（按 BKSEC 配置 + 指定样例风险单渲染，不实际发送）

    配置来源二选一（用于支持保存前预览）：
    - 传 bksec_config：用前端当前表单配置（未保存也可预览）；
    - 传 strategy_id：反查该策略已保存的 bksec_config。
    """

    name = gettext_lazy("预览工单")

    class RequestSerializer(serializers.Serializer):
        bksec_config = serializers.DictField(label=gettext_lazy("BKSEC工单配置"), required=True)
        risk_id = serializers.CharField(label=gettext_lazy("样例风险单ID"), required=True)

    def perform_request(self, validated_request_data):
        config = parse_bksec_config(validated_request_data["bksec_config"])
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        return build_ticket_preview(config, risk)


class SendTestTicket(TicketResourceMeta):
    """
    发送测试工单（经 SOPS 真实通道推送，仅发给指定接收人，不影响正式派单）

    测试结果即生产路径的验证；任务状态由前端轮询 get_task_status 接口获取。
    配置来源二选一（用于支持保存前测试）：
    - 传 bksec_config：用前端当前表单配置（未保存也可测试）；
    - 不传：从风险单反查已保存的策略 BKSEC 配置。
    """

    name = gettext_lazy("发送测试工单")

    class RequestSerializer(serializers.Serializer):
        test_receivers = serializers.ListField(
            label=gettext_lazy("测试接收人"), child=serializers.CharField(), required=True
        )
        # 测试发送必须指定样例风险单：不传则所有 {{ risk.xxx }} 渲染为空，测试单大量字段为空、失去验证意义
        risk_id = serializers.CharField(label=gettext_lazy("样例风险单ID"), required=True)
        bksec_config = serializers.DictField(label=gettext_lazy("BKSEC工单配置"), required=True)

    def perform_request(self, validated_request_data):
        # 后端 feature 硬拦截（前端隐藏后仍可能被 API 直接调用）
        ensure_bksec_enabled()
        risk = get_object_or_404(Risk, risk_id=validated_request_data["risk_id"])
        strategy = Strategy.objects.filter(strategy_id=risk.strategy_id).first()
        if strategy is None:
            raise serializers.ValidationError(gettext_lazy("该风险单未关联策略，无法发送测试工单"))
        # 配置来源：前端当前配置（支持未保存配置测试）
        config = parse_bksec_config(validated_request_data["bksec_config"])
        # 回调隔离守卫（插件 Callback 表按风险单复用）
        validate_bksec_test_target(risk)
        # 测试发送前置：兜底同步插件侧 Config（确保插件侧与本次入参一致）
        sync_bksec_test_config(strategy, config)
        # 渲染插件入参常量
        constants = build_test_constants(config, risk, validated_request_data["test_receivers"])
        # 确保预置套餐就绪
        if not settings.BKSEC_SOPS_TEMPLATE_ID:
            raise serializers.ValidationError(gettext_lazy("预置发单套餐未就绪（未配置套餐模板 ID），无法发送测试工单"))
        from services.web.risk.models import ProcessApplication

        pa = (
            ProcessApplication.objects.filter(is_builtin=True, sops_template_id=int(settings.BKSEC_SOPS_TEMPLATE_ID))
            .order_by("-id")
            .first()
        )
        if pa is None:
            raise serializers.ValidationError(gettext_lazy("预置发单套餐未就绪，无法发送测试工单"))
        # 经预置套餐模板创建并启动测试任务（与正式发送同一通道、同一入参结构）。
        # 注意：插件侧错误（Config 缺失/白名单/参数格式）发生在 SOPS 异步执行阶段，
        # 此处只能捕获 SOPS 调用自身的失败（网络/鉴权），插件错误由 get_task_status 轮询侧转换提示
        try:
            result = api.bk_sops.create_task(
                name="【测试】{}_{}".format(pa.name, int(datetime.datetime.now().timestamp() * 1000)),
                constants=constants,
                bk_biz_id=settings.DEFAULT_BK_BIZ_ID,
                template_id=pa.sops_template_id,
            )
            api.bk_sops.start_task(task_id=result["task_id"], bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        except Exception as err:  # NOCC:broad-except(SOPS 调用失败转友好提示)
            logger.exception("[SendTestTicket] SOPS task create/start failed, risk_id=%s", risk.risk_id)
            raise serializers.ValidationError(gettext_lazy("SOPS 测试任务创建/启动失败：%s") % err)
        # 生成执行记录（is_test=True，与正式单结构一致；风险详情页过滤、处理套餐执行记录可见）
        task_name = "【测试】{}_{}".format(pa.name, int(datetime.datetime.now().timestamp() * 1000))
        status = api.bk_sops.get_task_status(task_id=result["task_id"], bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        TicketNode.objects.create(
            risk_id=risk.risk_id,
            # 真实操作人：便于排查"谁发的测试单"（测试单身份由 is_test 区分，不再占用 operator）
            operator=get_request_username(),
            current_operator=[],
            action="AutoProcess",
            timestamp=datetime.datetime.now().timestamp(),
            time=datetime.datetime.now().strftime(api_settings.DATETIME_FORMAT),
            process_result={
                "task": result,
                "status": status,
                "pa_id": pa.id,
                "pa_name": pa.name,
                "task_name": task_name,
                "trigger": "test",
                # 测试接收人：与 operator 互补，记录本次测试工单实际发给谁（仅落库排查用，执行记录接口不透出）
                "test_receivers": validated_request_data["test_receivers"],
                "duration": None,  # 测试单创建时无耗时，状态更新时同步
            },
            duration=None,  # 测试单创建时无耗时，状态更新时同步
            extra={},
            status=TicketNodeStatus.RUNNING,
            is_test=True,
        )
        logger.info(
            "[SendTestTicket] SOPS task started, task_id=%s risk_id=%s",
            result.get("task_id"),
            risk.risk_id,
        )
        return {"task": result, "constants": constants}


class GetTaskStatus(TicketResourceMeta):
    """
    查询测试任务状态（透传 SOPS 任务状态，供前端轮询至终态）

    两个入口二选一：
    - task_id：会话内轮询（测试发送返回值携带）；
    - risk_id：刷新后恢复——task_id 随内存丢失，改用样例风险单 ID 定位本人最近一条测试单，
      用户身份由后端从请求上下文获取，前端无法伪造。

    失败时附带失败提示（failure_hint）：透出失败节点的原始错误文本，取不到才回退通用提示。
    注意：插件侧错误（如 Config 缺失）发生在 SOPS 异步执行阶段，create_task 时刻无法感知，
    只能在本接口（轮询）侧获取。
    """

    name = gettext_lazy("查询测试任务状态")

    GENERIC_HINT = "任务执行失败，详情请查看 SOPS 任务执行记录"

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.CharField(label=gettext_lazy("SOPS任务ID"), required=False, allow_blank=True)
        risk_id = serializers.CharField(label=gettext_lazy("风险ID"), required=False, allow_blank=True)

        def validate(self, attrs):
            attrs = super().validate(attrs)
            if not attrs.get("task_id") and not attrs.get("risk_id"):
                raise serializers.ValidationError(gettext_lazy("task_id 与 risk_id 至少传一个"))
            return attrs

    def perform_request(self, validated_request_data):
        task_id = validated_request_data.get("task_id") or ""
        if not task_id:
            # 刷新恢复：按样例风险单 + 当前登录用户定位最近一条测试单，取其 task_id 继续走统一逻辑
            node = self._find_latest_test_node(validated_request_data["risk_id"])
            if node is None:
                return {}
            task_id = str((node.process_result or {}).get("task", {}).get("task_id") or "")
            if not task_id:
                return {}
        status = api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        result = dict(status)
        # 回传 task_id：strategy_id 恢复场景下前端据此接续后续轮询
        result["task_id"] = task_id
        state = result.get("state")

        # 失败提示：透出失败节点原始错误，供前端展示
        failure_hint = ""
        if state in SOPSTaskStatus.get_failed_status():
            failure_hint = self._build_failure_hint(task_id, result)
            result["failure_hint"] = failure_hint

        # 测试单执行记录状态同步（一次性发送，无轮询任务，由前端查询时更新）
        if state in SOPSTaskStatus.get_finished_status():
            node = self._find_test_node(task_id)
            if node:
                from django.db import transaction

                with transaction.atomic():
                    node = TicketNode.objects.select_for_update().get(id=node.id)
                    node.process_result["status"] = dict(status)
                    if failure_hint:
                        node.process_result["failure_hint"] = failure_hint
                    # 冗余存储 duration（秒）：同步到独立整数字段用于数值排序，JSON 数值排序会按字符串比较出错
                    # 复用统一实现：任务级时间缺失时退化为子节点时间，且兼容有时区/无时区混用
                    duration = calc_task_duration(status)
                    node.process_result["duration"] = duration
                    node.duration = duration
                    node.status = TicketNodeStatus.FINISHED
                    node.save(update_fields=["process_result", "status", "duration"])
        return result

    @staticmethod
    def _find_latest_test_node(risk_id: str):
        """
        按样例风险单定位当前登录用户最近一条测试单（刷新后恢复轮询用）

        用户身份取自请求上下文而非入参，前端无法伪造，也不会串到他人记录。
        """
        return (
            TicketNode.objects.filter(
                is_test=True,
                action="AutoProcess",
                risk_id=risk_id,
                operator=get_request_username(),
            )
            .order_by("-timestamp")
            .first()
        )

    @staticmethod
    def _find_test_node(task_id: str):
        """
        按 task_id 定位测试节点

        process_result 中 task_id 的类型取决于 SOPS 返回（int/str），而 JSONField 路径查询
        类型敏感：按字符串过滤匹配不到 int，会导致测试节点状态永远停留在 running。
        故取最近的未结束测试节点逐个比对，与存储类型无关。
        """
        candidates = TicketNode.objects.filter(is_test=True, status=TicketNodeStatus.RUNNING).order_by("-timestamp")[
            :BKSEC_TEST_NODE_SCAN_LIMIT
        ]
        for node in candidates:
            if str((node.process_result or {}).get("task", {}).get("task_id", "")) == str(task_id):
                return node
        return None

    def _build_failure_hint(self, task_id: str, status: dict) -> str:
        """失败提示：回源取失败节点错误文本（顺带回写逐节点 error_message），取不到回退通用提示"""
        return fill_failure_info(status, task_id=task_id, generic=self.GENERIC_HINT)


def _normalize_field_type(value) -> str:
    """
    归一化 BKSEC 字段类型

    接口返回的是 storage_type，且大小写不统一（同时存在 STRING / string），统一转小写后输出为 type。
    已知取值：string / int / object / timestamp；未知取值原样小写返回，不丢弃信息。
    接口未返回类型时保持为空串，由前端自行决定缺省渲染方式。
    """
    return str(value or "").strip().lower()


def _extract_risk_access_fields(item: dict) -> list:
    """
    从风险类型对象中抽取工单字段 schema（risk_access_fields）
    入参示例（来自 BKSEC risk_access_list API）：
    {
        "id": 159,
        "name": "云账号未启用MFA",
        "is_formal": True,
        "risk_access_fields": [
            {"id": 9, "key": "submitter", "name": "提单人", "sequence": 0, "storage_type": "STRING",
             "source_type": "CUSTOM", "unique": False},
        ]
    }
    required 由审计中心按白名单 BKSEC_REQUIRED_FIELD_KEYS 判定（BKSEC 不返回该字段）：
    target / target_type / operator 为必填，其余一律非必填。
    type 取自接口的 storage_type 并归一化小写（string / int / object / timestamp）。

    返回值示例：
    [
        {"key": "target", "name": "风险资产信息", "required": True, "type": "string"},
        {"key": "submitter", "name": "提单人", "required": False, "type": "string"},
    ]
    """
    if not isinstance(item, dict):
        return []
    raw_fields = item.get("risk_access_fields") or item.get("fields") or []
    fields = []
    if isinstance(raw_fields, list):
        for f in raw_fields:
            if not isinstance(f, dict):
                continue
            key = f.get("key", "")
            fields.append(
                {
                    "key": key,
                    "name": f.get("name", "") or f.get("label", ""),
                    "required": key in BKSEC_REQUIRED_FIELD_KEYS,
                    "type": _normalize_field_type(f.get("type") or f.get("storage_type", "")),
                }
            )
    return fields


def _normalize_risk_type(item: dict) -> dict:
    """
    归一化 BKSEC 风险类型列表项

    入参示例（来自 BKSEC risk_access_list API）：
    {
        "id": 159,
        "name": "云账号未启用MFA",
        "is_formal": True,
        "risk_access_fields": [...]
    }

    返回值示例：
    {
        "risk_type_id": "159",
        "risk_type_name": "云账号未启用MFA",
        "is_formal": True,
        "fields": [
            {"key": "submitter", "name": "提单人", "required": False, "type": "string"},
        ]
    }
    """
    if not isinstance(item, dict):
        return {}
    return {
        "risk_type_id": str(item.get("id", "")),
        "risk_type_name": item.get("name", "") or item.get("risk_type_name", ""),
        "is_formal": bool(item.get("is_formal", False)),
        "fields": _extract_risk_access_fields(item),
    }
