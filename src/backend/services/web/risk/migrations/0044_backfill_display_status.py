from django.db import migrations


def forwards(apps, schema_editor):
    """
    根据现有 status 回填 display_status。
    """
    Risk = apps.get_model("risk", "Risk")
    TicketNode = apps.get_model("risk", "TicketNode")

    print("[forwards] 开始回填 display_status", flush=True)

    # -------- 第一步：全量直接映射 status → display_status --------
    # 包含 await_deal → await_deal，先把所有记录都设为默认映射值
    full_mapping = {
        "new": "new",
        "for_approve": "for_approve",
        "auto_process": "auto_process",
        "closed": "closed",
        "await_deal": "await_deal",
    }
    for status_val, display_val in full_mapping.items():
        updated = (
            Risk.objects.filter(status=status_val)
            .exclude(display_status=display_val)
            .update(display_status=display_val)
        )
        print(f"[forwards] 映射 status={status_val} → display_status={display_val}, 更新 {updated} 条", flush=True)

    # -------- 第二步：修正少量 await_deal 中有操作历史的 → processing --------
    # 从 TicketNode 取出所有有非 NewRisk 操作的 risk_id（通常很少），直接作为子查询更新
    processing_risk_ids = TicketNode.objects.exclude(action="NewRisk").values_list("risk_id", flat=True).distinct()
    updated = (
        Risk.objects.filter(status="await_deal", risk_id__in=processing_risk_ids)
        .exclude(display_status="processing")
        .update(display_status="processing")
    )
    print(f"[forwards] await_deal + 有操作历史 → processing, 共更新 {updated} 条", flush=True)

    print("[forwards] 回填 display_status 完成", flush=True)


def backwards(apps, schema_editor):
    """回滚：将 display_status 全部重置为与 status 的默认映射"""
    Risk = apps.get_model("risk", "Risk")

    print("[backwards] 开始回滚 display_status", flush=True)

    status_to_display = {
        "new": "new",
        "for_approve": "for_approve",
        "auto_process": "auto_process",
        "closed": "closed",
        "await_deal": "new",
    }
    for status_val, display_val in status_to_display.items():
        updated = (
            Risk.objects.filter(status=status_val)
            .exclude(display_status=display_val)
            .update(display_status=display_val)
        )
        print(f"[backwards] 映射 status={status_val} → display_status={display_val}, 更新 {updated} 条", flush=True)

    print("[backwards] 回滚 display_status 完成", flush=True)


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0043_add_risk_display_status"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
