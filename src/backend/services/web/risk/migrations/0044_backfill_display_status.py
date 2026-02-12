from django.db import migrations

# 分批大小，避免单次 update 影响行过多导致锁表
BATCH_SIZE = 5000


def _batch_update_by_status(model, status_val, display_val):
    """
    分批更新：按 status 筛选并设置 display_status。
    利用 status 上的索引直接定位，每批用 pk 范围游标推进，避免重复全表扫描。
    """
    total_updated = 0
    last_pk = ""
    while True:
        batch_pks = list(
            model.objects.filter(status=status_val, pk__gt=last_pk)
            .exclude(display_status=display_val)
            .order_by("pk")
            .values_list("pk", flat=True)[:BATCH_SIZE]
        )
        if not batch_pks:
            break
        count = model.objects.filter(pk__in=batch_pks).update(display_status=display_val)
        total_updated += count
        last_pk = batch_pks[-1]
        print(
            f"[_batch_update_by_status] 本批更新 {count} 条, 累计 {total_updated} 条, "
            f"status={status_val} → display_status={display_val}",
            flush=True,
        )
    print(
        f"[_batch_update_by_status] 完成, 共更新 {total_updated} 条, " f"status={status_val} → display_status={display_val}",
        flush=True,
    )
    return total_updated


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
        updated = _batch_update_by_status(Risk, status_val, display_val)
        print(f"[forwards] 映射 status={status_val} → display_status={display_val}, 更新 {updated} 条", flush=True)

    # -------- 第二步：修正少量 await_deal 中有操作历史的 → processing --------
    # 先从 TicketNode 取出所有有非 NewRisk 操作的 risk_id（通常很少）
    processing_risk_ids = list(
        TicketNode.objects.exclude(action="NewRisk").values_list("risk_id", flat=True).distinct()
    )
    print(f"[forwards] 有非 NewRisk 操作历史的 risk_id 数量: {len(processing_risk_ids)}", flush=True)

    if processing_risk_ids:
        # 分批更新这些 risk_id 对应的 await_deal 记录为 processing
        total_updated = 0
        for i in range(0, len(processing_risk_ids), BATCH_SIZE):
            batch_ids = processing_risk_ids[i : i + BATCH_SIZE]
            count = (
                Risk.objects.filter(status="await_deal", risk_id__in=batch_ids)
                .exclude(display_status="processing")
                .update(display_status="processing")
            )
            total_updated += count
            print(f"[forwards] 修正 processing 本批 {count} 条, 累计 {total_updated} 条", flush=True)
        print(f"[forwards] await_deal + 有操作历史 → processing, 共更新 {total_updated} 条", flush=True)
    else:
        print("[forwards] 无需修正 processing（没有非 NewRisk 操作历史）", flush=True)

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
        "await_deal": "processing",
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
