# -*- coding: utf-8 -*-
from apps.notice.models import NoticeContent, NoticeContentConfig
from apps.notice.senders.mail import MailSender
from tests.base import TestCase


class TestMailSender(TestCase):
    def test_default_mail_template_does_not_render_title_before_content(self):
        sender = MailSender(
            receivers=["admin"],
            title="【蓝鲸审计中心】风险数据导出结果通知",
            content=NoticeContent(NoticeContentConfig(key="body", name="", value="您好 admin：导出完成")),
        )

        mail_content = sender.mail_content

        self.assertNotIn("【蓝鲸审计中心】风险数据导出结果通知", mail_content)
        self.assertNotIn("second-title", mail_content)
        self.assertNotIn("<title>", mail_content)
        self.assertNotIn("<hr/>\n<div class=\"content\"", mail_content)
        self.assertIn("您好 admin：导出完成", mail_content)
