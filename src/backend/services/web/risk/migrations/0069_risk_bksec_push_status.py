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
        ("risk", "0068_alter_processapplication_approve_service_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="risk",
            name="bksec_push_status",
            field=models.CharField(
                choices=[
                    ("not_pushed", "未推送"),
                    ("success", "推送成功"),
                    ("failed", "推送失败"),
                ],
                db_index=True,
                default="not_pushed",
                help_text="BKSEC 推送状态：未推送 / 推送成功 / 推送失败",
                max_length=32,
                verbose_name="BKSEC Push Status",
            ),
        ),
        migrations.AddField(
            model_name="risk",
            name="bksec_push_event_id",
            field=models.CharField(
                blank=True,
                help_text="BKSEC 推送返回的事件 ID（WeSec 侧 event_id，非工单号），用于排查",
                max_length=255,
                null=True,
                verbose_name="BKSEC Push Event ID",
            ),
        ),
    ]
