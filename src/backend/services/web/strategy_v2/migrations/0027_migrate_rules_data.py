# -*- coding: utf-8 -*-
"""
数据迁移：将现有单规则策略迁移到 StrategyRule 表，并回填 Risk/ManualEvent 元信息。

迁移内容：
1. 为每个 rule 策略生成 1 条 StrategyRule（幂等，跳过已迁移策略）
2. 回填 Risk 表的元信息字段（strategy_rule, risk_level, risk_hazard, risk_guidance, confirmer）
3. 回填 ManualEvent 表的元信息字段（strategy_rule, risk_level, risk_hazard, risk_guidance）
4. 更新 Strategy.rule_order

注意：
- 当前迁移只处理场景策略（scene_binding），尚未有全局策略
- processor_groups/notice_groups 迁移到 StrategyRule.processor/follower
- confirmer 为空列表（无全局策略）
- dispatch_rule 为 null（无全局策略）

【不可逆声明】本数据迁移为不可逆迁移。回滚（backwards）不做任何数据清理：
无法可靠识别"仍保持迁移原样"的记录（StrategyRule.created_by 在用户编辑后不变），
按 created_by 回滚会误删用户已编辑的规则、清空 rule_order 并留下 Risk/ManualEvent
的 strategy_rule 悬空引用。如需回退请走人工数据订正流程。
"""

from django.db import migrations

# 数据迁移创建者标识，backwards 判定是否为本次迁移写入
MIGRATION_CREATED_BY = "migration_0027"


