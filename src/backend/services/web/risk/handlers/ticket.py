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
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc
import datetime
import json
from typing import Any, List, Optional

from bk_resource import api, resource
from bk_resource.exceptions import APIRequestError
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
from rest_framework.settings import api_settings

from apps.itsm.constants import TicketStatus
from apps.itsm.utils import is_itsm_v4_enabled
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.saas import get_saas_url
from apps.notice.models import NoticeGroup
from apps.permission.handlers.actions import ActionEnum
from apps.sops.constants import SOPSConstantSourceType, SOPSTaskStatus
from core.exceptions import RiskStatusInvalid
from services.web.risk.constants import (
    DEFAULT_RISK_OPERATE_NOTICE_CONFIG,
    RISK_OPERATE_NOTICE_CONFIG_KEY,
    SECURITY_PERSON_KEY,
    ApproveTicketFields,
    ItsmVersion,
    RiskDisplayStatus,
    RiskLabel,
    RiskStatus,
    TicketNodeStatus,
)
from services.web.risk.exceptions import AutoProcessParamsError
from services.web.risk.handlers.risk import RiskHandler
from services.web.risk.handlers.rule import RiskRuleHandler
from services.web.risk.models import (
    ProcessApplication,
    Risk,
    RiskRule,
    TicketNode,
    UserType,
)
from services.web.risk.parser import RiskNoticeParser
from services.web.risk.utils import calc_task_duration
from services.web.strategy_v2.constants import StrategyType
from services.web.strategy_v2.models import Strategy

# 流转历史去重窗口（秒）：窗口期内内容完全相同的重复写入视为同一次流转，不再重复落库
HISTORY_DEDUP_WINDOW_SEC = 5


def _is_user_input_constant(constant: dict) -> bool:
    """创建任务时需要覆盖的用户入参。

    标准运维里 show 才是执行参数。custom 与从节点输入勾选出来的 component_inputs
    都取创建任务时传入的值；component_outputs 绑定节点输出，隐藏变量保留模板绑定。
    """

    return (
        constant.get("show_type") == "show" and constant.get("source_type") in SOPSConstantSourceType.user_input_types()
    )


def _is_condition_hide(constant: dict) -> bool:
    """模板用字符串 "true"/"false" 标记条件隐藏，布尔值同样认。"""
    flag = constant.get("is_condition_hide")
    if isinstance(flag, bool):
        return flag
    return isinstance(flag, str) and flag.strip().lower() == "true"


def _normalize_sops_constant_value(constant: dict, value: Any) -> Any:
    """按 BK-SOPS 变量协议转换常量值。

    人员选择器的原生值是逗号分隔字符串；其他结构化值保留历史 JSON 字符串行为。
    """

    if constant.get("custom_type") == "bk_user_selector" and isinstance(value, list):
        return ",".join(map(str, value))
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


