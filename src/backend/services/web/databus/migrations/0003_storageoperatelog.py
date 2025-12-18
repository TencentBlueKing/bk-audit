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
        ("databus", "0002_auto_20220817_1055"),
    ]

    operations = [
        migrations.CreateModel(
            name="StorageOperateLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cluster_id", models.BigIntegerField(verbose_name="集群ID")),
                ("operator", models.CharField(blank=True, max_length=32, null=True, verbose_name="操作人")),
                ("operate_at", models.DateTimeField(auto_now_add=True, verbose_name="操作时间")),
                ("request_id", models.CharField(blank=True, max_length=64, null=True, verbose_name="请求ID")),
            ],
            options={
                "verbose_name": "集群操作记录",
                "verbose_name_plural": "集群操作记录",
                "ordering": ["-id"],
            },
        ),
    ]
