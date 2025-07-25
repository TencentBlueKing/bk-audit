# Generated by Django 4.2.19 on 2025-07-06 15:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('strategy_v2', '0013_auto_20250307_1329'),
        ('risk', '0026_risk_created_at_risk_created_by_risk_updated_at_and_more'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='risk',
            index_together={
                ('risk_id', 'event_time'),
                ('risk_id', 'last_operate_time'),
                ('strategy', 'raw_event_id', 'status'),
                ('strategy', 'event_time'),
            },
        ),
    ]
