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
    SensitiveObject,
    System,
    SystemRole,
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
    list_display = ["system_id", "namespace", "name", "name_en", "clients", "has_logo", "has_system_url", "roles"]
    ordering = ["namespace", "system_id"]
    search_fields = ["system_id", "name", "name_en"]
    list_filter = ["namespace"]

    @admin.display(description="图标", boolean=True)
    def has_logo(self, obj: System):
        return bool(obj.logo_url)

    @admin.display(description="访问地址", boolean=True)
    def has_system_url(self, obj: System):
        return bool(obj.system_url)

    @admin.display(description="管理员")
    def roles(self, obj: System):
        roles = SystemRole.objects.filter(system_id=obj.system_id)
        return ",".join([role.username for role in roles])


@admin.register(ResourceType)
class ResourceTypeAdmin(admin.ModelAdmin):
    list_display = ["id", "system_id", "resource_type_id", "name", "name_en", "sensitivity", "version"]
    ordering = ["system_id", "resource_type_id"]
    search_fields = ["system_id", "resource_type_id"]


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ["id", "system_id", "action_id", "type", "name", "name_en", "sensitivity", "version"]
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
