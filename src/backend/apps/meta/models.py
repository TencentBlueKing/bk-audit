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
from typing import Union

from blueapps.utils.logger import logger
from django.db import models
from django.utils.translation import gettext_lazy

from apps.exceptions import MetaConfigNotExistException
from apps.meta.constants import GLOBAL_CONFIG_LEVEL_INSTANCE, ConfigLevelChoices
from core.models import OperateRecordModel, SoftDeleteModel, SoftDeleteModelManager


class Unset:
    ...


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


class System(OperateRecordModel):
    """
    接入系统: 从 IAM 同步
    """

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, unique=True, null=False)
    namespace = models.CharField(gettext_lazy("namespace"), max_length=32, db_index=True)
    name = models.CharField(gettext_lazy("名称"), max_length=64, null=True)
    name_en = models.CharField(gettext_lazy("英文名称"), max_length=64, null=True)
    clients = models.JSONField(gettext_lazy("客户端"), max_length=64, null=True)
    provider_config = models.JSONField(gettext_lazy("系统配置"), null=True)
    logo_url = models.CharField(gettext_lazy("应用图标"), max_length=255, null=True)
    system_url = models.CharField(gettext_lazy("访问地址"), max_length=255, null=True)
    description = models.TextField(gettext_lazy("应用描述"), null=True)

    class Meta:
        verbose_name = gettext_lazy("接入系统")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class SystemRole(OperateRecordModel):
    """
    接入系统角色: 从 IAM 同步
    目前仅有接入系统管理员角色，系统管理直接复用 IAM 管理员角色，不独立接入 IAM
    """

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, db_index=True, null=False)
    role = models.CharField(gettext_lazy("角色名称"), max_length=32)
    username = models.CharField(gettext_lazy("用户名"), max_length=64, db_index=True)

    class Meta:
        verbose_name = gettext_lazy("系统角色")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class ResourceType(OperateRecordModel):
    """
    资源类型: 从 IAM 同步
    """

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, db_index=True, null=False)
    resource_type_id = models.CharField(gettext_lazy("资源类型ID"), max_length=64, db_index=True, null=False)
    name = models.CharField(gettext_lazy("名称"), max_length=64)
    name_en = models.CharField(gettext_lazy("英文名称"), max_length=64)
    sensitivity = models.IntegerField(gettext_lazy("敏感等级"))
    provider_config = models.JSONField(gettext_lazy("资源类型配置"), null=True)
    version = models.IntegerField(gettext_lazy("版本"))
    description = models.TextField(gettext_lazy("描述信息"), blank=True, null=True)

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


class Action(OperateRecordModel):
    """
    操作: 从 IAM 同步
    """

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64, db_index=True, null=False)
    action_id = models.CharField(gettext_lazy("操作ID"), max_length=64, null=True)
    name = models.CharField(gettext_lazy("名称"), max_length=64)
    name_en = models.CharField(gettext_lazy("英文名称"), max_length=64)
    sensitivity = models.IntegerField(gettext_lazy("敏感等级"))
    type = models.CharField(gettext_lazy("操作类型"), max_length=64)
    version = models.IntegerField(gettext_lazy("版本"))
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


class Field(OperateRecordModel):
    """
    标准审计事件
    """

    field_name = models.CharField(gettext_lazy("字段名称"), max_length=64, primary_key=True)
    field_type = models.CharField(gettext_lazy("字段类型"), max_length=32)
    alias_name = models.CharField(gettext_lazy("别名"), max_length=32, blank=True)
    is_text = models.BooleanField(gettext_lazy("是否分词"), default=False)
    is_time = models.BooleanField(gettext_lazy("是否时间字段"), default=False)
    is_json = models.BooleanField(gettext_lazy("是否为Json格式"), default=False)
    is_analyzed = models.BooleanField(gettext_lazy("是否分词"), default=False)
    is_dimension = models.BooleanField(gettext_lazy("是否纬度"), default=True)
    is_delete = models.BooleanField(gettext_lazy("是否删除"), default=False)
    is_required = models.BooleanField(gettext_lazy("是否必须"), default=True)
    is_display = models.BooleanField(gettext_lazy("是否展示"), default=True)
    is_built_in = models.BooleanField(gettext_lazy("是否内置"), default=True)
    option = models.JSONField(gettext_lazy("jsonschema声明"), null=True, default=dict)
    description = models.TextField(gettext_lazy("描述"), null=True)
    priority_index = models.SmallIntegerField(gettext_lazy("优先指数"), default=0)

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
