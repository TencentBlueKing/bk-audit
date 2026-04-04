# -*- coding: utf-8 -*-
"""
场景隔离重构：移除 Strategy、LinkTable 的 scene_id 字段，改为通过 ResourceBinding 关联
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("strategy_v2", "0024_add_scene_id"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="strategy",
            name="scene_id",
        ),
        migrations.RemoveField(
            model_name="linktable",
            name="scene_id",
        ),
    ]
