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

from bk_resource import resource
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.translation import gettext
from opentelemetry import trace
from opentelemetry.trace import format_trace_id

from apps.notice.constants import ADMIN_NOTICE_GROUP_ID, RelateType
from apps.notice.models import NoticeContent, NoticeContentConfig, NoticeGroup
from apps.notice.parser import IgnoreMemberVariableParser


class ErrorMsgHandler:
    """
    异常消息通知
    """

    def __init__(self, title, content):
        self.title = f"{gettext('【蓝鲸审计中心%s】') % settings.RUN_MODE} {title}"
        self.content = self.build_content(content)

    def send(self):
        notice_group: NoticeGroup = NoticeGroup.objects.get(group_id=ADMIN_NOTICE_GROUP_ID)
        receivers = IgnoreMemberVariableParser().parse_group(notice_group)
        resource.notice.send_notice(
            relate_type=RelateType.ERROR,
            relate_id=self.get_current_trace_id(self.__class__.__name__),
            agg_key=None,
            msg_type=[c.get("msg_type") for c in notice_group.notice_config if "msg_type" in c],
            receivers=receivers,
            title=self.title,
            content=self.content.to_string(),
        )
        logger.info("[SendErrorMsgDone] NoticeGroup => %s; Members => %s", notice_group.pk, receivers)

    def build_content(self, content: str) -> NoticeContent:
        return NoticeContent(
            NoticeContentConfig(key="err_msg", name=gettext("异常信息"), value=content),
            NoticeContentConfig(
                key="trace_id",
                name=gettext("TraceID"),
                value=self.get_current_trace_id(self.__class__.__name__),
            ),
        )

    @classmethod
    def get_current_trace_id(cls, name: str) -> str:
        try:
            tracer = trace.get_tracer_provider().get_tracer(settings.APP_CODE)
            with tracer.start_as_current_span(name) as span:
                return format_trace_id(span.get_span_context().trace_id)
        except Exception:  # NOCC:broad-except(需要处理所有异常)
            return ""
