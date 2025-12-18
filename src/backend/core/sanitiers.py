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

from abc import ABC, abstractmethod

import nh3
from markupsafe import escape


class BaseSanitizer(ABC):
    """
    净化器的抽象基类，定义了所有净化器必须遵守的接口契约。
    """

    @abstractmethod
    def sanitize(self, content: str) -> str:
        """
        接收一个字符串，返回净化后的安全字符串。
        """
        raise NotImplementedError()


class Nh3Sanitizer(BaseSanitizer):
    """
    一个使用 nh3 库实现的具体净化器。
    """

    # 将默认配置放在这里，与自身逻辑相关
    default_nh3_options = {
        'tags': {'p', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'a', 'br', 'h1', 'h2', 'h3'},
        'attributes': {'a': {'href', 'title'}},
        'strip_comments': True,
    }

    def __init__(self, nh3_options: dict = None):
        """
        初始化nh3净化器
        :param nh3_options: 传递给 nh3.clean 的自定义选项
        """
        self.nh3_options = nh3_options or self.default_nh3_options

    def sanitize(self, content: str) -> str:
        """
        实现基类的 sanitize 方法，使用 nh3.clean 进行净化。
        """
        return nh3.clean(content, **self.nh3_options)


class HtmlEscapeSanitizer(BaseSanitizer):
    """
    一个使用 markupsafe.escape 来实现“净化”的净化器。
    转义所有HTML特殊字符，将输入内容强制转换为安全的纯文本。
    """

    def sanitize(self, content: str) -> str:
        """
        实现基类的 sanitize 方法，使用 markupsafe.escape 对内容进行HTML转义。
        """
        return str(escape(content))
