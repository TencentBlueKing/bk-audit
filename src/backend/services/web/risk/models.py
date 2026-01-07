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

import datetime
from functools import cached_property
from typing import List, Union

from bk_audit.constants.log import DEFAULT_EMPTY_VALUE
from bk_audit.log.models import AuditInstance
from blueapps.utils.request_provider import get_request_username
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import Field, Max, Q, QuerySet
from django.db.models.functions import Substr
from django.utils.translation import gettext_lazy
from pydantic import ValidationError as PydanticValidationError

from apps.meta.models import Tag
from apps.permission.handlers.actions import ActionEnum, ActionMeta, get_action_by_id
from apps.permission.handlers.permission import Permission
from core.models import OperateRecordModel, SoftDeleteModel, UUIDField
from core.sql.constants import FieldType
from core.sql.model import WhereCondition
from services.web.risk.constants import (
    LIST_RISK_FIELD_MAX_LENGTH,
    EventMappingFields,
    RenderTaskStatus,
    RiskLabel,
    RiskReportStatus,
    RiskStatus,
    TicketNodeStatus,
)
from services.web.risk.converter.queryset import RiskPathEqDjangoQuerySetConverter
from services.web.strategy_v2.models import Strategy, StrategyTag


def generate_risk_id() -> str:
    """ "
    年月日时分秒+6位随机码
    """

    now = datetime.datetime.now()
    risk_id = f"{now.strftime('%Y%m%d%H%M%S')}{('%.6f' % now.timestamp()).split('.')[1]}"
    if Risk.objects.filter(risk_id=risk_id).exists():
        return generate_risk_id()
    return risk_id


class UserType(models.TextChoices):
    OPERATOR = "operator"
    NOTICE_USER = "notice_user"


class StrategyTagMixin:
    """
    提供策略标签相关能力
    """

    @cached_property
    def strategy_tags(self) -> QuerySet[Tag]:
        """
        返回策略关联的所有Tag对象的QuerySet
        """
        return Tag.objects.filter(strategy_tags__strategy_id=self.strategy_id)

    def get_tag_ids(self):
        """
        获取风险的标签ID列表

        Returns:
            List[int]: 标签ID列表
        """
        return list(self.strategy_tags.values_list("tag_id", flat=True))

    def get_tag_names(self):
        """
        获取风险的标签名称列表

        Returns:
            List[str]: 标签名称列表
        """
        return list(self.strategy_tags.values_list("tag_name", flat=True))

    @classmethod
    def prefetch_strategy_tags(cls, queryset: QuerySet["StrategyTagMixin"]):
        """
        预加载策略标签，避免N+1查询

        Args:
            queryset: Risk的QuerySet

        Returns:
            QuerySet: 预加载了策略标签的QuerySet
        """

        # 预加载策略和策略标签
        return queryset.select_related('strategy').prefetch_related(
            models.Prefetch(
                'strategy__tags',  # 使用StrategyTag的related_name
                queryset=StrategyTag.objects.select_related('tag'),
                to_attr='prefetched_tags',
            )
        )


