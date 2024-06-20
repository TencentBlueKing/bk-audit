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

from apps.notice.builders.base import BUILD_RESPONSE_TYPE, Builder
from apps.notice.models import NoticeContent, NoticeContentConfig


class ErrorBuilder(Builder):
    """
    异常信息构造器
    """

    def build_msg(self, *args, **kwargs) -> BUILD_RESPONSE_TYPE:
        content = NoticeContent(
            *[
                NoticeContentConfig(
                    key=line.split(": ", 1)[0], name=line.split(": ", 1)[0], value=line.split(": ", 1)[1]
                )
                for line in self.notice_log.content.split("\n")
                if line.find(": ") != -1
            ]
        )
        return self.notice_log.title, content, None, {}

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
