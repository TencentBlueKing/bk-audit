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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0066_bksec_preset_pa_and_ticketnode_is_test"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketnode",
            name="duration",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="Duration",
                help_text="处理耗时（秒），用于执行记录排序；未结束/缺失为 null",
            ),
        ),
    ]
