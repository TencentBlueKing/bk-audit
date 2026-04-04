# -*- coding: utf-8 -*-
"""
场景隔离 Phase 2：为 Strategy 和 LinkTable 新增 scene_id 字段
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("strategy_v2", "0023_strategy_report_auto_render"),
    ]

    operations = [
        migrations.AddField(
            model_name="strategy",
            name="scene_id",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text="策略所属的审计场景，初期允许为空，存量数据迁移后改为必填",
                null=True,
                verbose_name="所属场景ID",
            ),
        ),
        migrations.AddField(
            model_name="linktable",
            name="scene_id",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text="联表所属的审计场景，初期允许为空，存量数据迁移后改为必填",
                null=True,
                verbose_name="所属场景ID",
            ),
        ),
    ]
