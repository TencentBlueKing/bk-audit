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
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the specific language
governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from urllib.parse import urlparse

from django.conf import settings
from django.utils.translation import gettext_lazy as _


class URLSecurityError(Exception):
    """URL 安全校验失败（调用方自行决定拒绝方式：日志拦截 / ValidationError）"""


ALLOWED_SCHEMES = ("http", "https")
# 资源路径禁用前缀：? / # 会截断路径注入 query/fragment，// 有 protocol-relative 歧义
PATH_FORBIDDEN_PREFIXES = ("?", "#", "//")


def validate_request_url(url: str, allow_empty: bool = True) -> None:
    """校验请求 URL 安全性：非空（可选）、scheme 限 http/https、高危端口黑名单。

    判定逻辑与 services/web/databus/collector/snapshot/join/http_pull.py 的
    validate_url_security 同构（单一实现源），供 schema 拉取出口校验与序列化层
    写入校验共用；http_pull 切换为共享实现列入二期。

    :param url: 待校验 URL
    :param allow_empty: 空值是否放行（默认放行，空值场景由调用方容错/兜底）
    :raises URLSecurityError: 校验失败
    """
    if not url:
        if allow_empty:
            return
        raise URLSecurityError(_("URL不能为空"))
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise URLSecurityError(_("URL必须使用http或https协议"))
    if not parsed.netloc:
        raise URLSecurityError(_("URL缺少有效主机名"))
    try:
        port = parsed.port
    except ValueError:
        # urlparse 惰性解析端口，畸形端口（如 http://host:abc/）访问 .port 时抛 ValueError
        raise URLSecurityError(_("URL端口格式非法"))
    if port and port in settings.HIGH_RISK_PORTS:
        raise URLSecurityError(_("URL包含高危端口: {}").format(port))


def mask_authorization(headers: dict) -> dict:
    """返回请求头脱敏副本：Authorization 值仅保留认证类型前缀（如 Basic ***）。"""
    masked = dict(headers or {})
    auth = masked.get("Authorization")
    if auth:
        scheme = str(auth).split(" ", 1)[0]
        masked["Authorization"] = f"{scheme} ***"
    return masked


def validate_resource_path(path: str) -> None:
    """校验资源类型 path 形态：禁 ?/# 前缀（截断注入）、// 前缀（协议相对歧义）、://（scheme 注入）、空白字符。

    供序列化层写入校验与存量扫描命令共用（规则同源）。

    :raises URLSecurityError: 校验失败
    """
    if not path:
        return
    if path.startswith(PATH_FORBIDDEN_PREFIXES):
        raise URLSecurityError(_("资源路径不能以 ?、#、// 开头"))
    if "://" in path:
        raise URLSecurityError(_("资源路径不能包含协议标识"))
    if any(ch.isspace() for ch in path):
        raise URLSecurityError(_("资源路径不能包含空白字符"))
