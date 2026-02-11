from django.db import migrations

# 分批大小，避免单次 update 影响行过多导致锁表
BATCH_SIZE = 2000


def _batch_update(model, queryset, **update_kwargs):
    """分批更新，每次处理 BATCH_SIZE 条记录"""
    total_updated = 0
    while True:
        batch_pks = list(queryset.values_list("pk", flat=True)[:BATCH_SIZE])
        if not batch_pks:
            break
        count = len(batch_pks)
        model.objects.filter(pk__in=batch_pks).update(**update_kwargs)
        total_updated += count
        print(f"[_batch_update] 本批更新 {count} 条, 累计更新 {total_updated} 条, update_kwargs={update_kwargs}", flush=True)
    print(f"[_batch_update] 完成, 共更新 {total_updated} 条, update_kwargs={update_kwargs}", flush=True)
    return total_updated


def forwards(apps, schema_editor):
    """根据现有 status 回填 display_status"""
    Risk = apps.get_model("risk", "Risk")
    TicketNode = apps.get_model("risk", "TicketNode")

    print("[forwards] 开始回填 display_status", flush=True)

    # 1. 批量默认映射：status → display_status
    status_to_display = {
        "new": "new",
        "for_approve": "for_approve",
        "auto_process": "auto_process",
        "closed": "closed",
        "await_deal": "processing",  # 默认映射为"处理中"
    }
    for status_val, display_val in status_to_display.items():
        print(f"[forwards] 映射 status={status_val} → display_status={display_val}", flush=True)
        _batch_update(
            Risk,
            Risk.objects.filter(status=status_val).exclude(display_status=display_val),
            display_status=display_val,
        )

    # 2. 特殊处理：仅有 NewRisk 操作历史的 await_deal → "待处理"
    #    使用子查询替代 Python set 操作，避免大数据量下的内存和 SQL IN 问题
    print("[forwards] 开始特殊处理: 仅有 NewRisk 操作历史的 await_deal → await_deal(待处理)", flush=True)
    await_risks = Risk.objects.filter(status="await_deal")
    has_other_actions = (
        TicketNode.objects.filter(risk_id__in=await_risks.values("risk_id")).exclude(action="NewRisk").values("risk_id")
    )
    pure_new_risks = await_risks.exclude(risk_id__in=has_other_actions)
    updated = _batch_update(Risk, pure_new_risks, display_status="await_deal")
    print(f"[forwards] 特殊处理完成, 共 {updated} 条 await_deal 风险回退为待处理", flush=True)

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
        print(f"[backwards] 映射 status={status_val} → display_status={display_val}", flush=True)
        _batch_update(
            Risk,
            Risk.objects.filter(status=status_val).exclude(display_status=display_val),
            display_status=display_val,
        )

    print("[backwards] 回滚 display_status 完成", flush=True)


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0043_add_risk_display_status"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
