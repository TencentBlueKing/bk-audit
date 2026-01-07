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

from services.web.vision.models import VisionPanel
from tests.base import TestCase

from .constants import (
    CHECK_DATA,
    DATASET_QUERY_PARAMS,
    DATASET_QUERY_RESPONSE,
    GET_DATA,
    META_QUERY_PARAMS,
    META_QUERY_RESPONSE,
    TEST_VARIABLE_PARAMS,
    TEST_VARIABLE_RESPONSE,
)


class TestVision(TestCase):
    """测试审计报表数据接口"""

    def setUp(self):
        VisionPanel.objects.create(
            id="just_test",
            name="just_test",
            vision_id="just_test_raw",
            handler="SystemDiagnosisVisionHandler",
        )

    @mock.patch(
        "services.web.vision.handlers.query.api.bk_vision.query_meta",
        mock.Mock(return_value=META_QUERY_RESPONSE['data']),
    )
    @mock.patch(
        "services.web.vision.handlers.filter.SystemDiagnosisFilter.get_data",
        mock.Mock(return_value=GET_DATA),
    )
    def test_meta_query(self):
        result = self.resource.vision.query_meta(**META_QUERY_PARAMS)
        for item in result['data']['panels']:
            if item['mode'] == 'action' and item['chartConfig']["flag"] == "system_id":
                self.assertEqual(item['chartConfig']['json'], GET_DATA)

    @mock.patch(
        "services.web.vision.handlers.filter.SystemDiagnosisFilter.check_data",
        mock.Mock(return_value=CHECK_DATA),
    )
    @mock.patch(
        "services.web.vision.handlers.query.api.bk_vision.query_dataset",
        mock.Mock(return_value=DATASET_QUERY_RESPONSE['data']),
    )
    @mock.patch("django.core.cache.cache.get")
    @mock.patch("django.core.cache.cache.set")
    def test_data_set_query(self, mock_cache_set, mock_cache_get):
        mock_cache_get.return_value = None
        result = self.resource.vision.query_dataset(**DATASET_QUERY_PARAMS)
        self.assertTrue(result['result'])
        mock_cache_set.assert_called_once()
        mock_cache_get.assert_called_once()

    @mock.patch(
        "api.bk_vision.default.QueryTestVariable.perform_request",
        mock.Mock(return_value=TEST_VARIABLE_RESPONSE['data']),
    )
    def test_variable(self):
        """测试变量数据接口"""
        result = self.resource.vision.query_test_variable(**TEST_VARIABLE_PARAMS)
        self.assertIn("values", result)
        self.assertEqual(len(result["values"]), 2)
