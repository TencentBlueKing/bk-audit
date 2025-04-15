# Generated by Django 3.2.18 on 2023-09-19 08:22

from django.db import migrations, models

import services.web.risk.models


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0016_update_risk_event_end_time"),
    ]

    operations = [
        migrations.AlterField(
            model_name="risk",
            name="risk_id",
            field=models.CharField(
                default=services.web.risk.models.generate_risk_id,
                max_length=255,
                primary_key=True,
                serialize=False,
                verbose_name="Risk ID",
            ),
        ),
    ]
