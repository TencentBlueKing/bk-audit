# Generated by Django 3.2.23 on 2024-12-19 13:07

import django.utils.timezone
from django.db import migrations, models

import core.models


class Migration(migrations.Migration):

    dependencies = [
        ("strategy_v2", "0008_alter_strategy_event_basic_field_configs"),
    ]

    operations = [
        migrations.CreateModel(
            name="LinkTableTag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                (
                    "created_by",
                    models.CharField(blank=True, default="", max_length=32, null=True, verbose_name="创建者"),
                ),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                (
                    "updated_by",
                    models.CharField(blank=True, default="", max_length=32, null=True, verbose_name="修改者"),
                ),
                ("link_table_uid", models.CharField(max_length=64, verbose_name="Link Table UID")),
                ("tag_id", models.BigIntegerField(verbose_name="Tag ID")),
            ],
            options={
                "verbose_name": "Link Table Tag",
                "verbose_name_plural": "Link Table Tag",
                "ordering": ["-id"],
            },
        ),
        migrations.AddField(
            model_name="strategy",
            name="link_table_uid",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="Link Table UID"),
        ),
        migrations.AddField(
            model_name="strategy",
            name="link_table_version",
            field=models.IntegerField(blank=True, null=True, verbose_name="Link Table Version"),
        ),
        migrations.AddField(
            model_name="strategy",
            name="strategy_type",
            field=models.CharField(
                choices=[("rule", "规则策略"), ("model", "模型策略")],
                default="model",
                max_length=16,
                verbose_name="Strategy Type",
            ),
        ),
        migrations.AlterField(
            model_name="strategy",
            name="control_id",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="Control ID"),
        ),
        migrations.AlterField(
            model_name="strategy",
            name="control_version",
            field=models.IntegerField(blank=True, null=True, verbose_name="Version"),
        ),
        migrations.CreateModel(
            name="LinkTable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                (
                    "created_by",
                    models.CharField(blank=True, default="", max_length=32, null=True, verbose_name="创建者"),
                ),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                (
                    "updated_by",
                    models.CharField(blank=True, default="", max_length=32, null=True, verbose_name="修改者"),
                ),
                ("namespace", models.CharField(db_index=True, max_length=32, verbose_name="Namespace")),
                (
                    "uid",
                    core.models.UUIDField(
                        default=core.models.UUIDField.get_default_value, max_length=64, verbose_name="Link Table UID"
                    ),
                ),
                ("version", models.IntegerField(db_index=True, verbose_name="Link Table Version")),
                ("name", models.CharField(max_length=50, verbose_name="Link Table Name")),
                ("config", models.JSONField(verbose_name="Config")),
                (
                    "description",
                    models.CharField(blank=True, default="", max_length=200, null=True, verbose_name="Description"),
                ),
            ],
            options={
                "verbose_name": "Link Table",
                "verbose_name_plural": "Link Table",
                "ordering": ["namespace", "-updated_at"],
                "unique_together": {("uid", "version")},
            },
        ),
    ]
