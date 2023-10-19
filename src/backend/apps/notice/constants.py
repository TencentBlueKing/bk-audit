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

from django.utils.translation import gettext_lazy

from core.choices import TextChoices

ADMIN_NOTICE_GROUP_ID = 1
ADMIN_NOTICE_GROUP_NAME = gettext_lazy("审计中心管理员")

NOTICE_GROUP_NAME_REGEX = r"[\\\|\/\:\*\<\>\"\?,]+"

NOTICE_LOG_EXPIRED_DAYS = 30

BK_AUDIT_MAIL_DEFAULT_TEMPLATE = "templates/notice/mail.html"

NOTICE_WHITELIST_USER_KEY = "NOTICE_WHITELIST_USER"


class MsgType(TextChoices):
    """
    通知类型
    """

    WEIXIN = "weixin", gettext_lazy("微信")
    RTX = "rtx", gettext_lazy("企业微信")
    MAIL = "mail", gettext_lazy("邮件")
    VOICE = "voice", gettext_lazy("语音")
    SMS = "sms", gettext_lazy("短信")
