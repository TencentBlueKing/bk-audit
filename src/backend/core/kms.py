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
import copy
import json
import logging
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

logger = logging.getLogger(__name__)

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


# 凭据格式（分类 -> 实例 -> 字段 多层 JSON）-> 扁平「环境变量名 -> 明文」映射
# 顶层分类键（小写）；与扁平 env 形式（全大写）互斥，用于识别信封形态。
_DOCUMENT_CATEGORIES = frozenset(
    {
        "bkapp_id_secret",
        "mysql",
        "rabbitmq",
        "redis",
        "elasticsearch",
        "doris",
        "platform",
        "bkbase",
        "telemetry",
        "ai",
        "tokens",
        "bkrepo",
    }
)

# 初始化配置基底模板：仅在 Chart 未注入 BKAPP_INIT_*_CONFIG 时兜底（非敏感占位）
# 正常路径是「合并」：Chart 提供域名/端口/集群名/保留策略等非敏感字段，凭据包只覆盖 auth 字段。
# 用模板重建会把这些字段清空（domain_name 为空、port 为 0），初始化必然失败。
_INIT_ES_TEMPLATE = [
    {
        "namespace": "default",
        "cluster_name": "",
        "bkbase_cluster_en_name": "",
        "domain_name": "",
        "source_type": "",
        "port": "0",
        "schema": "http",
        "auth_info": {"username": "", "password": ""},
        "enable_hot_warm": False,
        "hot_attr_name": "",
        "hot_attr_value": "",
        "warm_attr_name": "",
        "warm_attr_value": "",
        "setup_config": {
            "retention_days_max": 14,
            "retention_days_default": 7,
            "number_of_replicas_max": 1,
            "number_of_replicas_default": 1,
        },
        "admin": [],
        "description": "",
    }
]
_INIT_REDIS_TEMPLATE = [
    {
        "namespace": "default",
        "redis_name_en": "",
        "redis_name": "",
        "connection_info": {
            "enable_sentinel": False,
            "name_sentinel": "",
            "host_sentinel": "",
            "port_sentinel": 0,
            "host": "",
            "port": 0,
            "password": "",
        },
        "version": "",
    }
]
_INIT_DORIS_TEMPLATE = [
    {
        "cluster_name": "",
        "auth_info": {"username": "", "password": ""},
        # 必须为 True：SystemInitHandler._init_doris 对非预定义集群直接抛 ParamsNotValid
        "pre_defined": True,
        "pre_defined_extra_config": {},
    }
]


def _is_document_shape(data) -> bool:
    """识别信封是否为多层分类 JSON"""
    return isinstance(data, dict) and bool(_DOCUMENT_CATEGORIES & set(data))


def _dig(data, *path, default=None):
    """按路径安全取值：任一中间层缺失即返回 default。"""
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _deep_set(node, path, value) -> None:
    """按路径写入嵌套 dict（路径尾端赋值）。"""
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value


# 初始化凭据字段 -> 配置元素内的嵌套路径
_INIT_AUTH_FIELD_MAP = {"username": ("auth_info", "username"), "password": ("auth_info", "password")}
_INIT_REDIS_FIELD_MAP = {"password": ("connection_info", "password")}
# 初始化配置的默认实例键：对应 Chart 配置数组的第一个元素
_INIT_DEFAULT_INSTANCE_KEY = "default"


