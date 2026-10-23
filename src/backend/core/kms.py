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
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

KMS 信封解密 + 凭据注入（开发侧 (b) 接入）

设计要点（详见 src/document/KMS/ 文档）：
1. 最小侵入：仅在 settings 加载最早期调用一次 `inject_kms_secrets()`，
   后续所有 `os.getenv(...)` 无感读到解密后的明文，业务零改动。
2. 可关闭：总开关 `BKAPP_KMS_ENABLED`（默认 false），关闭时本模块零副作用。
3. Fail-fast：开关开启但信封/私钥缺失、解密失败、明文非合法 JSON、
   凭证包 schema 校验不通过时，直接 `raise`，使进程启动失败（容器报错退出）。
4. 合规：禁止记录私钥、明文、完整信封；
   - 信封/私钥/明文在读取时登记到 `core.sensitive`；
   - 启动边界上的异常链被净化（清空原始 traceback，只保留脱敏后的原因）；
   - 未捕获异常出口由 `core.sensitive.install_redacted_excepthook` 兜底清洗。
5. 依赖 `bk-kms-sdk`（延迟导入），开关关闭时不会强依赖该 SDK。

凭证包 schema（一期冻结，见 `KMS_ALLOWED_SECRET_KEYS`）：
    { "secrets": { "环境变量名": "明文", ... } }
同时兼容信封解密后直接是扁平 map {环境变量名: 明文} 的形态。
- 只允许覆盖「密钥/凭据类」环境变量（白名单），拒绝控制项与任意键；
- 值只允许 str/int/float/bool，拒绝 None 与结构化值；
- 按启用功能校验必填项，缺失即拒绝启动，避免开关开启后仍静默使用旧明文配置。

明文落 env 的验收口径（一期）：
- 一期允许解密后的明文写入 `os.environ`（`BKAPP_KMS_ENV_INJECTION`，默认 true），
  因为 settings 与大量 `os.getenv` 依赖该通道，关闭会造成配置缺失；
- 同时始终写入进程内凭据表，新的取值点统一走 `get_secret()`；
- 残余风险：明文可被同进程读取、`/proc/<pid>/environ` 可见、
  会被未显式指定 env 的子进程继承；二期把 settings 的 `os.getenv` 收敛到
  `get_secret()` 后即可关闭 env 注入。
"""
import json
import os
import re
from pathlib import Path

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

# 允许由凭证包覆盖的环境变量（仅密钥/凭据类）
KMS_ALLOWED_SECRET_KEYS = frozenset(
    {
        "APP_TOKEN",
        "BKAPP_AI_AGENT_SECRET_KEY",
        "BKAPP_AI_AUDIT_REPORT_SECRET_KEY",
        "BKAPP_ALERT_ACCESS_TOKEN",
        "BKAPP_BKBASE_DATA_TOKEN",
        "BKAPP_FETCH_USER_INFO_TOKEN",
        "BKAPP_INIT_DORIS_CONFIG",
        "BKAPP_INIT_ES_CONFIG",
        "BKAPP_INIT_KAFKA_CONFIG",
        "BKAPP_INIT_REDIS_CONFIG",
        "BKAPP_LOG_EXPORT_STATUS_ACCESS_TOKEN",
        "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN",
        "BKPAAS_APP_SECRET",
        "MYSQL_PASSWORD",
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

# 功能开关 -> (开关未显式配置时是否视为开启, 开启时必须额外提供的密钥)
# 说明：仅对「开关打开就一定会被消费」的凭据设必填，一次性的初始化配置（BKAPP_INIT_*）保持可选，避免误杀合法部署。
KMS_FEATURE_REQUIRED_SECRETS = {
    "BKAPP_PLATFORM_AUTH_ENABLED": (True, ("BKAPP_PLATFORM_AUTH_ACCESS_TOKEN",)),
    "BKAPP_FEATURE_AI_CAPABILITY": (False, ("BKAPP_AI_AGENT_SECRET_KEY", "BKAPP_AI_AUDIT_REPORT_SECRET_KEY")),
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
    """读取 Base64 编码的 KMS 信封，优先从文件读取，env 兜底。"""
    path = os.getenv(KMS_ENVELOPE_PATH_KEY)
    envelope = ""
    if path:
        envelope = Path(path).read_text(encoding="utf-8").strip()
    if not envelope:
        raise ImproperlyConfigured("KMS 已开启但信封内容为空")
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


def _enabled_feature_required_keys() -> list:
    """按当前启用功能汇总必填密钥。"""
    required: list = list(KMS_BASE_REQUIRED_SECRETS)
    for switch, (default_on, keys) in KMS_FEATURE_REQUIRED_SECRETS.items():
        if _is_switch_on(switch, default_on):
            required.extend(keys)
    return required


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
            raise ImproperlyConfigured("KMS 凭证包包含不允许覆盖的环境变量: %s（仅允许密钥类环境变量）" % key)
        if value is None or not isinstance(value, KMS_ALLOWED_VALUE_TYPES):
            raise ImproperlyConfigured("KMS 凭证包中 %s 的值类型不被允许（仅允许字符串/数字/布尔）" % key)
        validated[key] = str(value)

    missing = [key for key in _enabled_feature_required_keys() if key not in validated]
    if missing:
        raise ImproperlyConfigured("KMS 凭证包缺少必需的密钥: %s" % ", ".join(sorted(set(missing))))

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
