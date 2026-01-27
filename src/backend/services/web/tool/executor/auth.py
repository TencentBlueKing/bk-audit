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
import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Dict, Union
from urllib.parse import urlparse

from apps.meta.constants import SENSITIVE_REPLACE_VALUE
from services.web.tool.constants import (
    ApiAuthMethod,
    BkAppAuthConfig,
    BkAuthItem,
    HmacSignatureAuthConfig,
    HmacSignatureAuthItem,
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


class HmacSignatureAuthHandler(BaseAuthHandler):
    """HMAC签名认证"""

    def __init__(self, config: HmacSignatureAuthConfig):
        self.config = config
        self.host = ""
        self.path = ""
        self.method = "POST"

    def set_request_info(self, url: str, method: str) -> None:
        """
        从TURL中解析并设置请求信息
        :param url: 完整的请求URL
        :param method: HTTP请求方法
        """
        parsed = urlparse(url)
        self.host = parsed.netloc
        self.path = parsed.path or "/"
        self.method = method

    def _generate_signature(self, method: str, path: str, date: str) -> str:
        """
        生成HMAC-SHA256签名
        :param method: HTTP请求方法
        :param path: 请求路径
        :param date: 日期字符串
        :return: Base64编码的签名
        """
        # 构建签名字符串
        signing_str = f"(request-target): {method.lower()} {path}\n"
        signing_str += f"host: {self.host}\n"
        signing_str += f"date: {date}"

        # 计算HMAC-SHA256
        digest = hmac.new(self.config.secret_key.encode('utf-8'), signing_str.encode('utf-8'), hashlib.sha256).digest()

        # Base64编码
        return base64.b64encode(digest).decode('utf-8')

    def apply_auth(self, headers: Dict[str, str], url: str = None, method: str = None) -> None:
        """
        应用HMAC签名认证信息到请求头
        :param headers: 请求头字典
        :param url: 完整的请求URL（可选，传入时会自动解析host和path）
        :param method: HTTP请求方法（可选）
        """
        # 如果传入了url和method，则解析并更新请求信息
        if url and method:
            self.set_request_info(url, method)

        method = method or self.method
        path = self.path

        # 使用本地时间格式化并附带GMT标记
        date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')

        # 生成签名
        signature = self._generate_signature(method, path, date)

        # 构建Authorization头
        if self.config.app_code:
            headers['X-APP-CODE'] = self.config.app_code
        headers['Date'] = date
        headers['Authorization'] = (
            f'Signature keyId="{self.config.secret_id}",'
            f'algorithm="hmac-sha256",'
            f'headers="(request-target) host date",'
            f'signature="{signature}"'
        )

    def mask_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        对请求头进行脱敏，用于日志记录
        :param headers: 原始请求头
        :return: 脱敏后的请求头
        """
        masked = headers.copy()
        if 'Authorization' in masked:
            masked['Authorization'] = SENSITIVE_REPLACE_VALUE
        return masked


class AuthHandlerFactory:
    """认证处理器工厂"""

    @staticmethod
    def get_handler(
        auth_config: Union[BkAuthItem, HmacSignatureAuthItem, NoAuthItem], url: str = "", method: str = ""
    ) -> BaseAuthHandler:
        """
        根据认证配置获取对应的认证处理器
        :param auth_config: 认证配置
        :param url: 完整的请求URL（用于HMAC签名认证，会自动解析host和path）
        :param method: HTTP请求方法（用于HMAC签名认证）
        :return: 认证处理器实例
        """
        auth_method = auth_config.method
        if auth_method == ApiAuthMethod.BK_APP_AUTH.value:
            return BkAppAuthHandler(auth_config.config)
        elif auth_method == ApiAuthMethod.HMAC_SIGNATURE.value:
            handler = HmacSignatureAuthHandler(auth_config.config)
            if url:
                handler.set_request_info(url, method)
            return handler
        elif auth_method == ApiAuthMethod.NONE.value:
            return NoAuthHandler()
        else:
            # 默认返回无认证或抛出异常，这里暂定无认证
            return NoAuthHandler()
