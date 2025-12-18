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
        ("databus", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="collectorconfig",
            options={"ordering": ["-id"], "verbose_name": "采集项", "verbose_name_plural": "采集项"},
        ),
        migrations.AlterModelOptions(
            name="collectorplugin",
            options={"ordering": ["-id"], "verbose_name": "采集插件", "verbose_name_plural": "采集插件"},
        ),
        migrations.AddField(
            model_name="collectorplugin",
            name="allocation_min_days",
            field=models.IntegerField(default=0, verbose_name="冷热数据时间"),
        ),
        migrations.AddField(
            model_name="collectorplugin",
            name="retention",
            field=models.IntegerField(default=7, verbose_name="过期时间"),
        ),
        migrations.AddField(
            model_name="collectorplugin",
            name="storage_replies",
            field=models.IntegerField(default=1, verbose_name="副本数量"),
        ),
        migrations.AddField(
            model_name="collectorplugin",
            name="storage_shards_nums",
            field=models.IntegerField(default=1, verbose_name="分片数量"),
        ),
        migrations.AddField(
            model_name="collectorplugin",
            name="storage_shards_size",
            field=models.IntegerField(default=1, verbose_name="分片大小"),
        ),
    ]
