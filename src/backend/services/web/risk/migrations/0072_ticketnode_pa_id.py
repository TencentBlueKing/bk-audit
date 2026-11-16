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

# 执行记录列表性能优化迁移：
# 1. 新增 TicketNode.pa_id（执行时套餐快照），用于替代 process_result.pa_name 的 JSON 过滤；
# 2. 增加执行记录列表常用复合索引：
#    action+sops_start_time、action+pa_id+sops_start_time、action+risk_id+sops_start_time。
#
# 历史数据回填不放在迁移中，避免大表长事务和死锁。
# 请执行 docs/scripts/backfill_ticketnode_pa_id.py 完成 pa_id / sops_start_time 回填。

from django.db import migrations, models


def column_exists(schema_editor, table: str, column: str) -> bool:
    """检查列是否存在，兼容迁移被中断后的重跑。"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
            [table, column],
        )
        return cursor.fetchone()[0] > 0


def index_exists(schema_editor, table: str, index_name: str) -> bool:
    """检查索引是否存在，兼容迁移被中断后的重跑。"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s",
            [table, index_name],
        )
        return cursor.fetchone()[0] > 0


def _expected_field_index_name(schema_editor, table: str, field) -> str:
    """复用 Django 自动命名规则，推导 db_index=True 字段的索引名。"""
    return schema_editor._create_index_name(table, [field.column])


class SafeAddField(migrations.AddField):
    """列已存在时跳过，并补齐缺失的 db_index 索引。"""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        table = model._meta.db_table
        field = model._meta.get_field(self.name)

        if not column_exists(schema_editor, table, field.column):
            super().database_forwards(app_label, schema_editor, from_state, to_state)
            return
        print(f"[SafeAddField] column exists, skip => {table}.{self.name}", flush=True)
        if not getattr(field, "db_index", False):
            return
        index_name = _expected_field_index_name(schema_editor, table, field)
        if index_exists(schema_editor, table, index_name):
            print(f"[SafeAddField] index exists, skip => {table}.{field.column} ({index_name})", flush=True)
            return
        schema_editor.execute(
            schema_editor._create_index_sql(
                field.model,
                fields=[field],
                name=index_name,
            )
        )


class SafeAddIndex(migrations.AddIndex):
    """索引已存在时跳过，兼容迁移被中断后的重跑。"""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        table = model._meta.db_table
        if index_exists(schema_editor, table, self.index.name):
            print(f"[SafeAddIndex] index exists, skip => {table}.{self.index.name}", flush=True)
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0071_riskwhitelist"),
    ]

    operations = [
        SafeAddField(
            model_name="ticketnode",
            name="pa_id",
            field=models.BigIntegerField(
                blank=True,
                db_index=True,
                help_text="执行时套餐快照，用于执行记录按套餐筛选；历史记录由脚本回填",
                null=True,
                verbose_name="Process Application ID",
            ),
        ),
        SafeAddIndex(
            model_name="ticketnode",
            index=models.Index(fields=["action", "sops_start_time"], name="risk_tn_act_start_idx"),
        ),
        SafeAddIndex(
            model_name="ticketnode",
            index=models.Index(fields=["action", "pa_id", "sops_start_time"], name="risk_tn_act_pa_start_idx"),
        ),
        SafeAddIndex(
            model_name="ticketnode",
            index=models.Index(fields=["action", "risk_id", "sops_start_time"], name="risk_tn_act_risk_start_idx"),
        ),
    ]
