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

from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.utils.translation import gettext
from drf_yasg.utils import swagger_auto_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permission.handlers.permission import FetchInstancePermission
from services.puller.puller.serializers import (
    ResourceViewRequestSerializer,
    ResourceViewResponseSerializer,
)
from services.puller.puller.utils.fetch import (
    ActionFetchHandler,
    ResourceTypeFetchHandler,
)


class ResourcesView(APIView):
    """BKBASE反向拉取资源接口"""

    authentication_classes = []
    permission_classes = [
        FetchInstancePermission,
    ]

    @swagger_auto_schema(
        operation_summary="资源反向拉取",
        tags=["Resource"],
        request_body=ResourceViewRequestSerializer(),
        responses={
            200: bk_resource_settings.DEFAULT_STANDARD_RESPONSE_BUILDER(
                data_serializer=ResourceViewResponseSerializer(), name="puller.ResourcesView"
            ).serializer,
            500: bk_resource_settings.DEFAULT_ERROR_RESPONSE_SERIALIZER,
        },
    )
    def post(self, request, *args, **kwargs):
        method = request.data.get("method")
        try:
            handler = getattr(self, method)
            data = handler(request, *args, **kwargs)
            logger.info(
                f"[{self.__class__.__module__}.{self.__class__.__name__}] "
                f"RequestData => {json.dumps(request.data)}; "
                f"ResponseData => {json.dumps(data)}"
            )
            return Response(data)
        except AttributeError:
            logger.info(
                f"[{self.__class__.__module__}.{self.__class__.__name__}] "
                f"RequestData => {json.dumps(request.data)}; "
                f"ResponseData => {NotImplementedError.__name__}"
            )
            raise NotImplementedError(f"{gettext('未实现方法')} => {method}")

    def fetch_instance_list(self, request, *args, **kwargs):
        type_name = request.data.get("type")
        if type_name == "resource_type":
            return self.get_data(ResourceTypeFetchHandler, request)
        if type_name == "action":
            return self.get_data(ActionFetchHandler, request)
        raise NotImplementedError(f"{gettext('未实现类型')} => {type_name}")

    def fetch_resource_type_schema(self, request, *args, **kwargs):
        type_name = request.data.get("type")
        if type_name == "resource_type":
            return self.get_schema(ResourceTypeFetchHandler, request)
        if type_name == "action":
            return self.get_schema(ActionFetchHandler, request)
        raise NotImplementedError(f"{gettext('未实现类型')} => {type_name}")

    def get_data(self, fetch_handler, request):
        serializer = ResourceViewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        filter_data = data.get("filter", {})
        return fetch_handler(
            filter_data.get("start_time"), filter_data.get("end_time"), data.get("page")
        ).fetch_instance_list()

    def get_schema(self, fetch_handler, request):
        return {"type": "object", "properties": fetch_handler.get_schema()}
