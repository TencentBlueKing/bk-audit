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

from django.db import migrations


class Migration(migrations.Migration):
    """
    将 analyse_report 相关表中所有 LONGTEXT 列的字符集改为 utf8mb4，
    以支持存储 4 字节 UTF-8 字符（如 emoji 表情符号）。

    涉及表和列：
    - risk_analysereportscenario: description, system_prompt
    - risk_analysereport: content, analysis_scope, custom_prompt
    """

    dependencies = [
        ("risk", "0046_analyse_report"),
    ]

    operations = [
        # ---- risk_analysereportscenario 表 ----
        migrations.RunSQL(
            sql="ALTER TABLE `risk_analysereportscenario` "
            "MODIFY COLUMN `description` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            reverse_sql="ALTER TABLE `risk_analysereportscenario` "
            "MODIFY COLUMN `description` LONGTEXT CHARACTER SET utf8 COLLATE utf8_general_ci;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE `risk_analysereportscenario` "
            "MODIFY COLUMN `system_prompt` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL;",
            reverse_sql="ALTER TABLE `risk_analysereportscenario` "
            "MODIFY COLUMN `system_prompt` LONGTEXT CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL;",
        ),
        # ---- risk_analysereport 表 ----
        migrations.RunSQL(
            sql="ALTER TABLE `risk_analysereport` "
            "MODIFY COLUMN `content` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            reverse_sql="ALTER TABLE `risk_analysereport` "
            "MODIFY COLUMN `content` LONGTEXT CHARACTER SET utf8 COLLATE utf8_general_ci;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE `risk_analysereport` "
            "MODIFY COLUMN `analysis_scope` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            reverse_sql="ALTER TABLE `risk_analysereport` "
            "MODIFY COLUMN `analysis_scope` LONGTEXT CHARACTER SET utf8 COLLATE utf8_general_ci;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE `risk_analysereport` "
            "MODIFY COLUMN `custom_prompt` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            reverse_sql="ALTER TABLE `risk_analysereport` "
            "MODIFY COLUMN `custom_prompt` LONGTEXT CHARACTER SET utf8 COLLATE utf8_general_ci;",
        ),
    ]