class Risk(StrategyTagMixin, OperateRecordModel):
    """
    Risk
    """

    risk_id = models.CharField(gettext_lazy("Risk ID"), primary_key=True, max_length=255, default=generate_risk_id)
    event_content = models.TextField(EventMappingFields.EVENT_CONTENT.description, null=True, blank=True)
    raw_event_id = models.CharField(EventMappingFields.RAW_EVENT_ID.description, max_length=255, db_index=True)
    strategy = models.ForeignKey(
        Strategy,
        db_constraint=False,
        verbose_name=EventMappingFields.STRATEGY_ID.description,
        on_delete=models.DO_NOTHING,
        related_name='risks',
    )
    event_evidence = models.TextField(EventMappingFields.EVENT_EVIDENCE.description, null=True, blank=True)
    event_type = models.JSONField(EventMappingFields.EVENT_TYPE.description, null=True, blank=True, default=list)
    event_data = models.JSONField(EventMappingFields.EVENT_DATA.description, null=True, blank=True)
    event_time = models.DateTimeField(EventMappingFields.EVENT_TIME.description, db_index=True)
    event_end_time = models.DateTimeField(
        EventMappingFields.EVENT_TIME.description, db_index=True, null=True, blank=True
    )
    event_source = models.CharField(
        EventMappingFields.EVENT_SOURCE.description, max_length=255, db_index=True, null=True, blank=True
    )
    operator = models.JSONField(EventMappingFields.OPERATOR.description, null=True, blank=True)
    status = models.CharField(
        gettext_lazy("Risk Status"), choices=RiskStatus.choices, default=RiskStatus.NEW, max_length=32, db_index=True
    )
    rule_id = models.BigIntegerField(gettext_lazy("Risk Rule ID"), null=True, blank=True)
    rule_version = models.IntegerField(gettext_lazy("Risk Rule Version"), null=True, blank=True)
    origin_operator = models.JSONField(
        gettext_lazy("Origin Operator"), max_length=64, null=True, blank=True, default=list
    )
    current_operator = models.JSONField(
        gettext_lazy("Current Operator"), max_length=64, null=True, blank=True, default=list
    )
    notice_users = models.JSONField(gettext_lazy("Notice Users"), default=list, null=True, blank=True)
    risk_label = models.CharField(
        gettext_lazy("Risk Label"),
        max_length=32,
        default=RiskLabel.NORMAL,
        null=True,
        blank=True,
        choices=RiskLabel.choices,
    )
    last_operate_time = models.DateTimeField(gettext_lazy("Last Operate Time"), auto_now=True, db_index=True)
    title = models.TextField(gettext_lazy("Risk Title"), null=True, blank=True, default=None)
    manual_synced = models.BooleanField(gettext_lazy("手动建的单是否已同步"), default=True)
    auto_generate_report = models.BooleanField(
        gettext_lazy("是否开启自动生成报告"),
        default=True,
        help_text=gettext_lazy("开启后策略产生新风险时会自动生成报告"),
    )

    class Meta:
        verbose_name = gettext_lazy("Risk")
        verbose_name_plural = verbose_name
        ordering = ["-event_time"]
        index_together = [
            ["strategy", "raw_event_id", "status"],
            ["strategy", "event_time"],
            ["risk_id", "event_time"],
            ["risk_id", "last_operate_time"],
        ]

    @classmethod
    def authed_risk_filter(cls, action: Union[ActionMeta, str]) -> Q:
        """
        获取有权限处理的风险筛选条件
        """

        q = Q(
            risk_id__in=TicketPermission.objects.filter(
                user_type__in=[UserType.NOTICE_USER, UserType.OPERATOR],
                user=get_request_username(),
                action=ActionEnum.LIST_RISK.id,
            ).values("risk_id")
        )

        permission = Permission(get_request_username())
        request = permission.make_request(action=get_action_by_id(action), resources=[])
        policies = permission.iam_client._do_policy_query(request)
        if policies:
            q |= RiskPathEqDjangoQuerySetConverter().convert(policies)
        return q

    @classmethod
    def annotated_queryset(cls) -> QuerySet["Risk"]:
        """
        返回默认的 Risk 查询集，包含截断后的 event_content_short 字段
        """
        return cls.objects.annotate(event_content_short=Substr("event_content", 1, LIST_RISK_FIELD_MAX_LENGTH)).defer(
            "event_content"
        )

    @classmethod
    def load_authed_risks(cls, action: Union[ActionMeta, str]) -> QuerySet["Risk"]:
        """
        获取有权限处理的风险
        """

        return cls.annotated_queryset().filter(cls.authed_risk_filter(action))

    @cached_property
    def last_history(self) -> Union["TicketNode", None]:
        from services.web.risk.handlers.ticket import MisReport, ReOpenMisReport

        nodes = TicketNode.objects.filter(risk_id=self.risk_id).order_by("-timestamp")
        for node in nodes:
            if node.action not in [MisReport.__name__, ReOpenMisReport.__name__]:
                return node
        return TicketNode()

    def auth_users(self, action: str, users: List[str], user_type: str = UserType.OPERATOR) -> None:
        """
        授权相关用户查询权限
        """
        TicketPermission.objects.bulk_create(
            objs=[
                TicketPermission(risk_id=self.risk_id, action=action, user_type=user_type, user=user) for user in users
            ],
            ignore_conflicts=True,
        )

    @classmethod
    def fields(cls) -> List[Field]:
        """
        返回风险的字段
        """

        return cls._meta.fields


