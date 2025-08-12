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
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Union

from bk_audit.constants.log import DEFAULT_EMPTY_VALUE
from bk_audit.log.models import AuditInstance
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import IntegerField, OuterRef, Q, QuerySet, Subquery, Value
from django.db.models.aggregates import Count
from django.db.models.functions import Coalesce
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy
from django.utils.translation import gettext_lazy as _
from treebeard.exceptions import InvalidPosition, NodeAlreadySaved
from treebeard.ns_tree import NS_Node

from apps.exceptions import MetaConfigNotExistException
from apps.meta.constants import (
    GLOBAL_CONFIG_LEVEL_INSTANCE,
    IAM_MANAGER_ROLE,
    SYSTEM_AUTH_TOKEN_LENGTH,
    SYSTEM_INSTANCE_SEPARATOR,
    ConfigLevelChoices,
    SystemAuditStatusEnum,
    SystemDiagnosisPushStatusEnum,
    SystemPermissionTypeEnum,
    SystemSourceTypeEnum,
)
from apps.meta.exceptions import UniqueNameInValid
from core.choices import Unset
from core.models import (
    OperateRecordModel,
    OperateRecordModelManager,
    SoftDeleteModel,
    SoftDeleteModelManager,
)
from core.utils.data import generate_random_string


class GlobalMetaConfig(OperateRecordModel):
    """
    GlobalMetaConfig 系统全局配置
    """

    config_level = models.CharField(gettext_lazy("配置级别"), max_length=24, choices=ConfigLevelChoices.choices)
    instance_key = models.CharField(gettext_lazy("配置归属Key"), max_length=255)
    config_key = models.CharField(gettext_lazy("配置Key"), max_length=255)
    config_value = models.JSONField(gettext_lazy("配置Value"), null=True)

    class Meta:
        verbose_name = gettext_lazy("系统全局配置")
        verbose_name_plural = verbose_name
        ordering = ["config_level", "instance_key", "config_key"]
        unique_together = [["config_level", "instance_key", "config_key"]]

    @classmethod
    def get(
        cls,
        config_key: str,
        config_level: str = ConfigLevelChoices.GLOBAL.value,
        instance_key: str = GLOBAL_CONFIG_LEVEL_INSTANCE,
        *,
        default=Unset,
    ):
        try:
            return cls.objects.get(
                config_key=config_key, instance_key=instance_key, config_level=config_level
            ).config_value
        except cls.DoesNotExist:
            if default != Unset:
                return default
            msg = "MetaConfig Not Exist: config_level => {}; config_key => {}; instance_key => {}".format(
                config_level, config_key, instance_key
            )
            logger.error(msg)
            raise MetaConfigNotExistException(message=msg)

    @classmethod
    def set(
        cls,
        config_key: str,
        config_value: any,
        config_level: str = ConfigLevelChoices.GLOBAL.value,
        instance_key: str = GLOBAL_CONFIG_LEVEL_INSTANCE,
    ):
        config, _ = cls.objects.get_or_create(
            config_level=config_level, config_key=config_key, instance_key=instance_key
        )
        config.config_value = config_value
        config.save()
        return config


class Namespace(SoftDeleteModel):
    """
    Namespace: 一个namespace有多个接入系统，namespace间资源隔离
    """

    namespace = models.CharField(gettext_lazy("namespace"), max_length=32, db_index=True, null=False)
    name = models.CharField(gettext_lazy("名称"), max_length=32)

    class Meta:
        verbose_name = gettext_lazy("命名空间")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class SystemModelManager(OperateRecordModelManager):
    def with_action_resource_type_count(self) -> QuerySet:
        """
        获取带 action 和 resource_type count 的 queryset
        """

        qs = self.get_queryset()

        action_count_subquery = (
            Action.objects.filter(system_id=OuterRef("system_id"))
            .values("system_id")
            .annotate(count=Count("*"))
            .values("count")
        )

        resource_type_count_subquery = (
            ResourceType.objects.filter(system_id=OuterRef("system_id"))
            .values("system_id")
            .annotate(count=Count("*"))
            .values("count")
        )

        queryset = qs.annotate(
            action_count=Coalesce(Subquery(action_count_subquery, output_field=IntegerField()), Value(0)),
            resource_type_count=Coalesce(Subquery(resource_type_count_subquery, output_field=IntegerField()), Value(0)),
        )

        return queryset


