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
from django.utils.translation import gettext_lazy

from services.web.databus.models import (
    CollectorConfig,
    CollectorPlugin,
    RedisConfig,
    Snapshot,
)


@admin.register(CollectorPlugin)
class CollectorPluginAdmin(admin.ModelAdmin):
    list_display = [
        "collector_plugin_id",
        "namespace",
        "plugin_scene",
        "collector_plugin_name",
        "collector_plugin_name_en",
        "bkdata_biz_id",
        "table_id",
        "etl_config",
        "config_count",
        "storage_changed",
    ]
    list_filter = ["namespace", "plugin_scene"]
    search_fields = ["collector_plugin_id", "collector_plugin_name"]
    ordering = ["-collector_plugin_id"]

    @admin.display(description=gettext_lazy("采集项数量"))
    def config_count(self, instance: CollectorPlugin) -> int:
        return CollectorConfig.objects.filter(collector_plugin_id=instance.collector_plugin_id).count()


@admin.register(CollectorConfig)
class CollectorConfigAdmin(admin.ModelAdmin):
    list_display = [
        "collector_config_id",
        "system_id",
        "bk_biz_id",
        "bk_data_id",
        "collector_config_name",
        "collector_config_name_en",
        "collector_plugin_info",
        "custom_type_raw",
        "etl_config",
        "join_data_rt",
        "bkbase_table_id",
        "has_storage",
        "storage_changed",
        "tail_log_time",
        "auth_rt",
        "is_deleted",
    ]
    list_filter = ["system_id", "custom_type", "is_deleted"]
    search_fields = ["collector_config_id", "collector_config_name"]
    ordering = ["-collector_config_id"]

    @admin.display(description=gettext_lazy("采集插件信息"))
    def collector_plugin_info(self, instance: CollectorConfig) -> str:
        try:
            plugin = CollectorPlugin.objects.get(collector_plugin_id=instance.collector_plugin_id)
            return "{}|{}".format(
                plugin.collector_plugin_id,
                CollectorPlugin.make_table_id(plugin.bkdata_biz_id, plugin.collector_plugin_name_en),
            )
        except CollectorPlugin.DoesNotExist:
            return ""

    @admin.display(description=gettext_lazy("类型"))
    def custom_type_raw(self, instance: CollectorConfig) -> str:
        return instance.custom_type


@admin.register(RedisConfig)
class RedisConfigAdmin(admin.ModelAdmin):
    list_display = ["redis_id", "namespace", "redis_name", "redis_name_en", "admin", "version"]
    search_fields = ["redis_id", "redis_name", "redis_name_en"]


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "system_id",
        "resource_type_id",
        "bkbase_data_id",
        "pull_type",
        "status",
        "bkbase_processing_id",
    ]
    search_fields = ["system_id", "resource_type_id"]
    ordering = ["system_id", "resource_type_id"]

    @admin.display
    def storage_type_display(self, instance) -> str:
        return ", ".join([str(s.storage_type) for s in instance.storages.all()])
