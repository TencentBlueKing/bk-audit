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
from typing import Optional, Set

from bk_audit.constants.log import DEFAULT_EMPTY_VALUE
from bk_audit.log.models import AuditInstance
from django.db import models
from django.db.models import Max, Q, QuerySet
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy

from apps.meta.models import Tag
from core.models import OperateRecordModel, SoftDeleteModel, UUIDField
from services.web.analyze.constants import FlowDataSourceNodeType, FlowSQLNodeType
from services.web.analyze.models import Control, ControlVersion
from services.web.strategy_v2.constants import (
    RiskLevel,
    StrategyFieldSourceEnum,
    StrategySource,
    StrategyStatusChoices,
    StrategyType,
)


class Strategy(SoftDeleteModel):
    """
    Strategy
    """

    namespace = models.CharField(gettext_lazy("Namespace"), max_length=64)
    strategy_id = models.BigAutoField(gettext_lazy("Strategy ID"), primary_key=True)
    strategy_name = models.CharField(gettext_lazy("Strategy Name"), max_length=64)
    control_id = models.CharField(gettext_lazy("Control ID"), max_length=64, null=True, blank=True)
    control_version = models.IntegerField(gettext_lazy("Version"), null=True, blank=True)
    strategy_type = models.CharField(
        gettext_lazy("Strategy Type"), choices=StrategyType.choices, default=StrategyType.MODEL, max_length=16
    )
    configs = models.JSONField(gettext_lazy("Configs"), default=dict, null=True, blank=True)
    sql = models.TextField(gettext_lazy("Rule Audit SQL"), null=True, blank=True)
    link_table_uid = models.CharField(
        gettext_lazy("Link Table UID"), max_length=64, null=True, blank=True, db_index=True
    )
    link_table_version = models.IntegerField(gettext_lazy("Link Table Version"), null=True, blank=True)
    status = models.CharField(
        gettext_lazy("Status"),
        max_length=64,
        choices=StrategyStatusChoices.choices,
        default=StrategyStatusChoices.STARTING.value,
    )
    status_msg = models.TextField(gettext_lazy("Status Message"), null=True, blank=True)
    backend_data = models.JSONField(gettext_lazy("Backend Data"), default=dict, null=True, blank=True)
    notice_groups = models.JSONField(gettext_lazy("Notice Groups"), default=list, null=True, blank=True)
    processor_groups = models.JSONField(gettext_lazy("Processor"), default=list, null=True, blank=True)
    description = models.TextField(gettext_lazy("Description"), null=True, blank=True)
    risk_level = models.CharField(
        gettext_lazy("Risk Level"), choices=RiskLevel.choices, max_length=16, null=True, default=None
    )
    risk_hazard = models.TextField(gettext_lazy("Risk Hazard"), null=True, blank=True, default=None)
    risk_guidance = models.TextField(gettext_lazy("Risk Guidance"), null=True, blank=True, default=None)
    risk_title = models.CharField(gettext_lazy("Risk Title"), max_length=255, null=True, blank=True, default=None)
    event_basic_field_configs = models.JSONField(
        gettext_lazy("Event Field Configs"), default=list, null=True, blank=True
    )
    event_data_field_configs = models.JSONField(gettext_lazy("Event Data Configs"), default=list, null=True, blank=True)
    event_evidence_field_configs = models.JSONField(
        gettext_lazy("Event Evidence Configs"), default=list, null=True, blank=True
    )
    risk_meta_field_config = models.JSONField(
        gettext_lazy("Risk Meta Field Config"), default=list, null=True, blank=True
    )
    is_formal = models.BooleanField(gettext_lazy("Is Formal"), default=True)
    source = models.CharField(
        gettext_lazy("Source"),
        choices=StrategySource.choices,
        default=StrategySource.USER,
        max_length=16,
        db_index=True,
    )
    report_enabled = models.BooleanField(
        gettext_lazy("是否启用报告"),
        default=False,
        help_text=gettext_lazy("启用后，风险单会自动生成事件调查报告"),
    )
    report_config = models.JSONField(
        gettext_lazy("报告配置"),
        default=dict,
        blank=True,
        help_text=gettext_lazy("报告模板配置（template + ai_variables）"),
    )

    class Meta:
        verbose_name = gettext_lazy("Strategy")
        verbose_name_plural = verbose_name
        ordering = ["control_id", "-strategy_id"]

    def __str__(self):
        # 便于 Django Admin 过滤器中展示清晰可读的策略名称
        return self.strategy_name or str(self.strategy_id)

    @property
    def control_type_id(self):
        return Control.objects.get(control_id=self.control_id).control_type_id

    @property
    def control_version_inst(self) -> ControlVersion:
        return ControlVersion.objects.get(control_id=self.control_id, control_version=self.control_version)

    @property
    def sql_node_type(self) -> str:
        data_source = self.configs["data_source"]
        source_type = data_source.get("source_type", FlowDataSourceNodeType.BATCH_REAL)
        return FlowSQLNodeType.get_sql_node_type(source_type)

    def build_sheet_name(self) -> str:
        """
        构建策略 sheet 页名称
        """
        return f"{self.strategy_name}_{self.strategy_id}"


class StrategyAuditInstance(AuditInstance):
    """
    Strategy Audit Instance
    """

    @property
    def instance_id(self):
        """
        实例ID
        @rtype: str
        """
        return getattr(self.instance, "strategy_id", DEFAULT_EMPTY_VALUE)

    @property
    def instance_name(self):
        """
        实例名
        @rtype: str
        """
        return getattr(self.instance, "strategy_name", DEFAULT_EMPTY_VALUE)

    @property
    def instance_data(self):
        """
        实例信息 JSON
        @rtype: dict
        """
        from services.web.strategy_v2.serializers import StrategyInfoSerializer

        return StrategyInfoSerializer(self.instance).data


