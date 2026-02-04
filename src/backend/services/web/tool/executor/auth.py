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

from core.models import get_request_username
from services.web.tool.constants import (
    ApiAuthMethod,
    BkAppAuthConfig,
    BkAuthItem,
    IEOPAuthConfig,
    IEOPAuthItem,
    NoAuthItem,
)


class BaseAuthHandler(abc.ABC):
    """认证处理器基类"""

    @abc.abstractmethod
    def apply_auth(self, headers: Dict[str, str], **kwargs) -> None:
        """
        应用认证信息到请求头
        :param headers: 请求头字典
        """
        raise NotImplementedError()


class NoAuthHandler(BaseAuthHandler):
    """无认证"""

    def apply_auth(self, headers: Dict[str, str], **kwargs) -> None:
        pass


class BkAppAuthHandler(BaseAuthHandler):
    """蓝鲸应用认证"""

    def __init__(self, config: BkAppAuthConfig):
        self.config = config

    def apply_auth(self, headers: Dict[str, str], **kwargs) -> None:
        headers["X-Bkapi-Authorization"] = json.dumps(
            {
                "bk_app_code": self.config.bk_app_code,
                "bk_app_secret": self.config.bk_app_secret,
            }
        )


class IEOPAuthHandler(BaseAuthHandler):
    """IEOP认证处理器（支持GET和POST请求）"""

    def __init__(self, config: IEOPAuthConfig):
        self.config = config
        self.host = ""
        self.path = ""
        self.method = "POST"

    def set_request_info(self, url: str, method: str = "POST") -> None:
        """
        从URL中解析并设置请求信息
        :param url: 完整的请求URL
        :param method: HTTP请求方法（支持GET和POST）
        """
        parsed = urlparse(url)
        self.host = parsed.netloc
        self.path = parsed.path or "/"
        self.method = method.upper()

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

    def _get_operator(self) -> str:
        """
        获取操作者：优先使用配置的operator，否则尝试获取当前用户
        :return: 操作者用户名
        """
        if self.config.operator:
            return self.config.operator
        return get_request_username() or ""

    def apply_auth(
        self,
        headers: Dict[str, str],
        *,
        body: Dict[str, any] = None,
        query_params: Dict[str, any] = None,
        url: str = None,
    ) -> None:
        """
        应用IEOP认证信息到请求头和请求体/URL参数
        :param headers: 请求头字典
        :param body: 请求体字典（POST请求时直接修改，自动添加认证参数）
        :param query_params: URL查询参数字典（GET请求时直接修改，自动添加认证参数）
        :param url: 完整的请求URL（可选，传入时会自动解析host和path）
        """
        # 如果传入了url，则解析并更新请求信息
        if url:
            self.set_request_info(url, self.method)

        method = self.method
        path = self.path

        # 使用本地时间格式化并附带GMT标记
        date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')

        # 生成签名
        signature = self._generate_signature(method, path, date)

        # 构建请求头
        headers['Date'] = date
        headers['Authorization'] = (
            f'Signature keyId="{self.config.secret_id}",'
            f'algorithm="hmac-sha256",'
            f'headers="(request-target) host date",'
            f'signature="{signature}"'
        )

        # 获取操作者（优先配置，否则当前用户）
        operator = self._get_operator()

        # 根据请求方法处理参数
        if method == "GET":
            # GET请求：将认证参数添加到URL query参数中
            if query_params is None:
                return
            query_params['app_code'] = self.config.app_code
            query_params['app_secret'] = self.config.app_secret
            if operator:
                query_params['operator'] = operator
        else:
            # POST请求：将认证参数添加到body中
            if body is None:
                return
            body['app_code'] = self.config.app_code
            body['app_secret'] = self.config.app_secret
            if operator:
                body['operator'] = operator
            # 对 body 中的 data 参数自动进行 json.loads 反序列化
            if 'data' in body and isinstance(body['data'], str):
                try:
                    body['data'] = json.loads(body['data'])
                except (json.JSONDecodeError, TypeError):
                    # 如果解析失败，保持原样
                    pass


class AuthHandlerFactory:
    """认证处理器工厂"""

    @staticmethod
    def get_handler(
        auth_config: Union[BkAuthItem, IEOPAuthItem, NoAuthItem], url: str = "", method: str = "POST"
    ) -> BaseAuthHandler:
        """
        根据认证配置获取对应的认证处理器
        :param auth_config: 认证配置
        :param url: 完整的请求URL（用于IEOP认证，会自动解析host和path）
        :param method: HTTP请求方法（IEOP认证支持GET和POST）
        :return: 认证处理器实例
        """
        auth_method = auth_config.method
        if auth_method == ApiAuthMethod.BK_APP_AUTH.value:
            return BkAppAuthHandler(auth_config.config)
        elif auth_method == ApiAuthMethod.IEOP_AUTH.value:
            handler = IEOPAuthHandler(auth_config.config)
            handler.method = method.upper()
            if url:
                handler.set_request_info(url, method)
            return handler
        elif auth_method == ApiAuthMethod.NONE.value:
            return NoAuthHandler()
        else:
            # 默认返回无认证或抛出异常，这里暂定无认证
            return NoAuthHandler()
