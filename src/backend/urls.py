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

from bk_notice_sdk import config as bk_notice_config
from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from drf_yasg import openapi
from drf_yasg.views import get_schema_view

from core.permissions import SwaggerPermission, TokenSwaggerPermission

info = openapi.Info(title="Audit", default_version="v1", description="审计中心 API")
schema_view = get_schema_view(
    info,
    public=True,
    permission_classes=(SwaggerPermission,),
    url=settings.BK_BACKEND_URL,
)
token_schema_view = get_schema_view(info, public=True, permission_classes=(TokenSwaggerPermission,))

urlpatterns = [
    path("bkadmin/", admin.site.urls),
    path("account/", include("blueapps.account.urls")),
    path("api/v1/meta/", include("apps.meta.urls")),
    path("api/v1/iam/", include("apps.permission.urls")),
    path("api/v1/", include("apps.notice.urls")),
    path("api/v1/", include("apps.feature.urls")),
    path("api/v1/sops/", include("apps.sops.urls")),
    path("api/v1/itsm/", include("apps.itsm.urls")),
    # path("swagger/", schema_view.with_ui(), name="swagger-ui"),
    # path("swagger.json", login_exempt(token_schema_view.without_ui()), name="swagger-json"),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path("", include(f"services.{settings.DEPLOY_SERVICE}.urls")),
    path(f"api/v1/{bk_notice_config.ENTRANCE_URL}", include(("bk_notice_sdk.urls", "notice"), namespace="notice")),
]