class System(OperateRecordModel):
    """
    接入系统: 从 IAM 同步
    """

    objects = SystemModelManager()

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, unique=True, null=False)
    source_type = models.CharField(
        gettext_lazy("系统来源类型"),
        max_length=32,
        choices=SystemSourceTypeEnum.choices,
        default=SystemSourceTypeEnum.IAM_V3.value,
    )
    instance_id = models.CharField(gettext_lazy("系统实例ID"), max_length=32, null=False, default="")
    namespace = models.CharField(gettext_lazy("namespace"), max_length=32, db_index=True)
    name = models.CharField(gettext_lazy("名称"), max_length=64, null=True, blank=True)
    name_en = models.CharField(gettext_lazy("英文名称"), max_length=64, null=True, blank=True)
    clients = models.JSONField(gettext_lazy("客户端"), null=True, blank=True, default=list)
    description = models.TextField(gettext_lazy("应用描述"), null=True, blank=True)
    provider_config = models.JSONField(
        gettext_lazy("系统配置"), null=True, default=dict, blank=True, help_text=gettext_lazy("IAM V3")
    )
    callback_url = models.CharField(gettext_lazy("回调地址"), max_length=255, null=True, blank=True)
    auth_token = models.CharField(gettext_lazy("系统鉴权 Token"), max_length=64, null=True, blank=True)
    managers = models.JSONField(gettext_lazy("系统管理员"), default=list, blank=True)
    permission_type = models.CharField(
        gettext_lazy("权限类型"),
        max_length=16,
        choices=SystemPermissionTypeEnum.choices,
        default=SystemPermissionTypeEnum.COMPLEX.value,
        null=True,
        blank=True,
    )
    # paas 同步信息
    logo_url = models.CharField(gettext_lazy("应用图标"), max_length=255, null=True, blank=True)
    system_url = models.CharField(gettext_lazy("访问地址"), max_length=255, null=True, blank=True)
    # 系统诊断
    enable_system_diagnosis_push = models.BooleanField(gettext_lazy("是否开启系统诊断推送"), default=False)
    system_diagnosis_extra = models.JSONField(gettext_lazy("系统诊断额外信息"), default=dict, blank=True)
    # 审计状态
    audit_status = models.CharField(
        gettext_lazy("审计状态"),
        choices=SystemAuditStatusEnum.choices,
        max_length=16,
        default=SystemAuditStatusEnum.PENDING.value,
    )

    class Meta:
        verbose_name = gettext_lazy("接入系统")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        unique_together = [["source_type", "instance_id"]]

    @classmethod
    def build_system_id(cls, source_type: str, instance_id: str) -> str:
        """
        根据 source_type 和 instance_id 构造系统ID
        """

        # 兼容旧版;IAM v3 system_id 和 instance_id 相同
        if source_type == SystemSourceTypeEnum.IAM_V3.value:
            return instance_id
        return f"{source_type}_{instance_id}"

    def update_join_data(self):
        """
        更新系统关联数据(异步)
        """

        try:
            from services.web.databus.tasks import refresh_system_snapshots
        except ImportError:
            return

        refresh_system_snapshots.delay(system_id=self.system_id)

    @cached_property
    def managers_list(self) -> List[str]:
        """
        获取管理员列表
        """

        if self.managers:
            return list(self.managers)
        elif self.source_type == SystemSourceTypeEnum.IAM_V3.value:
            return list(
                SystemRole.objects.filter(system_id=self.system_id, role=IAM_MANAGER_ROLE).values_list(
                    "username", flat=True
                )
            )
        return []

    @cached_property
    def base64_token(self):
        """
        获取 base64 编码的 token
        """

        from apps.permission.handlers.permission import FetchInstancePermission

        return FetchInstancePermission.build_auth(settings.FETCH_INSTANCE_USERNAME, self.auth_token)

    def save(self, *args, **kwargs):
        if not self.system_id:
            self.system_id = self.build_system_id(self.source_type, self.instance_id)
        super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        """
        删除系统及其资源
        """

        SystemRole.objects.filter(system_id=self.system_id).delete()
        SystemDiagnosisConfig.objects.filter(system_id=self.system_id).delete()
        SystemFavorite.objects.filter(system_id=self.system_id).delete()
        return super().delete(*args, **kwargs)

    @classmethod
    def bulk_update_system_audit_status(cls, system_ids: List[str] = None):
        """
        批量更新系统审计状态: 有快照 or 有采集配置 => 已接入；否则 => 待接入
        :param system_ids: 待更新的系统 ID
        """

        try:
            from services.web.databus.models import CollectorConfig, Snapshot
        except ImportError as e:
            logger.warning(f"Failed to import required models: {e}")
            return

        system_ids = set(system_ids)
        if not system_ids:
            logger.warning("No systems found for the given IDs.")
            return

        # 查询关联了 Snapshot 或 CollectorConfig 的系统 ID
        snapshot_systems = Snapshot.objects.filter(system_id__in=system_ids).values_list("system_id", flat=True)
        collector_systems = CollectorConfig.objects.filter(system_id__in=system_ids).values_list("system_id", flat=True)

        # 计算已接入和待接入的系统
        accessed_systems = (set(snapshot_systems) | set(collector_systems)) & system_ids
        pending_systems = system_ids - accessed_systems

        # 批量更新状态
        if accessed_systems:
            cls.objects.filter(system_id__in=accessed_systems).update(
                _update_record=False, audit_status=SystemAuditStatusEnum.ACCESSED.value
            )
        if pending_systems:
            cls.objects.filter(system_id__in=pending_systems).update(
                _update_record=False, audit_status=SystemAuditStatusEnum.PENDING.value
            )

        logger.info(
            f"Updated audit status for {len(accessed_systems)} accessed and {len(pending_systems)} pending systems."
        )

    @classmethod
    def gen_auth_token(cls) -> str:
        """
        生成系统鉴权 Token
        """

        return generate_random_string(length=SYSTEM_AUTH_TOKEN_LENGTH)


