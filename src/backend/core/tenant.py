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
import logging
from functools import lru_cache

from bk_resource import api
from django.conf import settings
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def use_multi_tenant_mode() -> bool:
    """统一的多租户模式判断, 取值 1/true/yes/on 视为开启。"""
    return str(getattr(settings, "BKPAAS_MULTI_TENANT_MODE", False)).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


@lru_cache(maxsize=1000)
def get_admin_username(bk_tenant_id: str) -> str:
    """获取指定租户的 bk_admin 用户对应的 bk_username

    1. 非多租户模式：回退 COMMON_USERNAME → DEFAULT_USERNAME
       → 允许单租户部署下平台态调用正常工作
    2. 多租户模式：调用 user_manage.batch_lookup_virtual_user 查询
       → bk_admin 是租户内的虚拟用户，由 user_manage 管理
       → 使用 @lru_cache 缓存，避免每次平台态调用都发 API 请求
    3. 调用 user_manage 时，该请求自身会经 AuditBkApiResource.build_header
       携带 X-Bk-Tenant-Id，不会形成循环依赖（bk_username="admin" 硬编码
       为 user_manage 接口的访问凭据，不是调用替换的目标）
    """
    if not use_multi_tenant_mode():
        username = getattr(settings, "COMMON_USERNAME", None) or getattr(settings, "DEFAULT_USERNAME", None)
        if not username:
            raise ValueError(_("get_admin_username: 未配置管理员用户名（COMMON_USERNAME / DEFAULT_USERNAME）"))
        return username

    try:
        result = api.user_manage.batch_lookup_virtual_user(
            bk_tenant_id=bk_tenant_id,
            lookup_field="login_name",
            lookups="bk_admin",
            bk_username="admin",
        )
    except Exception:
        logger.exception("获取管理员用户失败，bk_tenant_id=%s，API调用异常", bk_tenant_id)
        raise ValueError(gettext("get_admin_username: 获取管理员用户失败"))

    if not isinstance(result, list) or not result:
        logger.warning("获取管理员用户失败，返回结果为空，bk_tenant_id=%s", bk_tenant_id)
        raise ValueError(gettext("get_admin_username: 获取管理员用户失败"))

    username = result[0].get("bk_username") or result[0].get("username")
    if not username:
        logger.warning(
            "获取管理员用户失败，用户名字段为空，bk_tenant_id=%s, result[0]=%s",
            bk_tenant_id,
            result[0],
        )
        raise ValueError(gettext("get_admin_username: 获取管理员用户失败"))

    return username


# --- 共享资源命名工具 ---


def tenant_key(domain: str, *parts) -> str:
    """Redis key 前缀化（备选路径/双保险用）"""
    prefix = getattr(settings, "AUDIT_TENANT_PREFIX", "")
    return f"{prefix}{domain}:{':'.join(parts)}"


def tenant_queue(name: str) -> str:
    """Celery 队列名前缀化（备选 vhost 方案）"""
    prefix = getattr(settings, "AUDIT_TENANT_PREFIX", "")
    return f"{prefix}{name}" if prefix else name


def tenant_index(name: str) -> str:
    """ES index / 索引集 / 插件名前缀化"""
    prefix = getattr(settings, "AUDIT_TENANT_PREFIX", "")
    return f"{prefix}{name}" if prefix else name


def get_bk_tenant_id() -> str:
    """获取当前实例绑定的租户 ID"""
    return getattr(settings, "BK_TENANT_ID", "")
