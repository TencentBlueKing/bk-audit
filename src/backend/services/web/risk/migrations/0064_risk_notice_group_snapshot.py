# -*- coding: utf-8 -*-
"""
风险通知组快照：
Risk 新增 notice_group_snapshot 字段，风险生成时固化通知组完整信息
（组ID、名称、成员、通知方式、描述、角色），发送通知时优先按快照发送。
"""

from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0063_risk_idx_scene_del_status_time"),
    ]

    operations = [
        migrations.AddField(
            model_name="risk",
            name="notice_group_snapshot",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=_("关注人通知组完整信息快照，包含组ID、名称、成员、通知方式、描述"),
                null=True,
                verbose_name=_("Notice Group Snapshot"),
            ),
        ),
    ]
