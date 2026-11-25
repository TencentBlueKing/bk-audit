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
import json
import logging
import re
import traceback as traceback_module

from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_or_create_local_request_id

from core.sensitive import REDACTED, redact_secrets


class RedactedRequestLogMixin:
    """关闭框架明文请求日志，改为自记录脱敏完整日志（BKSEC 1578945）。

    适用于请求体或响应体含凭据（password/token 等）的 Resource：
    - support_data_collect=False 关闭 bk_resource 框架 RequestLogHandler 的明文落盘；
    - 成功路径：request() 按 core.sensitive 键名口径自记录完整请求/响应（仅敏感值 ***），
      排障上下文（host/port/名称/版本）全保留；
    - 失败路径：只记录受控字段（脱敏请求体 + 异常类型 + 错误码 + 请求 ID），
      不落 str(err) 自由文本——上游错误文本可能携带未登记凭据，键名脱敏不可靠（评审 P1）。
    使用方式：置于继承链首位，如 class XxxResource(RedactedRequestLogMixin, BaseResource)。
    """

    support_data_collect = False

    def request(self, request_data=None, **kwargs):
        """脱敏版请求日志：完整保留排障上下文，仅敏感键名值打码"""
        # viewset（request_data 传入）与直调（**kwargs）两种入口归一化
        log_request_data = request_data if request_data is not None else kwargs
        try:
            response_data = super().request(request_data=request_data, **kwargs)
        except Exception as err:
            self._log_failure(log_request_data, err)
            raise
        self._log_redacted(log_request_data, response_data)
        return response_data

    def _log_redacted(self, request_data, response_data):
        logger.info(
            "[ResourceRequestLog][Redacted]\nResource => %s.%s\nRequestData => %s\nResponseData => %s",
            self.__module__,
            self.__class__.__name__,
            json.dumps(redact_secrets(request_data), ensure_ascii=False, default=str),
            json.dumps(redact_secrets(response_data), ensure_ascii=False, default=str),
        )

    def _log_failure(self, request_data, err):
        """失败日志只记录受控字段：异常消息自由文本可能携带未登记凭据，不做键名脱敏"""
        logger.info(
            "[ResourceRequestLog][Redacted][Failed]\nResource => %s.%s\nRequestID => %s\n"
            "Exception => %s\nCode => %s\nRequestData => %s",
            self.__module__,
            self.__class__.__name__,
            get_or_create_local_request_id(),
            type(err).__name__,
            getattr(err, "code", None) or getattr(err, "ERROR_CODE", "") or "",
            json.dumps(redact_secrets(request_data), ensure_ascii=False, default=str),
        )


# 自由文本凭据形态：password=xxx / "password": "xxx" / token: xxx 等（BKSEC 1578945 SDK 残余平替）
FREE_TEXT_SECRET_PATTERN = re.compile(
    r"(?i)[\"']?(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential)[\"']?\s*[=:]\s*"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;&，；\)）】>]+)"
)


def redact_free_text(text: str) -> str:
    """自由文本凭据打码：匹配 key=value / key: value / "key": "value" 形态的疑似凭据片段"""
    return FREE_TEXT_SECRET_PATTERN.sub(lambda m: "{}={}".format(m.group(1), REDACTED), text)


class BkResourceLogRedactionFilter(logging.Filter):
    """bk_resource SDK 失败日志脱敏平替（BKSEC 1578945 SDK 残余）。

    锁定依赖 bk-resource==0.4.11 在异常到达应用层 mixin 前打印上游错误原文
    （contrib/api.py L150/L188/L194/L218-224），不受 support_data_collect 控制、
    资源层无法拦截。本过滤器对 bk_resource logger 的消息文本与异常 traceback
    做疑似凭据打码，日志上下文（错误消息/URL/traceback）完整保留；SDK 修复后可移除。
    """

    def filter(self, record):
        try:
            message = record.getMessage()
            redacted = redact_free_text(message)
            if redacted != message:
                record.msg = redacted
                record.args = None
            if record.exc_info:
                exc_text = "".join(traceback_module.format_exception(*record.exc_info))
                redacted_exc_text = redact_free_text(exc_text)
                if redacted_exc_text != exc_text:
                    # 仅当 traceback 含疑似凭据时替换（formatter 优先使用 exc_text，输出等价）
                    record.exc_text = redacted_exc_text
                    record.exc_info = None
        except Exception:  # NOCC:broad-except(脱敏失败不得阻断日志记录)
            pass
        return True


def install_bk_resource_log_redaction():
    """幂等安装 SDK 日志脱敏过滤器（模块加载即生效，SDK 修复版本后可移除）"""
    bk_logger = logging.getLogger("bk_resource")
    if not any(isinstance(f, BkResourceLogRedactionFilter) for f in bk_logger.filters):
        bk_logger.addFilter(BkResourceLogRedactionFilter())


install_bk_resource_log_redaction()
