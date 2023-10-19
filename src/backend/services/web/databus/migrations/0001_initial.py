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

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CollectorConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("system_id", models.CharField(db_index=True, max_length=64, verbose_name="系统ID")),
                ("bk_biz_id", models.IntegerField(db_index=True, verbose_name="所属业务")),
                ("bk_data_id", models.IntegerField(null=True, verbose_name="DATAID")),
                ("collector_plugin_id", models.IntegerField(verbose_name="BK-LOG 采集插件ID")),
                ("collector_config_id", models.IntegerField(verbose_name="BK-LOG 采集项ID")),
                ("collector_config_name", models.CharField(max_length=64, verbose_name="BK-LOG 采集项名称")),
                ("collector_config_name_en", models.CharField(max_length=64, null=True, verbose_name="BK-LOG 采集项英文名称")),
                (
                    "custom_type",
                    models.CharField(
                        choices=[("log", "容器日志上报"), ("otlp_trace", "otlpTrace上报"), ("otlp_log", "otlp日志上报")],
                        default="log",
                        max_length=30,
                        verbose_name="自定义类型",
                    ),
                ),
                ("fields", models.JSONField(default=list, verbose_name="字段列表")),
                ("bkbase_table_id", models.CharField(max_length=255, null=True, verbose_name="清洗")),
                ("processing_id", models.CharField(max_length=255, null=True, verbose_name="清洗")),
                ("has_storage", models.BooleanField(default=False, verbose_name="是否有入库")),
                ("description", models.TextField(null=True, verbose_name="描述")),
                ("etl_config", models.CharField(max_length=64, null=True, verbose_name="清洗配置")),
                ("etl_params", models.JSONField(default=dict, verbose_name="清洗参数")),
                ("join_data_rt", models.CharField(default=None, max_length=64, null=True, verbose_name="数据关联RT")),
                ("tail_log_time", models.DateTimeField(null=True, verbose_name="最新数据时间")),
                ("storage_changed", models.BooleanField(default=False, verbose_name="更新集群")),
            ],
            options={
                "verbose_name": "collector plugin",
                "verbose_name_plural": "collector plugin",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="CollectorPlugin",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("namespace", models.CharField(db_index=True, max_length=32, verbose_name="namespace")),
                ("collector_plugin_id", models.IntegerField(db_index=True, verbose_name="BK-LOG 采集插件ID")),
                ("collector_plugin_name", models.CharField(max_length=32, verbose_name="BK-LOG 采集插件名称")),
                (
                    "collector_plugin_name_en",
                    models.CharField(max_length=64, null=True, verbose_name="BK-LOG 采集插件英文名称"),
                ),
                ("bkdata_biz_id", models.IntegerField(verbose_name="数据所属业务")),
                ("table_id", models.IntegerField(verbose_name="结果表ID")),
                ("index_set_id", models.IntegerField(verbose_name="索引集ID")),
                ("etl_config", models.CharField(max_length=64, null=True, verbose_name="清洗配置")),
                ("etl_params", models.JSONField(default=dict, verbose_name="清洗参数")),
                ("storage_changed", models.BooleanField(default=False, verbose_name="更新集群")),
            ],
            options={
                "verbose_name": "collector plugin",
                "verbose_name_plural": "collector plugin",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="RedisConfig",
            fields=[
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("redis_id", models.BigAutoField(primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(max_length=64, verbose_name="命名空间")),
                ("redis_name_en", models.CharField(max_length=64, unique=True, verbose_name="资源ID")),
                ("redis_name", models.CharField(max_length=64, verbose_name="资源名称")),
                ("admin", models.JSONField(default=list, null=True, verbose_name="管理员")),
                ("connection_info", models.JSONField(verbose_name="连接信息")),
                ("version", models.CharField(max_length=32, verbose_name="版本")),
                ("extra", models.JSONField(default=dict, verbose_name="补充信息")),
            ],
            options={
                "verbose_name": "Redis Config",
                "verbose_name_plural": "Redis Config",
                "ordering": ["-redis_id"],
            },
        ),
        migrations.CreateModel(
            name="Snapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("system_id", models.CharField(max_length=64, verbose_name="系统ID")),
                ("resource_type_id", models.CharField(max_length=64, verbose_name="资源类型ID")),
                ("bkbase_data_id", models.IntegerField(null=True, verbose_name="接入ID")),
                ("bkbase_processing_id", models.CharField(max_length=255, null=True, verbose_name="清洗ID")),
                ("bkbase_table_id", models.CharField(max_length=255, null=True, verbose_name="入库表")),
                ("is_public", models.BooleanField(default=False, verbose_name="是否公共")),
                (
                    "status",
                    models.CharField(
                        choices=[("closed", "已关闭"), ("running", "运行中"), ("failed", "失败"), ("preparing", "启动中")],
                        default="closed",
                        max_length=32,
                        verbose_name="状态",
                    ),
                ),
            ],
            options={
                "verbose_name": "快照配置",
                "verbose_name_plural": "快照配置",
                "unique_together": {("system_id", "resource_type_id")},
            },
        ),
    ]
