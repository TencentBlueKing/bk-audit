# -*- coding: utf-8 -*-
"""
NL2RiskFilter 查询历史：risk_view_type 列默认值改为 "all" 并回填存量。
本迁移作为新的 0062 执行：
1. AlterField 将 risk_view_type 默认改为 "all"（与模型保持一致）。
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
    """回滚：将回填成 "all" 的记录重置为空（列定义由 AlterField 自动反向移除默认值）。"""
    NL2RiskFilterLog = apps.get_model("risk", "NL2RiskFilterLog")

    print("[backwards] 开始回滚 NL2RiskFilterLog.risk_view_type 回填数据", flush=True)
    reset = NL2RiskFilterLog.objects.filter(risk_view_type=RISK_VIEW_TYPE_ALL).update(risk_view_type="")
    print(f"[backwards] 重置 {reset} 条 NL2RiskFilterLog.risk_view_type = ''", flush=True)


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0061_nl2riskfilterlog_risk_view_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="nl2riskfilterlog",
            name="risk_view_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("all", "全部风险"),
                    ("scene", "场景风险"),
                    ("todo", "待我处理"),
                    ("watch", "我的关注"),
                    ("processed", "处理历史"),
                    ("confirm", "待我确认"),
                ],
                db_index=True,
                default="all",
                max_length=32,
                verbose_name="风险视图类型",
            ),
        ),
        migrations.RunPython(_backfill, _reverse_backfill),
    ]