def forwards(apps, schema_editor):
    """正向迁移"""
    Strategy = apps.get_model("strategy_v2", "Strategy")
    StrategyRule = apps.get_model("strategy_v2", "StrategyRule")
    Risk = apps.get_model("risk", "Risk")
    ManualEvent = apps.get_model("risk", "ManualEvent")

    print("[forwards] 开始数据迁移", flush=True)

    # -------- 第一步：为每个 rule 策略生成 StrategyRule --------
    print("[forwards] 第一步：迁移策略规则", flush=True)

    # 只处理 rule 类型的策略（排除已软删策略，避免为其创建孤儿规则行）
    rule_strategies = Strategy.objects.filter(strategy_type="rule", is_deleted=False)
    strategy_count = rule_strategies.count()
    print(f"[forwards] 共有 {strategy_count} 个 rule 策略需要迁移", flush=True)

    # strategy_id -> (strategy_rule_id, risk_level, risk_hazard, risk_guidance)
    strategy_rule_map = {}

    for strategy in rule_strategies:
        # 幂等：已有规则的策略跳过
        existing_rule = StrategyRule.objects.filter(strategy=strategy).first()
        if existing_rule:
            if not (strategy.rule_order or []):
                active_rule_ids = list(StrategyRule.objects.filter(strategy=strategy).values_list("rule_id", flat=True))
                Strategy.objects.filter(pk=strategy.strategy_id).update(rule_order=active_rule_ids)
            strategy_rule_map[strategy.strategy_id] = (
                existing_rule.rule_id,
                strategy.risk_level,
                strategy.risk_hazard,
                strategy.risk_guidance,
            )
            print(
                f"[forwards] 策略 {strategy.strategy_id} 已有规则 {existing_rule.rule_id}，跳过创建",
                flush=True,
            )
            continue

        # configs 必须为 dict（含 select/where/having）；非 dict（历史遗留的 list 事件字段映射等）
        # 视为格式异常，跳过迁移并告警，留待人工确认后重新配置规则
        if not isinstance(strategy.configs, dict):
            print(
                f"[forwards] 策略 {strategy.strategy_id} configs 为非 dict "
                f"（{type(strategy.configs).__name__}），跳过迁移，请人工确认该策略配置",
                flush=True,
            )
            continue
        # 从 configs 中提取 where 和 having
        configs = strategy.configs or {}
        where_conditions = configs.get("where")
        having_conditions = configs.get("having")

        # 构建 conditions：使用与 model 默认值一致的结构
        conditions = {
            "where": where_conditions if where_conditions else None,
            "having": having_conditions if having_conditions else None,
        }

        # 生成规则名称（截断至64字符）
        rule_name = f"{strategy.strategy_name} 规则1"
        if len(rule_name) > 64:
            rule_name = rule_name[:64]

        # 创建 StrategyRule
        strategy_rule = StrategyRule.objects.create(
            strategy=strategy,
            rule_name=rule_name,
            conditions=conditions,
            risk_title=strategy.risk_title,
            risk_level=strategy.risk_level,
            risk_hazard=strategy.risk_hazard,
            risk_guidance=strategy.risk_guidance,
            processor=strategy.processor_groups or [],
            follower=strategy.notice_groups or [],
            created_by=MIGRATION_CREATED_BY,
            updated_by=MIGRATION_CREATED_BY,
        )

        strategy_rule_map[strategy.strategy_id] = (
            strategy_rule.rule_id,
            strategy.risk_level,
            strategy.risk_hazard,
            strategy.risk_guidance,
        )

        # 更新 Strategy.rule_order
        Strategy.objects.filter(pk=strategy.strategy_id).update(rule_order=[strategy_rule.rule_id])

        print(
            f"[forwards] 策略 {strategy.strategy_id} 迁移完成，生成规则 {strategy_rule.rule_id}",
            flush=True,
        )

    print(f"[forwards] 第一步完成，共处理 {len(strategy_rule_map)} 个策略", flush=True)

    # -------- 第二步：按策略分组批量回填 Risk 表 --------
    print("[forwards] 第二步：分组回填 Risk 表", flush=True)

    total_updated = 0
    for strategy_id, (rule_id, risk_level, risk_hazard, risk_guidance) in strategy_rule_map.items():
        updated = Risk.objects.filter(strategy_id=strategy_id, strategy_rule__isnull=True,).update(
            strategy_rule_id=rule_id,
            risk_level=risk_level,
            risk_hazard=risk_hazard,
            risk_guidance=risk_guidance,
            # 无全局策略，confirmer 保持空列表
            confirmer=[],
        )
        if updated:
            total_updated += updated
            print(f"[forwards] Risk strategy={strategy_id} 回填 {updated} 条", flush=True)

    print(f"[forwards] 第二步完成，共回填 {total_updated} 条风险", flush=True)

    # -------- 第三步：按策略分组批量回填 ManualEvent 表 --------
    print("[forwards] 第三步：分组回填 ManualEvent 表", flush=True)

    total_me_updated = 0
    for strategy_id, (rule_id, risk_level, risk_hazard, risk_guidance) in strategy_rule_map.items():
        updated = ManualEvent.objects.filter(strategy_id=strategy_id, strategy_rule__isnull=True,).update(
            strategy_rule_id=rule_id,
            risk_level=risk_level,
            risk_hazard=risk_hazard,
            risk_guidance=risk_guidance,
        )
        if updated:
            total_me_updated += updated
            print(f"[forwards] ManualEvent strategy={strategy_id} 回填 {updated} 条", flush=True)

    print(f"[forwards] 第三步完成，共回填 {total_me_updated} 条手工事件", flush=True)

    print("[forwards] 数据迁移完成", flush=True)


def backwards(apps, schema_editor):
    """
    回滚迁移：本迁移声明为【不可逆】。
    """
    print(
        "无法可靠识别迁移原样记录（created_by 在编辑后不变），声明为不可逆，回滚不删除任何数据。",
        flush=True,
    )


class Migration(migrations.Migration):
    """
    数据迁移：将现有单规则策略迁移到 StrategyRule 表

    当前状态：
    - 所有策略都是场景策略（scene_binding），无全局策略（platform_binding）
    - processor_groups/notice_groups 迁移到 StrategyRule
    - confirmer 为空（无全局策略）
    """

    atomic = False

    dependencies = [
        ("strategy_v2", "0026_add_multi_rule_support"),
        ("risk", "0059_add_multi_rule_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
