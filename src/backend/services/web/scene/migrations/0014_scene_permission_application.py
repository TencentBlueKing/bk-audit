import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scene", "0013_alter_resourcebinding_visibility_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScenePermissionApplication",
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
                ("applicant", models.CharField(db_index=True, max_length=64, verbose_name="申请人")),
                (
                    "role",
                    models.CharField(
                        choices=[("manager", "场景管理员"), ("user", "场景使用者")],
                        db_index=True,
                        max_length=16,
                        verbose_name="申请角色",
                    ),
                ),
                ("reason", models.TextField(blank=True, default="", verbose_name="申请理由")),
                ("itsm_sn", models.CharField(db_index=True, max_length=64, verbose_name="ITSM单号")),
                (
                    "itsm_ticket_id",
                    models.CharField(db_index=True, max_length=128, unique=True, verbose_name="ITSM工单ID"),
                ),
                (
                    "itsm_ticket_url",
                    models.CharField(blank=True, default="", max_length=512, verbose_name="ITSM工单链接"),
                ),
                (
                    "callback_token",
                    models.CharField(blank=True, default="", max_length=128, verbose_name="回调鉴权Token"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "待审批"),
                            ("approved", "审批通过"),
                            ("rejected", "已驳回"),
                            ("terminated", "已终止"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                        verbose_name="审批状态",
                    ),
                ),
                (
                    "grant_status",
                    models.CharField(
                        blank=True,
                        choices=[("success", "授权成功"), ("failed", "授权失败")],
                        db_index=True,
                        default="",
                        max_length=16,
                        verbose_name="授权状态",
                    ),
                ),
                ("approvers", models.JSONField(default=list, verbose_name="审批人")),
                ("reject_reason", models.TextField(blank=True, default="", verbose_name="拒绝理由")),
                ("grant_method", models.CharField(blank=True, default="", max_length=32, verbose_name="授权方式")),
                ("grant_error", models.TextField(blank=True, default="", verbose_name="授权错误")),
                ("retry_count", models.IntegerField(default=0, verbose_name="授权重试次数")),
                ("finished_at", models.DateTimeField(blank=True, null=True, verbose_name="完结时间")),
                (
                    "scene",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="permission_applications",
                        to="scene.scene",
                    ),
                ),
            ],
            options={
                "verbose_name": "场景权限申请",
                "verbose_name_plural": "场景权限申请",
                "ordering": ["-updated_at"],
                "indexes": [
                    models.Index(fields=["applicant", "status"], name="applicant_status_idx"),
                    models.Index(fields=["scene", "status"], name="scene_status_idx"),
                    models.Index(fields=["status", "retry_count"], name="status_retry_idx"),
                    models.Index(fields=["status", "created_at"], name="status_created_idx"),
                ],
            },
        ),
    ]
