# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0044_backfill_display_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="risk",
            name="has_report",
            field=models.BooleanField(
                default=False,
                db_index=True,
                verbose_name="是否已生成报告",
                help_text="任何流程为该风险生成报告后置为 True",
            ),
        ),
    ]
