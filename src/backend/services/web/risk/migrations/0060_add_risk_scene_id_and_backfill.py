# -*- coding: utf-8 -*-
"""
场景隔离重构：将 Risk 的场景归属改为 Risk.scene_id 字段。

1. 新增 Risk.scene_id 列。
2. 一次性回填存量 Risk.scene_id=NULL：
   - 使用策略场景绑定 ResourceBinding(STRATEGY) -> scene_id 进行回填。
"""

from django.db import migrations, models
from django.utils.translation import gettext_lazy


def _build_strategy_scene_map(apps):
    """策略场景绑定 ResourceBinding(STRATEGY) -> scene_id"""
    ResourceBindingScene = apps.get_model("scene", "ResourceBindingScene")
    result = {}
    for strategy_id, scene_id in ResourceBindingScene.objects.filter(
        scene__is_deleted=False,
        binding__resource_type="strategy",
    ).values_list("binding__resource_id", "scene_id"):
        result.setdefault(str(strategy_id), scene_id)
    return result


def forwards(apps, schema_editor):
    Risk = apps.get_model("risk", "Risk")

    print("[forwards] 开始回填 Risk.scene_id（源自策略绑定）", flush=True)

    strategy_scene_map = _build_strategy_scene_map(apps)

    print(
        f"[forwards] 来源规模：策略绑定={len(strategy_scene_map)}",
        flush=True,
    )

    rows = Risk.objects.filter(scene_id__isnull=True, strategy_id__isnull=False).values_list("risk_id", "strategy_id")

    to_update = []
    from_strategy, skipped = 0, 0
    for risk_id, strategy_id in rows:
        scene_id = strategy_scene_map.get(str(strategy_id))
        if scene_id is None:
            skipped += 1
            continue
        from_strategy += 1
        to_update.append((risk_id, scene_id))

    if to_update:
        objs = [Risk(risk_id=rid, scene_id=sid) for rid, sid in to_update]
        Risk.objects.bulk_update(objs, ["scene_id"], batch_size=2000)

    print(
        f"[forwards] 回填完成：更新={len(to_update)} " f"(策略绑定={from_strategy}), " f"无法判定跳过={skipped}",
        flush=True,
    )
    if skipped:
        print(
            f"[forwards][WARN] {skipped} 条风险未能从策略绑定判定场景，保持 scene_id=NULL，" "请检查其策略配置或 ResourceBinding(STRATEGY) 是否缺失",
            flush=True,
        )


def backwards(apps, schema_editor):
    """回滚：清空回填数据，恢复 scene_id 全部为空（列结构由 migrations.AddField 自动反向移除）"""
    Risk = apps.get_model("risk", "Risk")

    print("[backwards] 开始回滚 Risk.scene_id 回填数据", flush=True)
    reset = Risk.objects.filter(scene_id__isnull=False).update(scene_id=None)
    print(f"[backwards] 重置 {reset} 条 Risk.scene_id = NULL", flush=True)


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0059_add_multi_rule_fields"),
        ("scene", "0014_scene_permission_application"),
        ("strategy_v2", "0027_migrate_rules_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="risk",
            name="scene_id",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text=gettext_lazy("风险归属场景"),
                null=True,
                verbose_name=gettext_lazy("Scene ID"),
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
