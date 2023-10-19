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
            name="FeatureToggle",
            fields=[
                (
                    "feature_id",
                    models.CharField(max_length=64, primary_key=True, serialize=False, verbose_name="特性开关ID"),
                ),
                ("alias", models.CharField(blank=True, max_length=64, null=True, verbose_name="特性开关别名")),
                (
                    "status",
                    models.CharField(
                        choices=[("deny", "已关闭"), ("test", "灰度测试")],
                        default="deny",
                        max_length=32,
                        verbose_name="特性开关status",
                    ),
                ),
                ("is_enable_view", models.BooleanField(default=True, verbose_name="是否在前端展示")),
                ("config", models.JSONField(blank=True, null=True, verbose_name="特性开关配置")),
            ],
            options={
                "verbose_name": "特性开关",
                "verbose_name_plural": "特性开关",
                "ordering": ["feature_id"],
            },
        ),
    ]
