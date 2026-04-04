# -*- coding: utf-8 -*-
"""
场景隔离 Phase 2：为 NoticeGroup 新增 scene_id 字段
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notice", "0007_alter_noticelogv2_relate_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="noticegroup",
            name="scene_id",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text="通知组所属的审计场景，初期允许为空，存量数据迁移后改为必填",
                null=True,
                verbose_name="所属场景ID",
            ),
        ),
    ]