class ManualEvent(OperateRecordModel):
    """
    手工录入的风险事件，除了主键与风险Model一致
    """

    manual_event_id = models.BigAutoField(gettext_lazy("Manual Risk Event ID"), primary_key=True)
    event_content = models.TextField(EventMappingFields.EVENT_CONTENT.description, null=True, blank=True)
    raw_event_id = models.CharField(EventMappingFields.RAW_EVENT_ID.description, max_length=255, db_index=True)
    strategy = models.ForeignKey(
        Strategy,
        db_constraint=True,
        verbose_name=EventMappingFields.STRATEGY_ID.description,
        on_delete=models.DO_NOTHING,
        related_name='manual_events',
    )
    event_evidence = models.TextField(EventMappingFields.EVENT_EVIDENCE.description, null=True, blank=True)
    event_type = models.CharField(EventMappingFields.EVENT_TYPE.description, null=True, blank=True, max_length=255)
    event_data = models.JSONField(EventMappingFields.EVENT_DATA.description, null=True, blank=True)
    event_time = models.DateTimeField(EventMappingFields.EVENT_TIME.description, db_index=True)
    event_source = models.CharField(
        EventMappingFields.EVENT_SOURCE.description, max_length=255, db_index=True, null=True, blank=True
    )
    operator = models.CharField(EventMappingFields.OPERATOR.description, null=True, blank=True, max_length=255)
    status = models.CharField(
        gettext_lazy("Risk Status"), choices=RiskStatus.choices, default=RiskStatus.NEW, max_length=32, db_index=True
    )
    rule_id = models.BigIntegerField(gettext_lazy("Risk Rule ID"), null=True, blank=True)
    rule_version = models.IntegerField(gettext_lazy("Risk Rule Version"), null=True, blank=True)
    origin_operator = models.JSONField(
        gettext_lazy("Origin Operator"), max_length=64, null=True, blank=True, default=list
    )
    current_operator = models.JSONField(
        gettext_lazy("Current Operator"), max_length=64, null=True, blank=True, default=list
    )
    notice_users = models.JSONField(gettext_lazy("Notice Users"), default=list, null=True, blank=True)
    risk_label = models.CharField(
        gettext_lazy("Risk Label"),
        max_length=32,
        default=RiskLabel.NORMAL,
        null=True,
        blank=True,
        choices=RiskLabel.choices,
    )
    last_operate_time = models.DateTimeField(gettext_lazy("Last Operate Time"), auto_now=True, db_index=True)
    title = models.TextField(gettext_lazy("Risk Title"), null=True, blank=True, default=None)
    manual_synced = models.BooleanField(gettext_lazy("手动建的单是否已同步"), default=False)

    class Meta:
        verbose_name = gettext_lazy("手动事件存储")
        verbose_name_plural = verbose_name
        ordering = ["-event_time"]
        index_together = [["strategy", "raw_event_id", "status"], ["strategy", "event_time"]]


class RiskAuditInstance(AuditInstance):
    """
    Risk Audit Instance
    """

    @property
    def instance_id(self):
        """
        实例ID
        @rtype: str
        """
        return getattr(self.instance, "risk_id", DEFAULT_EMPTY_VALUE)

    @property
    def instance_name(self):
        """
        实例名
        @rtype: str
        """
        return getattr(self.instance, "risk_id", DEFAULT_EMPTY_VALUE)

    @property
    def instance_data(self):
        """
        实例信息 JSON
        @rtype: dict
        """
        from services.web.risk.serializers import RiskInfoSerializer

        return RiskInfoSerializer(self.instance).data


def get_next_pa_id() -> int:
    pa = ProcessApplication.objects.all().order_by("-auto_id").first()
    if pa:
        return (pa.auto_id or 0) + 1
    return 1


