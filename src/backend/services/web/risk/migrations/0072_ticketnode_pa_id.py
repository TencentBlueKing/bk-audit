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
# 2. 回填历史 AutoProcess 节点的 pa_id：优先取 process_result.pa_id，
#    缺失时按 Risk.rule_id/rule_version -> RiskRule.pa_id 兜底；
# 3. 回填 sops_start_time：优先从 process_result.status 解析实际开始时间，缺失时回退 timestamp；
# 4. 增加执行记录列表常用复合索引：
#    action+sops_start_time、action+pa_id+sops_start_time、action+risk_id+sops_start_time。

from django.db import migrations, models
from django.db.models import Q


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


def backfill_ticket_node_pa_id(apps, schema_editor):
    """回填 TicketNode.pa_id 和 sops_start_time。"""

    import time

    from django.db import OperationalError, transaction

    from services.web.risk.utils import calc_task_start_timestamp

    TicketNode = apps.get_model("risk", "TicketNode")
    Risk = apps.get_model("risk", "Risk")
    RiskRule = apps.get_model("risk", "RiskRule")

    batch_size = 500
    last_id = ""
    total_updated = 0
    failed_batches = []

    while True:
        rows = list(
            TicketNode.objects.filter(action="AutoProcess")
            .filter(Q(pa_id__isnull=True) | Q(sops_start_time__isnull=True))
            .filter(id__gt=last_id)
            .order_by("id")
            .values("id", "risk_id", "process_result", "pa_id", "sops_start_time", "timestamp")[:batch_size]
        )
        if not rows:
            break

        batch = []
        for row in rows:
            process_result = row["process_result"] or {}
            pa_id = row["pa_id"]
            if not pa_id:
                pa_id = process_result.get("pa_id")
            if not pa_id:
                risk = Risk.objects.filter(risk_id=row["risk_id"]).only("rule_id", "rule_version").first()
                if risk and risk.rule_id:
                    rule_queryset = RiskRule.objects.filter(rule_id=risk.rule_id)
                    if risk.rule_version is not None:
                        rule_queryset = rule_queryset.filter(version=risk.rule_version)
                    else:
                        rule_queryset = rule_queryset.order_by("-version")
                    pa_id = rule_queryset.values_list("pa_id", flat=True).first()

            sops_start_time = row["sops_start_time"]
            if sops_start_time is None:
                sops_start_time = calc_task_start_timestamp(process_result.get("status") or {})
                if sops_start_time is None:
                    sops_start_time = row["timestamp"]

            batch.append(
                TicketNode(
                    id=row["id"],
                    pa_id=pa_id or row["pa_id"],
                    sops_start_time=sops_start_time,
                )
            )

        for attempt in range(3):
            try:
                with transaction.atomic(using=schema_editor.connection.alias):
                    TicketNode.objects.bulk_update(batch, ["pa_id", "sops_start_time"], batch_size=batch_size)
                break
            except OperationalError as err:
                # 1205 lock wait timeout / 1213 deadlock：小批次重试，避免整个迁移失败
                if err.args and err.args[0] in (1205, 1213) and attempt < 2:
                    print(
                        f"[backfill_ticket_node_pa_id] retry {attempt + 1}, error={err}, "
                        f"id range=({rows[0]['id']}, {rows[-1]['id']})",
                        flush=True,
                    )
                    time.sleep(1)
                    continue
                failed_batches.append({"start_id": rows[0]["id"], "end_id": rows[-1]["id"], "error": str(err)})
                print(
                    f"[backfill_ticket_node_pa_id][ERROR] batch failed, "
                    f"id range=({rows[0]['id']}, {rows[-1]['id']}), error={err}",
                    flush=True,
                )
                break

        last_id = rows[-1]["id"]
        total_updated += len(batch)
        print(
            f"[backfill_ticket_node_pa_id] batch done: updated={len(batch)}, total={total_updated}, "
            f"last_id={last_id}",
            flush=True,
        )

    print(
        f"[backfill_ticket_node_pa_id] finished: updated={total_updated}, failed_batches={len(failed_batches)}",
        flush=True,
    )
    if failed_batches:
        raise Exception(f"TicketNode pa_id backfill failed batches: {failed_batches}")


class Migration(migrations.Migration):

    # 禁用整体事务：按小批次提交，降低大表回填时的锁持有时间和死锁概率
    atomic = False

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
                help_text="执行时套餐快照，用于执行记录按套餐筛选；历史记录由迁移回填",
                null=True,
                verbose_name="Process Application ID",
            ),
        ),
        migrations.RunPython(backfill_ticket_node_pa_id, migrations.RunPython.noop),
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
