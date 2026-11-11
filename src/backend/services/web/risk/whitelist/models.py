# -*- coding: utf-8 -*-
"""风险白名单表。由 services.web.risk.models 导入后挂到 risk 应用。"""

from django.db import models
from django.utils.translation import gettext_lazy

from core.models import SoftDeleteModel
from services.web.risk.whitelist.constants import (
    HitAction,
    WhitelistStatus,
    WhitelistType,
)


class RiskWhitelist(SoftDeleteModel):
    """风险白名单规则。"""

    scene = models.ForeignKey(
        "scene.Scene",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        db_index=True,
        verbose_name=gettext_lazy("所属场景"),
    )
    risk_id = models.CharField(gettext_lazy("来源风险单"), max_length=255, blank=True, default="", db_index=True)
    whitelist_type = models.CharField(gettext_lazy("加白类型"), max_length=32, choices=WhitelistType.choices, db_index=True)
    match_scope = models.JSONField(gettext_lazy("匹配范围"), default=dict)
    reason = models.CharField(gettext_lazy("加白原因"), max_length=500)
    is_permanent = models.BooleanField(gettext_lazy("是否永久"), default=False)
    expire_at = models.DateTimeField(gettext_lazy("到期时间"), null=True, blank=True, db_index=True)
    status = models.CharField(
        gettext_lazy("状态"),
        max_length=16,
        choices=WhitelistStatus.choices,
        default=WhitelistStatus.PENDING,
        db_index=True,
    )
    itsm_sn = models.CharField(gettext_lazy("ITSM单号"), max_length=64, blank=True, default="")
    itsm_ticket_id = models.CharField(gettext_lazy("ITSM工单ID"), max_length=128, blank=True, default="")
    itsm_ticket_url = models.CharField(gettext_lazy("ITSM工单链接"), max_length=512, blank=True, default="")
    callback_token = models.CharField(gettext_lazy("回调鉴权Token"), max_length=128, blank=True, default="")
    reject_reason = models.TextField(gettext_lazy("驳回理由"), blank=True, default="")

    class Meta:
        app_label = "risk"
        verbose_name = gettext_lazy("风险白名单")
        verbose_name_plural = verbose_name
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["scene", "status"], name="risk_wl_scene_status_idx"),
        ]

    def __str__(self):
        return f"RiskWhitelist({self.id})"


class RiskWhitelistHit(SoftDeleteModel):
    """白名单命中记录。"""

    whitelist = models.ForeignKey(
        RiskWhitelist, on_delete=models.CASCADE, related_name="hits", verbose_name=gettext_lazy("白名单")
    )
    hit_at = models.DateTimeField(gettext_lazy("命中时间"), db_index=True)
    action = models.CharField(gettext_lazy("拦截动作"), max_length=32, choices=HitAction.choices)
    risk_id = models.CharField(gettext_lazy("关联风险单"), max_length=255, blank=True, default="")
    match_snapshot = models.JSONField(gettext_lazy("命中时的匹配范围"), default=dict)
    event_snapshot = models.JSONField(gettext_lazy("事件快照"), default=dict)

    class Meta:
        app_label = "risk"
        verbose_name = gettext_lazy("风险白名单命中")
        verbose_name_plural = verbose_name
        ordering = ["-hit_at", "-id"]
        indexes = [
            models.Index(fields=["whitelist", "hit_at"], name="risk_wl_hit_time_idx"),
        ]
