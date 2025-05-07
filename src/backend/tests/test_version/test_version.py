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
from unittest import mock

from django.conf import settings

from core.models import get_request_username
from core.utils.data import ordered_dict_to_json
from services.web.version.models import VersionLog, VersionLogVisit
from services.web.version.utils import get_version_id
from tests.base import TestCase
from tests.test_version.constants import (
    VERSION_INFO_PARAMS,
    VERSION_INFO_PARAMS_OF_EXCEPT,
    GetLocalRequestMock,
)


class VersionTest(TestCase):
    def setUp(self) -> None:
        self.version_log = VersionLog.objects.all()
        self.version_log_visit = VersionLogVisit.objects.all()

    def test_version_list(self):
        """VersionListResource"""

        result = ordered_dict_to_json(self.resource.version.version_list())

        last_version = get_version_id(self.version_log.order_by("release_at").last().version)
        show_version = not bool(
            self.version_log_visit.filter(version=last_version, username=get_request_username()).count()
        )
        version_logs_of_item = [
            {"version": get_version_id(i.version), "release_at": i.release_at.strftime("%Y-%m-%d")}
            for i in self.version_log
        ]
        version_logs_of_set = [dict(i) for i in ({tuple(i.items()) for i in version_logs_of_item})]
        version_logs = sorted(version_logs_of_set, key=lambda x: x["release_at"], reverse=True)
        version_list_data = {
            "show_version": show_version,
            "version_logs": version_logs,
            "last_version": last_version,
        }

        self.assertEqual(result, version_list_data)

    @mock.patch("version.resources.mistune.Markdown", mock.Mock(return_value=object))
    @mock.patch("version.resources.get_local_request", mock.Mock(return_value=GetLocalRequestMock()))
    def test_version_info(self):
        """ "VersionInfoResource"""
        result = self.resource.version.version_info(**VERSION_INFO_PARAMS)

        version = VERSION_INFO_PARAMS["version"]
        language = settings.LANGUAGE_CODE
        version_info_data = self.version_log.get(version=f"{version}.{language}").content

        self.assertEqual(result, version_info_data)

    @mock.patch("version.resources.get_local_request", mock.Mock(return_value=GetLocalRequestMock()))
    def test_version_info_of_except(self):
        """ "VersionInfoResource"""
        with self.assertRaises(VersionLog.DoesNotExist):
            self.resource.version.version_info(**VERSION_INFO_PARAMS_OF_EXCEPT)
