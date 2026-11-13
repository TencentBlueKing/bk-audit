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


def backfill_ticket_node_pa_id(apps, schema_editor):
    """回填 TicketNode.pa_id 和 sops_start_time。"""

    from services.web.risk.utils import calc_task_start_timestamp

    TicketNode = apps.get_model("risk", "TicketNode")
    Risk = apps.get_model("risk", "Risk")
    RiskRule = apps.get_model("risk", "RiskRule")

    batch = []
    queryset = (
        TicketNode.objects.filter(action="AutoProcess")
        .filter(Q(pa_id__isnull=True) | Q(sops_start_time__isnull=True))
        .only("id", "risk_id", "process_result", "pa_id", "sops_start_time", "timestamp")
    )
    for node in queryset.iterator(chunk_size=1000):
        process_result = node.process_result or {}
        pa_id = node.pa_id
        if not pa_id:
            pa_id = process_result.get("pa_id")
        if not pa_id:
            risk = Risk.objects.filter(risk_id=node.risk_id).only("rule_id", "rule_version").first()
            if risk and risk.rule_id:
                rule_queryset = RiskRule.objects.filter(rule_id=risk.rule_id)
                if risk.rule_version is not None:
                    rule_queryset = rule_queryset.filter(version=risk.rule_version)
                else:
                    rule_queryset = rule_queryset.order_by("-version")
                pa_id = rule_queryset.values_list("pa_id", flat=True).first()

        sops_start_time = node.sops_start_time
        if sops_start_time is None:
            sops_start_time = calc_task_start_timestamp(process_result.get("status") or {})
            if sops_start_time is None:
                sops_start_time = node.timestamp

        batch.append(
            TicketNode(
                id=node.id,
                pa_id=pa_id or node.pa_id,
                sops_start_time=sops_start_time,
            )
        )
        if len(batch) >= 1000:
            TicketNode.objects.bulk_update(batch, ["pa_id", "sops_start_time"])
            batch = []
    if batch:
        TicketNode.objects.bulk_update(batch, ["pa_id", "sops_start_time"])


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0071_riskwhitelist"),
    ]

    operations = [
        migrations.AddField(
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
        migrations.AddIndex(
            model_name="ticketnode",
            index=models.Index(fields=["action", "sops_start_time"], name="risk_tn_act_start_idx"),
        ),
        migrations.AddIndex(
            model_name="ticketnode",
            index=models.Index(fields=["action", "pa_id", "sops_start_time"], name="risk_tn_act_pa_start_idx"),
        ),
        migrations.AddIndex(
            model_name="ticketnode",
            index=models.Index(fields=["action", "risk_id", "sops_start_time"], name="risk_tn_act_risk_start_idx"),
        ),
    ]
