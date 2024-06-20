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

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.settings import api_settings

from apps.meta.utils.saas import get_saas_url
from apps.notice.builders.base import BUILD_RESPONSE_TYPE, Builder
from apps.notice.models import NoticeButton, NoticeContent, NoticeContentConfig

try:
    from services.web.risk.constants import EventMappingFields
    from services.web.risk.models import Risk
    from services.web.strategy_v2.models import Strategy
except ImportError:
    pass


class RiskBuilder(Builder):
    """
    风险通知构造器
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.risk = Risk.objects.filter(risk_id=self.relate_id).first()
        if self.risk is None:
            self.strategy = None
        else:
            self.strategy = Strategy.objects.filter(strategy_id=self.risk.strategy_id).first()

    def build_msg(self, *args, **kwargs) -> BUILD_RESPONSE_TYPE:
        # 构造标题
        title = self.notice_log.title

        # 构造内容
        risk_time = self.risk.event_time.astimezone(timezone.get_current_timezone())
        risk_url = "{}/risk-manage/detail/{}".format(get_saas_url(settings.APP_CODE), self.risk.risk_id)

        # 聚合增加内容
        if self.need_agg:
            notice_contents = [
                NoticeContentConfig(
                    key="notice_info",
                    name="",
                    value=(gettext("您有共%d条风险待处理，请及时前往审计中心查看处理，以下为其中1个风险信息") % self.agg_count)
                    if "待办" in title or "Pending" in title
                    else (gettext("发现共%d条新风险，请点击前往审计中心查看详情，以下为其中1个风险信息") % self.agg_count),
                )
            ]
        else:
            notice_contents = []

        # 消息主要内容
        notice_contents.extend(
            [
                NoticeContentConfig(
                    key="risk_id", name=gettext("Risk ID"), value=f'<a href="{risk_url}">{self.risk.risk_id}</a>'
                ),
                NoticeContentConfig(
                    key=EventMappingFields.EVENT_CONTENT.field_name,
                    name=gettext("风险描述"),
                    value=self.risk.event_content or "- -",
                ),
                NoticeContentConfig(
                    key="strategy",
                    name=gettext("命中策略"),
                    value=f"{self.strategy.strategy_name}({self.strategy.strategy_id})",
                ),
                NoticeContentConfig(
                    key=EventMappingFields.OPERATOR.field_name,
                    name=gettext("责任人"),
                    value="; ".join(self.risk.operator if isinstance(self.risk.operator, list) else []) or "- -",
                ),
                NoticeContentConfig(
                    key=EventMappingFields.EVENT_TIME.field_name,
                    name=gettext("风险发现时间"),
                    value=risk_time.strftime(api_settings.DATETIME_FORMAT),
                ),
            ]
        )
        content = NoticeContent(*notice_contents)

        button = NoticeButton(text=gettext("Show Detail"), url=risk_url)

        return title, content, button, {}

    def build_mail(self) -> BUILD_RESPONSE_TYPE:
        pass

    def build_rtx(self) -> BUILD_RESPONSE_TYPE:
        pass

    def build_sms(self) -> BUILD_RESPONSE_TYPE:
        pass

    def build_voice(self) -> BUILD_RESPONSE_TYPE:
        pass

    def build_weixin(self) -> BUILD_RESPONSE_TYPE:
        pass
