# Generated by Django 4.2.19 on 2025-06-03 01:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('query', '0003_alter_logexporttask_task_end_time_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='logexporttask',
            name='alert_sented',
            field=models.BooleanField(default=False, verbose_name='是否已发送告警'),
        ),
    ]