class ProcessApplication(SoftDeleteModel):
    """
    处理套餐
    """

    id = models.BigAutoField(gettext_lazy("ID"), primary_key=True)
    uniq_id = UUIDField(gettext_lazy("UUID"), unique=True)
    name = models.CharField(gettext_lazy("Name"), max_length=64, db_index=True)
    sops_template_id = models.BigIntegerField(gettext_lazy("SOps Template ID"))
    need_approve = models.BooleanField(gettext_lazy("Need Approve"), default=True)
    approve_service_id = models.BigIntegerField(gettext_lazy("Approve Service ID"), null=True, blank=True)
    approve_config = models.JSONField(gettext_lazy("Approve Config"), null=True, blank=True)
    description = models.TextField(gettext_lazy("Description"), null=True, blank=True)
    is_enabled = models.BooleanField(gettext_lazy("Is Enabled"), default=True)

    class Meta:
        verbose_name = gettext_lazy("Process Application")
        verbose_name_plural = verbose_name
        ordering = ["-updated_at"]


class RiskRule(SoftDeleteModel):
    """
    风险处理规则
    """

    id = models.BigAutoField(gettext_lazy("ID"), primary_key=True)
    uniq_id = UUIDField(gettext_lazy("UUID"), unique=True)
    rule_id = models.BigIntegerField(gettext_lazy("Rule ID"), db_index=True, null=True, blank=True)
    version = models.IntegerField(gettext_lazy("版本号"), null=True, blank=True)
    name = models.CharField(gettext_lazy("Risk Rule Name"), max_length=64, db_index=True)
    scope = models.JSONField(gettext_lazy("Rule Scope"))
    pa_id = models.BigIntegerField(gettext_lazy("Process Application ID"), db_index=True, null=True, blank=True)
    pa_params = models.JSONField(gettext_lazy("Process Application Params"), null=True, blank=True)
    auto_close_risk = models.BooleanField(gettext_lazy("Auto Close Risk"), default=True)
    priority_index = models.IntegerField(gettext_lazy("Priority Index"), default=0)
    is_enabled = models.BooleanField(gettext_lazy("Is Enabled"), default=True)

    class Meta:
        verbose_name = gettext_lazy("Risk Rule")
        verbose_name_plural = verbose_name
        ordering = ["-updated_at"]
        unique_together = [["rule_id", "version"]]
        index_together = [["priority_index", "rule_id", "version"]]

    @classmethod
    def get_rule_or_404(cls, **kwargs) -> "RiskRule":
        rule = cls.objects.filter(**kwargs).order_by("-version").first()
        if rule:
            return rule
        raise cls.DoesNotExist()

    @classmethod
    def load_latest_rules(cls) -> QuerySet:
        max_versions = cls.objects.all().order_by().values("rule_id").annotate(max_version=Max("version"))
        q = Q()
        for v in max_versions:
            q |= Q(rule_id=v["rule_id"], version=v["max_version"])
        return cls.objects.filter(q)


class RiskRuleAuditInstance(AuditInstance):
    """
    Risk Rule Audit Instance
    """

    @property
    def instance_id(self):
        """
        实例ID
        @rtype: str
        """
        return getattr(self.instance, "rule_id", DEFAULT_EMPTY_VALUE)

    @property
    def instance_name(self):
        """
        实例名
        @rtype: str
        """
        return getattr(self.instance, "name", DEFAULT_EMPTY_VALUE)

    @property
    def instance_data(self):
        """
        实例信息 JSON
        @rtype: dict
        """
        from services.web.risk.serializers import RiskRuleInfoSerializer

        return RiskRuleInfoSerializer(self.instance).data


class RiskExperience(SoftDeleteModel):
    """
    Risk Experience
    """

    risk_id = models.CharField(gettext_lazy("Risk ID"), max_length=255, db_index=True)
    content = models.TextField(gettext_lazy("Risk Experience Content"))

    class Meta:
        verbose_name = gettext_lazy("Risk Experience")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class TicketNode(models.Model):
    """
    Ticket History
    """

    id = UUIDField(verbose_name=gettext_lazy("ID"), primary_key=True)
    risk_id = models.CharField(gettext_lazy("Risk ID"), max_length=255, db_index=True)
    operator = models.CharField(gettext_lazy("Operator"), max_length=255, db_index=True)
    current_operator = models.JSONField(gettext_lazy("Current Operator"), null=True, blank=True, default=list)
    action = models.CharField(gettext_lazy("Action"), max_length=64, db_index=True)
    timestamp = models.FloatField(gettext_lazy("Timestamp"), db_index=True)
    time = models.CharField(gettext_lazy("Time"), max_length=32)
    process_result = models.JSONField("Process Result", default=dict)
    extra = models.JSONField("Extra", default=dict)
    status = models.CharField(
        gettext_lazy("Status"),
        max_length=32,
        choices=TicketNodeStatus.choices,
        default=TicketNodeStatus.RUNNING,
        db_index=True,
    )

    class Meta:
        verbose_name = gettext_lazy("Ticket History")
        verbose_name_plural = verbose_name
        ordering = ["-timestamp"]


