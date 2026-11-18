# -*- coding: utf-8 -*-
"""
风险列表慢查询修复：
添加 scene_id 联合索引，解决按场景过滤风险列表时的慢查询问题。
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('risk', '0062_alter_nl2riskfilterlog_risk_view_type_and_backfill'),
    ]

    operations = [
        # 索引 1：覆盖基础场景过滤（scene_id + is_deleted + event_time）
        # 适用于：个人视图/场景视图的基础列表查询
        migrations.AddIndex(
            model_name='risk',
            index=models.Index(
                fields=['scene_id', 'is_deleted', 'event_time'],
                name='idx_risk_scene_isdel_time',
            ),
        ),
        migrations.AddIndex(
            model_name='risk',
            index=models.Index(
                fields=['scene_id', 'display_status', 'event_time'],
                name='idx_risk_scene_status_time',
            ),
        ),
        migrations.AddIndex(
            model_name='risk',
            index=models.Index(
                fields=['scene_id', 'is_deleted', 'display_status', 'event_time'],
                name='idx_risk_scene_del_status_time',
            ),
        ),
    ]
