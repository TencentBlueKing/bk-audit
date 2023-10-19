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

import mistune
from bk_resource import Resource
from bk_resource.contrib.model import ModelResource
from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_local_request
from django.conf import settings
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from core.models import get_request_username
from services.web.entry.resources import I18nResource
from services.web.version.models import VersionLog, VersionLogVisit
from services.web.version.serializers import (
    VersionLogInfoRequestSerializer,
    VersionLogListSerializer,
)
from services.web.version.utils import get_version_id


class VersionListResource(ModelResource):
    name = gettext_lazy("版本列表")
    tags = ["Version"]
    action = "list"
    model = VersionLog
    serializer_class = VersionLogListSerializer

    def perform_request(self, validated_request_data: dict) -> any:
        # 获取版本信息
        _version_logs = super().perform_request(validated_request_data)
        last_version = get_version_id(VersionLog.objects.order_by("-release_at").first().version)
        show_version = not bool(
            VersionLogVisit.objects.filter(version=last_version, username=get_request_username()).count()
        )
        # 多语言去重
        version_logs = []
        version_ids = []
        for version in _version_logs:
            version["version"] = get_version_id(version["version"])
            if version["version"] in version_ids:
                continue
            version_ids.append(version["version"])
            version_logs.append(version)
        # 响应
        return {"show_version": show_version, "version_logs": version_logs, "last_version": last_version}


class VersionInfoResource(Resource):
    name = gettext_lazy("版本信息")
    tags = ["Version"]
    RequestSerializer = VersionLogInfoRequestSerializer
    serializer_class = serializers.CharField

    def perform_request(self, validated_request_data):
        version = validated_request_data["version"]
        # 多语言支持
        request = get_local_request()
        language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, settings.LANGUAGE_CODE)
        if not I18nResource.check_for_language(language):
            language = settings.LANGUAGE_CODE
        # 版本
        try:
            version_log = VersionLog.objects.get(version=f"{version}.{language}")
        except VersionLog.DoesNotExist:
            version_log = VersionLog.objects.get(version=f"{version}.{settings.LANGUAGE_CODE}")
        VersionLogVisit.objects.update_or_create(
            version=get_version_id(version_log.version), username=get_request_username()
        )
        try:
            parser = mistune.Markdown(hard_wrap=True)
            html_version_log = parser(version_log.content)
        except Exception as err:
            logger.exception("[Log Parse Error] Version => %s; err => %s", version, err)
            html_version_log = version_log.content
        return html_version_log
