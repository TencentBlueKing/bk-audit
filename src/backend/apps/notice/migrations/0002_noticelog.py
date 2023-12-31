# Generated by Django 3.2.12 on 2023-03-21 08:52

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notice", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoticeLog",
            fields=[
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(blank=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("log_id", models.BigAutoField(primary_key=True, serialize=False, verbose_name="ID")),
                ("msg_type", models.CharField(max_length=255, verbose_name="发送方式")),
                ("title", models.TextField(blank=True, null=True, verbose_name="标题")),
                ("content", models.TextField(blank=True, null=True, verbose_name="内容")),
                ("md5", models.CharField(max_length=255, verbose_name="消息Hash值")),
                ("send_at", models.BigIntegerField(verbose_name="发送时间")),
            ],
            options={
                "verbose_name": "消息记录",
                "verbose_name_plural": "消息记录",
                "ordering": ["-log_id"],
                "index_together": {("md5", "send_at")},
            },
        ),
    ]
