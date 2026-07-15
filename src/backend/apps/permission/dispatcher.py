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
from django.http import JsonResponse
from iam.contrib.django.dispatcher import (
    DjangoBasicResourceApiDispatcher,
    InvalidPageException,
)
from iam.contrib.django.dispatcher.dispatchers import fail_response, success_response
from iam.contrib.django.dispatcher.exceptions import KeywordTooShortException
from iam.resource.utils import get_filter_obj, get_page_obj

from apps.permission.handlers.backends import is_iam_v4_backend

RESOURCE_CALLBACK_PROTOCOL_V3 = "v3"
RESOURCE_CALLBACK_PROTOCOL_V4 = "v4"


class BkAuditResourceApiDispatcher(DjangoBasicResourceApiDispatcher):
    @staticmethod
    def _normalize_resource_type(data: dict) -> str | None:
        return data.get("type") or data.get("resource_type_id") or data.get("resource_type")

    @staticmethod
    def _is_v4_page(page: dict) -> bool:
        return isinstance(page, dict) and ("page" in page or "page_size" in page)

    @staticmethod
    def _normalize_v4_page(page: dict) -> dict:
        try:
            page_index = int(page["page"])
            page_size = int(page["page_size"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("page and page_size must be positive integers")

        if page_index <= 0 or page_size <= 0:
            raise ValueError("page and page_size must be positive integers")

        return {
            **page,
            "limit": page_size,
            "offset": (page_index - 1) * page_size,
        }

    @staticmethod
    def _get_protocol() -> str:
        """Return callback response protocol from IAM backend config only."""
        return RESOURCE_CALLBACK_PROTOCOL_V4 if is_iam_v4_backend() else RESOURCE_CALLBACK_PROTOCOL_V3

    def _normalize_request_data(self, data: dict, protocol: str) -> dict:
        """Adapt IAM V4 callback fields to the legacy SDK dispatcher/provider contract."""
        if protocol != RESOURCE_CALLBACK_PROTOCOL_V4:
            return data

        page = data.get("page")
        if self._is_v4_page(page):
            data["page"] = self._normalize_v4_page(page)

        if data.get("method") == "fetch_instance_info" and "requires" in data:
            filters = dict(data.get("filter") or {})
            filters.setdefault("attrs", data.get("requires") or [])
            data["filter"] = filters

        filters = data.get("filter") or {}
        if data.get("method") == "list_instance" and isinstance(filters, dict) and "keyword" in filters:
            data["_use_v4_keyword_search"] = True

        return data

    def _format_response(self, response: JsonResponse, protocol: str) -> JsonResponse:
        if protocol != RESOURCE_CALLBACK_PROTOCOL_V4:
            return response

        try:
            payload = json.loads(response.content)
        except Exception:  # NOCC:broad-except(兼容异常响应)
            return response

        request_id = response.get("X-Request-Id", "")
        if payload.get("result") is False:
            code = payload.get("code") or response.status_code
            status = code if isinstance(code, int) and 400 <= code <= 599 else 400
            formatted = JsonResponse(
                {"error": {"code": str(code), "message": payload.get("message", "")}},
                status=status,
            )
        else:
            formatted = JsonResponse({"data": payload.get("data")}, status=response.status_code)

        formatted["X-Request-Id"] = request_id
        return formatted

    def _fail_response(self, code: int, message: str, request_id: str, protocol: str) -> JsonResponse:
        return self._format_response(fail_response(code, message, request_id), protocol)

    def _dispatch(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID", "")

        try:
            data = json.loads(request.body)
        except Exception:  # NOCC:broad-except(需要处理所有错误)
            data = None

        protocol = self._get_protocol()

        # auth check
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        auth_allowed = self.iam.is_basic_auth_allowed(self.system, auth)

        if not auth_allowed:
            logger.error("resource request(%s) auth failed with auth param: %s", request_id, auth)
            return self._fail_response(401, "basic auth failed", request_id, protocol)

        if data is None:
            logger.error("resource request(%s) failed with invalid body: %s", request_id, request.body)
            return self._fail_response(400, "reqeust body is not a valid json", request_id, protocol)

        # check basic params
        method = data.get("method")
        resource_type = self._normalize_resource_type(data)
        if not (method and resource_type):
            logger.error(
                "resource request(%s) failed with invalid data: %s. method and resource type required",
                request_id,
                data,
            )
            return self._fail_response(400, "method and resource type is required field", request_id, protocol)

        # check resource type
        if resource_type not in self._provider:
            logger.error("resource request(%s) failed with unsupported resource type: %s", request_id, resource_type)
            return self._fail_response(404, "unsupported resource type: {}".format(resource_type), request_id, protocol)

        data["type"] = resource_type
        try:
            data = self._normalize_request_data(data, protocol)
        except (TypeError, ValueError) as e:
            logger.error("resource request(%s) failed with invalid page: %s", request_id, data.get("page"))
            return self._fail_response(400, "invalid page: {}".format(e), request_id, protocol)

        # check method and process
        processor = getattr(self, "_dispatch_{}".format(method), None)
        if not processor:
            logger.error("resource request(%s) failed with unsupported method: %s", request_id, method)
            return self._fail_response(404, "unsupported method: {}".format(method), request_id, protocol)

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

        response = self._format_response(response, protocol)

        logger.info(
            f"[IAMResource] RequestData => {data}; "
            f"ResponseData => {response.content.decode('utf-8')}; "
            f"RequestID => {request_id}"
        )
        return response

    def _dispatch_list_instance(self, request, data, request_id):
        if data.pop("_use_v4_keyword_search", False):
            return self._dispatch_v4_keyword_search(request, data, request_id)
        return super()._dispatch_list_instance(request, data, request_id)

    def _dispatch_v4_keyword_search(self, request, data: dict, request_id: str) -> JsonResponse:
        options = self._get_options(request)
        filter_obj = get_filter_obj(data.get("filter"), ["parent", "keyword"])
        page_obj = get_page_obj(data.get("page"))
        provider = self._provider[data["type"]]

        pre_process = getattr(provider, "pre_search_instance", None)
        if pre_process and callable(pre_process):
            pre_process(filter_obj, page_obj, **options)

        filter_search_function = getattr(provider, "filter_search_instance_results", None)
        if filter_search_function and callable(filter_search_function):
            parent = filter_obj.parent
            parent_id = parent["id"] if parent else None
            resource_type = parent["type"] if parent else None
            results, count = filter_search_function(parent_id, resource_type, filter_obj.keyword, page_obj)
            return success_response({"count": count, "results": results}, request_id)

        search_function = getattr(provider, "search_instance", None)
        if not (search_function and callable(search_function)):
            return fail_response(404, "resource type: {} not support search instance".format(data["type"]), request_id)

        result = provider.search_instance(filter_obj, page_obj, **options)
        return success_response(result.to_dict(), request_id)