class RiskFlowBaseHandler:
    """
    用于流转风险单状态
    """

    name = gettext_lazy("默认流转")
    allowed_status = []
    enable_notice = True
    # 是否允许重复写入流转历史：纯留痕类动作（如风险处理经验）需要保留每一次记录
    allow_duplicate_history = False

    # 本次流转使用的 ITSM 版本：由建单类流转（如 ForApprove）在 process 中按部署开关确定后写入节点。
    # 为 None 时沿用模型默认版本，供后续状态查询/撤销按同一版本处理。
    itsm_version = None

    # 默认映射：status → display_status
    # 子类可覆盖以实现特殊映射（如 NewRisk 将 AWAIT_PROCESS 映射为"待处理"）
    DISPLAY_STATUS_MAP = {
        RiskStatus.NEW: RiskDisplayStatus.NEW,
        RiskStatus.PENDING_CONFIRM: RiskDisplayStatus.PENDING_CONFIRM,  # 二次确认状态
        RiskStatus.FOR_APPROVE: RiskDisplayStatus.FOR_APPROVE,
        RiskStatus.AUTO_PROCESS: RiskDisplayStatus.AUTO_PROCESS,
        RiskStatus.CLOSED: RiskDisplayStatus.CLOSED,
        RiskStatus.AWAIT_PROCESS: RiskDisplayStatus.PROCESSING,  # 默认"处理中"
    }

    def __init__(self, risk_id: str, operator: str):
        self.risk: Risk = Risk.objects.get(risk_id=risk_id)
        self.operator = operator
        self.rule: RiskRule = None
        self.process_application: ProcessApplication = None
        self.init_rule()
        self.init_process_application()
        self.strategy: Strategy = Strategy.objects.filter(strategy_id=self.risk.strategy_id).first()

    def init_rule(self) -> None:
        if self.risk.rule_id:
            self.rule: RiskRule = RiskRule.objects.filter(
                rule_id=self.risk.rule_id, version=self.risk.rule_version
            ).first()
        else:
            self.rule: RiskRule = None

    def init_process_application(self, pa_id: str = None) -> None:
        if pa_id:
            self.process_application: ProcessApplication = ProcessApplication.objects.filter(id=pa_id).first()
        elif self.rule and self.rule.pa_id:
            self.process_application: ProcessApplication = ProcessApplication.objects.filter(id=self.rule.pa_id).first()
        else:
            self.process_application: ProcessApplication = None

    @classmethod
    def load_security_person(cls) -> List[str]:
        """
        获取安全接口人
        """

        return GlobalMetaConfig.get(config_key=SECURITY_PERSON_KEY)

    def load_processor(self) -> List[str]:
        """
        获取处理人(用安全接口人进行兜底)

        处理人来源
        规则策略
            1. 全局策略风险：分派规则 DispatchRule.processor
            2. 场景策略风险：命中发现规则的 StrategyRule.processor
        模型策略（strategy_type=model）：策略级 processor_groups
        """

        # 获取策略
        if not self.strategy:
            return self.load_security_person()

        # 1. 规则策略 全局策略风险：从分派规则中获取处理组
        if getattr(self.risk, "dispatch_rule_id", None):
            from services.web.strategy_v2.models import DispatchRule

            # 建单时已固化处理人快照：直接复用，分派规则后续编辑不影响已产生单据
            if self.risk.current_operator:
                return self.risk.current_operator

            dispatch_rule = DispatchRule._base_manager.filter(rule_id=self.risk.dispatch_rule_id).first()
            if dispatch_rule:
                processor_groups: List[NoticeGroup] = list(
                    NoticeGroup.objects.filter(group_id__in=dispatch_rule.processor or [])
                )
                parsed_members = RiskNoticeParser(risk=self.risk).parse_groups(processor_groups)
                if parsed_members:
                    return parsed_members
            return self.load_security_person()

        # 2. 规则策略 场景策略：从命中发现规则中获取处理组
        if self.strategy.strategy_type == StrategyType.RULE:
            from services.web.strategy_v2.models import StrategyRule

            group_ids = []
            if getattr(self.risk, "strategy_rule_id", None):
                rule = StrategyRule._base_manager.filter(rule_id=self.risk.strategy_rule_id).first()
                if rule:
                    group_ids = rule.processor or []
            if not group_ids:
                # 未关联规则（旧 SQL 未重建窗口期建的单据）时回退策略级处理组，
                group_ids = self.strategy.processor_groups or []
            processor_groups = list(NoticeGroup.objects.filter(group_id__in=group_ids))
            origin_members = NoticeGroup.parse_members(processor_groups)
            # 解析处理组
            parsed_members = RiskNoticeParser(risk=self.risk).parse_groups(processor_groups)
            logger.info(
                f"[{self.__class__.__name__}]Risk:{self.risk.risk_id};"
                f"Notice Groups Members:{origin_members};Parsed Members:{parsed_members}"
            )
            return parsed_members or self.load_security_person()

        # 3. 模型策略：策略级处理组
        processor_groups = list(NoticeGroup.objects.filter(group_id__in=self.strategy.processor_groups or []))
        origin_members = NoticeGroup.parse_members(processor_groups)
        # 解析处理组(变量)
        parsed_members = RiskNoticeParser(risk=self.risk).parse_groups(processor_groups)
        logger.info(
            f"[{self.__class__.__name__}]Risk:{self.risk.risk_id};"
            f"Notice Groups Members:{origin_members};Parsed Members:{parsed_members}"
        )
        return parsed_members or self.load_security_person()

    def load_last_operator(self) -> List[str]:
        """
        获取上一个人工处理节点的处理人
        仅适用于人工发起处理套餐的情况，因为人工发起处理套餐，在这之前一定会有人工处理节点并且动作为处理套餐
        需要处理审批失败和执行失败两种情况
        """

        nodes = TicketNode.objects.filter(risk_id=self.risk.risk_id, is_test=False).order_by("-timestamp")
        for node in nodes:
            if node.action == CustomProcess.__name__ and node.extra.get("custom_action") == AutoProcess.__name__:
                return [node.operator]
        return []

    @transaction.atomic()
    def run(self, *args, **kwargs) -> None:
        """
        处理风险单
        """

        self.pre_check(*args, **kwargs)
        process_result = self.process(*args, **kwargs)
        self.update_operator(process_result=process_result, *args, **kwargs)
        self.update_status(process_result=process_result, *args, **kwargs)
        self.sync_display_status()
        self.record_history(process_result=process_result, *args, **kwargs)
        self.auth_current_operator()
        self.notice_current_operator()
        self.auth_notice_user()
        self.post_process(process_result=process_result, *args, **kwargs)

    def resolve_display_status(self) -> Optional[str]:
        """
        解析展示状态。
        """
        return self.DISPLAY_STATUS_MAP.get(self.risk.status)

    def sync_display_status(self):
        """根据当前 status 自动同步 display_status"""
        display_status = self.resolve_display_status()
        if display_status and self.risk.display_status != display_status:
            self.risk.display_status = display_status
            self.risk.save(update_fields=["display_status"])

    def pre_check(self, *args, **kwargs) -> None:
        """
        预检查
        """

        # 已关闭状态
        if self.risk.status == RiskStatus.CLOSED:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.status)

        # 待确认状态禁止所有普通操作（仅 ConfirmRisk 和 ConfirmAsMisReport 允许）
        if self.risk.status == RiskStatus.PENDING_CONFIRM:
            raise RiskStatusInvalid(message="待确认状态不能执行此操作")

        # 状态不在允许的范围内
        if self.allowed_status and self.risk.status not in self.allowed_status:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.status)

    @abc.abstractmethod
    def process(self, *args, **kwargs) -> dict:
        """
        处理风险逻辑
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        """
        更新风险状态
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        """
        更新处理人
        """

        raise NotImplementedError()

    def record_history(self, process_result: dict, *args, **kwargs) -> None:
        """
        记录流转历史
        """

        extra = self.build_history(process_result=process_result, *args, **kwargs)
        # 记录本次流转使用的 ITSM 版本：已有工单后续按该版本查询/撤销
        fields = {"itsm_version": self.itsm_version} if self.itsm_version else {}
        # 只写一条：此前这里写过两次（一次直接 create、一次 create_params），
        # 导致同一次流转产生两条内容完全相同的节点
        self._create_history_node(process_result, extra, **fields)
        self.risk.save(update_fields=["last_operate_time"])

    def _create_history_node(self, process_result: dict, extra: dict, **fields) -> Optional[TicketNode]:
        """写入一条流转历史节点

        幂等兜底：同一次流转被重复写入会产出两条内容完全相同的节点（执行记录/流转历史出现重复数据），
        故在写入层判断——同一风险单、同一动作在窗口期内已存在 process_result 与 extra 均相同的节点时跳过。
        所有写入流转历史的地方都应走这里，避免直接 TicketNode.objects.create；
        fields 用于补充额外落库字段（如 itsm_version）。
        """

        if not self.allow_duplicate_history and self._has_same_history(process_result, extra):
            logger.warning(
                f"[RecordHistory] Skip duplicated node, risk_id={self.risk.risk_id}, action={self.__class__.__name__}"
            )
            return None
        create_params = {
            "risk_id": self.risk.risk_id,
            "operator": self.operator,
            "current_operator": self.risk.current_operator,
            "action": self.__class__.__name__,
            "timestamp": datetime.datetime.now().timestamp(),
            "time": datetime.datetime.now().strftime(api_settings.DATETIME_FORMAT),
            "process_result": process_result,
            "duration": process_result.get("duration"),
            "extra": extra,
        }
        create_params.update(fields)
        return TicketNode.objects.create(**create_params)

    def _has_same_history(self, process_result: dict, extra: dict) -> bool:
        """窗口期内是否已存在内容完全相同的流转节点"""

        latest = (
            TicketNode.objects.filter(risk_id=self.risk.risk_id, action=self.__class__.__name__)
            .order_by("-timestamp")
            .first()
        )
        if latest is None:
            return False
        if datetime.datetime.now().timestamp() - (latest.timestamp or 0) > HISTORY_DEDUP_WINDOW_SEC:
            return False
        return (latest.process_result or {}) == (process_result or {}) and (latest.extra or {}) == (extra or {})

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        """
        构造历史内容
        """

        return {}

    def record_create_node(self) -> None:
        """
        补写"风险产生"节点（after_confirm 分派建单时未写该节点）。

        直接复用 NewRisk 的 record_history，使该节点与 direct 流程写出的完全同构
        （action=NewRisk、extra={}）。幂等，已存在则跳过。
        在确认流程的事务内、于"风险确认/误报确认"节点之前调用，
        以保证时间戳天然递增，前端展示顺序正确（无需回拨时间戳）。
        """

        if TicketNode.objects.filter(risk_id=self.risk.risk_id, action=NewRisk.__name__).exists():
            return
        NewRisk(risk_id=self.risk.risk_id, operator=self.operator).record_history({})

    def post_process(self, process_result: dict, *args, **kwargs) -> None:
        """
        处理结束后执行
        """

        pass

    def auth_current_operator(self) -> None:
        """
        向当前责任人授权
        """

        if not self.risk.current_operator or not isinstance(self.risk.current_operator, list):
            return

        self.risk.auth_users(
            action=ActionEnum.LIST_RISK.id, users=self.risk.current_operator, user_type=UserType.OPERATOR
        )

    def auth_notice_user(self) -> None:
        """
        向关注人授权
        """

        if not self.risk.notice_users or not isinstance(self.risk.notice_users, list):
            return

        self.risk.auth_users(
            action=ActionEnum.LIST_RISK.id, users=self.risk.notice_users, user_type=UserType.NOTICE_USER
        )

    def notice_current_operator(self) -> None:
        """
        通知当前责任人
        """

        if not self.enable_notice or not self.risk.current_operator or not isinstance(self.risk.current_operator, list):
            return

        # 初始化虚拟通知组
        notice_group = NoticeGroup(
            group_member=self.risk.current_operator,
            notice_config=GlobalMetaConfig.get(
                RISK_OPERATE_NOTICE_CONFIG_KEY, default=DEFAULT_RISK_OPERATE_NOTICE_CONFIG
            ),
        )
        # 构造通知内容
        RiskHandler.send_notice(risk=self.risk, notice_groups=[notice_group], is_todo=True)


