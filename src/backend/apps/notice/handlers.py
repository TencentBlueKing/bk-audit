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

import datetime
import json
import os
from typing import List

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.common_utils import ignored
from blueapps.utils.logger import logger
from django.conf import settings
from django.template import Template, engines
from django.template.backends.django import Template as BackendTemplate
from django.utils import timezone
from django.utils.translation import gettext
from opentelemetry import trace
from opentelemetry.trace import format_trace_id
from rest_framework.settings import api_settings

from apps.meta.models import GlobalMetaConfig
from apps.notice.constants import (
    ADMIN_NOTICE_GROUP_ID,
    BK_AUDIT_MAIL_DEFAULT_TEMPLATE,
    NOTICE_WHITELIST_USER_KEY,
    MsgType,
)
from apps.notice.models import (
    NoticeButton,
    NoticeContent,
    NoticeContentConfig,
    NoticeGroup,
    NoticeLog,
)
from apps.notice.tasks import send_notice


class NoticeHandler:
    """
    处理通知
    """

    def __init__(
        self,
        *,
        notice_group: NoticeGroup,
        title: str,
        content: NoticeContent,
        button: NoticeButton = None,
        skip_recent_check: bool = False,
        **configs,
    ):
        self.notice_group = notice_group
        self.title = title
        self.content = content
        self.configs = configs
        self.button = button
        self.skip_recent_check = skip_recent_check

    def send(self) -> None:
        for notice_config in self.notice_group.notice_config:
            # 获取处理方法
            msg_type = notice_config.get("msg_type")
            sender: callable = getattr(self, f"send_{msg_type}", None)
            if sender is None:
                logger.warn("[MsgTypeUnsupported] NoticeGroup => %s; MsgType => %s", self.notice_group.pk, msg_type)
                continue
            # 校验消息白名单
            white_list = self._load_white_list()
            if white_list:
                self.notice_group.group_member = [u for u in self.notice_group.group_member if u in white_list]
            # 记录日志
            notice_log = self._record_send_log(msg_type)
            # 校验聚合
            if not self.skip_recent_check:
                recent_log = self._check_recent_notice(notice_log, msg_type)
                if recent_log is not None:
                    msg = "[RecentSendCheckNotPass] NoticeLog => %s;" % recent_log.pk
                    notice_log.is_duplicate = True
                    notice_log.extra = msg
                    notice_log.save(update_fields=["is_duplicate", "extra"])
                    logger.info(msg)
                    continue
            # 发送消息
            if self.notice_group.group_member:
                notice_log.is_success, notice_log.extra = sender()
                notice_log.save(update_fields=["is_success", "extra"])

    def send_weixin(self) -> (bool, str):
        params = {
            "receiver__username": self.notice_group.group_member,
            "data": {
                **self.configs,
                "heading": self.title,
                "message": self.weixin_content,
            },
        }
        return self._call_api(api.bk_cmsi.send_weixin, **params)

    @property
    def weixin_content(self) -> str:
        return self.content.to_string()

    def send_rtx(self) -> (bool, str):
        params = {
            **self.configs,
            "title": self.title,
            "receiver__username": self.notice_group.group_member,
            "content": self.rtx_content,
        }
        return self._call_api(api.bk_cmsi.send_rtx, **params)

    @property
    def rtx_content(self) -> str:
        return self.content.to_string()

    def send_voice(self) -> (bool, str):
        params = {
            **self.configs,
            "auto_read_message": self.voice_content,
            "receiver__username": self.notice_group.group_member,
        }
        return self._call_api(api.bk_cmsi.send_voice, **params)

    @property
    def voice_content(self) -> str:
        return self.title

    def send_sms(self) -> (bool, str):
        params = {
            **self.configs,
            "msg_type": MsgType.SMS.value,
            "receiver__username": self.notice_group.group_member,
            "title": self.title,
            "content": self.sms_content,
        }
        return self._call_api(api.bk_cmsi.send_msg, **params)

    @property
    def sms_content(self) -> str:
        return self.content.to_string()

    def send_mail(self) -> (bool, str):
        params = {
            **self.configs,
            "receiver__username": self.notice_group.group_member,
            "title": self.title,
            "content": self.mail_content,
        }
        return self._call_api(api.bk_cmsi.send_mail, **params)

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

    def _call_api(self, api_resource: callable, **params) -> (bool, str):
        try:
            result = api_resource(**params)
            with ignored(json.JSONDecodeError, TypeError, ValueError):
                result = json.dumps(result, ensure_ascii=False)
            return True, str(result)
        except APIRequestError as err:
            msg = "[SendNoticeFailed] NoticeGroup => {}; Params => {}; Err => {};".format(
                self.notice_group.pk, params, err
            )
            logger.error(msg)
            return False, msg

    def _record_send_log(self, msg_type) -> NoticeLog:
        return NoticeLog.objects.create(
            msg_type=msg_type,
            title=self.title,
            content=self.content.to_string(),
            md5=NoticeLog.build_hash(self.notice_group.group_member, msg_type, self.title, self.content),
            send_at=int(datetime.datetime.now().timestamp() * 1000),
            receivers=self.notice_group.group_member,
            trace_id=self.get_current_trace_id(self.__class__.__name__),
        )

    def _check_recent_notice(self, notice_log: NoticeLog, msg_type: str) -> NoticeLog:
        md5 = NoticeLog.build_hash(self.notice_group.group_member, msg_type, self.title, self.content)
        send_at = int(
            (datetime.datetime.now() - datetime.timedelta(minutes=settings.NOTICE_AGG_MINUTES)).timestamp() * 1000
        )
        return NoticeLog.objects.filter(md5=md5, send_at__gte=send_at).exclude(log_id=notice_log.log_id).first()

    def _load_white_list(self) -> List[str]:
        return GlobalMetaConfig.get(NOTICE_WHITELIST_USER_KEY, default=[])

    @classmethod
    def get_current_trace_id(cls, name: str) -> str:
        try:
            tracer = trace.get_tracer_provider().get_tracer(settings.APP_CODE)
            with tracer.start_as_current_span(name) as span:
                return format_trace_id(span.get_span_context().trace_id)
        except Exception:  # NOCC:broad-except(需要处理所有异常)
            return ""


class ErrorMsgHandler:
    """
    异常消息通知
    """

    def __init__(self, title, content, **kwargs):
        self.title = f"{gettext('【蓝鲸审计中心%s】') % settings.RUN_MODE} {title}"
        self.content = self.build_content(content)
        self.kwargs = kwargs

    def send(self):
        notice_group = NoticeGroup.objects.get(group_id=ADMIN_NOTICE_GROUP_ID)
        send_notice.delay(notice_group=notice_group, title=self.title, content=self.content, **self.kwargs)
        logger.info("[SendErrorMsgDone] NoticeGroup => %s; Members => %s", notice_group.pk, notice_group.group_member)

    def build_content(self, content: str) -> NoticeContent:
        return NoticeContent(
            NoticeContentConfig(key="err_msg", name=gettext("异常信息"), value=content),
            NoticeContentConfig(
                key="trace_id",
                name=gettext("TraceID"),
                value=NoticeHandler.get_current_trace_id(self.__class__.__name__),
            ),
        )
