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

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notice", "0004_auto_20230907_1906"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoticeLogV2",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "relate_type",
                    models.CharField(
                        choices=[("risk", "风险"), ("error", "异常")], db_index=True, max_length=16, verbose_name="关联类型"
                    ),
                ),
                (
                    "relate_id",
                    models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="关联ID"),
                ),
                ("agg_key", models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="聚合标识")),
                ("msg_type", models.JSONField(default=list, verbose_name="消息类型")),
                ("receivers", models.JSONField(default=list, verbose_name="接收人")),
                ("title", models.TextField(blank=True, null=True, verbose_name="消息标题")),
                ("content", models.TextField(blank=True, null=True, verbose_name="消息内容")),
                ("create_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("schedule_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="发送时间")),
                ("schedule_result", models.BooleanField(blank=True, db_index=True, null=True, verbose_name="发送结果")),
                ("debug_info", models.TextField(blank=True, null=True, verbose_name="发送调试信息")),
            ],
            options={
                "verbose_name": "通知记录",
                "verbose_name_plural": "通知记录",
                "ordering": ["-id"],
                "index_together": {("relate_type", "agg_key", "schedule_at", "create_at")},
            },
        ),
    ]
