# -*- coding: utf-8 -*-
"""
策略上的风险危害、处理指引改为 utf8mb4。

这两列会抄到风险单。列仍是 utf8 时，含 emoji 的模板在写入阶段就会被截断。
只改 LONGTEXT，不转换整表。同表字段合并为一次 ALTER，回退时保留 utf8mb4 列定义。
"""

from django.db import migrations


def _modify_table(table, columns):
    """在一次 ALTER 中修改同表的全部长文本列，减少重建和锁表次数。"""
    modify_sql = ", ".join(
        f"MODIFY COLUMN `{column}` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL" for column in columns
    )
    return migrations.RunSQL(
        sql=f"ALTER TABLE `{table}` {modify_sql};",
        reverse_sql=migrations.RunSQL.noop,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("strategy_v2", "0027_migrate_rules_data"),
    ]

    operations = [
        _modify_table("strategy_v2_strategy", ("risk_hazard", "risk_guidance")),
        _modify_table("strategy_v2_strategyrule", ("risk_hazard", "risk_guidance")),
    ]
