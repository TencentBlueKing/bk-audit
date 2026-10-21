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
        ("risk", "0065_alter_risk_longtext_charset_utf8mb4"),
    ]

    operations = [
        migrations.AddField(
            model_name="processapplication",
            name="is_builtin",
            field=models.BooleanField(
                default=False,
                help_text="系统内置套餐（如 BKSEC 发单），请勿删除或停用",
                verbose_name="Is Builtin",
            ),
        ),
        migrations.AddField(
            model_name="riskrule",
            name="auto_strategy_id",
            field=models.BigIntegerField(
                blank=True,
                db_index=True,
                help_text="策略 BKSEC 发单自动创建时记录来源策略 ID，非空表示系统自动规则",
                null=True,
                verbose_name="Auto Created By Strategy",
            ),
        ),
        migrations.AddField(
            model_name="ticketnode",
            name="is_test",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Is Test"),
        ),
    ]
