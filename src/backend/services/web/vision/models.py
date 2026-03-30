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
import importlib

from bk_audit.log.models import AuditInstance
from django.db import models
from django.db.models import Count, Q
from django.db.models.enums import TextChoices
from django.utils.translation import gettext_lazy

from core.models import OperateRecordModel, SoftDeleteModel
from services.web.vision.exceptions import VisionHandlerInvalid


class Scenario(TextChoices):
    DEFAULT = "default", gettext_lazy("默认")
    PER_APP = "per_app", gettext_lazy("按应用")
    TOOL = "tool", gettext_lazy("工具")


class ReportGroup(OperateRecordModel):
    """报表分组"""

    name = models.CharField(gettext_lazy("分组名称"), max_length=255, unique=True)
    priority_index = models.IntegerField(gettext_lazy("排序权重"), default=0, db_index=True)

    class Meta:
        verbose_name = gettext_lazy("报表分组")
        verbose_name_plural = verbose_name
        ordering = ["-priority_index", "name"]

    def __str__(self):
        return self.name

    @classmethod
    def get_or_create_by_name(cls, group_name: str) -> "ReportGroup":
        group, _ = cls.objects.get_or_create(
            name=group_name,
            defaults={"priority_index": cls.objects.count()},
        )
        return group

    @classmethod
    def cleanup_empty(cls):
        cls.objects.annotate(
            panel_count=Count("panels", filter=Q(panels__is_deleted=False)),
        ).filter(panel_count=0).delete()


class VisionPanel(SoftDeleteModel):
    """
    仪表盘
    """

    id = models.CharField(gettext_lazy("ID"), primary_key=True, max_length=255)
    vision_id = models.CharField(gettext_lazy("视图ID"), max_length=255, null=True)
    name = models.CharField(gettext_lazy("Name"), max_length=255, blank=True, null=True)
    priority_index = models.IntegerField(gettext_lazy("优先指数"), default=0)
    handler = models.CharField(gettext_lazy("处理器"), max_length=255, default="CommonVisionHandler")
    scenario = models.CharField(gettext_lazy("场景"), max_length=255, default="default", choices=Scenario.choices)
    description = models.TextField(gettext_lazy("描述"), blank=True, default="")
    group = models.ForeignKey(
        ReportGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="panels",
        verbose_name=gettext_lazy("所属分组"),
    )
    is_enabled = models.BooleanField(gettext_lazy("是否启用"), default=True)

    class Meta:
        verbose_name = gettext_lazy("仪表盘")
        verbose_name_plural = verbose_name
        ordering = ["-priority_index", "name"]

    def get_vision_handler_class(self):
        try:
            return getattr(importlib.import_module("services.web.vision.handlers.query"), self.handler)
        except (ImportError, AttributeError):
            raise VisionHandlerInvalid(self.handler)


class VisionPanelInstance:
    def __init__(self, panel: VisionPanel):
        self.instance_id = panel.id
        self.instance_name = panel.name

    @property
    def instance(self):
        return AuditInstance(self)


class ReportUserPreference(models.Model):
    """用户报表偏好"""

    username = models.CharField(gettext_lazy("用户名"), max_length=255, unique=True)
    config = models.JSONField(gettext_lazy("偏好配置"), default=dict)

    class Meta:
        verbose_name = gettext_lazy("用户报表偏好")
        verbose_name_plural = verbose_name
