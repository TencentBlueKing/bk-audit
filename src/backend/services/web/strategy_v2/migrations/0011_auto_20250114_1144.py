# Generated by Django 3.2.23 on 2025-01-14 03:44

from django.db import migrations, models

import core.models


class Migration(migrations.Migration):

    dependencies = [
        ('strategy_v2', '0010_strategy_sql'),
    ]

    operations = [
        migrations.AlterField(
            model_name='linktable',
            name='name',
            field=models.CharField(db_index=True, max_length=50, verbose_name='Link Table Name'),
        ),
        migrations.AlterField(
            model_name='linktable',
            name='uid',
            field=core.models.UUIDField(
                db_index=True,
                default=core.models.UUIDField.get_default_value,
                max_length=64,
                verbose_name='Link Table UID',
            ),
        ),
        migrations.AlterField(
            model_name='strategy',
            name='event_evidence_field_configs',
            field=models.JSONField(blank=True, default=list, null=True, verbose_name='Event Evidence Configs'),
        ),
    ]