class SystemDiagnosisConfig(OperateRecordModel):
    """
    系统诊断: 从系统推送
    """

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, null=False, unique=True)
    push_uid = models.CharField(gettext_lazy("系统诊断推送订阅uid"), max_length=64, null=True, default=None)
    push_status = models.CharField(
        gettext_lazy("系统诊断推送状态"), choices=SystemDiagnosisPushStatusEnum.choices, null=True, blank=True, max_length=32
    )
    push_config = models.JSONField(gettext_lazy("系统诊断推送配置"), default=dict, blank=True, null=True)
    push_result = models.JSONField(gettext_lazy("系统诊断推送结果"), default=dict, blank=True, null=True)
    push_error_message = models.TextField(gettext_lazy("系统诊断推送错误信息"), null=True, default=None, blank=True)

    class Meta:
        verbose_name = gettext_lazy("系统诊断")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class SystemInstance:
    def __init__(self, system_info: dict):
        self.instance_id = system_info.get("system_id", DEFAULT_EMPTY_VALUE)
        self.instance_name = system_info.get("name", DEFAULT_EMPTY_VALUE)
        self.instance_data = system_info

    @property
    def instance(self):
        return AuditInstance(self)


class SystemRole(OperateRecordModel):
    """
    接入系统角色: 从 IAM V3 同步
    目前仅有接入系统管理员角色，系统管理直接复用 IAM 管理员角色，不独立接入 IAM
    """

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, db_index=True, null=False)
    role = models.CharField(gettext_lazy("角色名称"), max_length=32)
    username = models.CharField(gettext_lazy("用户名"), max_length=64, db_index=True)

    class Meta:
        verbose_name = gettext_lazy("系统角色")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class ResourceTypeTreeNode(NS_Node):
    related = models.OneToOneField(
        "ResourceType",
        on_delete=models.DO_NOTHING,
        related_name="tree_node",
    )

    def __str__(self) -> str:
        return f"<ResourceTypeTreeNode {self.pk}→{self.related_id}>"