class NewRisk(RiskFlowBaseHandler):
    """
    新风险
    """

    name = gettext_lazy("流转新风险")
    allowed_status = [RiskStatus.NEW, RiskStatus.CLOSED]
    DISPLAY_STATUS_MAP = {
        **RiskFlowBaseHandler.DISPLAY_STATUS_MAP,
        RiskStatus.AWAIT_PROCESS: RiskDisplayStatus.AWAIT_PROCESS,  # 覆盖为"待处理"
    }

    def record_history(self, process_result: dict, *args, **kwargs) -> None:
        # 默认由本方法写出"风险产生"节点（direct 建单路径依赖此行为）。
        # 仅当确认流程已通过 record_create_node() 先行写入该节点时，
        # 由调用方传入 skip_record=True 避免重复记录。
        if kwargs.get("skip_record"):
            return
        super().record_history(process_result=process_result, *args, **kwargs)

    def pre_check(self, *args, **kwargs) -> None:
        if (
            self.risk.status == RiskStatus.CLOSED
            and self.risk.risk_label != RiskLabel.MISREPORT
            or self.risk.status not in self.allowed_status
        ):
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.status)

    def process(self, *args, **kwargs) -> dict:
        # 初始化参数
        self.risk.origin_operator = []
        # 分派风险建单时已固化处理人快照（_apply_dispatch），流转时保留，由 update_operator 复用
        if not getattr(self.risk, "dispatch_rule_id", None):
            self.risk.current_operator = []
        self.risk.save(update_fields=["origin_operator", "current_operator"])
        # 只有有责任人时走规则；系统自动规则例外（如策略 BKSEC 发单）：
        # 自动派单不依赖责任人，无责任人也走规则，发单责任人兜底为安全接口人
        if self.risk.operator or self._has_enabled_auto_rule():
            # 初始化处理规则
            self.match_risk_rule()
            # 重新初始化
            self.init_rule()
            self.init_process_application()
        # 范围记录内容
        return {"rule_id": self.risk.rule_id, "rule_version": self.risk.rule_version}

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        # 有处理套餐则当前处理人为空，否则为安全责任人
        self.risk.current_operator = [] if self.process_application and self.risk.operator else self.load_processor()
        self.risk.save(update_fields=["current_operator"])

    def _has_enabled_auto_rule(self) -> bool:
        """策略是否存在启用的系统自动规则（auto_strategy_id 非空）：自动派单不依赖责任人，无责任人也走规则匹配。

        按最新版本判定——启停只作用于最新版本，历史版本的 is_enabled 不代表当前状态。
        """
        return RiskRule.load_latest_rules().filter(auto_strategy_id=self.risk.strategy_id, is_enabled=True).exists()

    def match_risk_rule(self) -> None:
        RiskRuleHandler(risk_id=self.risk.risk_id).bind_rule()
        self.risk.refresh_from_db()

    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        # 处理套餐
        if self.process_application:
            if self.process_application.need_approve:
                self.risk.status = RiskStatus.FOR_APPROVE
            else:
                self.risk.status = RiskStatus.AUTO_PROCESS
        # 人工处理
        else:
            self.risk.status = RiskStatus.AWAIT_PROCESS
        self.risk.save(update_fields=["status"])


