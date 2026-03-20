from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    """
    回填 has_report 字段：
    对所有已存在 RiskReport 记录的 Risk，将 has_report 置为 True。
    """
    Risk = apps.get_model("risk", "Risk")
    RiskReport = apps.get_model("risk", "RiskReport")

    print("[forwards] 开始回填 has_report", flush=True)

    # RiskReport 以 risk_id 为主键，直接取出所有已有报告的 risk_id
    risk_ids_with_report = RiskReport.objects.values_list("risk_id", flat=True)

    now = timezone.now()
    updated = Risk.objects.filter(risk_id__in=risk_ids_with_report, has_report=False).update(
        has_report=True, updated_at=now
    )
    print(f"[forwards] 共更新 {updated} 条 Risk.has_report = True", flush=True)

    print("[forwards] 回填 has_report 完成", flush=True)


def backwards(apps, schema_editor):
    """
    回滚：将所有 Risk.has_report 重置为 False。
    （字段本身由 0043_risk_has_report 管理，这里只重置数据）
    """
    Risk = apps.get_model("risk", "Risk")

    print("[backwards] 开始回滚 has_report", flush=True)

    now = timezone.now()
    updated = Risk.objects.filter(has_report=True).update(has_report=False, updated_at=now)
    print(f"[backwards] 共重置 {updated} 条 Risk.has_report = False", flush=True)

    print("[backwards] 回滚 has_report 完成", flush=True)


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0044_backfill_display_status"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
