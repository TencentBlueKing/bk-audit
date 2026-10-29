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
import json
import os
import re
from pathlib import Path
from typing import Optional

from django.core.exceptions import ImproperlyConfigured

from core.sensitive import (
    format_redacted_exception,
    register_sensitive,
    sanitize_exception,
    strip_traceback,
)

# 总开关：是否启用 KMS 信封解密注入
KMS_ENABLED_KEY = "BKAPP_KMS_ENABLED"
# 信封文件优先从环境变量指定的路径读取（避免明文落在环境变量中）
KMS_ENVELOPE_PATH_KEY = "BKAPP_KMS_ENVELOPE_PATH"
# 私钥内容（Base64 PEM），由运维以 Secret 注入，不是文件路径
KMS_PRIVATE_KEY_ENV_KEY = "BK_KMS_PRIVATE_KEY"
# 解密后 JSON 中承载「环境变量名 -> 明文」映射的根字段名
KMS_SECRETS_FIELD = "secrets"
# 是否把解密后的明文写入 os.environ（一期默认 true，兼容 os.getenv 取值）
KMS_ENV_INJECTION_KEY = "BKAPP_KMS_ENV_INJECTION"
# 白名单外追加允许的键（逗号分隔），用于灰度期临时放行新凭据
KMS_EXTRA_SECRET_KEYS_KEY = "BKAPP_KMS_EXTRA_SECRET_KEYS"

# 允许由凭证包覆盖的环境变量
KMS_ALLOWED_SECRET_KEYS = frozenset(
    {
        "APP_TOKEN",
        "BKAPP_AI_AGENT_SECRET_KEY",
        "BKAPP_AI_AUDIT_LOG_SEARCH_SECRET_KEY",
        "BKAPP_AI_AUDIT_REPORT_SECRET_KEY",
        "BKAPP_AI_USER_INTENT_SECRET_KEY",
        "BKAPP_ALERT_ACCESS_TOKEN",
        "BKAPP_BKBASE_DATA_TOKEN",
        "BKAPP_FETCH_USER_INFO_TOKEN",
        "BKAPP_INIT_DORIS_CONFIG",
        "BKAPP_INIT_ES_CONFIG",
        "BKAPP_INIT_KAFKA_CONFIG",
        "BKAPP_INIT_REDIS_CONFIG",
        "BKAPP_LOG_EXPORT_STATUS_ACCESS_TOKEN",
        "BKAPP_OTEL_BK_DATA_TOKEN",
        "BKAPP_OTEL_LOG_BK_DATA_TOKEN",
        "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN",
        "BKAPP_PLATFORM_AUTH_ACCESS_USERNAME",
        "BKPAAS_APP_ID",
        "BKPAAS_APP_SECRET",
        "BKREPO_PASSWORD",
        "MYSQL_PASSWORD",
        "MYSQL_USER",
        "RABBITMQ_PASSWORD",
        "RABBITMQ_USER",
        "REDIS_PASSWORD",
    }
)

# 明确禁止覆盖的键：KMS 自身控制项 + 部署控制项
KMS_FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "BKAPP_DEPLOY_SERVICE",
        "BKAPP_KMS_ENABLED",
        "BKAPP_KMS_ENVELOPE_PATH",
        "BKAPP_KMS_ENV_INJECTION",
        "BKAPP_KMS_EXTRA_SECRET_KEYS",
        "BK_KMS_PRIVATE_KEY",
        "DJANGO_SETTINGS_MODULE",
    }
)

# 基础必填：KMS 开启即必须随凭证包提供
KMS_BASE_REQUIRED_SECRETS = ("BKPAAS_APP_SECRET",)

# 与 config/default.py 中 PLATFORM_AUTH_ACCESS_USERNAME 的默认值保持一致（settings 侧兜底）
# 修改此处前请先同步 config/default.py，否则启动校验与运行期取值会不一致
DEFAULT_PLATFORM_AUTH_ACCESS_USERNAME = "admin"

# 功能开关 -> (开关未显式配置时是否视为开启, 额外必填的「凭据组」)
# 一次性的初始化配置（BKAPP_INIT_*）保持可选，避免误杀合法部署。
KMS_FEATURE_REQUIRED_SECRETS = {
    "BKAPP_PLATFORM_AUTH_ENABLED": (
        True,
        # 一个「凭据组」：token 或 username 任一有效即可
        [
            [
                ("BKAPP_PLATFORM_AUTH_ACCESS_TOKEN", ""),
                ("BKAPP_PLATFORM_AUTH_ACCESS_USERNAME", DEFAULT_PLATFORM_AUTH_ACCESS_USERNAME),
            ]
        ],
    ),
    "BKAPP_FEATURE_AI_CAPABILITY": (True, []),
}

# 视为「关闭」的开关取值
_SWITCH_OFF_VALUES = ("0", "false", "no", "off", "disabled", "unavailable", "")

# 允许的值类型：None / list / dict 一律拒绝（避免写出字符串 "None"）
KMS_ALLOWED_VALUE_TYPES = (str, int, float, bool)