def _load_env_init_config(key: str) -> Optional[list]:
    """读取 Chart 已注入的初始化配置（JSON 数组）。

    None 表示未注入，按模板兜底；[] 表示已注入但不可用，此时不覆盖原值。
    """
    raw = os.getenv(key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        logger.warning("[KMS] %s 不是合法 JSON，跳过凭据合并，保留原值", key)
        return []
    if not isinstance(data, list):
        logger.warning("[KMS] %s 不是配置数组，跳过凭据合并，保留原值", key)
        return []
    return data


def _parse_init_instance_key(instance_key: str):
    """初始化凭据的实例键解析：default -> (0, None)；default__<cluster> -> (None, cluster)。"""
    if instance_key == _INIT_DEFAULT_INSTANCE_KEY:
        return 0, None
    _, sep, cluster_name = instance_key.partition("__")
    if sep and cluster_name:
        return None, cluster_name
    return 0, None


def _instance_creds(raw: dict, category: str) -> dict:
    """取某分类下的实例凭据：{实例键: {字段: 值}}，忽略空实例。"""
    instances = raw.get(category) if isinstance(raw, dict) else None
    if not isinstance(instances, dict):
        return {}
    return {key: value for key, value in instances.items() if isinstance(value, dict) and value}


def _merge_init_config(instances: dict, template: list, field_map: dict, key: str) -> Optional[str]:
    """把凭据字段合并进 Chart 提供的初始化配置，返回整串 JSON。

    关键约束：只覆盖 auth 类字段，域名/端口/集群名/保留策略等非敏感字段必须原样保留；
    否则初始化会拿着空地址去建集群。未匹配到配置元素的实例按模板追加。
    """
    configs = _load_env_init_config(key)
    if configs is None:
        logger.warning("[KMS] 未找到 %s，按内置模板兜底，非敏感字段需由部署侧确认", key)
        # 兜底时按凭据里的实例逐个新建，避免留下一个没有域名的空白骨架元素
        merged: list = []
    elif not configs:
        return None
    else:
        merged = copy.deepcopy(configs)

    for instance_key, creds in instances.items():
        index, cluster_name = _parse_init_instance_key(instance_key)
        target = None
        if cluster_name is not None:
            target = next(
                (item for item in merged if isinstance(item, dict) and item.get("cluster_name") == cluster_name), None
            )
        elif index < len(merged) and isinstance(merged[index], dict):
            target = merged[index]
        if target is None:
            target = copy.deepcopy(template[0])
            if cluster_name:
                target["cluster_name"] = cluster_name
            merged.append(target)
        for src_field, dst_path in field_map.items():
            value = creds.get(src_field)
            if value in (None, ""):
                continue
            _deep_set(target, list(dst_path), value)
    return json.dumps(merged, ensure_ascii=False)


def _warn_unknown_categories(raw: dict) -> None:
    """文档形态下未识别的分类键会被忽略，留一条不含任何键名的告警。

    键名同样来自解密后的凭据声明，落日志会被判定为敏感信息明文输出
    （CodeQL py/clear-text-logging-sensitive-data），因此只提示「存在」，不输出键名与值。
    """
    if not any(key not in _DOCUMENT_CATEGORIES for key in raw):
        return
    logger.warning("[KMS] 凭据声明中存在未识别的分类键，相关凭据已忽略；请对照录入模板核对分类名")


def _transform_document_bundle(raw: dict) -> dict:
    """集中补齐「多层 JSON -> 扁平 env」的转换，及其初始化配置的合成/合并。"""
    _warn_unknown_categories(raw)
    secrets: dict = {}

    # --- 运行时业务凭据：分类.实例.字段 -> env 名 ---
    bkapp = _dig(raw, "bkapp_id_secret", "default", default={}) or {}
    if "app_code" in bkapp:
        secrets["BKPAAS_APP_ID"] = bkapp["app_code"]
    if "app_secret" in bkapp:
        secrets["BKPAAS_APP_SECRET"] = bkapp["app_secret"]

    mysql = _dig(raw, "mysql", "default", default={}) or {}
    if "username" in mysql:
        secrets["MYSQL_USER"] = mysql["username"]
    if "password" in mysql:
        secrets["MYSQL_PASSWORD"] = mysql["password"]

    rabbitmq = _dig(raw, "rabbitmq", "default", default={}) or {}
    if "username" in rabbitmq:
        secrets["RABBITMQ_USER"] = rabbitmq["username"]
    if "password" in rabbitmq:
        secrets["RABBITMQ_PASSWORD"] = rabbitmq["password"]

    # redis.default：应用缓存 Redis，对应 BK_REDIS 缓存连接。
    redis_default = _dig(raw, "redis", "default", default={}) or {}
    if "password" in redis_default:
        secrets["REDIS_PASSWORD"] = redis_default["password"]

    platform = _dig(raw, "platform", "default", default={}) or {}
    if "username" in platform:
        secrets["BKAPP_PLATFORM_AUTH_ACCESS_USERNAME"] = platform["username"]
    if "access_token" in platform:
        secrets["BKAPP_PLATFORM_AUTH_ACCESS_TOKEN"] = platform["access_token"]

    bkbase = _dig(raw, "bkbase", "default", default={}) or {}
    if "token" in bkbase:
        secrets["BKAPP_BKBASE_DATA_TOKEN"] = bkbase["token"]

    trace = _dig(raw, "telemetry", "trace", default={}) or {}
    if "token" in trace:
        secrets["BKAPP_OTEL_BK_DATA_TOKEN"] = trace["token"]
    audit_log = _dig(raw, "telemetry", "audit_log", default={}) or {}
    if "token" in audit_log:
        secrets["BKAPP_OTEL_LOG_BK_DATA_TOKEN"] = audit_log["token"]

    ai = _dig(raw, "ai", default={}) or {}
    if isinstance(ai, dict):
        if "audit_log_search" in ai and isinstance(ai["audit_log_search"], dict):
            secrets["BKAPP_AI_AUDIT_LOG_SEARCH_SECRET_KEY"] = ai["audit_log_search"].get("secret_key", "")
        if "user_intent" in ai and isinstance(ai["user_intent"], dict):
            secrets["BKAPP_AI_USER_INTENT_SECRET_KEY"] = ai["user_intent"].get("secret_key", "")

    tokens = _dig(raw, "tokens", default={}) or {}
    if isinstance(tokens, dict):
        if "alert" in tokens and isinstance(tokens["alert"], dict):
            secrets["BKAPP_ALERT_ACCESS_TOKEN"] = tokens["alert"].get("token", "")
        if "log_export_status" in tokens and isinstance(tokens["log_export_status"], dict):
            secrets["BKAPP_LOG_EXPORT_STATUS_ACCESS_TOKEN"] = tokens["log_export_status"].get("token", "")

    bkrepo = _dig(raw, "bkrepo", "default", default={}) or {}
    if "password" in bkrepo:
        secrets["BKREPO_PASSWORD"] = bkrepo["password"]

    # --- 初始化链路凭据：只覆盖 auth 字段，合并进 Chart 已注入的 *CONFIG ---
    # 实例键：default -> 配置数组第一个元素；default__<cluster_name> -> 按 cluster_name 匹配
    es_instances = _instance_creds(raw, "elasticsearch")
    if es_instances:
        es_config = _merge_init_config(es_instances, _INIT_ES_TEMPLATE, _INIT_AUTH_FIELD_MAP, "BKAPP_INIT_ES_CONFIG")
        if es_config is not None:
            secrets["BKAPP_INIT_ES_CONFIG"] = es_config

    doris_instances = _instance_creds(raw, "doris")
    if doris_instances:
        doris_config = _merge_init_config(
            doris_instances, _INIT_DORIS_TEMPLATE, _INIT_AUTH_FIELD_MAP, "BKAPP_INIT_DORIS_CONFIG"
        )
        if doris_config is not None:
            secrets["BKAPP_INIT_DORIS_CONFIG"] = doris_config

    # redis.init：初始化登记时使用的「存储」Redis，与上方 redis.default（应用缓存）
    # 是两个独立实例、用途互斥，故从 redis.init 单独取密码，合并进 BKAPP_INIT_REDIS_CONFIG，绝不与应用缓存共用。
    redis_init = _dig(raw, "redis", "init", default={}) or {}
    if isinstance(redis_init, dict) and redis_init:
        redis_config = _merge_init_config(
            {_INIT_DEFAULT_INSTANCE_KEY: redis_init},
            _INIT_REDIS_TEMPLATE,
            _INIT_REDIS_FIELD_MAP,
            "BKAPP_INIT_REDIS_CONFIG",
        )
        if redis_config is not None:
            secrets["BKAPP_INIT_REDIS_CONFIG"] = redis_config

    return secrets


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

    extracted = _extract_secrets(data)
    # 凭据格式（多层分类 JSON）需转换为扁平 env 映射；扁平格式原样通过。
    if _is_document_shape(extracted):
        return _transform_document_bundle(extracted)
    return extracted


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