class ResourceType(OperateRecordModel):
    """
    资源类型: 从 IAM 同步
    """

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, db_index=True, null=False)
    resource_type_id = models.CharField(gettext_lazy("资源类型ID"), max_length=64, db_index=True, null=False)
    unique_id = models.CharField(
        gettext_lazy("唯一标识，资源类型场景下为'{系统ID}:{资源类型ID}'"), max_length=255, db_index=True, null=False, unique=True
    )
    name = models.CharField(gettext_lazy("名称"), max_length=64)
    name_en = models.CharField(gettext_lazy("英文名称"), max_length=64, null=True, blank=True)
    sensitivity = models.IntegerField(gettext_lazy("敏感等级"), default=0)
    provider_config = models.JSONField(gettext_lazy("资源类型配置"), null=True, default=dict, blank=True)
    path = models.CharField(gettext_lazy("资源路径"), max_length=255, default="")
    version = models.IntegerField(gettext_lazy("版本"), default=0, blank=True)
    description = models.TextField(gettext_lazy("描述信息"), blank=True, null=True)
    # 最多保存一个父 id；[] 表示根节点
    ancestor = models.JSONField(gettext_lazy("父资源类型"), default=list, blank=True)

    def __str__(self):
        return f"<ResourceType {self.unique_id}, with ancestor {self.ancestor}>"

    def __init__(self, *args, **kwargs):
        ancestors_data = kwargs.pop('ancestors', None)
        super().__init__(*args, **kwargs)
        if ancestors_data is not None:
            self.ancestors = ancestors_data

    def __setattr__(self, name, value):
        if name == 'ancestors':
            if isinstance(value, list):
                super().__setattr__('ancestor', value[:1])
            else:
                raise TypeError("ancestors must be a list")
        else:
            super().__setattr__(name, value)

    def clean(self):
        expected = f"{self.system_id}:{self.resource_type_id}"
        if self.unique_id and self.unique_id != expected:
            raise UniqueNameInValid(gettext_lazy("unique_id 必须为 %(val)s") % {"val": expected})
        # 如果外部没传值，就自动填
        self.unique_id = expected
        super().clean()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.clean()
            super().save(*args, **kwargs)
            # 同步树
            self._sync_tree(self)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        """
        删除节点时：
        1. 将直接子节点全部提为“森林”根节点；
        2. 清空子节点的 ancestor 字段；
        3. 删除自身 tree node；
        4. 删除自身 ResourceType —— 全程同一事务。
        """

        # ① 行级锁自己，防并发
        self.__class__.objects.select_for_update().filter(pk=self.pk)

        node: Optional[ResourceTypeTreeNode] = getattr(self, "tree_node", None)

        if node:
            children: List[ResourceTypeTreeNode] = list(node.get_children())

            # ② 移动子节点到根，并锁根节点
            for child in children:
                ResourceTypeTreeNode.objects.select_for_update().filter(pk__in=[child.pk, child.get_root().pk])
                child.move(child.get_root(), pos="last-sibling")

            # ③ 批量清空孩子的 ancestor
            self.__class__.objects.filter(pk__in=[c.related_id for c in children]).update(ancestor=[])

            # ④ 删除自己的 TreeNode
            node.delete()

            # 删除资源类型关联
            ResourceTypeActionRelation.objects.filter(
                system_id=self.system_id, resource_type_id=self.resource_type_id
            ).delete()
        # ⑤ 同一事务内删除 ResourceType 本身
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = gettext_lazy("资源类型")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        unique_together = [["system_id", "resource_type_id"]]

    @classmethod
    def get_name(cls, system_id: str, instance_id: str, default: str = None) -> str:
        try:
            return cls.objects.get(system_id=system_id, resource_type_id=instance_id).name
        except cls.DoesNotExist:
            return default or instance_id

    def resource_request_url(self, system: System = None) -> str:
        if not system:
            system = System.objects.filter(system_id=self.system_id).first()
        return system.callback_url.rstrip("/") + "/" + self.path.lstrip("/")

    @staticmethod
    def _sync_tree(rt: "ResourceType"):
        """
        确保：
          • 每个 ResourceType 恰有一个 TreeNode
          • TreeNode 的父节点 == rt.ancestor（空则为根）
        """
        # 1. 锁定自身，防并发修改
        rt = ResourceType.objects.select_for_update().select_related(None).get(pk=rt.pk)

        # 2. 获取 / 创建 TreeNode（处理并发）
        try:
            node = rt.tree_node
        except ResourceTypeTreeNode.DoesNotExist:
            try:
                node = ResourceTypeTreeNode.add_root(related=rt)
            except IntegrityError:
                node = rt.tree_node  # 并发事务已创建

        # 3. 解析并锁定目标父节点
        desired_parent: Optional[ResourceTypeTreeNode] = None
        parent_ids = rt.ancestor or []
        if parent_ids:
            parent_rt = (
                ResourceType.objects.select_for_update()
                .filter(resource_type_id=parent_ids[0], system_id=rt.system_id)
                .select_related("tree_node")
                .first()
            )
            desired_parent = getattr(parent_rt, "tree_node", None)
            if not desired_parent:
                raise ValueError(f"父节点 {parent_ids[0]} 不存在")

        # 4. 如父节点不同 → 迁移
        current_parent = node.get_parent()
        if current_parent == desired_parent:
            return

        # 环检测
        if desired_parent and (desired_parent == node or desired_parent.is_descendant_of(node)):
            raise ValueError(f"循环依赖：不能把 {node} 移到自身或其后代 {desired_parent} 下")

        # 锁定即将写入的节点
        lock_ids = [node.pk]
        if desired_parent:
            lock_ids.append(desired_parent.pk)
        ResourceTypeTreeNode.objects.select_for_update().filter(pk__in=lock_ids)

        try:
            if desired_parent:
                node.move(
                    desired_parent,
                    pos="sorted-child" if ResourceTypeTreeNode.node_order_by else "last-child",
                )
            else:
                node.move(node.get_root(), pos="last-sibling")
        except (InvalidPosition, NodeAlreadySaved) as exc:
            logger.exception("Tree move failed: %s → %s", node, desired_parent)
            raise ValueError(f"移动节点失败：{exc}") from exc

    @property
    def ancestors(self) -> List[dict]:
        """
        获取祖先节点
        """
        info = [item.related.resource_type_id for item in self.tree_node.get_ancestors()]
        info.reverse()
        return info


