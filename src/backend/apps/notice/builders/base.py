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

import abc
from typing import Callable, Optional, Tuple, TypeAlias

from apps.notice.models import NoticeButton, NoticeContent, NoticeLogV2

BUILD_RESPONSE_TYPE: TypeAlias = Tuple[str, NoticeContent, Optional[NoticeButton], dict]


class Builder:
    """
    消息内容构造器
    """

    def __init__(self, notice_log: NoticeLogV2, need_agg: bool, agg_count: int) -> None:
        self.notice_log = notice_log
        self.relate_id = self.notice_log.relate_id
        self.need_agg = need_agg
        self.agg_count = agg_count

    def build_msg(self, msg_type: str) -> BUILD_RESPONSE_TYPE:
        """
        构建消息
        :param msg_type: 消息类型
        :return: (title, content, button, configs)
        """

        _builder: Callable[[], BUILD_RESPONSE_TYPE] = getattr(self, f"build_{msg_type}")
        return _builder()

    @abc.abstractmethod
    def build_mail(self) -> BUILD_RESPONSE_TYPE:
        raise NotImplementedError()

    @abc.abstractmethod
    def build_rtx(self) -> BUILD_RESPONSE_TYPE:
        raise NotImplementedError()

    @abc.abstractmethod
    def build_sms(self) -> BUILD_RESPONSE_TYPE:
        raise NotImplementedError()

    @abc.abstractmethod
    def build_voice(self) -> BUILD_RESPONSE_TYPE:
        raise NotImplementedError()

    @abc.abstractmethod
    def build_weixin(self) -> BUILD_RESPONSE_TYPE:
        raise NotImplementedError()