class CloseRisk(RiskFlowBaseHandler):
    """
    手动关单
    """

    name = gettext_lazy("关单")
    enable_notice = False

    def pre_check(self, *args, **kwargs) -> None:

        if self.risk.status == RiskStatus.PENDING_CONFIRM:
            raise RiskStatusInvalid(message="待确认状态不能执行关单操作")
        return

    def process(self, description: str, *args, **kwargs) -> dict:
        return {}

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        self.risk.current_operator = []
        self.risk.save(update_fields=["current_operator"])

    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        self.risk.status = RiskStatus.CLOSED
        self.risk.save(update_fields=["status"])

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        return kwargs


class ForApprove(RiskFlowBaseHandler):
    """
    审批中
    """

    name = gettext_lazy("自动处理审批")
    allowed_status = [RiskStatus.FOR_APPROVE, RiskStatus.NEW, RiskStatus.AWAIT_PROCESS]

    def _build_approve_form_data(self, ticket_info: dict) -> dict:
        """构造发起审批单据所需的 form_data。"""

        # 预计算特殊字段值（按 bare_key 索引）
        special_values = {
            ApproveTicketFields.TITLE.key: gettext("【审计中心】执行%s审批") % self.process_application.name,
            ApproveTicketFields.PROCESS_APPLICATION_NAME_FIELD.key: self.process_application.name,
            ApproveTicketFields.TAGS.key: ";".join(self.risk.get_tag_names()),
            ApproveTicketFields.OPERATOR.key: ";".join(self.risk.operator),
            ApproveTicketFields.RISK_URL.key: "{}/risk-manage/detail/{}".format(
                get_saas_url(settings.APP_CODE), self.risk.risk_id
            ),
        }

        form_data = {}
        for field in ticket_info["fields"]:
            key = field["key"]
            # V4 表单字段 key 带 ticket__ 命名空间前缀，统一去前缀后比对
            bare_key = key.split("__", 1)[-1]
            if bare_key in special_values:
                value = special_values[bare_key]
            else:
                value = (
                    self.process_application.approve_config.get(key, {}).get("value")
                    or self.process_application.approve_config.get(bare_key, {}).get("value")
                    or getattr(self.risk, bare_key, "")
                )
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
            form_data[key] = value
        return form_data

    def process(self, pa_config: dict = None, **kwargs) -> dict:
        """
        三种发起方式
        1. 规则发起审批
        2. 人工选择处理套餐
        3. 自动更新审批状态
        """

        itsm_version = self.risk.last_history.itsm_version

        # 已发起则获取单据状态（V4 按工单 ID 查询，V3 按 sn 查询；ticket_detail 各版本通用）
        if itsm_version == ItsmVersion.V4:
            ticket_id = self.load_approve_ticket_id()
            if ticket_id:
                return {"status": get_itsm_ticket_status(ticket_id)}
        elif itsm_version == ItsmVersion.V3:
            sn = self.load_approve_sn()
            if sn:
                return {"status": api.bk_itsm.ticket_approve_result(sn=[sn])[0]}

        # 手动传入处理套餐需要重新初始化处理套餐
        if pa_config:
            self.init_process_application(pa_config["pa_id"])

        # 未发起则发起单据：按部署级开关选择版本
        # - 已启用 ITSM V4（迁移后）=> 无单据的风险单统一用 V4 创建；
        # - 未升级 ITSM V4 的部署环境 => 保留 V3 接口契约（approve_service_id 仍是 V3 服务 ID）。
        if is_itsm_v4_enabled():
            return self._create_v4_ticket()
        return self._create_v3_ticket()

    def _create_v4_ticket(self) -> dict:
        """按 ITSM V4 创建审批单据（approve_service_id 为 workflow_key）。"""

        self.itsm_version = ItsmVersion.V4
        ticket_info = resource.itsm.get_service_detail(
            id=self.process_application.approve_service_id, version=ItsmVersion.V4
        )
        form_data = self._build_approve_form_data(ticket_info)

        ticket = api.bk_itsm_v4.ticket_create(
            operator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            workflow_key=self.process_application.approve_service_id,
            form_data=form_data,
            is_submit=True,
        )
        status = get_itsm_ticket_status(ticket["id"])
        return {"ticket": ticket, "status": status}

    def _create_v3_ticket(self) -> dict:
        """按 ITSM V3 创建审批单据（approve_service_id 为 V3 服务 ID）。"""

        self.itsm_version = ItsmVersion.V3
        ticket_info = resource.itsm.get_service_detail(
            id=self.process_application.approve_service_id, version=ItsmVersion.V3
        )
        form_data = self._build_approve_form_data(ticket_info)
        fields = []
        for field in ticket_info["fields"]:
            field["value"] = form_data.get(field["key"], "")
            fields.append(field)

        ticket = api.bk_itsm.create_ticket(
            service_id=self.process_application.approve_service_id,
            creator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            fields=fields,
        )
        status = api.bk_itsm.ticket_approve_result(sn=[ticket["sn"]])[0]
        return {"ticket": ticket, "status": status}

    @staticmethod
    def _parse_workflow_fields(workflow_detail: dict) -> dict:
        """
        将 V4 Workflows 接口返回的单个流程（workflow dict）解析为字段列表。

        workflow dict 来自 workflows().items[0]，其表单字段定义位于
        form_canvas_data.jsonschema.properties（key 形如 ticket__title）。
        """

        form_canvas_data = workflow_detail.get("form_canvas_data") or {}
        jsonschema = form_canvas_data.get("jsonschema") or {}
        properties = jsonschema.get("properties") or {}
        fields = []
        for key, prop in properties.items():
            fields.append(
                {
                    "key": key,
                    "name": prop.get("title", ""),
                    "type": prop.get("type", "STRING").upper(),
                }
            )
        return {"fields": fields}

    def update_operator(self, process_result: dict, **kwargs) -> None:
        status = process_result.get("status", {})
        current_status = status.get("current_status")
        approve_result = status.get("approve_result")
        # 审批不通过，单据异常，转给节点处理人或安全责任人
        if (current_status in TicketStatus.get_success_status() and not approve_result) or (
            current_status in TicketStatus.get_failed_status()
        ):
            self.risk.current_operator = self.load_last_operator() or self.load_processor()
        # 其他情况处理人为空
        else:
            self.risk.current_operator = []
        self.risk.save(update_fields=["current_operator"])

    def load_approve_ticket_id(self) -> str:
        """
        取单据 id 作为「是否已发起」的判断依据。
        """

        return str(self.risk.last_history.process_result.get("ticket", {}).get("id") or "")

    def load_approve_sn(self) -> str:
        """
        工单编号。V4 不再按 sn 查询，仅用于识别 V3 遗留的历史在途单据（无 V4 工单 ID）。
        """

        return self.risk.last_history.process_result.get("ticket", {}).get("sn", "") or ""

    def update_status(self, process_result: dict, **kwargs) -> None:
        status = process_result.get("status", {})
        current_status = status.get("current_status")
        approve_result = status.get("approve_result")
        # 不通过 或 单据状态异常
        if (current_status in TicketStatus.get_failed_status()) or (
            current_status in TicketStatus.get_success_status() and not approve_result
        ):
            self.risk.status = RiskStatus.AWAIT_PROCESS
        # 通过
        elif current_status in TicketStatus.get_success_status() and approve_result:
            self.risk.status = RiskStatus.AUTO_PROCESS
        # 其他情况保留为审批中
        else:
            self.risk.status = RiskStatus.FOR_APPROVE
        self.risk.save(update_fields=["status"])

    def record_history(self, process_result: dict, **kwargs) -> None:
        # 首次发起需要记录
        if process_result.get("ticket"):
            return super().record_history(process_result, **kwargs)
        # 已有单据且状态不同则更新状态
        if "status" in process_result:
            history_status = self.risk.last_history.process_result.get("status") or {}
            current_status = process_result.get("status") or {}
            if current_status.get("current_status") != history_status.get("current_status"):
                self.risk.last_history.process_result.update(process_result)
                self.risk.last_history.save(update_fields=["process_result"])

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        return kwargs


