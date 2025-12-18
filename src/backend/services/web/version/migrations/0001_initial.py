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

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="VersionLog",
            fields=[
                ("version", models.CharField(max_length=32, primary_key=True, serialize=False, verbose_name="版本号")),
                ("content", models.TextField(blank=True, null=True, verbose_name="版本日志")),
                ("release_at", models.DateField(verbose_name="发布时间")),
            ],
            options={
                "verbose_name": "版本日志",
                "verbose_name_plural": "版本日志",
                "ordering": ["-release_at"],
            },
        ),
        migrations.CreateModel(
            name="VersionLogVisit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.CharField(max_length=32, verbose_name="版本号")),
                ("username", models.CharField(max_length=64, verbose_name="用户名")),
                ("visit_at", models.DateTimeField(auto_now=True, verbose_name="查看时间")),
            ],
            options={
                "verbose_name": "版本日志访问记录",
                "verbose_name_plural": "版本日志访问记录",
                "ordering": ["username", "-visit_at"],
                "unique_together": {("version", "username")},
            },
        ),
    ]
