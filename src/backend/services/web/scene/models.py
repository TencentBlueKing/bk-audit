# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import gettext_lazy

from core.models import OperateRecordModel
from services.web.scene.constants import (
    ResourceVisibilityType,
    SceneStatus,
    VisibilityScope,
)


class Scene(OperateRecordModel):
    """审计场景"""

    scene_id = models.BigAutoField(gettext_lazy("场景ID"), primary_key=True)
    name = models.CharField(gettext_lazy("场景名称"), max_length=128, db_index=True)
    description = models.TextField(gettext_lazy("场景描述"), blank=True, default="")
    status = models.CharField(
        gettext_lazy("状态"),
        max_length=32,
        choices=SceneStatus.choices,
        default=SceneStatus.ENABLED,
        db_index=True,
    )
    managers = models.JSONField(gettext_lazy("场景管理员列表"), default=list)
    users = models.JSONField(gettext_lazy("场景使用者列表"), default=list)

    class Meta:
        verbose_name = gettext_lazy("审计场景")
        verbose_name_plural = verbose_name
        ordering = ["-scene_id"]

    def __str__(self):
        return f"Scene({self.scene_id}: {self.name})"


class SceneSystem(OperateRecordModel):
    """场景关联系统及数据过滤规则"""

    scene = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name="scene_systems")
    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, db_index=True)
    is_all_systems = models.BooleanField(gettext_lazy("是否关联全部系统"), default=False)
    filter_rules = models.JSONField(gettext_lazy("数据过滤规则"), default=list)

    class Meta:
        verbose_name = gettext_lazy("场景-系统关联")
        verbose_name_plural = verbose_name
        unique_together = [("scene", "system_id")]

    def __str__(self):
        return f"SceneSystem({self.scene_id}: {self.system_id})"


class SceneDataTable(OperateRecordModel):
    """场景关联数据表及数据过滤规则"""

    scene = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name="scene_tables")
    table_id = models.CharField(gettext_lazy("数据表ID"), max_length=128, db_index=True)
    filter_rules = models.JSONField(gettext_lazy("数据过滤规则"), default=list)

    class Meta:
        verbose_name = gettext_lazy("场景-数据表关联")
        verbose_name_plural = verbose_name
        unique_together = [("scene", "table_id")]

    def __str__(self):
        return f"SceneDataTable({self.scene_id}: {self.table_id})"


class ResourceVisibility(OperateRecordModel):
    """平台资源（报表/工具）的场景可见范围"""

    resource_type = models.CharField(
        gettext_lazy("资源类型"),
        max_length=32,
        choices=ResourceVisibilityType.choices,
        db_index=True,
    )
    resource_id = models.CharField(gettext_lazy("资源ID"), max_length=64, db_index=True)
    visibility_type = models.CharField(
        gettext_lazy("可见范围类型"),
        max_length=32,
        choices=VisibilityScope.choices,
    )
    scene_ids = models.JSONField(gettext_lazy("可见场景ID列表"), default=list)
    system_ids = models.JSONField(gettext_lazy("可见系统ID列表"), default=list)

    class Meta:
        verbose_name = gettext_lazy("资源可见范围")
        verbose_name_plural = verbose_name
        unique_together = [("resource_type", "resource_id")]

    def __str__(self):
        return f"ResourceVisibility({self.resource_type}: {self.resource_id})"

    def is_visible_to_scene(self, scene_id: int) -> bool:
        """判断资源对指定场景是否可见"""
        if self.visibility_type == VisibilityScope.ALL_VISIBLE:
            return True
        if self.visibility_type == VisibilityScope.ALL_SCENES:
            return True
        if self.visibility_type == VisibilityScope.SPECIFIC_SCENES:
            return scene_id in self.scene_ids
        if self.visibility_type == VisibilityScope.SPECIFIC_SYSTEMS:
            # 需要检查场景关联的系统是否在可见系统列表中
            scene_system_ids = set(SceneSystem.objects.filter(scene_id=scene_id).values_list("system_id", flat=True))
            return bool(scene_system_ids & set(self.system_ids))
        return False