class Action(OperateRecordModel):
    """
    操作: 从 IAM 同步
    """

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, db_index=True, null=False)
    action_id = models.CharField(gettext_lazy("操作ID"), max_length=64, null=True)
    unique_id = models.CharField(gettext_lazy("唯一标识"), max_length=255, db_index=True, unique=True)
    name = models.CharField(gettext_lazy("名称"), max_length=64)
    name_en = models.CharField(gettext_lazy("英文名称"), max_length=64, null=True, blank=True)
    sensitivity = models.IntegerField(gettext_lazy("敏感等级"), default=0)
    type = models.CharField(gettext_lazy("操作类型"), max_length=64, blank=True, null=True)
    version = models.IntegerField(gettext_lazy("版本"), default=0, blank=True)
    description = models.TextField(gettext_lazy("描述信息"), blank=True, null=True)

    class Meta:
        verbose_name = gettext_lazy("操作")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        unique_together = [["system_id", "action_id"]]

    @classmethod
    def get_name(cls, system_id: str, instance_id: str, default: str = None) -> str:
        try:
            return cls.objects.get(system_id=system_id, action_id=instance_id).name
        except cls.DoesNotExist:
            return default or instance_id

    @classmethod
    def gen_unique_id(cls, system_id: str, action_id: str) -> str:
        """
        生成唯一的操作ID
        """

        return f"{system_id}{SYSTEM_INSTANCE_SEPARATOR}{action_id}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        保存操作时，生成唯一的操作ID
        """

        if not self.unique_id:
            self.unique_id = self.gen_unique_id(self.system_id, self.action_id)
        return super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        """
        删除操作时，删除关联的资源类型ID
        """

        ResourceTypeActionRelation.objects.filter(system_id=self.system_id, action_id=self.action_id).delete()
        return super().delete(*args, **kwargs)

    @classmethod
    def get_resource_type_id_map(cls, system_ids: List[str]) -> Dict[str, Dict[str, List[str]]]:
        """
        获取资源类型ID到资源类型ID列表的映射
        """

        # 获取所有操作的关联资源类型
        resource_relations = ResourceTypeActionRelation.objects.filter(
            system_id__in=system_ids,
        ).values('system_id', 'action_id', 'resource_type_id')

        # 构建操作ID到资源类型ID列表的映射
        action_to_resources = defaultdict(lambda: defaultdict(list))
        for relation in resource_relations:
            action_to_resources[relation['system_id']][relation['action_id']].append(relation['resource_type_id'])

        return action_to_resources

    @property
    def resource_type_ids(self) -> List[str]:
        """
        从 ResourceTypeActionRelation 获取该操作的关联资源类型ID
        """

        return [
            relation.resource_type_id
            for relation in ResourceTypeActionRelation.objects.filter(action_id=self.action_id)
        ]

    @resource_type_ids.setter
    def resource_type_ids(self, value: List[str]):
        """
        设置该操作的关联资源类型ID
        """

        self.set_resource_type_ids(value)

    @classmethod
    def bulk_set_resource_types(cls, action_relations: List[dict]):
        """
        批量设置操作与资源类型关系
        :param action_relations: [{
            "system_id": "system_id",
            "action_id": "action_id",
            "resource_type_ids": ["resource_type1", ...]
        }, ...]
        """
        if not action_relations:
            return

        # 第一步：查询现有关系
        action_keys = {(r['system_id'], r['action_id']) for r in action_relations}
        existing_q = Q()
        for system_id, action_id in action_keys:
            existing_q |= Q(system_id=system_id, action_id=action_id)

        existing_relations = defaultdict(set)
        for rel in ResourceTypeActionRelation.objects.filter(existing_q):
            key = (rel.system_id, rel.action_id)
            existing_relations[key].add(rel.resource_type_id)

        # 第二步：计算差异 - 需要删除和需要添加的关系
        to_delete = []
        to_create = []

        for relation in action_relations:
            system_id = relation['system_id']
            action_id = relation['action_id']
            new_ids = set(relation['resource_type_ids'])

            key = (system_id, action_id)
            current_ids = existing_relations.get(key, set())

            # 需要删除的关系
            for res_id in current_ids - new_ids:
                to_delete.append(Q(system_id=system_id, action_id=action_id, resource_type_id=res_id))

            # 需要添加的关系
            for res_id in new_ids - current_ids:
                to_create.append(
                    ResourceTypeActionRelation(system_id=system_id, action_id=action_id, resource_type_id=res_id)
                )

        # 第三步：批量执行操作
        with transaction.atomic():
            # 批量删除
            if to_delete:
                # 构建Q对象组合
                delete_query = Q()
                for q_obj in to_delete:
                    delete_query |= q_obj
                ResourceTypeActionRelation.objects.filter(delete_query).delete()

            # 批量创建
            if to_create:
                ResourceTypeActionRelation.objects.bulk_create(to_create, batch_size=1000)

    def set_resource_type_ids(self, resource_type_ids: List[str]):
        """
        设置操作关联的资源类型ID
        """

        resource_type_ids = ResourceType.objects.filter(
            system_id=self.system_id, resource_type_id__in=resource_type_ids
        ).values_list("resource_type_id", flat=True)

        self.bulk_set_resource_types(
            [{"system_id": self.system_id, "action_id": self.action_id, "resource_type_ids": resource_type_ids}]
        )


class ResourceTypeActionRelation(OperateRecordModel):
    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, db_index=True)
    resource_type_id = models.CharField(gettext_lazy("资源类型ID"), max_length=64, db_index=True)
    action_id = models.CharField(gettext_lazy("操作ID"), max_length=64, db_index=True)

    class Meta:
        verbose_name = gettext_lazy("资源类型操作关系")
        verbose_name_plural = verbose_name
        ordering = ["system_id", "resource_type_id"]
        unique_together = [["system_id", "resource_type_id", "action_id"]]


class Field(OperateRecordModel):
    """
    标准审计字段
    """

    field_name = models.CharField(gettext_lazy("字段名称"), max_length=64, primary_key=True)
    field_type = models.CharField(gettext_lazy("字段类型"), max_length=32)
    alias_name = models.CharField(gettext_lazy("别名"), max_length=32, blank=True)
    is_text = models.BooleanField(gettext_lazy("是否分词"), default=False)
    is_time = models.BooleanField(gettext_lazy("是否时间字段"), default=False)
    is_json = models.BooleanField(gettext_lazy("是否为Json格式"), default=False)
    is_analyzed = models.BooleanField(gettext_lazy("是否分词"), default=False)
    is_zh_analyzed = models.BooleanField(gettext_lazy("是否中文分词"), default=False)  # doris选项
    is_index = models.BooleanField(gettext_lazy("是否索引"), default=False)  # doris选项
    is_dimension = models.BooleanField(gettext_lazy("是否纬度"), default=True)
    is_delete = models.BooleanField(gettext_lazy("是否删除"), default=False)
    is_required = models.BooleanField(gettext_lazy("是否必须"), default=True)
    is_display = models.BooleanField(gettext_lazy("是否展示"), default=True)
    is_built_in = models.BooleanField(gettext_lazy("是否内置"), default=True)
    option = models.JSONField(gettext_lazy("jsonschema声明"), null=True, default=dict)
    description = models.TextField(gettext_lazy("描述"), null=True)
    priority_index = models.SmallIntegerField(gettext_lazy("优先指数"), default=0)
    property = models.JSONField(gettext_lazy("属性"), default=dict)

    class Meta:
        verbose_name = gettext_lazy("字段")
        verbose_name_plural = verbose_name
        ordering = ["-priority_index", "field_name"]

    def __hash__(self):
        if self.pk is None:
            return hash(self.field_name)
        return hash(self.pk)

    def to_json(self):
        return {
            "field_name": self.field_name,
            "field_type": self.field_type,
            "alias_name": self.alias_name,
            "is_text": self.is_text,
            "is_time": self.is_time,
            "is_json": self.is_json,
            "is_analyzed": self.is_analyzed,
            "is_dimension": self.is_dimension,
            "is_delete": self.is_delete,
            "is_required": self.is_required,
            "is_display": self.is_display,
            "is_built_in": self.is_built_in,
            "option": self.option,
            "description": str(self.description),
            "priority_index": self.priority_index,
            "property": self.property,
        }


def make_sensitive_obj_pk():
    return uuid.uuid1().hex


class SensitiveObjectManager(SoftDeleteModelManager):
    def all(self, *args, **kwargs):
        return super().filter(is_deleted=False, is_private=False)

    def filter(self, *args, **kwargs):
        kwargs["is_private"] = False
        return super().filter(*args, **kwargs)

    def get(self, *args, **kwargs):
        kwargs["is_private"] = False
        return super().get(*args, **kwargs)


class SensitiveObject(SoftDeleteModel):
    id = models.CharField(gettext_lazy("敏感ID"), primary_key=True, default=make_sensitive_obj_pk, max_length=64)
    name = models.CharField(gettext_lazy("名称"), max_length=64)
    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, null=True, blank=True)
    resource_type = models.CharField(gettext_lazy("资源类型"), max_length=64, null=True, blank=True)
    resource_id = models.CharField(gettext_lazy("资源ID"), max_length=64, null=True, blank=True)
    fields = models.JSONField(gettext_lazy("关联字段"))
    priority_index = models.SmallIntegerField(gettext_lazy("优先指数"), default=0)
    is_private = models.BooleanField(gettext_lazy("是否隐藏"), default=False, db_index=True)

    objects = SensitiveObjectManager()
    _objects = SoftDeleteModelManager()

    class Meta:
        verbose_name = gettext_lazy("敏感信息对象")
        verbose_name_plural = verbose_name
        ordering = ["-priority_index"]


class CustomField(OperateRecordModel):
    """
    自定义字段
    """

    route_path = models.CharField(gettext_lazy("字段归属页面"), max_length=64)
    username = models.CharField(gettext_lazy("用户名"), max_length=64, null=True, blank=True)
    fields = models.JSONField(gettext_lazy("自定义字段"), null=True)

    class Meta:
        verbose_name = gettext_lazy("用户字段")
        verbose_name_plural = verbose_name
        unique_together = [["route_path", "username"]]


class DataMap(OperateRecordModel):
    """
    数据字典
    """

    data_field = models.CharField(gettext_lazy("数据字段"), max_length=255)
    data_key = models.CharField(gettext_lazy("数据键"), max_length=255)
    data_alias = models.CharField(gettext_lazy("数据别名"), max_length=255)

    class Meta:
        verbose_name = gettext_lazy("数据字典")
        verbose_name_plural = verbose_name
        ordering = ["data_field", "data_key"]
        unique_together = [["data_field", "data_key"]]

    @classmethod
    def get_alias(cls, data_field: str, data_key: str, cache_data: defaultdict = None, default: str = None) -> str:
        """
        获取单个别名
        """

        # 统一转换为字符串处理
        data_key = str(data_key)
        # 优先使用缓存
        cache_data = defaultdict(dict) if cache_data is None else cache_data
        if data_key in cache_data[data_field].keys():
            return cache_data[data_field][data_key]
        # 获取数据
        try:
            alias = cls.objects.get(data_field=data_field, data_key=data_key).data_alias
        except cls.DoesNotExist:
            alias = data_key if default is None else default
            # 设置缓存
        cache_data[data_field][data_key] = alias
        # 响应
        return alias

    @classmethod
    def trans_data(
        cls, data: Union[list, dict], data_fields: list, build_data_fields: callable = lambda x: x, many: bool = False
    ) -> Union[list, dict]:
        """
        转换数据 (仅支持第一层)
        """

        # 无数据
        if not data:
            return data
        # 兼容多数据的情况
        if not many:
            data = [data]
        # 数据缓存
        data_map_cache = defaultdict(dict)
        # 转换
        for item in data:
            for field in data_fields:
                item[field] = cls.get_alias(build_data_fields(field), item.get(field), data_map_cache)
        # 响应
        return data if many else data[0]


class Tag(OperateRecordModel):
    """
    Tags of Strategy, Risk ...
    """

    tag_id = models.BigAutoField(gettext_lazy("Tag ID"), primary_key=True)
    tag_name = models.CharField(gettext_lazy("Tag Name"), max_length=64, unique=True)

    class Meta:
        verbose_name = gettext_lazy("Tag")
        verbose_name_plural = verbose_name
        ordering = ["-tag_id"]


class GeneralConfigScene(models.TextChoices):
    """通用配置场景"""

    SEARCH_CONFIG = "search_config", gettext_lazy("搜索配置")


class GeneralConfig(OperateRecordModel):
    """用于存储通用配置，支持用户特定的配置"""

    id = models.BigAutoField(primary_key=True)
    scene = models.CharField(max_length=255, help_text="配置场景，标识配置的应用场景", choices=GeneralConfigScene.choices)
    config_name = models.CharField(max_length=255, help_text="配置名称，标识配置的名称")
    config_content = models.JSONField(help_text="配置内容，存储具体的配置数据，JSON格式")

    class Meta:
        unique_together = ('scene', 'config_name', 'created_by')

    def __str__(self):
        return f"{self.scene} - {self.config_name} by {self.created_by}"


class SystemFavorite(OperateRecordModel):
    """
    System Favorite
    """

    system_id = models.CharField(gettext_lazy("System ID"), max_length=64)
    favorite = models.BooleanField(gettext_lazy("Favorite"), default=False)
    username = models.CharField(gettext_lazy("Username"), max_length=64)

    class Meta:
        verbose_name = gettext_lazy("System Favorite")
        verbose_name_plural = verbose_name
        unique_together = [["system_id", "username"]]


class EnumMappingCollection(models.Model):
    """
    存储一个枚举映射集合的信息。
    """

    collection_id = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Enum Mapping Collection"
        verbose_name_plural = "Enum Mapping Collections"


class EnumMappingEntity(models.Model):
    """
    存储一个枚举值的映射关系，包括 key 和 name。
    """

    collection = models.ForeignKey(EnumMappingCollection, related_name='entities', on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.key}: {self.name}"

    class Meta:
        unique_together = ('collection', 'key')  # 确保同一个 collection 中，key 是唯一的
        verbose_name = "Enum Mapping Entity"
        verbose_name_plural = "Enum Mapping Entities"


class EnumMappingRelatedType(models.TextChoices):
    """枚举映射关联类型"""

    STRATEGY = "strategy", _("策略")
    TOOL = "tool", _("工具")


class EnumMappingCollectionRelation(models.Model):
    """
    存储 EnumMappingCollection 和 外部引用对象 之间的关系
    """

    collection_id = models.CharField(max_length=255)
    related_object_id = models.CharField(max_length=255)
    related_type = models.CharField(
        max_length=64,
        choices=EnumMappingRelatedType.choices,
    )

    def __str__(self):
        return f"{self.collection_id} -> {self.related_type} {self.related_object_id}"

    class Meta:
        unique_together = ('collection_id', 'related_object_id', 'related_type')
        verbose_name = "Collection to Strategy Relation"
        verbose_name_plural = "Collection to Strategy Relations"
