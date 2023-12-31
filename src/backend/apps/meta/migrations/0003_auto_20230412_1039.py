# Generated by Django 3.2.12 on 2023-04-12 02:39

import django.utils.timezone
from django.db import migrations, models

import apps.meta.models


class Migration(migrations.Migration):

    dependencies = [
        ("meta", "0002_alter_namespace_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="sensitiveobject",
            name="is_private",
            field=models.BooleanField(db_index=True, default=False, verbose_name="是否隐藏"),
        ),
        migrations.AddField(
            model_name="sensitiveobject",
            name="resource_id",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="资源ID"),
        ),
        migrations.AddField(
            model_name="sensitiveobject",
            name="resource_type",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="资源类型"),
        ),
        migrations.AddField(
            model_name="sensitiveobject",
            name="system_id",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="系统ID"),
        ),
        migrations.AlterField(
            model_name="sensitiveobject",
            name="id",
            field=models.CharField(
                default=apps.meta.models.make_sensitive_obj_pk,
                max_length=64,
                primary_key=True,
                serialize=False,
                verbose_name="敏感ID",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="sensitiveobject",
            unique_together={("system_id", "resource_type", "resource_id")},
        ),
        migrations.CreateModel(
            name="DataMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("data_field", models.CharField(max_length=255, verbose_name="数据字段")),
                ("data_key", models.CharField(max_length=255, verbose_name="数据键")),
                ("data_alias", models.CharField(max_length=255, verbose_name="数据别名")),
            ],
            options={
                "verbose_name": "数据字典",
                "verbose_name_plural": "数据字典",
                "ordering": ["data_field", "data_key"],
                "unique_together": {("data_field", "data_key")},
            },
        ),
    ]
