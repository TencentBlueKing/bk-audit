# -*- coding: utf-8 -*-
"""
场景隔离重构：移除 NoticeGroup 的 scene_id 字段，改为通过 ResourceBinding 关联
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notice", "0008_add_scene_id"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="noticegroup",
            name="scene_id",
        ),
    ]
