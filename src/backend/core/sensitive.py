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

敏感信息脱敏工具（KMS 启动边界 + 全局异常出口）

设计要点：
1. 登记制：信封 / 私钥 / 解密后明文在读取时登记，
   之后任何写往 stderr、日志、异常文案的文本都经过 `scrub()` 清洗。
2. 异常链净化：`sanitize_exception()` 把原始异常压成「类型 + 脱敏原因」的副本，
   并清空原始异常的 `__traceback__`（其中每个帧都持有敏感局部变量），
   使 `stackprinter` / `traceback` 等格式化器无从打印明文。
3. 格式化器收敛：`install_redacted_excepthook()` 在保留详细堆栈的同时，
   屏蔽敏感变量名与 KMS 相关源文件，输出前再整体清洗一遍。
"""
import re
import sys
import threading
import traceback
from typing import Any, Iterable, Optional, Set

# 脱敏占位符
REDACTED = "***"
# 过短的值不做登记，避免把 "1"、"true" 之类的短串替换成 *** 造成噪音
MIN_REDACT_LENGTH = 8

# 结构化敏感片段（PEM 私钥等）：即便漏登记也能兜底识别
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"),
)

# 变量名正则：命中即不打印变量内容（stackprinter 侧同时避免对变量求值）
SENSITIVE_VAR_PATTERNS = (
    r".*password.*",
    r".*passwd.*",
    r".*secret.*",
    r".*token.*",
    r".*private_key.*",
    r".*_key$",
    r"envelope",
    r"plaintext",
    r"ciphertext",
    r"signature",
    r"secrets",
)

# 敏感源文件：这些文件的帧不展开局部变量
SENSITIVE_SOURCE_PATH_PATTERNS = (
    r".*[\\/]core[\\/]kms\.py",
    r".*[\\/]core[\\/]sensitive\.py",
)

_sensitive_values: Set[str] = set()


def register_sensitive(*values: Any) -> None:
    """登记敏感值：信封、私钥、解密后明文、以及解密后的业务凭据明文。"""
    for value in values:
        if isinstance(value, str):
            if len(value) >= MIN_REDACT_LENGTH:
                _sensitive_values.add(value)
        elif isinstance(value, dict):
            register_sensitive(*list(value.values()))
        elif isinstance(value, (list, tuple, set)):
            register_sensitive(*list(value))


def clear_sensitive() -> None:
    """清空登记表（仅用于测试隔离）。"""
    _sensitive_values.clear()


def registered_sensitive() -> Set[str]:
    """返回当前登记的敏感值（测试用）。"""
    return set(_sensitive_values)


def scrub(text: Any, extra_values: Optional[Iterable[Any]] = None) -> str:
    """把文本中已登记的敏感值替换为占位符。"""
    result = str(text)
    for value in sorted(_sensitive_values, key=len, reverse=True):
        result = result.replace(value, REDACTED)
    for value in extra_values or ():
        if isinstance(value, str) and len(value) >= MIN_REDACT_LENGTH:
            result = result.replace(value, REDACTED)
    for pattern in SENSITIVE_TEXT_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


def strip_traceback(err: BaseException) -> BaseException:
    """清空异常的 traceback：帧上的敏感局部变量随之不可达。"""
    err.__traceback__ = None
    return err


def sanitize_exception(err: BaseException, max_length: int = 200) -> RuntimeError:
    """把异常压成「类型 + 脱敏原因」的副本，供 `raise ... from` 使用。

    - 副本不带 traceback，格式化器不会回溯到持有敏感局部变量的帧；
    - 副本的原因文案经过 `scrub()` 清洗并截断，避免明文被异常消息带出。
    """
    reason = scrub("{}: {}".format(type(err).__name__, str(err)))[:max_length]
    safe_err = RuntimeError(reason)
    safe_err.__traceback__ = None
    return safe_err


def format_redacted_exception(err: BaseException) -> str:
    """按标准 traceback 格式化并清洗（不展开敏感值）。"""
    return scrub("".join(traceback.format_exception(type(err), err, err.__traceback__)))


def _format_exc_tuple(exc_tuple, style: str, extra_paths: Iterable[str]) -> str:
    try:
        import stackprinter
    except ImportError:  # pragma: no cover - stackprinter 缺失时回落标准 traceback
        return "".join(traceback.format_exception(*exc_tuple))

    suppressed_paths = list(SENSITIVE_SOURCE_PATH_PATTERNS) + list(extra_paths or ())
    try:
        return stackprinter.format(
            exc_tuple,
            style=style,
            suppressed_vars=list(SENSITIVE_VAR_PATTERNS),
            suppressed_paths=suppressed_paths,
        )
    except Exception:  # pragma: no cover - 格式化器自身异常不得吞掉告警
        return "".join(traceback.format_exception(*exc_tuple))


def install_redacted_excepthook(style: str = "plaintext", extra_paths: Optional[Iterable[str]] = None) -> bool:
    """安装脱敏版 excepthook，替代 `stackprinter.set_excepthook()`。

    保留 stackprinter 的详细堆栈，但：
    - 命中 `SENSITIVE_VAR_PATTERNS` 的变量不打印内容；
    - KMS 相关源文件的帧不展开局部变量；
    - 输出前统一 `scrub()`，把已登记的明文替换成占位符。
    """
    extra_paths = tuple(extra_paths or ())

    def _write(exc_tuple) -> None:
        sys.stderr.write(scrub(_format_exc_tuple(exc_tuple, style, extra_paths)))

    def excepthook(etype, value, tb) -> None:
        _write((etype, value, tb))

    def threading_excepthook(args) -> None:
        _write((args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = threading_excepthook
    return True
