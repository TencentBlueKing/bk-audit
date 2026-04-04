# -*- coding: utf-8 -*-
"""
场景隔离重构：移除 Risk、ProcessApplication、RiskRule 的 scene_id 字段，改为通过 ResourceBinding 关联
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0045_add_scene_id"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="risk",
            name="scene_id",
        ),
        migrations.RemoveField(
            model_name="processapplication",
            name="scene_id",
        ),
        migrations.RemoveField(
            model_name="riskrule",
            name="scene_id",
        ),
    ]
