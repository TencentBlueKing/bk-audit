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
        ("strategy_v2", "0028_alter_strategy_longtext_charset_utf8mb4"),
    ]

    operations = [
        migrations.AddField(
            model_name="strategy",
            name="bksec_config",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="BKSEC 发单配置（enabled / risk_type_id / field_mappings）",
                verbose_name="BKSEC 安全工单配置",
            ),
        ),
    ]
