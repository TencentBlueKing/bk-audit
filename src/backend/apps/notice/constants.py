# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from typing import Optional

from django.utils.translation import gettext_lazy

from core.choices import TextChoices

ADMIN_NOTICE_GROUP_ID = 1
ADMIN_NOTICE_GROUP_NAME = gettext_lazy("审计中心管理员")

NOTICE_GROUP_NAME_REGEX = r"[\\\|\/\:\*\<\>\"\?,]+"

NOTICE_LOG_EXPIRED_DAYS = 30

BK_AUDIT_MAIL_DEFAULT_TEMPLATE = "templates/notice/mail.html"

NOTICE_WHITELIST_USER_KEY = "NOTICE_WHITELIST_USER"

NOTICE_AGG_DURATION_KEY = "NOTICE_AGG_DURATION"
DEFAULT_NOTICE_AGG_DURATION = 0  # 默认不聚合

NOTICE_AGG_MAX_NOTICE_KEY = "NOTICE_AGG_MAX_NOTICE"
DEFAULT_NOTICE_AGG_MAX_NOTICE = 0  # 默认不聚合

NOTICE_LAST_AGG_TIME_KEY = "notice:last_agg_time:{relate_type}:{agg_key}"


class MsgType(TextChoices):
    """
    通知类型
    """

    WEIXIN = "weixin", gettext_lazy("微信")
    RTX = "rtx", gettext_lazy("企业微信")
    MAIL = "mail", gettext_lazy("邮件")
    VOICE = "voice", gettext_lazy("语音")
    SMS = "sms", gettext_lazy("短信")


class RelateType(TextChoices):
    """
    通知关联类型
    """

    RISK = "risk", gettext_lazy("风险")
    ERROR = "error", gettext_lazy("异常")
    LOG_EXPORT = "log_export", gettext_lazy("日志导出")


class MemberVariable(TextChoices):
    """
    成员变量
    """

    OPERATOR = "$OPERATOR", gettext_lazy("责任人")
    OPERATOR_LEADER = "$OPERATOR_LEADER", gettext_lazy("责任人上级")

    @classmethod
    def match(cls, key: str) -> Optional["MemberVariable"]:
        """
        匹配成员变量
        """

        return cls._value2member_map_.get(key)


# 日志导出信息安全声明
LOG_EXPORT_SECURITY_STATEMENT = gettext_lazy(
    """信息安全声明：
    此邮件中包含导出数据，为高敏感数据资产，请遵守法律法规合规使用，如有泄露，承担相应的法律责任。
    如果您不是这封邮件的接收者，请删除邮件，并邮件告知邮件发送方。
    """
)

# BK Audit SaaS 后台模块
BK_AUDIT_SAAS_BACKEND_MODULE = "api"
