# -*- coding: utf-8 -*-
"""风险白名单常量。"""

import os

from django.db import models
from django.utils.translation import gettext_lazy

# ITSM V4 审批流程编码
RISK_WHITELIST_WORKFLOW_KEY = os.getenv("BKAPP_RISK_WHITELIST_WORKFLOW_KEY", "")
# ITSM 回调地址。
RISK_WHITELIST_CALLBACK_URL = f'{os.getenv("BKAPP_BKAUDIT_CALLBACK_URL_PREFIX", "")}/risk_whitelist_callback/callback/'


class WhitelistType(models.TextChoices):
    FALSE_POSITIVE = "false_positive", gettext_lazy("误报加白")
    RISK_ACCEPTANCE = "risk_acceptance", gettext_lazy("冒险加白")


class WhitelistStatus(models.TextChoices):
    PENDING = "pending", gettext_lazy("待审批")
    ACTIVE = "active", gettext_lazy("生效中")
    DISABLED = "disabled", gettext_lazy("已停用")
    EXPIRED = "expired", gettext_lazy("已到期")
    REJECTED = "rejected", gettext_lazy("已驳回")


class HitAction(models.TextChoices):
    SUPPRESS_NEW = "suppress_new", gettext_lazy("抑制新单")
    SUPPRESS_APPEND = "suppress_append", gettext_lazy("抑制追加")


WHITELIST_NODE_ACTION = "WhitelistApply"
STRATEGY_FIELDS = {"strategy_id", "strategy"}
DELETABLE_STATUS = {
    WhitelistStatus.DISABLED,
    WhitelistStatus.EXPIRED,
    WhitelistStatus.REJECTED,
}
FLOW_STATUS = {WhitelistStatus.PENDING, WhitelistStatus.REJECTED}