class TicketPermission(models.Model):
    """
    Ticket Permission
    """

    risk_id = models.CharField(gettext_lazy("Risk ID"), max_length=255, db_index=True)
    action = models.CharField(gettext_lazy("Action"), max_length=32, db_index=True)
    user = models.CharField(gettext_lazy("User"), max_length=255, db_index=True)
    authorized_at = models.DateTimeField(gettext_lazy("Authorized Time"), auto_now_add=True)
    user_type = models.CharField(gettext_lazy("User Type"), choices=UserType.choices, max_length=32, db_index=True)

    class Meta:
        verbose_name = gettext_lazy("Ticket Permission")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        unique_together = [["risk_id", "action", "user", "user_type"]]


class RiskEventSubscription(SoftDeleteModel):
    """
    风险事件订阅配置。

    - `token`: 对外暴露给订阅方的查询凭证，需唯一并可直接定位订阅记录；
    - `namespace`: 绑定 BKBase 命名空间，用于选择不同业务集群内的 Doris 结果表；
    - `condition`: 以 WhereCondition JSON 存储的筛选条件，运行时会解析为 Pydantic 对象；
    - `is_enabled`: 控制订阅是否可被拉取，关闭时任何 token 查询都会走 NotFound。
    """

    token = UUIDField(gettext_lazy("订阅 Token"), unique=True, db_index=True)
    name = models.CharField(gettext_lazy("配置名称"), max_length=128, blank=True, default="")
    namespace = models.CharField(
        gettext_lazy("命名空间"),
        max_length=64,
        default=settings.DEFAULT_NAMESPACE,
        db_index=True,
    )
    description = models.TextField(gettext_lazy("描述"), blank=True, default="")
    condition = models.JSONField(gettext_lazy("筛选条件"), default=dict, blank=True)
    is_enabled = models.BooleanField(gettext_lazy("是否启用"), default=True)

    class Meta:
        verbose_name = gettext_lazy("风险事件订阅")
        verbose_name_plural = verbose_name
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name or self.token}"

    @staticmethod
    def validate_condition_dict(condition: dict | None) -> WhereCondition | None:
        """
        将存储的 dict 验证并转换为 WhereCondition。

        - condition 为空时返回 None；
        - 有内容时使用 Pydantic model_validate 解析，失败则抛 DjangoValidationError。
        """
        if not condition:
            return None
        try:
            parsed = WhereCondition.model_validate(condition)
            normalized = RiskEventSubscription._sanitize_condition(parsed)
            RiskEventSubscription._validate_json_paths(normalized)
            return normalized
        except PydanticValidationError as exc:  # pragma: no cover - 防御性
            error_messages = []
            for err in exc.errors():
                loc = ".".join(str(part) for part in err.get("loc", [])) or "condition"
                error_messages.append(f"{loc}: {err.get('msg')}")
            raise DjangoValidationError({"condition": error_messages or ["invalid condition"]}) from exc

    @staticmethod
    def _sanitize_condition(condition: WhereCondition | None) -> WhereCondition | None:
        """
        递归移除空的条件节点，确保不会出现空 AND/OR 组。
        """
        if condition is None:
            return None

        # 清理子节点
        sanitized_children = []
        for child in condition.conditions:
            sanitized_child = RiskEventSubscription._sanitize_condition(child)
            if sanitized_child and (sanitized_child.condition or sanitized_child.conditions):
                sanitized_children.append(sanitized_child)

        condition.conditions = sanitized_children

        # 当前节点既没有 condition 也没有子节点 => 视为 None
        if not condition.condition and not condition.conditions:
            return None
        return condition

    @staticmethod
    def _validate_json_paths(condition: WhereCondition | None) -> None:
        """
        确保携带 keys 的字段为合法 JSON 路径，并补全默认类型。
        """
        if not condition:
            return

        stack = [condition]
        while stack:
            current = stack.pop()
            if current.condition and current.condition.field:
                field = current.condition.field
                if field.keys:
                    RiskEventSubscription._assert_valid_keys(field.keys)
                    if not field.field_type:
                        field.field_type = FieldType.STRING
            stack.extend(current.conditions or [])

    @staticmethod
    def _assert_valid_keys(keys: list[str]) -> None:
        """
        校验 JSON path keys，要求为非空字符串列表。
        """
        if not isinstance(keys, list) or not keys:
            raise DjangoValidationError({"condition": ["JSON path 必须是非空字符串数组"]})
        cleaned = []
        for key in keys:
            if not isinstance(key, str):
                raise DjangoValidationError({"condition": ["JSON path 仅支持字符串 key"]})
            stripped = key.strip()
            if not stripped:
                raise DjangoValidationError({"condition": ["JSON path 不允许空字符串"]})
            cleaned.append(stripped)
        keys.clear()
        keys.extend(cleaned)

    def get_where_condition(self) -> WhereCondition | None:
        """
        获取订阅的筛选条件，自动调用 validate_condition_dict 做校验。
        """
        return self.validate_condition_dict(self.condition)

    def set_where_condition(self, where: WhereCondition | None) -> None:
        """
        将 WhereCondition 序列化为 JSON 存储；没有条件时写入空 dict。
        """
        self.condition = where.model_dump(exclude_none=True) if where else {}


