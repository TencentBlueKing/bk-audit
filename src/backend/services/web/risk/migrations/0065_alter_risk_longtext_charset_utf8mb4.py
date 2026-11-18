# -*- coding: utf-8 -*-
"""
风险自由文本列改为 utf8mb4。

MySQL 的 utf8 只支持 3 字节。风险描述以 emoji 开头时，非严格模式会从该字符起
把后续正文截掉，只留下类似 "### " 的前缀。JSON 列本身是 utf8mb4，原文仍在 event_data 里。

只 MODIFY 这些 LONGTEXT，不 CONVERT 整表，避免 varchar(255) 主键在 767 字节索引上限下失败。
历史被截断的描述不在迁移里回填，避免扫全表；量不大，后续按 risk_id 用 SQL 单独修。
该变更不可逆，回退迁移时保留 utf8mb4 列定义，避免新写入的 emoji 数据被截断。
"""

from django.db import migrations


def _modify_table(table, columns):
    """在一次 ALTER 中修改同表的全部长文本列，减少重建和锁表次数。"""
    modify_sql = ", ".join(
        f"MODIFY COLUMN `{column}` LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci "
        f"{'NULL' if null else 'NOT NULL'}"
        for column, null in columns
    )
    return migrations.RunSQL(
        sql=f"ALTER TABLE `{table}` {modify_sql};",
        reverse_sql=migrations.RunSQL.noop,
    )


TABLE_COLUMNS = (
    (
        "risk_risk",
        (
            ("event_content", True),
            ("event_evidence", True),
            ("title", True),
            ("risk_hazard", True),
            ("risk_guidance", True),
        ),
    ),
    (
        "risk_manualevent",
        (
            ("event_content", True),
            ("event_evidence", True),
            ("title", True),
            ("risk_hazard", True),
            ("risk_guidance", True),
        ),
    ),
    ("risk_riskexperience", (("content", False),)),
    ("risk_riskreport", (("content", False),)),
)


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0064_risk_notice_group_snapshot"),
    ]

    operations = [_modify_table(table, columns) for table, columns in TABLE_COLUMNS]
