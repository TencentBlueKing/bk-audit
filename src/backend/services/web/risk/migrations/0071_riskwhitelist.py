# -*- coding: utf-8 -*-
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0070_ticketnode_sops_start_time"),
        ("scene", "0014_scene_permission_application"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiskWhitelist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "created_at",
                    models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="创建时间"),
                ),
                (
                    "created_by",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=32, null=True, verbose_name="创建者"
                    ),
                ),
                ("updated_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="更新时间")),
                (
                    "updated_by",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=32, null=True, verbose_name="修改者"
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                (
                    "scene",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="scene.scene",
                        verbose_name="所属场景",
                    ),
                ),
                (
                    "risk_id",
                    models.CharField(blank=True, db_index=True, default="", max_length=255, verbose_name="来源风险单"),
                ),
                (
                    "whitelist_type",
                    models.CharField(
                        choices=[("false_positive", "误报加白"), ("risk_acceptance", "冒险加白")],
                        db_index=True,
                        max_length=32,
                        verbose_name="加白类型",
                    ),
                ),
                ("match_scope", models.JSONField(default=dict, verbose_name="匹配范围")),
                ("reason", models.CharField(max_length=500, verbose_name="加白原因")),
                ("is_permanent", models.BooleanField(default=False, verbose_name="是否永久")),
                ("expire_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="到期时间")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "待审批"),
                            ("active", "生效中"),
                            ("disabled", "已停用"),
                            ("expired", "已到期"),
                            ("rejected", "已驳回"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                        verbose_name="状态",
                    ),
                ),
                ("itsm_sn", models.CharField(blank=True, default="", max_length=64, verbose_name="ITSM单号")),
                ("itsm_ticket_id", models.CharField(blank=True, default="", max_length=128, verbose_name="ITSM工单ID")),
                ("itsm_ticket_url", models.CharField(blank=True, default="", max_length=512, verbose_name="ITSM工单链接")),
                ("callback_token", models.CharField(blank=True, default="", max_length=128, verbose_name="回调鉴权Token")),
                ("reject_reason", models.TextField(blank=True, default="", verbose_name="驳回理由")),
            ],
            options={
                "verbose_name": "风险白名单",
                "verbose_name_plural": "风险白名单",
                "ordering": ["-updated_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="riskwhitelist",
            index=models.Index(fields=["scene", "status"], name="risk_wl_scene_status_idx"),
        ),
        migrations.CreateModel(
            name="RiskWhitelistHit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "created_at",
                    models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="创建时间"),
                ),
                (
                    "created_by",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=32, null=True, verbose_name="创建者"
                    ),
                ),
                ("updated_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="更新时间")),
                (
                    "updated_by",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=32, null=True, verbose_name="修改者"
                    ),
                ),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("hit_at", models.DateTimeField(db_index=True, verbose_name="命中时间")),
                (
                    "action",
                    models.CharField(
                        choices=[("suppress_new", "抑制新单"), ("suppress_append", "抑制追加")],
                        max_length=32,
                        verbose_name="拦截动作",
                    ),
                ),
                ("risk_id", models.CharField(blank=True, default="", max_length=255, verbose_name="关联风险单")),
                ("match_snapshot", models.JSONField(default=dict, verbose_name="命中时的匹配范围")),
                ("event_snapshot", models.JSONField(default=dict, verbose_name="事件快照")),
                (
                    "whitelist",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hits",
                        to="risk.riskwhitelist",
                        verbose_name="白名单",
                    ),
                ),
            ],
            options={
                "verbose_name": "风险白名单命中",
                "verbose_name_plural": "风险白名单命中",
                "ordering": ["-hit_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="riskwhitelisthit",
            index=models.Index(fields=["whitelist", "hit_at"], name="risk_wl_hit_time_idx"),
        ),
    ]
