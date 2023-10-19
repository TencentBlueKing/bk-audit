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

from bk_resource import resource
from bk_resource.settings import bk_resource_settings
from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.views import APIView

from services.web.entry.handler.healthz import HealthzHandler
from services.web.entry.throttlers import HealthzThrottle


class ViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.entry.home),
        ResourceRoute("GET", resource.entry.ping, endpoint="ping"),
        ResourceRoute("GET", resource.entry.logout, endpoint="logout"),
        ResourceRoute("GET", resource.entry.generate_watermark, endpoint="watermark"),
    ]


class I18nViewSet(ResourceViewSet):
    resource_routes = [ResourceRoute("GET", resource.entry.i18n, pk_field="language")]


class HealthzView(APIView):
    """
    健康监测
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = [HealthzThrottle]

    def get(self, request, *args, **kwargs):
        setattr(request, "user", get_user_model()(username=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME))
        return Response(HealthzHandler().healthz)
