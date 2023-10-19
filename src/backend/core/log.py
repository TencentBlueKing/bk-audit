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

import datetime
import logging
import os

import json_log_formatter
from django.conf import settings
from rest_framework.settings import api_settings


class JsonLogFormatter(json_log_formatter.JSONFormatter):
    """
    日志格式化器
    """

    def json_record(self, message: str, extra: dict, record: logging.LogRecord) -> dict:
        from blueapps.utils.request_provider import get_or_create_local_request_id

        # 移除request
        if "request" in extra:
            request = extra.pop("request")
            extra["username"] = request.user.username
        extra["request_id"] = get_or_create_local_request_id()
        extra["bk_app_code"] = settings.APP_CODE
        extra["bk_app_module"] = os.getenv("BKPAAS_APP_MODULE_NAME", "default")
        extra["bk_run_mode"] = settings.RUN_MODE
        extra["message"] = message
        extra["name"] = record.name
        extra["level"] = record.levelname
        extra["func"] = record.funcName
        extra["path"] = record.pathname
        extra["lineno"] = record.lineno
        extra["process"] = record.process
        extra["thread"] = record.thread
        if "time" not in extra:
            extra["time"] = datetime.datetime.now().strftime(api_settings.DATETIME_FORMAT)

        if record.exc_info:
            extra["exc_info"] = self.formatException(record.exc_info)

        return extra
