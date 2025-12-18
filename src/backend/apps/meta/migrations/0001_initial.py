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

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Field",
            fields=[
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("field_name", models.CharField(max_length=64, primary_key=True, serialize=False, verbose_name="字段名称")),
                ("field_type", models.CharField(max_length=32, verbose_name="字段类型")),
                ("alias_name", models.CharField(blank=True, max_length=32, verbose_name="别名")),
                ("is_text", models.BooleanField(default=False, verbose_name="是否分词")),
                ("is_time", models.BooleanField(default=False, verbose_name="是否时间字段")),
                ("is_json", models.BooleanField(default=False, verbose_name="是否为Json格式")),
                ("is_analyzed", models.BooleanField(default=False, verbose_name="是否分词")),
                ("is_dimension", models.BooleanField(default=True, verbose_name="是否纬度")),
                ("is_delete", models.BooleanField(default=False, verbose_name="是否删除")),
                ("is_required", models.BooleanField(default=True, verbose_name="是否必须")),
                ("is_display", models.BooleanField(default=True, verbose_name="是否展示")),
                ("is_built_in", models.BooleanField(default=True, verbose_name="是否内置")),
                ("option", models.JSONField(default=dict, null=True, verbose_name="jsonschema声明")),
                ("description", models.TextField(null=True, verbose_name="描述")),
                ("priority_index", models.SmallIntegerField(default=0, verbose_name="优先指数")),
            ],
            options={
                "verbose_name": "字段",
                "verbose_name_plural": "字段",
                "ordering": ["-priority_index", "field_name"],
            },
        ),
        migrations.CreateModel(
            name="Namespace",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("namespace", models.CharField(db_index=True, max_length=32, verbose_name="namespace")),
                ("name", models.CharField(max_length=32, verbose_name="名称")),
            ],
            options={
                "verbose_name": "namespace",
                "verbose_name_plural": "namespace",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="SensitiveObject",
            fields=[
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="敏感ID"
                    ),
                ),
                ("name", models.CharField(max_length=64, verbose_name="名称")),
                ("fields", models.JSONField(verbose_name="关联字段")),
                ("priority_index", models.SmallIntegerField(default=0, verbose_name="优先指数")),
            ],
            options={
                "verbose_name": "敏感信息对象",
                "verbose_name_plural": "敏感信息对象",
                "ordering": ["-priority_index"],
            },
        ),
        migrations.CreateModel(
            name="System",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("system_id", models.CharField(max_length=64, unique=True, verbose_name="系统ID")),
                ("namespace", models.CharField(db_index=True, max_length=32, verbose_name="namespace")),
                ("name", models.CharField(max_length=64, null=True, verbose_name="名称")),
                ("name_en", models.CharField(max_length=64, null=True, verbose_name="英文名称")),
                ("clients", models.JSONField(max_length=64, null=True, verbose_name="客户端")),
                ("provider_config", models.JSONField(null=True, verbose_name="系统配置")),
                ("logo_url", models.CharField(max_length=255, null=True, verbose_name="应用图标")),
                ("system_url", models.CharField(max_length=255, null=True, verbose_name="访问地址")),
                ("description", models.TextField(null=True, verbose_name="应用描述")),
            ],
            options={
                "verbose_name": "接入系统",
                "verbose_name_plural": "接入系统",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="SystemRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("system_id", models.CharField(db_index=True, max_length=64, verbose_name="系统ID")),
                ("role", models.CharField(max_length=32, verbose_name="角色名称")),
                ("username", models.CharField(db_index=True, max_length=64, verbose_name="用户名")),
            ],
            options={
                "verbose_name": "系统角色",
                "verbose_name_plural": "系统角色",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="ResourceType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("system_id", models.CharField(db_index=True, max_length=64, verbose_name="系统ID")),
                ("resource_type_id", models.CharField(db_index=True, max_length=64, verbose_name="资源类型ID")),
                ("name", models.CharField(max_length=64, verbose_name="名称")),
                ("name_en", models.CharField(max_length=64, verbose_name="英文名称")),
                ("sensitivity", models.IntegerField(verbose_name="敏感等级")),
                ("provider_config", models.JSONField(null=True, verbose_name="资源类型配置")),
                ("version", models.IntegerField(verbose_name="版本")),
                ("description", models.TextField(blank=True, null=True, verbose_name="描述信息")),
            ],
            options={
                "verbose_name": "资源类型",
                "verbose_name_plural": "资源类型",
                "ordering": ["-id"],
                "unique_together": {("system_id", "resource_type_id")},
            },
        ),
        migrations.CreateModel(
            name="GlobalMetaConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                (
                    "config_level",
                    models.CharField(
                        choices=[("global", "全局配置"), ("biz", "业务配置"), ("system", "应用配置"), ("namespace", "命名空间")],
                        max_length=24,
                        verbose_name="配置级别",
                    ),
                ),
                ("instance_key", models.CharField(max_length=255, verbose_name="配置归属Key")),
                ("config_key", models.CharField(max_length=255, verbose_name="配置Key")),
                ("config_value", models.JSONField(null=True, verbose_name="配置Value")),
            ],
            options={
                "verbose_name": "系统全局配置",
                "verbose_name_plural": "系统全局配置",
                "ordering": ["config_level", "instance_key", "config_key"],
                "unique_together": {("config_level", "instance_key", "config_key")},
            },
        ),
        migrations.CreateModel(
            name="CustomField",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("route_path", models.CharField(max_length=64, verbose_name="字段归属页面")),
                ("username", models.CharField(blank=True, max_length=64, null=True, verbose_name="用户名")),
                ("fields", models.JSONField(null=True, verbose_name="自定义字段")),
            ],
            options={
                "verbose_name": "用户字段",
                "verbose_name_plural": "用户字段",
                "unique_together": {("route_path", "username")},
            },
        ),
        migrations.CreateModel(
            name="Action",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("system_id", models.CharField(db_index=True, max_length=64, verbose_name="系统ID")),
                ("action_id", models.CharField(max_length=64, null=True, verbose_name="操作ID")),
                ("name", models.CharField(max_length=64, verbose_name="名称")),
                ("name_en", models.CharField(max_length=64, verbose_name="英文名称")),
                ("sensitivity", models.IntegerField(verbose_name="敏感等级")),
                ("type", models.CharField(max_length=64, verbose_name="操作类型")),
                ("version", models.IntegerField(verbose_name="版本")),
                ("description", models.TextField(blank=True, null=True, verbose_name="描述信息")),
            ],
            options={
                "verbose_name": "操作",
                "verbose_name_plural": "操作",
                "ordering": ["-id"],
                "unique_together": {("system_id", "action_id")},
            },
        ),
    ]
