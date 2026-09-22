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
from typing import List, Optional

from bk_resource import api, resource
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
from rest_framework.settings import api_settings

from apps.itsm.constants import TicketStatus
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.saas import get_saas_url
from apps.notice.models import NoticeGroup
from apps.permission.handlers.actions import ActionEnum
from apps.sops.constants import SOPSTaskStatus
from core.exceptions import RiskStatusInvalid
from services.web.risk.constants import (
    DEFAULT_RISK_OPERATE_NOTICE_CONFIG,
    RISK_OPERATE_NOTICE_CONFIG_KEY,
    SECURITY_PERSON_KEY,
    ApproveTicketFields,
    RiskDisplayStatus,
    RiskLabel,
    RiskStatus,
)
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
from services.web.strategy_v2.models import Strategy


class RiskFlowBaseHandler:
    """
    用于流转风险单状态
    """

    name = gettext_lazy("默认流转")
    allowed_status = []
    enable_notice = True

    # 默认映射：status → display_status
    # 子类可覆盖以实现特殊映射（如 NewRisk 将 AWAIT_PROCESS 映射为"待处理"）
    DISPLAY_STATUS_MAP = {
        RiskStatus.NEW: RiskDisplayStatus.NEW,
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
        """

        # 获取策略
        if not self.strategy:
            return self.load_security_person()
        # 获取处理组成员
        processor_groups: List[NoticeGroup] = list(
            NoticeGroup.objects.filter(group_id__in=self.strategy.processor_groups or [])
        )
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

        nodes = TicketNode.objects.filter(risk_id=self.risk.risk_id).order_by("-timestamp")
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

        # 已关闭状态 或 状态不在允许的范围内
        if self.risk.status == RiskStatus.CLOSED or (
            self.allowed_status and self.risk.status not in self.allowed_status
        ):
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

        TicketNode.objects.create(
            risk_id=self.risk.risk_id,
            operator=self.operator,
            current_operator=self.risk.current_operator,
            action=self.__class__.__name__,
            timestamp=datetime.datetime.now().timestamp(),
            time=datetime.datetime.now().strftime(api_settings.DATETIME_FORMAT),
            process_result=process_result,
            extra=self.build_history(process_result=process_result, *args, **kwargs),
        )
        self.risk.save(update_fields=["last_operate_time"])

    def build_history(self, process_result: dict, *args, **kwargs) -> dict:
        """
        构造历史内容
        """

        return {}

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
        self.risk.current_operator = []
        self.risk.save(update_fields=["origin_operator", "current_operator"])
        # 只有有责任人时走规则
        if self.risk.operator:
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

    def process(self, pa_config: dict = None, **kwargs) -> dict:
        """
        三种发起方式
        1. 规则发起审批
        2. 人工选择处理套餐
        3. 自动更新审批状态
        """

        # 获取单据ID（V4 的 ticket_detail 仅支持按工单 ID 查询，不再支持按 sn 查询）
        ticket_id = self.load_approve_ticket_id()
        # 已发起则获取单据状态
        if ticket_id:
            return {"status": get_itsm_ticket_status(ticket_id)}
        # 兼容历史在途单据：V3 遗留单据只有 sn、没有 V4 工单 ID，无法用 V4 查询。
        # 此时必须保持审批中并告警，否则会被误判为「未发起」而重复建单
        sn = self.load_approve_sn()
        if sn:
            logger.warning(
                "[ForApprove] risk %s has legacy itsm ticket without v4 id, skip creating: sn=%s",
                self.risk.risk_id,
                sn,
            )
            return {"status": build_legacy_ticket_status(sn)}
        # 手动传入处理套餐需要重新初始化处理套餐
        if pa_config:
            self.init_process_application(pa_config["pa_id"])
        # 未发起则发起单据
        # 使用 V4 的 Workflows 接口获取流程（服务）详情，代替 V3 的 GetServiceDetail
        # bk_resource 已解包网关信封，workflows() 返回 {"items":[workflow, ...]}，
        # 此处取首个流程详情（workflow dict）交给 _parse_workflow_fields 解析字段
        workflow_detail = api.bk_itsm_v4.workflows(workflow_keys=self.process_application.approve_service_id)
        items = workflow_detail.get("items") or []
        workflow = items[0] if items else {}
        ticket_info = self._parse_workflow_fields(workflow)
        # V4 ticket_create 使用 form_data（字段 key -> value 字典），代替 V3 的 fields 列表
        form_data = {}
        for field in ticket_info["fields"]:
            key = field["key"]
            # V4 表单字段 key 带 ticket__ 命名空间前缀（如 ticket__title），统一去前缀后比对
            bare_key = key.split("__", 1)[-1]
            # 标题字段直接赋值
            if bare_key == ApproveTicketFields.TITLE.key:
                form_data[key] = gettext("【审计中心】执行%s审批") % self.process_application.name
                continue
            # 处理方案名称
            if bare_key == ApproveTicketFields.PROCESS_APPLICATION_NAME_FIELD.key:
                form_data[key] = self.process_application.name
                continue
            # 标签
            if bare_key == ApproveTicketFields.TAGS.key:
                form_data[key] = ";".join(self.risk.get_tag_names())
                continue
            # 责任人
            if bare_key == ApproveTicketFields.OPERATOR.key:
                form_data[key] = ";".join(self.risk.operator)
                continue
            # 风险链接
            if bare_key == ApproveTicketFields.RISK_URL.key:
                form_data[key] = "{}/risk-manage/detail/{}".format(get_saas_url(settings.APP_CODE), self.risk.risk_id)
                continue
            # 获取风险字段，以配置优先；key 与 bare_key 均尝试回退到风险对象属性
            value = (
                self.process_application.approve_config.get(key, {}).get("value")
                or self.process_application.approve_config.get(bare_key, {}).get("value")
                or getattr(self.risk, key, "")
                or getattr(self.risk, bare_key, "")
            )
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            form_data[key] = value
        ticket = api.bk_itsm_v4.ticket_create(
            operator=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
            workflow_key=self.process_application.approve_service_id,
            form_data=form_data,
            is_submit=True,
        )
        status = get_itsm_ticket_status(ticket["id"])
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
        V4 的 ticket_detail 仅支持按工单 ID 查询，故以 ID 作为「是否已发起」的判断依据。
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
    从 V4 工单详情里取当前处理人。

    V4 没有 V3 的 updated_by 字段，此处用当前处理人近似替代，
    以保证返回结构与 V3 的 ticket_approve_result 一致。
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


def build_legacy_ticket_status(sn: str) -> dict:
    """
    构造 V3 遗留单据（只有 sn、无 V4 工单 ID）的占位状态。

    状态取 RUNNING，使风险单保持「审批中」，避免 ForApprove 误判为
    「未发起」而重复建单。
    """

    return {
        "id": "",
        "sn": sn,
        "title": "",
        "update_at": "",
        "ticket_url": "",
        "updated_by": "",
        "approve_result": False,
        "current_status": TicketStatus.RUNNING.value,
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
            return {"status": api.bk_sops.get_task_status(task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID)}
        # 优先使用参数
        pa_config = pa_config
        # 或者使用上个节点(审批节点)配置
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
        pa_params = pa_params if pa_params is not None else (self.rule.pa_params if self.rule else pa_params)
        constants = {}
        for c in template_info["pipeline_tree"]["constants"].values():
            field = pa_params.get(c["key"])
            # 如果配置了常量，优先使用，没有常量使用字段映射
            value = field.get("value") or getattr(self.risk, field.get("field"), "")
            # 对值的类型进行转换
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            if isinstance(value, datetime.datetime):
                value = value.astimezone(tz=timezone.get_default_timezone()).strftime(api_settings.DATETIME_FORMAT)
            constants[c["key"]] = value
        params = {
            "name": f"{self.process_application.name}_{int(datetime.datetime.now().timestamp() * 1000)}",
            "constants": constants,
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "template_id": self.process_application.sops_template_id,
        }
        # 没有任务创建任务
        result = api.bk_sops.create_task(**params)
        api.bk_sops.start_task(task_id=result["task_id"], bk_biz_id=settings.DEFAULT_BK_BIZ_ID)
        return {
            "task": result,
            "status": api.bk_sops.get_task_status(task_id=result["task_id"], bk_biz_id=settings.DEFAULT_BK_BIZ_ID),
        }

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
                self.risk.last_history.save(update_fields=["process_result"])

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
