# -*- coding: utf-8 -*-
"""
数据迁移：为存量 Risk 建立 ResourceBinding(RISK) + ResourceBindingScene 记录。

背景：
- 本项目历史上 Risk 的场景归属通过 `strategy_id → ResourceBinding(STRATEGY) → ResourceBindingScene`路径反查得到。
- 新特性引入全局策略后，Risk 的场景归属变为运行时决定（DispatchRule.target_scene_id），策略侧的 binding 不再能唯一表达"这条 Risk 属于哪个场景"。
- 决策：Risk 使用 ResourceBinding 单轨制记录自身场景归属

本迁移要做的：
- 遍历存量 Risk，通过其 strategy_id 查到该策略绑定的 scene_id
- 为每条 Risk 创建 ResourceBinding(resource_type=risk) + ResourceBindingScene 记录（幂等）
- 找不到 scene_id 的孤儿 Risk（策略已删/无绑定）跳过，保留 NULL 场景归属

风险的场景归属通过 scene.ResourceBinding(resource_type=RISK) + ResourceBindingScene 建立，写入路径按策略类型分散到不同节点
- 场景策略：create_risk 创建 Risk 后立即写（scene_id 来自 strategy 的 ResourceBindingScene）
- 全局策略 direct：分派规则匹配、dispatch_rule 写回后写（scene_id 来自 DispatchRule.target_scene）
- 全局策略 after_confirm：confirmer 确认后写（PENDING_CONFIRM 阶段不建 binding）

"""

from django.db import migrations

# 分批处理，避免一次性加载/更新过多数据导致数据库压力过大或内存溢出
BATCH_SIZE = 5000
# resource_type / binding_type 直接使用字符串常量，避免 apps.get_model 无法拿到 TextChoices
RESOURCE_TYPE_RISK = "risk"
RESOURCE_TYPE_STRATEGY = "strategy"
BINDING_TYPE_SCENE = "scene_binding"


def _iter_batches(iterable, size):
    """按 size 切片迭代 list，避免一次性构造巨型 IN 列表。"""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


