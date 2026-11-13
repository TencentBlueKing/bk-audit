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

import os


class Empty:
    ...


def _kms_cache_value(key):
    """KMS 已注入的进程内凭据。

    当 `BKAPP_KMS_ENV_INJECTION=false`（env 不回写明文）时，密钥只存在于
    进程内凭据表 `_SECRETS_CACHE`，并不在 os.environ 中。此处作为 os.getenv
    缺失时的兜底来源。采用延迟导入，避免 settings 早期加载 config 时的循环依赖。
    """
    try:
        from core.kms import _SECRETS_CACHE
    except Exception:
        return None
    return _SECRETS_CACHE.get(key)


def get_env_or_raise(key):
    value = os.getenv(key, Empty)
    if value and value is not Empty:
        return value
    # 回落 KMS 凭据表：关闭 env 注入时，密钥仅存在于进程内缓存
    kms_value = _kms_cache_value(key)
    if kms_value:
        return kms_value
    raise RuntimeError(
        'Environment variable "{}" not found, you must set this variable to run this application.'.format(key)
    )
