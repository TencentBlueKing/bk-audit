# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import gettext_lazy

from core.models import OperateRecordModel, SoftDeleteModel, UUIDField
from services.web.tool.constants import DataSearchConfigTypeEnum, ToolTypeEnum
from services.web.vision.models import VisionPanel


class Tool(SoftDeleteModel):
    """
    工具
    """

    namespace = models.CharField(gettext_lazy("命名空间"), max_length=255, db_index=True)
    name = models.CharField(gettext_lazy("工具名称"), max_length=255, db_index=True)
    uid = UUIDField(gettext_lazy("工具UID"), db_index=True)
    version = models.IntegerField(gettext_lazy("版本"), db_index=True)
    description = models.TextField(gettext_lazy("工具描述"), null=True, blank=True, db_index=True)
    tool_type = models.CharField(gettext_lazy("工具类型"), choices=ToolTypeEnum.choices, max_length=16)
    config = models.JSONField(gettext_lazy("工具配置"), default=dict, blank=True)

    class Meta:
        verbose_name = gettext_lazy("Tool")
        verbose_name_plural = verbose_name
        unique_together = [("uid", "version")]
        ordering = ["namespace", "-updated_at"]


class DataSearchToolConfig(OperateRecordModel):
    """
    数据检索工具配置
    """

    tool = models.ForeignKey(Tool, db_constraint=False, on_delete=models.CASCADE)
    data_search_config_type = models.CharField(
        gettext_lazy("数据检索类型"), choices=DataSearchConfigTypeEnum.choices, max_length=32
    )
    sql = models.TextField(gettext_lazy("检索SQL"), null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("Data Search Tool Config")
        verbose_name_plural = verbose_name


class BkvisionToolConfig(OperateRecordModel):
    """
    Bkvision工具配置
    """

    tool = models.ForeignKey(Tool, db_constraint=False, on_delete=models.CASCADE)
    panel = models.ForeignKey(VisionPanel, db_constraint=False, on_delete=models.DO_NOTHING)

    class Meta:
        verbose_name = gettext_lazy("Bkvision Tool Config")
        verbose_name_plural = verbose_name


class ToolTag(OperateRecordModel):
    """
    工具标签关联表
    """

    tool_uid = models.CharField(gettext_lazy("工具UID"), max_length=64, db_index=True)
    tag_id = models.BigIntegerField(gettext_lazy("Tag ID"))

    class Meta:
        verbose_name = gettext_lazy("Tool Tag")
        verbose_name_plural = verbose_name
        unique_together = [("tool_uid", "tag_id")]