class RenderTask(OperateRecordModel):
    """
    渲染任务队列表

    用于记录需要渲染的报告任务，通过定时任务扫描并批量处理。
    """

    risk = models.ForeignKey(
        Risk,
        on_delete=models.CASCADE,
        related_name="render_tasks",
        verbose_name=gettext_lazy("关联风险"),
        db_index=True,
    )

    status = models.CharField(
        verbose_name=gettext_lazy("任务状态"),
        max_length=20,
        choices=RenderTaskStatus.choices,
        default=RenderTaskStatus.PENDING,
        db_index=True,
    )

    version = models.IntegerField(
        verbose_name=gettext_lazy("版本号"),
        default=1,
        help_text=gettext_lazy("用于控制并发，确保同一版本的渲染任务一致性"),
    )

    render_task_id = models.CharField(
        verbose_name=gettext_lazy("渲染器服务任务ID"),
        max_length=64,
        blank=True,
        null=True,
        help_text=gettext_lazy("调用渲染器服务后返回的任务ID，用于查询结果"),
    )

    error_message = models.TextField(
        verbose_name=gettext_lazy("错误信息"),
        blank=True,
        default="",
    )

    retry_count = models.IntegerField(
        verbose_name=gettext_lazy("重试次数"),
        default=0,
    )

    class Meta:
        verbose_name = gettext_lazy("渲染任务")
        verbose_name_plural = verbose_name
        ordering = ["risk", "-version"]
        unique_together = [["risk", "version"]]
        index_together = [
            ["risk", "status", "version"],
            ["status", "created_at"],
        ]

    def __str__(self):
        return f"RenderTask({self.risk_id}, {self.status}, v{self.version})"


class RiskReport(OperateRecordModel):
    """
    风险报告表
    """

    risk = models.OneToOneField(
        Risk,
        on_delete=models.CASCADE,
        related_name="report",
        verbose_name=gettext_lazy("关联风险"),
        primary_key=True,
    )

    content = models.TextField(
        verbose_name=gettext_lazy("报告内容"),
        blank=True,
        default="",
    )

    status = models.CharField(
        verbose_name=gettext_lazy("报告状态"),
        max_length=20,
        choices=RiskReportStatus.choices,
        default=RiskReportStatus.AUTO,
    )

    class Meta:
        verbose_name = gettext_lazy("风险报告")
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"RiskReport({self.risk_id})"