# V4 ITSM 工单状态标识（小写）与旧 ITSM TicketStatus（大写）的映射
ITSM_V4_STATUS_MAPPING = {
    "running": TicketStatus.RUNNING.value,
    "finished": TicketStatus.FINISHED.value,
    "termination": TicketStatus.TERMINATED.value,
    "failed": TicketStatus.FAILED.value,
    "revoked": TicketStatus.REVOKED.value,
    "suspend": TicketStatus.SUSPEND.value,
    "receiving": TicketStatus.RECEIVING.value,
    "distributing": TicketStatus.DISTRIBUTING.value,
    "wait": TicketStatus.WAIT.value,
}


def extract_current_processor(detail: dict) -> str:
    """
    从 V4 工单详情里取当前处理人
    """

    for item in detail.get("current_processors") or []:
        if not isinstance(item, dict) or item.get("processor_type") != "user":
            continue
        processor = item.get("processor")
        if isinstance(processor, (list, tuple)):
            return ";".join(str(p) for p in processor)
        return str(processor or "")
    return ""


def get_itsm_ticket_status(ticket_id: str) -> dict:
    """
    通过 ITSM V4 的 ticket_detail 接口获取工单审批状态。

    返回结构与 V3 的 ticket_approve_result 对齐（id/title/update_at/ticket_url/
    updated_by/approve_result/current_status），避免下游 sync_auto_result 与前端
    节点展示因字段缺失取不到值。
    """

    detail = api.bk_itsm_v4.ticket_detail(id=ticket_id)
    current_status = ITSM_V4_STATUS_MAPPING.get((detail.get("status") or "").lower())
    if not current_status:
        logger.warning("unmapped V4 itsm status: %s", detail.get("status"))
        current_status = detail.get("status")
    return {
        "id": detail.get("id"),
        "sn": detail.get("sn"),
        "title": detail.get("title") or "",
        "update_at": detail.get("updated_at") or "",
        "ticket_url": detail.get("frontend_url") or "",
        "updated_by": extract_current_processor(detail),
        "approve_result": detail.get("approve_result"),
        "current_status": current_status,
    }


