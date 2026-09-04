# -*- coding: utf-8 -*-
"""
NL2RiskFilter 查询历史：新增 risk_view_type 字段并回填存量。

1. 新增 NL2RiskFilterLog.risk_view_type 列，默认 "all"。
2. 一次性回填存量记录：将 risk_view_type 为空的记录置为 "all"
"""

from django.db import migrations, models

RISK_VIEW_TYPE_ALL = "all"


def _backfill(apps, schema_editor):
    NL2RiskFilterLog = apps.get_model("risk", "NL2RiskFilterLog")

    print("[forwards] 开始回填 NL2RiskFilterLog.risk_view_type=all", flush=True)

    updated = NL2RiskFilterLog.objects.filter(risk_view_type="").update(risk_view_type=RISK_VIEW_TYPE_ALL)

    print(f"[forwards] 回填完成：更新 {updated} 条 NL2RiskFilterLog.risk_view_type=all", flush=True)


def _reverse_backfill(apps, schema_editor):
    """回滚：恢复迁移前状态（存量记录 risk_view_type 均为空）。"""
    NL2RiskFilterLog = apps.get_model("risk", "NL2RiskFilterLog")

    print("[backwards] 开始回滚 NL2RiskFilterLog.risk_view_type 回填数据", flush=True)
    reset = NL2RiskFilterLog.objects.filter(risk_view_type=RISK_VIEW_TYPE_ALL).update(risk_view_type="")
    print(f"[backwards] 重置 {reset} 条 NL2RiskFilterLog.risk_view_type = ''", flush=True)


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0060_add_risk_scene_id_and_backfill"),
    ]

    operations = [
        migrations.AddField(
            model_name="nl2riskfilterlog",
            name="risk_view_type",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="all",
                max_length=32,
                verbose_name="风险视图类型",
            ),
        ),
        migrations.RunPython(_backfill, _reverse_backfill),
    ]
