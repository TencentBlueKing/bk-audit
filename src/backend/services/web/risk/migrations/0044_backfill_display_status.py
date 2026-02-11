from django.db import migrations
from django.db.models import Exists, OuterRef

# 分批大小，避免单次 update 影响行过多导致锁表
BATCH_SIZE = 5000


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
        print(
            f"[_batch_update] 本批更新 {count} 条, 累计更新 {total_updated} 条, update_kwargs={update_kwargs}",
            flush=True,
        )
    print(f"[_batch_update] 完成, 共更新 {total_updated} 条, update_kwargs={update_kwargs}", flush=True)
    return total_updated


def forwards(apps, schema_editor):
    """根据现有 status 回填 display_status"""
    Risk = apps.get_model("risk", "Risk")
    TicketNode = apps.get_model("risk", "TicketNode")

    print("[forwards] 开始回填 display_status", flush=True)

    # 1. 非 await_deal 状态：直接映射（数据量少，直接更新）
    simple_mapping = {
        "new": "new",
        "for_approve": "for_approve",
        "auto_process": "auto_process",
        "closed": "closed",
    }
    for status_val, display_val in simple_mapping.items():
        updated = (
            Risk.objects.filter(status=status_val)
            .exclude(display_status=display_val)
            .update(display_status=display_val)
        )
        print(f"[forwards] 映射 status={status_val} → display_status={display_val}, 更新 {updated} 条", flush=True)

    # 2. await_deal 状态：使用 Exists 判断是否有非 NewRisk 的操作历史，一步到位
    #    EXISTS 子查询在 MySQL 中会使用 semi-join 优化，远优于 NOT IN (subquery)
    has_non_new_risk_action = Exists(TicketNode.objects.filter(risk_id=OuterRef("risk_id")).exclude(action="NewRisk"))

    # 2a. 有非 NewRisk 操作历史 → processing（处理中）
    qs_processing = (
        Risk.objects.filter(status="await_deal").exclude(display_status="processing").filter(has_non_new_risk_action)
    )
    updated = _batch_update(Risk, qs_processing, display_status="processing")
    print(f"[forwards] await_deal + 有操作历史 → processing, 更新 {updated} 条", flush=True)

    # 2b. 仅有 NewRisk（或无操作历史） → await_deal（待处理）
    qs_await = (
        Risk.objects.filter(status="await_deal").exclude(display_status="await_deal").exclude(has_non_new_risk_action)
    )
    updated = _batch_update(Risk, qs_await, display_status="await_deal")
    print(f"[forwards] await_deal + 仅有 NewRisk → await_deal(待处理), 更新 {updated} 条", flush=True)

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