class AutoProcess(RiskFlowBaseHandler):
    """
    自动套餐处理
    """

    name = gettext_lazy("自动套餐处理")
    allowed_status = [RiskStatus.AUTO_PROCESS, RiskStatus.FOR_APPROVE, RiskStatus.AWAIT_PROCESS]

    def process(self, pa_config: dict = None, **kwargs) -> dict:
        """
        三种发起方式
        1. 审批通过
        2. 人工选择处理套餐
        3. 自动更新审批状态
        """

        # 已有任务获取状态
        task_id = self.load_task_id()
        if task_id:
            try:
                process_result = {
                    "status": api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
                }
                return self._attach_failure_hint(process_result, task_id=task_id)
            except APIRequestError as err:
                # 业务错误：不可恢复，降级为 FAILED 让下游走"转人工 + AWAIT_PROCESS"分支，
                err_data = getattr(err, "data", {}) or {}
                if "code" in err_data:
                    logger.exception(
                        f"[AutoProcess] get_task_status business error, "
                        f"risk_id={self.risk.risk_id}, task_id={task_id}, err={err}"
                    )
                    return self._attach_failure_hint({"status": {"state": SOPSTaskStatus.FAILED}})
                # HTTP 5xx / 网络异常 / 超时：可恢复，抛出让外层重试
                raise

        # 触发方式快照：人工选择(显式传参) / 审批通过(上个节点为审批) / 规则自动匹配
        last_node = self.risk.last_history
        trigger = (
            "manual" if pa_config else ("approve" if last_node and last_node.action == ForApprove.__name__ else "auto")
        )
        # pa_config 优先用显式传参；未传时取上个节点（审批节点）的配置
        if not pa_config and self.risk.last_history.action == ForApprove.__name__:
            pa_config = self.risk.last_history.extra.get("pa_config")
        # 配置有处理套餐则重新初始化处理套餐
        pa_id, pa_params = None, None
        if pa_config:
            pa_id, pa_params = pa_config["pa_id"], pa_config["pa_params"]
            self.init_process_application(pa_id=pa_id)
        # 构造任务参数
        template_info = api.bk_sops.get_template_info(
            template_id=self.process_application.sops_template_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID
        )
        pa_params = pa_params if pa_params is not None else (self.rule.pa_params if self.rule else {})
        if not isinstance(pa_params, dict):
            pa_params = {}
        # BKSEC 自动规则：pa_params 存的是模板，派单时按当前风险渲染成终值。
        # 渲染上下文只组装一次（load_risk_events 为外部查询，不可按字段重复触发）
        is_bksec_auto_rule = bool(getattr(self.rule, "auto_strategy_id", None))
        bksec_context = None
        if is_bksec_auto_rule:
            from services.web.risk.bksec.render import build_render_context

            bksec_context = build_render_context(risk=self.risk)
        constants = {}
        missing_keys = []
        for c in template_info["pipeline_tree"]["constants"].values():
            # 只覆盖用户入参。节点输出和隐藏变量传值会覆盖模板绑定，交给标准运维运行时处理。
            if not _is_user_input_constant(c):
                continue
            field = pa_params.get(c["key"])
            if not isinstance(field, dict):
                # 条件字段未渲染时前端不会提交 key，此时保留标准运维模板默认值。
                if _is_condition_hide(c):
                    continue
                missing_keys.append(c["key"])
                continue
            # 前端保证字段映射和直接输入互斥；取值后统一在调用边界适配 BK-SOPS 协议。
            field_name = field.get("field")
            value = getattr(self.risk, field_name, "") if field_name else field.get("value", "")
            # 责任人为空时兜底安全接口人。
            if field_name == "operator" and not value:
                value = [person for person in (self.load_security_person() or []) if person]
            # BKSEC 自动规则：pa_params 存的是模板，派单时按当前风险加工成终值
            if is_bksec_auto_rule:
                from services.web.risk.bksec.contract import render_bksec_constant

                value = render_bksec_constant(c["key"], value, bksec_context, self.risk)
            value = _normalize_sops_constant_value(c, value)
            if isinstance(value, datetime.datetime):
                value = value.astimezone(tz=timezone.get_default_timezone()).strftime(api_settings.DATETIME_FORMAT)
            constants[c["key"]] = value
        if missing_keys:
            raise AutoProcessParamsError(keys=",".join(missing_keys))
        params = {
            "name": f"{self.process_application.name}_{int(datetime.datetime.now().timestamp() * 1000)}",
            "constants": constants,
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "template_id": self.process_application.sops_template_id,
        }
        # 没有任务创建任务
        result = api.bk_sops.create_task(**params)
        api.bk_sops.start_task(task_id=result["task_id"], bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        process_result = {
            "task": result,
            "status": api.bk_sops.get_task_status(task_id=result["task_id"], bk_biz_id=settings.DEFAULT_BK_BIZ_ID),
            # 套餐/任务快照：执行记录据此展示（历史节点无快照时由记录接口走规则链路兜底）
            "pa_id": self.process_application.id,
            "pa_name": self.process_application.name,
            "task_name": params["name"],
            "trigger": trigger,
        }
        return self._attach_failure_hint(process_result, task_id=str(result.get("task_id") or ""))

    def _attach_failure_hint(self, process_result: dict, task_id: str = "") -> dict:
        """写入点落失败提示（非失败状态原样返回）"""
        status = process_result.get("status") or {}
        if status.get("state") in SOPSTaskStatus.get_failed_status():
            from services.web.risk.utils import fill_failure_info

            process_result["failure_hint"] = fill_failure_info(status, task_id=task_id)
        # 冗余存储 duration（秒），用于排序
        process_result["duration"] = calc_task_duration(status)
        return process_result

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        auto_close_risk = self.get_auto_close_risk(pa_config=kwargs.get("pa_config"))
        # 执行失败 或 需要人工处理，转给节点处理人或安全责任人
        if "status" in process_result and (
            process_result["status"]["state"] in SOPSTaskStatus.get_failed_status()
            or (process_result["status"]["state"] in SOPSTaskStatus.get_success_status() and not auto_close_risk)
        ):
            self.risk.current_operator = self.load_last_operator() or self.load_processor()
        # 其他情况处理人为空
        else:
            self.risk.current_operator = []
        self.risk.save(update_fields=["current_operator"])

    def update_status(self, process_result: dict, **kwargs) -> None:
        auto_close_risk = self.get_auto_close_risk(pa_config=kwargs.get("pa_config"))
        # 执行失败 或 处理成功且不自动关单，转给安全责任人
        if "status" in process_result and (
            process_result["status"]["state"] in SOPSTaskStatus.get_failed_status()
            or (process_result["status"]["state"] in SOPSTaskStatus.get_success_status() and not auto_close_risk)
        ):
            self.risk.status = RiskStatus.AWAIT_PROCESS
        else:
            self.risk.status = RiskStatus.AUTO_PROCESS
        self.risk.save(update_fields=["status"])

    def load_task_id(self) -> str:
        # 优先复用本风险单正在执行的套餐任务：last_history 会被人工处理/新建等节点顶掉，
        # 只看它会误判为"没有任务"从而重复建单（执行记录出现两条相同任务）
        running_node = (
            TicketNode.objects.filter(
                risk_id=self.risk.risk_id,
                action=AutoProcess.__name__,
                status=TicketNodeStatus.RUNNING,
            )
            .order_by("-timestamp")
            .first()
        )
        if running_node:
            task_id = str((running_node.process_result or {}).get("task", {}).get("task_id", "") or "")
            if task_id:
                return task_id
        return self.risk.last_history.process_result.get("task", {}).get("task_id", "")

    def record_history(self, process_result: dict, **kwargs) -> None:
        # 首次执行记录完整信息
        if "task" in process_result:
            return super().record_history(process_result, **kwargs)
        # 已有单据且状态不同则更新状态
        if "status" in process_result:
            current_status = process_result.get("status") or {}
            history_status = self.risk.last_history.process_result.get("status") or {}
            if current_status.get("state") != history_status.get("state"):
                self.risk.last_history.process_result.update(process_result)
                # duration 任务耗时写入执行记录
                if "duration" in process_result:
                    self.risk.last_history.duration = process_result["duration"]
                self.risk.last_history.save(update_fields=["process_result", "duration"])

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        history = {**kwargs}
        # 参数未传递 且 上一个审批节点有配置
        if (
            not kwargs.get("pa_config")
            and self.risk.last_history.action == ForApprove.__name__
            and self.risk.last_history.extra.get("pa_config")
        ):
            history["pa_config"] = self.risk.last_history.extra["pa_config"]
        return history

    def post_process(self, process_result: dict, *args, **kwargs) -> None:
        auto_close_risk = self.get_auto_close_risk(pa_config=kwargs.get("pa_config"))
        # 状态为完成 且 要自动关单
        # 状态为任意结束状态 且 误报
        flow_success = process_result["status"]["state"] in SOPSTaskStatus.get_success_status() and auto_close_risk
        flow_finished_and_misreport = (
            process_result["status"]["state"] in SOPSTaskStatus.get_finished_status()
            and self.risk.risk_label == RiskLabel.MISREPORT
        )
        if flow_success or flow_finished_and_misreport:
            CloseRisk(risk_id=self.risk.risk_id, operator=self.operator).run(description=gettext("套餐执行成功后自动关单"))

    def get_auto_close_risk(self, pa_config: dict = None) -> bool:
        # 优先使用参数
        if pa_config:
            return pa_config["auto_close_risk"]
        # 其次使用上个审批节点或当前节点的配置
        if self.risk.last_history.extra.get("pa_config"):
            return self.risk.last_history.extra["pa_config"]["auto_close_risk"]
        # 使用绑定的规则的配置
        return self.rule.auto_close_risk


class ReOpen(RiskFlowBaseHandler):
    """
    重开单据
    """

    name = gettext_lazy("重开风险")
    allowed_status = [RiskStatus.CLOSED]

    def pre_check(self, *args, **kwargs) -> None:
        if self.risk.status not in self.allowed_status:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.status)

    def process(self, new_operators: List[str], description: str = None, *args, **kwargs) -> dict:
        return {}

    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        # 只在关单状态重置状态
        if self.risk.status == RiskStatus.CLOSED:
            self.risk.status = RiskStatus.AWAIT_PROCESS
            self.risk.save(update_fields=["status"])

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        # 只在关单状态修改当前处理人
        if self.risk.status == RiskStatus.CLOSED:
            self.risk.current_operator = kwargs["new_operators"]
            self.risk.save(update_fields=["current_operator"])

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        return kwargs


