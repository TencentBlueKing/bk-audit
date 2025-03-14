# Generated by Django 4.2.19 on 2025-03-20 12:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vision', '0003_auto_20250307_1329'),
    ]

    operations = [
        migrations.AddField(
            model_name='visionpanel',
            name='handler',
            field=models.CharField(default='CommonVisionHandler', max_length=255, verbose_name='处理器'),
        ),
        migrations.AddField(
            model_name='visionpanel',
            name='vision_id',
            field=models.CharField(max_length=255, null=True, verbose_name='视图ID'),
        ),
    ]
