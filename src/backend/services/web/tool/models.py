# -*- coding: utf-8 -*-
from typing import Optional

from django.db import models
from django.db.models import F, OuterRef, QuerySet, Subquery
from django.utils.translation import gettext_lazy

from core.models import OperateRecordModel, SoftDeleteModel, UUIDField
from core.sql.parser.praser import SqlQueryAnalysis
from core.utils.data import unique_id
from services.web.tool.constants import (
    BkVisionConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.vision.models import Scenario, VisionPanel


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
    permission_owner = models.CharField(gettext_lazy("权限负责人"), max_length=255, help_text="用于工具的权限认证")
    is_bkvision = models.BooleanField(gettext_lazy("是否更新BkVision工具"), default=False)

    class Meta:
        verbose_name = gettext_lazy("Tool")
        verbose_name_plural = verbose_name
        unique_together = [("uid", "version")]
        ordering = ["namespace", "-updated_at"]

    @classmethod
    def all_latest_tools(cls):
        """
        获取每个工具（按 uid 区分）的最新版本（version 最大）的记录集合。
        """
        base_qs = cls.objects.filter(is_deleted=False)
        subquery = base_qs.filter(uid=OuterRef('uid')).order_by('-version').values('version')[:1]
        return base_qs.annotate(max_version=Subquery(subquery)).filter(version=F('max_version'))

    @classmethod
    def last_version_tool(cls, uid: str) -> Optional["Tool"]:
        """
        获取指定 UID 的最新版本 Tool
        """
        return cls.objects.filter(uid=uid).order_by("-version").first()

    @classmethod
    def fetch_tool_vision_panel(cls, vision_id: str, handler: str) -> VisionPanel:
        panel, _ = VisionPanel.objects.get_or_create(
            vision_id=vision_id,
            scenario=Scenario.TOOL.value,
            handler=handler,
            defaults={
                "id": unique_id(),
            },
        )
        return panel

    @classmethod
    def delete_by_uid(cls, uid: str):
        Tool.objects.filter(uid=uid, is_deleted=False).delete()
        ToolTag.objects.filter(tool_uid=uid).delete()
        ToolFavorite.objects.filter(tool_uid=uid).delete()

    def get_tags(self) -> QuerySet["ToolTag"]:
        """
        获取工具的标签
        """

        return ToolTag.objects.filter(tool_uid=self.uid)

    def is_created_by(self, username: str) -> bool:
        """
        是否由指定用户创建
        """

        return self.created_by == username

    def get_permission_owner(self) -> str:
        """
        获取权限负责人
        """

        return self.permission_owner or self.created_by

    def has_change_permission_owner(self, new_config: dict) -> bool:
        """
        是否需要变更权限人
        """

        if (
            self.tool_type == ToolTypeEnum.DATA_SEARCH
            and self.data_search_config.data_search_config_type == DataSearchConfigTypeEnum.SQL
        ):
            # 如果新 SQL 解析后新增表则变更权限人
            new_config = SQLDataSearchConfig.model_validate(new_config)
            old_sql_parsed_def = SqlQueryAnalysis(sql=self.data_search_config.sql).get_parsed_def()
            new_parsed_def = SqlQueryAnalysis(sql=new_config.sql).get_parsed_def()
            new_sql_tables = {table.table_name for table in new_parsed_def.referenced_tables}
            old_sql_tables = {table.table_name for table in old_sql_parsed_def.referenced_tables}
            return bool(new_sql_tables - old_sql_tables)
        elif self.tool_type == ToolTypeEnum.BK_VISION:
            old_vision_config = BkVisionConfig.model_validate(self.config)
            new_vision_config = BkVisionConfig.model_validate(new_config)
            # 如果新 bkvision uid 变更则变更权限人
            return old_vision_config.uid != new_vision_config.uid

        return False


class DataSearchToolConfig(OperateRecordModel):
    """
    数据检索工具配置
    """

    tool = models.OneToOneField(Tool, on_delete=models.CASCADE, related_name="data_search_config")
    data_search_config_type = models.CharField(
        gettext_lazy("数据检索类型"), choices=DataSearchConfigTypeEnum.choices, max_length=32
    )
    sql = models.TextField(gettext_lazy("检索SQL"), null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("Data Search Tool Config")
        verbose_name_plural = verbose_name


class BkVisionToolConfig(OperateRecordModel):
    """
    BkVision工具配置
    """

    tool = models.OneToOneField(Tool, on_delete=models.CASCADE, related_name="bkvision_config")
    panel = models.ForeignKey(VisionPanel, on_delete=models.DO_NOTHING, related_name="tools")
    updated_time = models.DateTimeField(gettext_lazy("bkvision更新时间"), blank=True, null=True, db_index=True)

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


class ToolFavorite(OperateRecordModel):
    """工具收藏

    使用 tool_uid 而非 tool_id 关联工具，确保工具版本更新后收藏状态仍然正确。
    """

    tool_uid = models.CharField(gettext_lazy("工具UID"), max_length=64, db_index=True)
    username = models.CharField(gettext_lazy("Username"), max_length=64, db_index=True)

    class Meta:
        verbose_name = gettext_lazy("Tool Favorite")
        verbose_name_plural = verbose_name
        unique_together = [["tool_uid", "username"]]
