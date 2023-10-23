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

from blueapps.utils.logger import logger
from iam.contrib.django.dispatcher import (
    DjangoBasicResourceApiDispatcher,
    InvalidPageException,
)
from iam.contrib.django.dispatcher.dispatchers import fail_response
from iam.contrib.django.dispatcher.exceptions import KeywordTooShortException


class BkAuditResourceApiDispatcher(DjangoBasicResourceApiDispatcher):
    def _dispatch(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID", "")

        # auth check
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        auth_allowed = self.iam.is_basic_auth_allowed(self.system, auth)

        if not auth_allowed:
            logger.error("resource request(%s) auth failed with auth param: %s", request_id, auth)
            return fail_response(401, "basic auth failed", request_id)

        try:
            data = json.loads(request.body)
        except Exception:  # NOCC:broad-except(需要处理所有错误)
            logger.error("resource request(%s) failed with invalid body: %s", request_id, request.body)
            return fail_response(400, "reqeust body is not a valid json", request_id)

        # check basic params
        method = data.get("method")
        resource_type = data.get("type")
        if not (method and resource_type):
            logger.error(
                "resource request(%s) failed with invalid data: %s. method and type required", request_id, data
            )
            return fail_response(400, "method and type is required field", request_id)

        # check resource type
        if resource_type not in self._provider:
            logger.error("resource request(%s) failed with unsupported resource type: %s", request_id, resource_type)
            return fail_response(404, "unsupported resource type: {}".format(resource_type), request_id)

        # check method and process
        processor = getattr(self, "_dispatch_{}".format(method), None)
        if not processor:
            logger.error("resource request(%s) failed with unsupported method: %s", request_id, method)
            return fail_response(404, "unsupported method: {}".format(method), request_id)

        logger.info("resource request(%s) with filter: %s, page: %s", request_id, data.get("filter"), data.get("page"))
        try:
            response = processor(request, data, request_id)
        except InvalidPageException as e:
            response = fail_response(422, str(e), request_id)
        except KeywordTooShortException as e:
            response = fail_response(406, str(e), request_id)
        except Exception as e:  # NOCC:broad-except(需要处理所有错误)
            logger.exception("resource request(%s) failed with exception: %s", request_id, e)
            response = fail_response(500, str(e), request_id)

        logger.info(
            f"[IAMResource] RequestData => {data}; "
            f"ResponseData => {response.content.decode('utf-8')}; "
            f"RequestID => {request_id}"
        )
        return response