_SECRET_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# 进程内凭据表：解密后的明文始终在此留存一份，供 get_secret() 取值
_SECRETS_CACHE: dict = {}


def is_kms_enabled() -> bool:
    """KMS 总开关是否开启。"""
    return str(os.getenv(KMS_ENABLED_KEY, "false")).lower() in ("1", "true", "yes", "on")


def _is_env_injection_enabled() -> bool:
    """是否把解密后的明文写入 os.environ（一期默认开启）。"""
    return str(os.getenv(KMS_ENV_INJECTION_KEY, "true")).lower() not in ("0", "false", "no", "off")


def _read_envelope() -> str:
    """读取 Base64 编码的 KMS 信封。"""
    path = os.getenv(KMS_ENVELOPE_PATH_KEY)
    if not path:
        raise ImproperlyConfigured("KMS 已开启但未配置信封文件路径 %s" % KMS_ENVELOPE_PATH_KEY)
    envelope = Path(path).read_text(encoding="utf-8").strip()
    if not envelope:
        raise ImproperlyConfigured("KMS 已开启但信封文件内容为空")
    register_sensitive(envelope)
    return envelope


def _read_private_key() -> str:
    """读取私钥内容（Base64 PEM），注意是私钥内容而非文件路径。"""
    key = os.getenv(KMS_PRIVATE_KEY_ENV_KEY)
    if not key:
        raise ImproperlyConfigured("KMS 已开启但未找到私钥 %s" % KMS_PRIVATE_KEY_ENV_KEY)
    key = key.strip()
    register_sensitive(key)
    return key


def _allowed_secret_keys() -> frozenset:
    """白名单 = 内置键 + 灰度期追加键。"""
    extra = os.getenv(KMS_EXTRA_SECRET_KEYS_KEY) or ""
    extra_keys = {item.strip() for item in extra.split(",") if item.strip()}
    return frozenset(KMS_ALLOWED_SECRET_KEYS | extra_keys)


def _is_switch_on(switch: str, default_on: bool) -> bool:
    """判断功能开关是否开启（兼容 strtobool 取值与 on/off 之外的自定义取值）。"""
    value = os.getenv(switch)
    if value is None:
        return default_on
    return str(value).strip().lower() not in _SWITCH_OFF_VALUES


def _effective_credential(key: str, default: Optional[str], validated: dict) -> str:
    """凭据的最终生效值：KMS 凭证包 -> 宿主环境变量 -> 运行期默认值。"""
    # KMS 凭证包优先；包内显式给空串等同于显式置空，不再继续回退
    if key in validated:
        return str(validated[key]).strip()
    if default is None:
        return ""
    # 宿主环境变量：区分「未设置」与「显式置空」，只有未设置才回退到运行期默认值
    env_value = os.getenv(key)
    if env_value is not None:
        return env_value.strip()
    return default


def _enabled_feature_required_groups() -> list:
    """按当前启用功能汇总必填「凭据组」：组内任意一个键的最终生效值非空即满足。"""
    # 基础必填不回退宿主环境变量：default=None 表示必须由凭证包提供
    groups: list = [((key, None),) for key in KMS_BASE_REQUIRED_SECRETS]
    for switch, (default_on, feature_groups) in KMS_FEATURE_REQUIRED_SECRETS.items():
        if _is_switch_on(switch, default_on):
            groups.extend(feature_groups)
    return groups


def _extract_secrets(data) -> dict:
    """从解密后的 JSON 中取出「环境变量名 -> 明文」映射。"""
    if not isinstance(data, dict):
        raise ImproperlyConfigured("KMS 信封解密后的内容不是合法的「环境变量名 -> 明文」映射")

    if KMS_SECRETS_FIELD in data:
        if set(data) != {KMS_SECRETS_FIELD}:
            raise ImproperlyConfigured("KMS 信封同时包含 %s 与其他字段，形态不合法" % KMS_SECRETS_FIELD)
        secrets = data[KMS_SECRETS_FIELD]
        if not isinstance(secrets, dict):
            raise ImproperlyConfigured("KMS 信封的 %s 字段不是「环境变量名 -> 明文」映射" % KMS_SECRETS_FIELD)
        return secrets

    return data


def validate_secrets(raw: dict) -> dict:
    """校验凭证包 schema：键白名单、值类型、按功能开关确定的必填项。

    校验错误只透出键名，不透出任何值。
    """
    if not isinstance(raw, dict) or not raw:
        raise ImproperlyConfigured("KMS 凭证包为空或不是「环境变量名 -> 明文」映射，拒绝启动")

    allowed_keys = _allowed_secret_keys()
    validated: dict = {}

    for key, value in raw.items():
        if not isinstance(key, str) or not _SECRET_KEY_PATTERN.match(key):
            raise ImproperlyConfigured("KMS 凭证包存在非法的环境变量名（仅允许大写字母、数字与下划线）")
        if key in KMS_FORBIDDEN_SECRET_KEYS:
            raise ImproperlyConfigured("KMS 凭证包不允许覆盖控制项环境变量: %s" % key)
        if key not in allowed_keys:
            raise ImproperlyConfigured("KMS 凭证包包含不在允许覆盖清单内的环境变量: %s" % key)
        if value is None or not isinstance(value, KMS_ALLOWED_VALUE_TYPES):
            raise ImproperlyConfigured("KMS 凭证包中 %s 的值类型不被允许（仅允许字符串/数字/布尔）" % key)
        validated[key] = str(value)

    missing = [
        " 或 ".join(key for key, _default in group)
        for group in _enabled_feature_required_groups()
        if not any(_effective_credential(key, default, validated) for key, default in group)
    ]
    if missing:
        raise ImproperlyConfigured("KMS 凭证包缺少必需的密钥: %s" % "; ".join(sorted(set(missing))))

    return validated