class StrategyTag(OperateRecordModel):
    """
    Tag of Strategy, only used for left side panel
    """

    strategy = models.ForeignKey(
        Strategy,
        db_column='strategy_id',
        on_delete=models.CASCADE,
        related_name="tags",
        verbose_name=gettext_lazy("Strategy"),
    )
    tag = models.ForeignKey(
        Tag,
        db_column='tag_id',
        on_delete=models.CASCADE,
        related_name="strategy_tags",
        verbose_name=gettext_lazy("Tag"),
    )

    class Meta:
        verbose_name = gettext_lazy("Strategy Tag")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        unique_together = [("strategy", "tag")]  # 防止重复关联


class StrategyTagSyncTrash(OperateRecordModel):
    """用于记录策略标签删除的墓碑数据"""

    original_id = models.BigIntegerField(gettext_lazy("Strategy Tag ID"), unique=True)
    strategy_id = models.BigIntegerField(gettext_lazy("Strategy ID"), default=0)
    tag_id = models.BigIntegerField(gettext_lazy("Tag ID"), default=0)

    class Meta:
        verbose_name = gettext_lazy("Strategy Tag Tombstone")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


@receiver(post_delete, sender=StrategyTag)
def record_strategy_tag_delete(sender, instance: StrategyTag, **kwargs):  # pylint: disable=unused-argument
    """记录策略标签删除事件，便于 IAM 回写清理"""

    StrategyTagSyncTrash.objects.update_or_create(
        original_id=instance.pk,
        defaults={
            "strategy_id": getattr(instance, "strategy_id", 0) or 0,
            "tag_id": getattr(instance, "tag_id", 0) or 0,
        },
    )


class LinkTable(OperateRecordModel):
    """
    联表数据
    """

    namespace = models.CharField(gettext_lazy("Namespace"), max_length=32, db_index=True)
    uid = UUIDField(gettext_lazy("Link Table UID"), db_index=True)
    version = models.IntegerField(gettext_lazy("Link Table Version"), db_index=True)
    name = models.CharField(gettext_lazy("Link Table Name"), max_length=200, db_index=True)
    config = models.JSONField(gettext_lazy("Config"))
    description = models.CharField(gettext_lazy("Description"), max_length=200, default="", blank=True, null=True)

    def __str__(self):
        return str(self.name)

    @property
    def display_name(self):
        return self.name

    class Meta:
        verbose_name = gettext_lazy("Link Table")
        verbose_name_plural = verbose_name
        unique_together = [("uid", "version")]
        ordering = ["namespace", "-updated_at"]

    @classmethod
    def last_version_link_table(cls, uid: str) -> Optional["LinkTable"]:
        """
        获取最新的版本的联表
        """

        return cls.objects.filter(uid=uid).order_by("-version").first()

    @classmethod
    def list_max_version_link_table(cls) -> QuerySet["LinkTable"]:
        """
        获取最大的版本的联表
        """

        # 找到每个 uid 的最大 version; order_by() 保证 uid 顺序
        max_versions = list(cls.objects.values("uid").annotate(max_version=Max("version")).order_by())
        q = Q()
        for max_version in max_versions:
            q |= Q(uid=max_version["uid"], version=max_version["max_version"])
        # 然后，基于 uid 和对应的最大 version 进行筛选
        return cls.objects.filter(q)

    @cached_property
    def rt_ids(self) -> Set[str]:
        """
        获取当前联表中的所有结果表
        """

        rt_ids = set()
        links = self.config.get("links", [])
        for link in links:
            rt_ids.add(link["left_table"]["rt_id"])
            rt_ids.add(link["right_table"]["rt_id"])
        return rt_ids


class LinkTableTag(OperateRecordModel):
    link_table_uid = models.CharField(gettext_lazy("Link Table UID"), max_length=64)
    tag_id = models.BigIntegerField(gettext_lazy("Tag ID"))

    class Meta:
        verbose_name = gettext_lazy("Link Table Tag")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class LinkTableAuditInstance(AuditInstance):
    """
    Link Table Audit Instance
    """

    @property
    def instance_id(self):
        """
        实例ID
        @rtype: str
        """
        return getattr(self.instance, "uid", DEFAULT_EMPTY_VALUE)

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
        from services.web.strategy_v2.serializers import LinkTableInfoSerializer

        return LinkTableInfoSerializer(self.instance).data


class StrategyTool(OperateRecordModel):
    """
    Strategy Tool
    """

    strategy = models.ForeignKey(
        Strategy,
        db_constraint=False,
        on_delete=models.CASCADE,
        related_name="tools",
        verbose_name=gettext_lazy("Strategy"),
    )
    tool_uid = models.CharField(gettext_lazy("工具UID"), max_length=64, db_index=True)
    tool_version = models.IntegerField(gettext_lazy("工具版本"), db_index=True)
    field_name = models.CharField(gettext_lazy("字段名"), max_length=64, db_index=True)
    field_source = models.CharField(gettext_lazy("字段来源"), max_length=16, choices=StrategyFieldSourceEnum.choices)

    class Meta:
        verbose_name = gettext_lazy("Strategy Tool")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        unique_together = [("strategy", "field_source", "field_name", "tool_uid")]  # 策略中的指定字段只能关联一个工具
