# -*- coding: utf-8 -*-
"""
场景隔离 Phase 2：为 Risk、ProcessApplication、RiskRule 新增 scene_id 字段
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0043_add_risk_display_status"),
        ("risk", "0044_backfill_display_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="risk",
            name="scene_id",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text="风险所属的审计场景，通过策略间接关联，初期允许为空",
                null=True,
                verbose_name="所属场景ID",
            ),
        ),
        migrations.AddField(
            model_name="processapplication",
            name="scene_id",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text="处理套餐所属的审计场景，初期允许为空，存量数据迁移后改为必填",
                null=True,
                verbose_name="所属场景ID",
            ),
        ),
        migrations.AddField(
            model_name="riskrule",
            name="scene_id",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text="处理规则所属的审计场景，初期允许为空，存量数据迁移后改为必填",
                null=True,
                verbose_name="所属场景ID",
            ),
        ),
    ]