def forwards(apps, schema_editor):
    """为存量 Risk 反查 strategy 场景并批量补建 RISK 绑定。"""
    Risk = apps.get_model("risk", "Risk")
    ResourceBinding = apps.get_model("scene", "ResourceBinding")
    ResourceBindingScene = apps.get_model("scene", "ResourceBindingScene")

    print("[forwards] 开始为存量 Risk 建立 RISK 场景绑定", flush=True)

    # 1. 一次性拉取 strategy_id -> scene_id 映射
    strategy_scene_map = {
        str(strategy_id): scene_id
        for strategy_id, scene_id in ResourceBindingScene.objects.filter(
            binding__resource_type=RESOURCE_TYPE_STRATEGY,
            binding__binding_type=BINDING_TYPE_SCENE,
            scene__is_deleted=False,
        ).values_list("binding__resource_id", "scene_id")
    }
    print(f"[forwards] 加载 strategy->scene 映射 {len(strategy_scene_map)} 条", flush=True)

    if not strategy_scene_map:
        print("[forwards] 无策略场景绑定，跳过 Risk 绑定回填", flush=True)
        return

    # 2. 提前查出已存在的 RISK 绑定，避免重复建
    existing_risk_ids = set(
        ResourceBinding.objects.filter(resource_type=RESOURCE_TYPE_RISK).values_list(
            "resource_id", flat=True
        )
    )
    print(f"[forwards] 已存在 RISK 绑定 {len(existing_risk_ids)} 条，将跳过", flush=True)

    # 3. 扫描 Risk，按 scene_id 分组待建列表,仅拉必要字段
    to_create_by_scene = {}  # scene_id -> [risk_id, ...]
    scanned = 0
    skipped_no_strategy_binding = 0
    for risk_id, strategy_id in (
        Risk.objects.exclude(strategy_id__isnull=True)
        .values_list("risk_id", "strategy_id")
        .iterator(chunk_size=BATCH_SIZE)
    ):
        scanned += 1
        risk_id_str = str(risk_id)
        if risk_id_str in existing_risk_ids:
            continue
        scene_id = strategy_scene_map.get(str(strategy_id))
        if scene_id is None:
            skipped_no_strategy_binding += 1
            continue
        to_create_by_scene.setdefault(scene_id, []).append(risk_id_str)

    total_to_create = sum(len(v) for v in to_create_by_scene.values())
    print(
        f"[forwards] 扫描 Risk {scanned} 条；待建绑定 {total_to_create} 条；"
        f"孤儿 Risk（策略无场景绑定）跳过 {skipped_no_strategy_binding} 条",
        flush=True,
    )

    if total_to_create == 0:
        print("[forwards] 无需回填", flush=True)
        return

    # 4. 分批 bulk_create：先建 ResourceBinding，再取回主键建 ResourceBindingScene
    created_binding_total = 0
    created_scene_total = 0

    for scene_id, risk_id_list in to_create_by_scene.items():
        for batch in _iter_batches(risk_id_list, BATCH_SIZE):
            # 4.1 建 binding
            ResourceBinding.objects.bulk_create(
                [
                    ResourceBinding(
                        resource_type=RESOURCE_TYPE_RISK,
                        resource_id=rid,
                        binding_type=BINDING_TYPE_SCENE,
                    )
                    for rid in batch
                ],
                batch_size=BATCH_SIZE,
                ignore_conflicts=True,
            )
            # 4.2 拉回本批的 binding id
            binding_pairs = list(
                ResourceBinding.objects.filter(
                    resource_type=RESOURCE_TYPE_RISK,
                    resource_id__in=batch,
                ).values_list("id", "resource_id")
            )
            created_binding_total += len(binding_pairs)

            # 4.3 建 ResourceBindingScene；需要先过滤已存在的
            existing_scene_binding_ids = set(
                ResourceBindingScene.objects.filter(
                    binding_id__in=[bid for bid, _ in binding_pairs],
                    scene_id=scene_id,
                ).values_list("binding_id", flat=True)
            )
            scene_rows = [
                ResourceBindingScene(binding_id=bid, scene_id=scene_id)
                for bid, _ in binding_pairs
                if bid not in existing_scene_binding_ids
            ]
            if scene_rows:
                ResourceBindingScene.objects.bulk_create(
                    scene_rows,
                    batch_size=BATCH_SIZE,
                    ignore_conflicts=True,
                )
                created_scene_total += len(scene_rows)

        print(
            f"[forwards] scene_id={scene_id} 处理完成，累计 binding={created_binding_total}, "
            f"scene_link={created_scene_total}",
            flush=True,
        )

    print(
        f"[forwards] 数据迁移完成：新建/复用 RISK 绑定 {created_binding_total} 条，"
        f"新增场景关联 {created_scene_total} 条",
        flush=True,
    )


def backwards(apps, schema_editor):
    """
    回滚：删除所有 RISK 类型的 ResourceBinding。
    """
    ResourceBinding = apps.get_model("scene", "ResourceBinding")

    print("[backwards] 警告：将删除所有 resource_type=risk 的 ResourceBinding 记录", flush=True)
    # ResourceBindingScene / ResourceBindingSystem 均通过 CASCADE 级联清理
    deleted, _ = ResourceBinding.objects.filter(resource_type=RESOURCE_TYPE_RISK).delete()
    print(f"[backwards] 已删除 {deleted} 条 RISK binding 相关记录（含级联）", flush=True)


class Migration(migrations.Migration):
    """
    存量 Risk 场景绑定回填。
    """

    dependencies = [
        ("risk", "0059_add_multi_rule_fields"),
        ("strategy_v2", "0027_migrate_rules_data"),
        ("scene", "0013_alter_resourcebinding_visibility_type"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