class MisReport(RiskFlowBaseHandler):
    """
    误报
    """

    name = gettext_lazy("误报")
    enable_notice = False

    def pre_check(self, *args, **kwargs) -> None:
        if self.risk.status == RiskStatus.PENDING_CONFIRM:
            raise RiskStatusInvalid(message="待确认状态不能执行此操作")
        # 检查风险标签
        if self.risk.risk_label != RiskLabel.NORMAL:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.risk_label)

    def process(self, description: str, revoke_process: bool, *args, **kwargs) -> dict:
        # 若上一个节点为审批节点，需要关单
        if self.risk.last_history.action == ForApprove.__name__:
            resource.risk.force_revoke_approve_ticket(risk_id=self.risk.risk_id, node_id=self.risk.last_history.id)
        # 终止自动处理节点
        if revoke_process and self.risk.last_history.action == AutoProcess.__name__:
            resource.risk.force_revoke_auto_process(risk_id=self.risk.risk_id, node_id=self.risk.last_history.id)
        # 标记误报
        self.risk.risk_label = RiskLabel.MISREPORT
        self.risk.save(update_fields=["risk_label"])
        return {}

    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        pass

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        self.risk.current_operator = []
        self.risk.save(update_fields=["current_operator"])

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        return kwargs

    def post_process(self, process_result: dict, *args, **kwargs) -> None:
        # 强制终止 或 上一个节点不是处理套餐
        if kwargs["revoke_process"] or not self.risk.last_history.action == AutoProcess.__name__:
            CloseRisk(risk_id=self.risk.risk_id, operator=self.operator).run(
                description=gettext("%s 标记误报，系统自动关单") % self.operator
            )


class ReOpenMisReport(RiskFlowBaseHandler):
    """
    解除误报
    """

    name = gettext_lazy("解除误报")

    def pre_check(self, *args, **kwargs) -> None:
        if self.risk.risk_label != RiskLabel.MISREPORT:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.risk_label)

    def process(self, new_operators: List[str], *args, **kwargs) -> dict:
        self.risk.risk_label = RiskLabel.NORMAL
        self.risk.save(update_fields=["risk_label"])
        return {}

    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        pass

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        pass

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        if self.risk.status != RiskStatus.CLOSED:
            return {"description": gettext("原套餐继续执行")}
        return {"description": gettext("指定处理人：%s") % ";".join(kwargs["new_operators"])}

    def post_process(self, process_result: dict, *args, **kwargs) -> None:
        if self.risk.status == RiskStatus.CLOSED:
            ReOpen(risk_id=self.risk.risk_id, operator=self.operator).run(
                new_operators=kwargs["new_operators"],
                description=gettext("%s 解除误报，系统自动重开单据") % self.operator,
            )


class CustomProcess(RiskFlowBaseHandler):
    """
    人工处理，仅用于流转
    """

    name = gettext_lazy("人工处理")
    enable_notice = False

    def process(self, *args, **kwargs) -> dict:
        return {}

    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        pass

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        pass

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        return {"action": "CustomProcess", **kwargs}


class RiskExperienceRecord(CustomProcess):
    """
    保存风险处理经验（纯留痕，不变更状态/处理人/展示状态）
    """

    name = gettext_lazy("风险处理经验")
    enable_notice = False
    # 每次保存都是一次独立留痕，不做历史去重
    allow_duplicate_history = True

    def pre_check(self, *args, **kwargs) -> None:
        pass

    def sync_display_status(self):
        pass

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        return {"description": kwargs.get("description", "")}


