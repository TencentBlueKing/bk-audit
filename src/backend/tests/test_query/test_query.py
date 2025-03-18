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

from core.exceptions import PermissionException
from services.web.databus.models import CollectorPlugin
from tests.base import TestCase
from tests.test_databus.collector_plugin.constants import PLUGIN_ID
from tests.test_query.constants import (
    BKBASE_COLLECTOR_SEARCH_API_RESP,
    COLLECTOR_SEARCH_CONFIG,
    COLLECTOR_SEARCH_DATA_RESP,
    COLLECTOR_SEARCH_PARAMS,
    ES_QUERY_SEARCH_API_RESP,
    FIELD_MAP_DATA,
    FIELD_MAP_PARAMS,
    GET_AUTH_SYSTEMS_API_RESP,
    PLUGIN_DATA,
    SEARCH_DATA,
    SEARCH_PARAMS,
    PermissionMock,
)


class EsQueryTest(TestCase):
    def setUp(self) -> None:
        CollectorPlugin.objects.create(**PLUGIN_DATA)

    @mock.patch(
        "query.resources.SearchLogPermission.get_auth_systems",
        mock.Mock(return_value=GET_AUTH_SYSTEMS_API_RESP),
    )
    @mock.patch("query.resources.resource.query.es_query", mock.Mock(return_value=ES_QUERY_SEARCH_API_RESP))
    def test_search(self):
        """SearchResource"""
        result = self.resource.query.search(**SEARCH_PARAMS)
        self.assertEqual(result, SEARCH_DATA)

    @mock.patch("query.resources.es.Permission", PermissionMock())
    def test_search_of_not_authorized_systems(self):
        """SearchResource"""
        with self.assertRaises(PermissionException):
            self.resource.query.search(**SEARCH_PARAMS)

    @mock.patch("query.resources.SearchLogPermission.any_search_log_permission", PermissionMock())
    def test_field_map(self):
        """FieldMapResource"""
        result = self.resource.query.field_map(**FIELD_MAP_PARAMS)
        self.assertEqual(result, FIELD_MAP_DATA)


class CollectorQueryTest(TestCase):
    def setUp(self) -> None:
        CollectorPlugin.objects.create(**PLUGIN_DATA)

    def test_collector_search_config(self):
        """CollectorSearchConfigResource"""
        result = self.resource.query.collector_search_config()
        self.assertEqual(result, COLLECTOR_SEARCH_CONFIG)

    @mock.patch("services.web.query.resources.GlobalMetaConfig.get", mock.Mock(return_value=PLUGIN_ID))
    @mock.patch(
        "services.web.query.resources.SearchLogPermission.get_auth_systems",
        mock.Mock(return_value=GET_AUTH_SYSTEMS_API_RESP),
    )
    @mock.patch(
        "services.web.query.resources.api.bk_base.query_sync.bulk_request",
        mock.Mock(return_value=BKBASE_COLLECTOR_SEARCH_API_RESP),
    )
    def test_collector_search(self):
        """CollectorSearchResource"""
        result = self.resource.query.collector_search(**COLLECTOR_SEARCH_PARAMS)
        self.assertEqual(result, COLLECTOR_SEARCH_DATA_RESP)
