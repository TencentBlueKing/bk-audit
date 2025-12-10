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
import json
from typing import Dict, Union

from apps.meta.constants import SENSITIVE_REPLACE_VALUE
from services.web.tool.constants import (
    ApiAuthMethod,
    BkAppAuthConfig,
    BkAuthItem,
    NoAuthItem,
)


class BaseAuthHandler(abc.ABC):
    """认证处理器基类"""

    @abc.abstractmethod
    def apply_auth(self, headers: Dict[str, str]) -> None:
        """
        应用认证信息到请求头
        :param headers: 请求头字典
        """
        raise NotImplementedError()

    def mask_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        对请求头进行脱敏，用于日志记录
        :param headers: 原始请求头
        :return: 脱敏后的请求头
        """
        return headers.copy()


class NoAuthHandler(BaseAuthHandler):
    """无认证"""

    def apply_auth(self, headers: Dict[str, str]) -> None:
        pass


class BkAppAuthHandler(BaseAuthHandler):
    """蓝鲸应用认证"""

    def __init__(self, config: BkAppAuthConfig):
        self.config = config

    def apply_auth(self, headers: Dict[str, str]) -> None:
        headers["X-Bkapi-Authorization"] = json.dumps(
            {
                "bk_app_code": self.config.bk_app_code,
                "bk_app_secret": self.config.bk_app_secret,
            }
        )

    def mask_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        masked = headers.copy()
        masked["X-Bkapi-Authorization"] = json.dumps(
            {
                "bk_app_code": self.config.bk_app_code,
                "bk_app_secret": SENSITIVE_REPLACE_VALUE,
            }
        )
        return masked


class AuthHandlerFactory:
    """认证处理器工厂"""

    @staticmethod
    def get_handler(auth_config: Union[BkAuthItem, NoAuthItem]) -> BaseAuthHandler:
        method = auth_config.method
        if method == ApiAuthMethod.BK_APP_AUTH.value:
            return BkAppAuthHandler(auth_config.config)
        elif method == ApiAuthMethod.NONE.value:
            return NoAuthHandler()
        else:
            # 默认返回无认证或抛出异常，这里暂定无认证
            return NoAuthHandler()
