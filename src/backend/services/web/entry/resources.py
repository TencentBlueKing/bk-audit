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

import abc

from bk_resource import api
from blueapps.utils.request_provider import get_local_request, get_request_username
from django.conf import settings
from django.contrib import auth
from django.utils.translation import gettext_lazy
from django.views.i18n import LANGUAGE_QUERY_PARAMETER
from rest_framework import serializers
from rest_framework.response import Response

from apps.audit.resources import AuditMixinResource
from apps.exceptions import LangCodeError
from services.web.entry.handler.entry import EntryHandler, WatermarkFeature
from services.web.entry.serializers import HomeResponseSerializer


class EntryMeta(AuditMixinResource, abc.ABC):
    tags = ["Entry"]


class HomeResource(EntryMeta):
    serializer_class = HomeResponseSerializer

    def perform_request(self, validated_request_data):
        return EntryHandler.entry(get_local_request())


class PingResource(EntryMeta):
    serializer_class = serializers.CharField

    def perform_request(self, validated_request_data):
        return "pong"


class LogoutResource(EntryMeta):
    def perform_request(self, validated_request_data):
        auth.logout(get_local_request())
        return


class I18nResource(EntryMeta):
    def perform_request(self, validated_request_data):
        lang_code = validated_request_data[LANGUAGE_QUERY_PARAMETER]
        if not lang_code or not self.check_for_language(lang_code):
            raise LangCodeError()
        response = Response()
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            lang_code,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
        return response

    @classmethod
    def check_for_language(cls, lang_code: str) -> bool:
        return lang_code in [lang for lang, _ in settings.LANGUAGES]


class GenerateWatermark(EntryMeta):
    name = gettext_lazy("Generate Watermark")

    def perform_request(self, validated_request_data):
        if not WatermarkFeature().available:
            return {"enabled": False}
        params = {"username": get_request_username()}
        if EntryHandler.get_version():
            params["version"] = EntryHandler.get_version()
        if validated_request_data.get("width") and validated_request_data.get("height"):
            params.update(
                {
                    "canvas_width": validated_request_data["width"],
                    "canvas_height": validated_request_data["height"],
                }
            )
        return {"enabled": True, "watermark": api.watermark.generate_watermark(**params)}
