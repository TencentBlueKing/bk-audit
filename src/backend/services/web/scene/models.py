# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import gettext_lazy

from core.models import (
    OperateRecordModel,
    SoftDeleteModel,
    SoftDeleteModelManager,
    SoftDeleteQuerySet,
)
from services.web.scene.constants import (
    ApplicationStatus,
    BindingType,
    GrantStatus,
    ResourceVisibilityType,
    SceneRole,
    SceneStatus,
    VisibilityScope,
)


class SceneQuerySet(SoftDeleteQuerySet):
    """场景软删除 QuerySet：删除前归档名称，释放 active name 唯一约束"""

    def delete(self):
        deleted_count = 0
        for scene in self:
            scene.delete()
            deleted_count += 1
        return deleted_count, {self.model._meta.label: deleted_count}


class SceneManager(SoftDeleteModelManager):
    def get_queryset(self):
        """获取默认过滤软删除数据且带场景归档删除行为的 queryset"""
        return SceneQuerySet(self.model, using=self._db).filter(is_deleted=False)


class Scene(SoftDeleteModel):
    """审计场景"""

    objects = SceneManager()

    SOFT_DELETE_NAME_SUFFIX_TEMPLATE = "__deleted__{}"

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
    iam_manager_group_id = models.BigIntegerField(
        gettext_lazy("管理用户组ID"), null=True, blank=True, help_text="IAM 管理用户组 ID"
    )
    iam_viewer_group_id = models.BigIntegerField(
        gettext_lazy("使用用户组ID"), null=True, blank=True, help_text="IAM 使用用户组 ID"
    )

    class Meta:
        verbose_name = gettext_lazy("审计场景")
        verbose_name_plural = verbose_name
        ordering = ["-scene_id"]
        unique_together = [("name", "is_deleted")]

    def __str__(self):
        return f"Scene({self.scene_id}: {self.name})"

    def get_soft_delete_name(self) -> str:
        """生成软删除归档名称，释放原始名称给后续重建使用"""
        suffix = self.SOFT_DELETE_NAME_SUFFIX_TEMPLATE.format(self.scene_id)
        max_length = self._meta.get_field("name").max_length
        return f"{self.name[: max_length - len(suffix)]}{suffix}"

    def delete(self, *args, **kwargs):  # pylint: disable=unused-argument
        if self.is_deleted:
            return
        self.name = self.get_soft_delete_name()
        self.is_deleted = True
        self.save(update_fields=["name", "is_deleted"])


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


class ResourceBinding(OperateRecordModel):
    """资源绑定关系（报表/工具与场景/平台的绑定）

    每个 resource_type + resource_id 组合唯一（一对一关系）。
    binding_type 决定绑定类型：
    - platform_binding: 平台级绑定，通过 visibility_type 控制可见范围
    - scene_binding: 场景级绑定，有且仅有一个场景关联
    """

    resource_type = models.CharField(
        gettext_lazy("资源类型"),
        max_length=32,
        choices=ResourceVisibilityType.choices,
        db_index=True,
    )
    resource_id = models.CharField(gettext_lazy("资源ID"), max_length=64, db_index=True)
    binding_type = models.CharField(
        gettext_lazy("绑定类型"),
        max_length=32,
        choices=BindingType.choices,
        db_index=True,
    )
    visibility_type = models.CharField(
        gettext_lazy("可见范围类型"),
        max_length=32,
        choices=VisibilityScope.choices,
        default=VisibilityScope.SPECIFIC_SCENES,
        blank=True,
        help_text="仅 platform_binding 时有效",
    )

    class Meta:
        verbose_name = gettext_lazy("资源绑定关系")
        verbose_name_plural = verbose_name
        unique_together = [("resource_type", "resource_id")]

    def __str__(self):
        return f"ResourceBinding({self.resource_type}: {self.resource_id}, {self.binding_type})"


class ResourceBindingScene(OperateRecordModel):
    """资源绑定-场景关联（一对多）"""

    binding = models.ForeignKey(ResourceBinding, on_delete=models.CASCADE, related_name="binding_scenes")
    scene = models.ForeignKey(Scene, on_delete=models.CASCADE, verbose_name=gettext_lazy("场景"), db_index=True)

    class Meta:
        verbose_name = gettext_lazy("资源绑定-场景关联")
        verbose_name_plural = verbose_name
        unique_together = [("binding", "scene")]

    def __str__(self):
        return f"ResourceBindingScene({self.binding_id}: scene={self.scene_id})"


class ResourceBindingSystem(OperateRecordModel):
    """资源绑定-系统关联（一对多）"""

    binding = models.ForeignKey(ResourceBinding, on_delete=models.CASCADE, related_name="binding_systems")
    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, db_index=True)

    class Meta:
        verbose_name = gettext_lazy("资源绑定-系统关联")
        verbose_name_plural = verbose_name
        unique_together = [("binding", "system_id")]

    def __str__(self):
        return f"ResourceBindingSystem({self.binding_id}: system={self.system_id})"


class ScenePermissionApplication(OperateRecordModel):
    """场景权限申请单"""

    scene = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name="permission_applications")
    applicant = models.CharField(gettext_lazy("申请人"), max_length=64, db_index=True)
    role = models.CharField(gettext_lazy("申请角色"), max_length=16, choices=SceneRole.choices, db_index=True)
    reason = models.TextField(gettext_lazy("申请理由"), blank=True, default="")

    # ITSM 单据
    itsm_sn = models.CharField(gettext_lazy("ITSM单号"), max_length=64, db_index=True)
    itsm_ticket_id = models.CharField(gettext_lazy("ITSM工单ID"), max_length=128, unique=True, db_index=True)
    itsm_ticket_url = models.CharField(gettext_lazy("ITSM工单链接"), max_length=512, blank=True, default="")
    callback_token = models.CharField(gettext_lazy("回调鉴权Token"), max_length=128, blank=True, default="")

    # 状态
    status = models.CharField(
        gettext_lazy("审批状态"),
        max_length=16,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
        db_index=True,
    )
    grant_status = models.CharField(
        gettext_lazy("授权状态"),
        max_length=16,
        choices=GrantStatus.choices,
        blank=True,
        default="",
        db_index=True,
    )
    approvers = models.JSONField(gettext_lazy("审批人"), default=list)
    reject_reason = models.TextField(gettext_lazy("拒绝理由"), blank=True, default="")

    # 授权结果
    grant_method = models.CharField(gettext_lazy("授权方式"), max_length=32, blank=True, default="")
    grant_error = models.TextField(gettext_lazy("授权错误"), blank=True, default="")
    retry_count = models.IntegerField(gettext_lazy("授权重试次数"), default=0)
    finished_at = models.DateTimeField(gettext_lazy("完结时间"), null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("场景权限申请")
        verbose_name_plural = verbose_name
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["applicant", "status"], name="applicant_status_idx"),
            models.Index(fields=["scene", "status"], name="scene_status_idx"),
            models.Index(fields=["status", "retry_count"], name="status_retry_idx"),
            models.Index(fields=["status", "created_at"], name="status_created_idx"),
        ]

    def __str__(self):
        return f"ScenePermissionApplication({self.id}: scene={self.scene_id}, applicant={self.applicant})"

    @property
    def is_terminal(self) -> bool:
        """审批终态（审批结果已确定，不再被轮询）"""
        return self.status != ApplicationStatus.PENDING
