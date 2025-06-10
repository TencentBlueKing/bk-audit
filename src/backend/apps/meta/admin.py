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

from django.contrib import admin

from apps.meta.models import (
    Action,
    CustomField,
    DataMap,
    Field,
    GlobalMetaConfig,
    Namespace,
    ResourceType,
    ResourceTypeActionRelation,
    ResourceTypeTreeNode,
    SensitiveObject,
    System,
    SystemDiagnosisConfig,
    SystemFavorite,
    Tag,
)


@admin.register(GlobalMetaConfig)
class GlobalMetaConfigAdmin(admin.ModelAdmin):
    list_display = ["config_level", "instance_key", "config_key", "config_value"]
    list_filter = ["config_level", "config_key"]
    search_fields = ["instance_key"]


@admin.register(Namespace)
class NamespaceAdmin(admin.ModelAdmin):
    list_display = ["namespace", "name"]


@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = [
        "source_type",
        "system_id",
        "instance_id",
        "namespace",
        "name",
        "name_en",
        "clients",
        "has_logo",
        "has_system_url",
        "roles",
        "enable_system_diagnosis_push",
        "audit_status",
    ]
    ordering = ["namespace", "system_id"]
    search_fields = ["system_id", "name", "name_en", "instance_id"]
    list_filter = ["namespace", "enable_system_diagnosis_push", "source_type", "audit_status"]

    @admin.display(description="图标", boolean=True)
    def has_logo(self, obj: System):
        return bool(obj.logo_url)

    @admin.display(description="访问地址", boolean=True)
    def has_system_url(self, obj: System):
        return bool(obj.system_url)

    @admin.display(description="管理员")
    def roles(self, obj: System):
        return ",".join(obj.managers_list)


@admin.register(ResourceType)
class ResourceTypeAdmin(admin.ModelAdmin):
    list_display = ["id", "system_id", "resource_type_id", "name", "name_en", "sensitivity", "version", "ancestor"]
    ordering = ["system_id", "resource_type_id"]
    search_fields = ["system_id", "resource_type_id"]


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "system_id",
        "action_id",
        "type",
        "name",
        "name_en",
        "sensitivity",
        "version",
    ]
    ordering = ["system_id", "action_id"]
    search_fields = ["system_id", "action_id"]


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = [
        "field_name",
        "field_type",
        "description",
        "is_text",
        "is_time",
        "is_json",
        "is_analyzed",
        "is_dimension",
        "is_delete",
        "is_required",
        "is_display",
        "is_built_in",
        "is_zh_analyzed",
        "is_index",
        "priority_index",
    ]
    search_fields = ["field_name", "description"]
    list_filter = [
        "field_type",
        "is_text",
        "is_time",
        "is_json",
        "is_analyzed",
        "is_dimension",
        "is_delete",
        "is_required",
        "is_display",
        "is_zh_analyzed",
        "is_index",
        "is_built_in",
    ]


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ["username", "route_path", "fields"]
    search_fields = ["username"]
    list_filter = ["route_path"]


@admin.register(SensitiveObject)
class SensitiveObjectAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "system_id", "resource_type", "resource_id", "fields", "is_private", "is_deleted"]
    list_filter = ["is_private", "is_deleted"]


@admin.register(DataMap)
class DataMapAdmin(admin.ModelAdmin):
    list_display = ["id", "data_field", "data_key", "data_alias"]
    list_filter = ["data_field"]
    search_fields = ["data_key"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["tag_id", "tag_name"]


@admin.register(SystemDiagnosisConfig)
class SystemDiagnosisConfigAdmin(admin.ModelAdmin):
    list_display = ["system_id", "get_system_name", "push_status", "error_exist", "created_at"]
    list_display_links = ["system_id"]
    search_fields = ["system_id", "push_status"]
    list_filter = ["push_status"]
    ordering = ["-created_at"]

    @admin.display(description="系统名称")
    def get_system_name(self, obj):
        """通过system_id关联获取系统名称"""
        system = System.objects.filter(system_id=obj.system_id).first()
        return system.name if system else "-"

    @admin.display(description="存在错误", boolean=True)
    def error_exist(self, obj):
        """错误状态标记"""
        return bool(obj.push_error_message)


@admin.register(SystemFavorite)
class SystemFavoriteAdmin(admin.ModelAdmin):
    list_display = ["system_id", "username", "favorite"]
    list_filter = ["system_id", "favorite"]
    search_fields = ["system_id", "username"]


@admin.register(ResourceTypeActionRelation)
class ResourceTypeActionRelationAdmin(admin.ModelAdmin):
    list_display = ["id", "system_id", "resource_type_id", "action_id"]
    ordering = ["-id"]
    search_fields = ["system_id", "resource_type_id", "action_id"]


@admin.register(ResourceTypeTreeNode)
class ResourceTypeTreeNodeAdmin(admin.ModelAdmin):
    list_display = ["id", "related", "tree_id", "lft", "rgt", "depth"]
    search_fields = ["related__system_id", "related__resource_type_id", "related__name"]
    list_filter = ["tree_id", "depth"]
