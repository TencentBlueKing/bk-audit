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
            "notice_time": timezone.now().strftime(api_settings.DATETIME_FORMAT),
            "content": self.content,
            "footer_content": gettext("此为系统邮件，由蓝鲸审计中心自动发送，请勿回复"),
            "button": self.button,
        }
        template_content: str = self.configs.get("_mail_template", "")
        if not template_content:
            with open(os.path.join(settings.BASE_DIR, BK_AUDIT_MAIL_DEFAULT_TEMPLATE), "r") as file:
                template_content = file.read()
        return BackendTemplate(Template(template_content), engines.all()[0]).render(context=context)
