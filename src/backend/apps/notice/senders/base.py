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
from typing import List

from bk_resource import APIResource

from apps.notice.models import NoticeButton, NoticeContent


class Sender:
    """
    发送器基类
    """

    @property
    @abc.abstractmethod
    def api_resource(self) -> APIResource:
        raise NotImplementedError()

    def __init__(
        self,
        receivers: List[str],
        title: str,
        content: NoticeContent,
        button: NoticeButton = None,
        **configs,
    ):
        self.receivers = receivers
        self.title = title
        self.content = content
        self.button = button
        self.configs = configs

    @abc.abstractmethod
    def _build_params(self) -> dict:
        raise NotImplementedError()

    def send(self) -> (bool, str):
        params = self._build_params()
        return self.api_resource(**params)