class TransOperator(CustomProcess):
    """
    转单
    """

    name = gettext_lazy("转单")
    enable_notice = True

    def process(self, **kwargs) -> dict:
        return {}

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        self.risk.current_operator = kwargs["new_operators"]
        self.risk.save(update_fields=["current_operator"])

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        history = super().build_history(process_result, *args, **kwargs)
        history.update({"new_operators": kwargs["new_operators"], "custom_action": self.__class__.__name__})
        return history

    def update_status(self, process_result: dict, **kwargs) -> None:
        self.risk.status = RiskStatus.AWAIT_PROCESS
        self.risk.save(update_fields=["status"])


class OperateFailed(RiskFlowBaseHandler):
    """
    自动处理异常
    """

    name = gettext_lazy("自动处理异常")
    enable_notice = False

    def process(self, description: str, *args, **kwargs) -> dict:
        return {}

    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        self.risk.status = RiskStatus.AWAIT_PROCESS
        self.risk.save(update_fields=["status"])

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        self.risk.current_operator = self.load_processor()
        self.risk.save(update_fields=["current_operator"])

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        return kwargs


class ConfirmRisk(RiskFlowBaseHandler):
    """
    风险确认 - 从 PENDING_CONFIRM 转为 NEW 并触发处理流程
    """

    name = gettext_lazy("风险确认")
    allowed_status = [RiskStatus.PENDING_CONFIRM]

    def pre_check(self, *args, **kwargs) -> None:
        if self.risk.status == RiskStatus.CLOSED:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.status)
        # 检查 allowed_status
        if self.allowed_status and self.risk.status not in self.allowed_status:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.status)

    def process(self, description: str = "", *args, **kwargs) -> dict:
        # 事务内使用 select_for_update 重新校验状态，防止并发确认
        with transaction.atomic():
            risk = Risk.objects.select_for_update().get(risk_id=self.risk.risk_id)
            if risk.status != RiskStatus.PENDING_CONFIRM:
                raise RiskStatusInvalid(message=f"风险状态已变更，当前状态：{risk.status}")
            # 更新状态
            risk.status = RiskStatus.NEW
            risk.display_status = RiskDisplayStatus.NEW
            risk.save(update_fields=["status", "display_status"])
        return {}

    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        pass

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        pass

    def record_history(self, process_result: dict, *args, **kwargs) -> None:
        self.record_create_node()
        super().record_history(process_result=process_result, *args, **kwargs)

    def post_process(self, process_result: dict, *args, **kwargs) -> None:
        transaction.on_commit(lambda: self._post_confirm_tasks(description=kwargs.get("description", "")))

    def _post_confirm_tasks(self, description: str = "") -> None:
        """事务提交后执行的任务：流转、渲染、通知、记录历史"""

        self.risk.refresh_from_db()
        NewRisk(risk_id=self.risk.risk_id, operator=self.operator).run(skip_record=True)
        try:
            RiskHandler().trigger_render_task(self.risk)
        except Exception as e:
            logger.exception(f"[ConfirmRenderFailed] risk_id={self.risk.risk_id}, err={e}")
        try:
            RiskHandler().send_risk_notice(self.risk)
        except Exception as e:
            logger.exception(f"[ConfirmNoticeFailed] risk_id={self.risk.risk_id}, err={e}")

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        return {"description": kwargs.get("description", "")}


class ConfirmAsMisReport(RiskFlowBaseHandler):
    """
    风险确认为误报 - 直接关单
    """

    name = gettext_lazy("误报确认")
    allowed_status = [RiskStatus.PENDING_CONFIRM]

    def pre_check(self, *args, **kwargs) -> None:
        # 检查 CLOSED 状态（不调用 super() 避免 PENDING_CONFIRM 检查）
        if self.risk.status == RiskStatus.CLOSED:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.status)
        # 检查 allowed_status
        if self.allowed_status and self.risk.status not in self.allowed_status:
            raise RiskStatusInvalid(message=RiskStatusInvalid.MESSAGE % self.risk.status)

    def process(self, description: str = "", *args, **kwargs) -> dict:
        with transaction.atomic():
            risk = Risk.objects.select_for_update().get(risk_id=self.risk.risk_id)
            if risk.status != RiskStatus.PENDING_CONFIRM:
                raise RiskStatusInvalid(message=f"风险状态已变更，当前状态：{risk.status}")
            # 标记误报并关闭
            risk.risk_label = RiskLabel.MISREPORT
            risk.status = RiskStatus.CLOSED
            risk.display_status = RiskDisplayStatus.CLOSED
            risk.save(update_fields=["status", "display_status", "risk_label"])
        return {}

    def update_status(self, process_result: dict, *args, **kwargs) -> None:
        pass

    def update_operator(self, process_result: dict, *args, **kwargs) -> None:
        # 关单后清空处理人
        self.risk.current_operator = []
        self.risk.save(update_fields=["current_operator"])

    def sync_display_status(self) -> None:
        self.risk.display_status = RiskDisplayStatus.CLOSED

    def post_process(self, process_result: dict, *args, **kwargs) -> None:
        # 外部任务放到事务提交后执行，保证数据已落库
        transaction.on_commit(lambda: self._post_confirm_tasks(description=kwargs.get("description", "")))

    def _post_confirm_tasks(self, description: str = "") -> None:
        """事务提交后执行：风险关闭"""
        CloseRisk(risk_id=self.risk.risk_id, operator=self.operator).run(
            description=gettext("%s 标记误报，系统自动关单") % self.operator
        )

    def record_history(self, process_result: dict, *args, **kwargs) -> None:
        self.record_create_node()
        super().record_history(process_result=process_result, *args, **kwargs)

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        # 记录确认说明和状态变更，供历史展示
        return {
            "description": kwargs.get("description", ""),
            "from_status": RiskStatus.PENDING_CONFIRM,
            "to_status": RiskStatus.CLOSED,
        }
