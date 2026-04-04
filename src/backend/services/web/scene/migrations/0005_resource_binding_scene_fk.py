# -*- coding: utf-8 -*-
"""
将 ResourceBindingScene.scene_id (IntegerField) 改为 scene (ForeignKey) 外键关联。
由于 Django ForeignKey 字段名为 scene，数据库列名仍为 scene_id，数据无需迁移。
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scene", "0004_resource_binding_refactor"),
    ]

    operations = [
        # 1. 先移除旧的 unique_together（引用旧字段名 scene_id）
        migrations.AlterUniqueTogether(
            name="resourcebindingscene",
            unique_together=set(),
        ),
        # 2. 重命名字段：scene_id -> scene（数据库列名不变，仍为 scene_id）
        migrations.RenameField(
            model_name="resourcebindingscene",
            old_name="scene_id",
            new_name="scene",
        ),
        # 3. 将字段类型从 IntegerField 改为 ForeignKey
        migrations.AlterField(
            model_name="resourcebindingscene",
            name="scene",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="scene.scene",
                verbose_name="场景",
            ),
        ),
        # 4. 添加新的 unique_together（引用新字段名 scene）
        migrations.AlterUniqueTogether(
            name="resourcebindingscene",
            unique_together={("binding", "scene")},
        ),
    ]
