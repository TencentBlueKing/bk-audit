# -*- coding: utf-8 -*-
"""
场景隔离重构：将 Risk 的场景归属从 ResourceBinding(RISK) 物化投影改为 Risk.scene_id 字段。

1. 新增 Risk.scene_id 列。
2. 一次性回填存量 Risk.scene_id=NULL：
   - 全局策略风险（有 dispatch_rule）：优先用 DispatchRule.target_scene_id（含待确认未建 RISK 绑定的情况）；
   - 其余：用本重构替换掉的旧表示 ResourceBinding(RISK) -> ResourceBindingScene.scene_id；
   - 兜底：策略场景绑定 ResourceBinding(STRATEGY) -> scene_id。
   三种来源指向同一场景，优先取分派规则以保证待确认风险也能回填。
"""

from django.db import migrations, models
from django.utils.translation import gettext_lazy


def _build_risk_binding_scene_map(apps):
    """历史 ResourceBinding(RISK) -> 首个 scene_id（本重构替换掉的旧场景表示）"""
    ResourceBinding = apps.get_model("scene", "ResourceBinding")
    ResourceBindingScene = apps.get_model("scene", "ResourceBindingScene")

    risk_bindings = list(ResourceBinding.objects.filter(resource_type="risk").values_list("resource_id", "id"))
    if not risk_bindings:
        return {}
    binding_ids = [b_id for (_, b_id) in risk_bindings]
    binding_scene_map = {}
    for binding_id, scene_id in ResourceBindingScene.objects.filter(
        scene__is_deleted=False,
        binding_id__in=binding_ids,
    ).values_list("binding_id", "scene_id"):
        # 取首个场景（正常情况下一个 RISK 绑定仅一个场景）
        binding_scene_map.setdefault(binding_id, scene_id)
    return {resource_id: binding_scene_map.get(binding_id) for resource_id, binding_id in risk_bindings}


def _build_dispatch_scene_map(apps):
    """DispatchRule.rule_id -> target_scene_id（全局策略风险场景来源，含待确认）

    使用 _base_manager 以包含已软删除的分派规则，与运行时 match_dispatch_rule /
    _apply_dispatch 的取场景逻辑保持一致（规则被删后已建单据的场景不应丢失）。
    """
    DispatchRule = apps.get_model("strategy_v2", "DispatchRule")
    return dict(DispatchRule._base_manager.values_list("rule_id", "target_scene_id"))


def _build_strategy_scene_map(apps):
    """策略场景绑定 ResourceBinding(STRATEGY) -> scene_id（兜底：场景策略风险无 RISK 绑定时）"""
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

    print("[forwards] 开始回填 Risk.scene_id（源自 ResourceBinding / DispatchRule / 策略绑定）", flush=True)

    risk_to_scene = _build_risk_binding_scene_map(apps)
    dispatch_scene_map = _build_dispatch_scene_map(apps)
    strategy_scene_map = _build_strategy_scene_map(apps)

    print(
        f"[forwards] 来源规模: RISK绑定={len(risk_to_scene)}, "
        f"分派规则={len(dispatch_scene_map)}, 策略绑定={len(strategy_scene_map)}",
        flush=True,
    )

    rows = Risk.objects.filter(scene_id__isnull=True).values_list("risk_id", "dispatch_rule_id", "strategy_id")

    to_update = []
    from_dispatch, from_binding, from_strategy, skipped = 0, 0, 0, 0
    for risk_id, dispatch_rule_id, strategy_id in rows:
        scene_id = None
        source = None
        if dispatch_rule_id and dispatch_rule_id in dispatch_scene_map:
            scene_id = dispatch_scene_map[dispatch_rule_id]
            source = "dispatch"
        if scene_id is None and risk_id in risk_to_scene:
            scene_id = risk_to_scene[risk_id]
            source = "binding"
        if scene_id is None:
            scene_id = strategy_scene_map.get(str(strategy_id))
            source = "strategy"
        if scene_id is None:
            skipped += 1
            continue
        if source == "dispatch":
            from_dispatch += 1
        elif source == "binding":
            from_binding += 1
        else:
            from_strategy += 1
        to_update.append((risk_id, scene_id))

    if to_update:
        objs = [Risk(risk_id=rid, scene_id=sid) for rid, sid in to_update]
        Risk.objects.bulk_update(objs, ["scene_id"], batch_size=2000)

    print(
        f"[forwards] 回填完成: 更新={len(to_update)} "
        f"(分派规则={from_dispatch}, RISK绑定={from_binding}, 策略绑定={from_strategy}), "
        f"无法判定跳过={skipped}",
        flush=True,
    )
    if skipped:
        print(
            f"[forwards][WARN] {skipped} 条风险未能从任何来源判定场景，保持 scene_id=NULL，"
            "请检查其策略/分派规则配置或历史 ResourceBinding(RISK) 是否缺失",
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
                help_text=gettext_lazy("风险归属场景（固化到风险单，作为列表/权限/IAM/Provider 的唯一场景来源）"),
                null=True,
                verbose_name=gettext_lazy("Scene ID"),
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
