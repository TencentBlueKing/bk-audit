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

import os

from bk_resource import api
from django.conf import settings
from django.template import Template, engines
from django.template.backends.django import Template as BackendTemplate
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.settings import api_settings

from apps.notice.constants import BK_AUDIT_MAIL_DEFAULT_TEMPLATE
from apps.notice.senders.base import Sender


class MailSender(Sender):
    """
    发送邮件消息
    """

    api_resource = api.bk_cmsi.send_mail

    def _build_params(self) -> dict:
        return {
            "receiver__username": self.receivers,
            "title": self.title,
            "content": self.mail_content,
            **self.configs,
        }

    @property
    def mail_content(self) -> str:
        context = {
            "title": self.title,
            "notice_time": timezone.localtime().strftime(api_settings.DATETIME_FORMAT),
            "content": self.content,
            "footer_content": gettext("此为系统邮件，由蓝鲸审计中心自动发送，请勿回复"),
            "button": self.button,
        }
        template_content: str = self.configs.get("_mail_template", "")
        if not template_content:
            with open(os.path.join(settings.BASE_DIR, BK_AUDIT_MAIL_DEFAULT_TEMPLATE), "r") as file:
                template_content = file.read()
        return BackendTemplate(Template(template_content), engines.all()[0]).render(context=context)