def load_kms_secrets() -> dict:
    """解密信封，返回 {环境变量名: 明文} 映射。"""
    from bk_kms import decrypt  # 延迟导入，避免开关关闭时也强依赖 SDK

    envelope = _read_envelope()
    private_key = _read_private_key()
    plaintext = None
    try:
        plaintext = decrypt(envelope=envelope, private_key=private_key)  # 失败抛 CryptoError
        register_sensitive(plaintext)
        data = json.loads(plaintext)  # 失败抛 JSONDecodeError
    except json.JSONDecodeError as err:
        # 异常对象自身持有整份明文正文，先清掉再向上抛
        err.doc = ""
        raise
    finally:
        # 无论成功失败，敏感值都不留在本帧的局部变量里
        plaintext = None
        envelope = None
        private_key = None

    return _extract_secrets(data)


def _load_validated_secrets() -> dict:
    """解密 + 校验，返回可直接注入的 {环境变量名: 明文}。"""
    raw = load_kms_secrets()
    try:
        return validate_secrets(raw)
    finally:
        raw = None


def get_secret(key: str, default=None):
    """读取凭据：优先取 KMS 解密后的进程内凭据，其次回落环境变量。

    新的取值点统一走这里，避免直接依赖 os.environ。
    """
    if key in _SECRETS_CACHE:
        return _SECRETS_CACHE[key]
    return os.getenv(key, default)


def get_secret_json(key: str, default=None):
    """读取 JSON 型凭据（如 BKAPP_INIT_ES_CONFIG），并把解析出的嵌套字段递归登记为敏感值。

    登记整段 JSON 字符串是不够的：`json.loads()` 之后再抛出的异常里，
    格式化器展示的是 dict 内容，整段 JSON 匹配不到其中的 password 等值。
    """
    raw = get_secret(key)
    if raw is None:
        if default is not None:
            return default
        raise ImproperlyConfigured("未找到 JSON 型凭据 %s" % key)
    # 解析前先登记整段明文：值可能来自宿主环境变量（未经 KMS 登记），
    # 一旦 json.loads 失败，本帧的 raw 与异常对象都会带着这段明文
    register_sensitive(raw)
    try:
        data = json.loads(raw)
    except Exception as err:
        # 覆盖 json.loads 的所有失败形态：JSONDecodeError（语法错误）、
        # RecursionError（深层嵌套）、ValueError / TypeError（类型异常）。
        # 明文不只在本帧：异常对象带整份 doc，json 库帧的局部变量 s 也携带原文，
        # 且 stackprinter 对长字符串会截断/换行，整串 scrub 匹配不到。
        # 因此与启动解密边界一致：清 doc -> 净化异常链 -> 抛脱敏异常。
        if getattr(err, "doc", None):
            err.doc = ""
        safe_cause = sanitize_exception(err)
        strip_traceback(err)
        del err
        raise ImproperlyConfigured("初始化 JSON 型凭据解析失败: %s" % safe_cause) from safe_cause
    finally:
        raw = None
    register_sensitive(data)
    return data


def _store_secrets(secrets: dict) -> None:
    """写入进程内凭据表；一期默认同步写入 os.environ（见模块 docstring 的验收口径）。"""
    register_sensitive(secrets)
    _SECRETS_CACHE.update(secrets)
    if not _is_env_injection_enabled():
        return
    for key, value in secrets.items():
        os.environ[key] = value


def inject_kms_secrets() -> None:
    """在 settings 加载早期调用：将解密后的密钥注入凭据表（一期同时注入 os.environ）。

    开关开启时，任何异常都会向上抛出，使进程启动失败（fail-fast）。
    """
    if not is_kms_enabled():
        return

    secrets = None
    try:
        secrets = _load_validated_secrets()
        _store_secrets(secrets)
    except Exception as err:
        # 只保留「错误类型 + 脱敏原因」：原始 traceback 的帧持有信封/私钥/明文，必须丢弃
        safe_cause = sanitize_exception(err)
        strip_traceback(err)
        del err
        raise ImproperlyConfigured("KMS 信封解密失败，应用拒绝启动: %s" % safe_cause) from safe_cause
    finally:
        secrets = None


def redact_startup_error(err: BaseException) -> str:
    """给启动失败日志使用的脱敏堆栈（不展开敏感局部变量与已登记明文）。"""
    return format_redacted_exception(err)
