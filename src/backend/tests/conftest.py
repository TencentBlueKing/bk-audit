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
import importlib
from unittest import mock

import pytest

from api.bk_base.default import DataflowBatchStatusList, GetFlowGraph
from tests.constants import MOCK_PROCESSING_ID, RISK_EVENT_TIMESTAMP


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    from django.conf import settings

    importlib.import_module(settings.ROOT_URLCONF)


def mock_bk_base_get_flow_graph():
    return mock.patch.object(
        GetFlowGraph,
        'perform_request',
        lambda *args, **kwargs: {
            "nodes": [
                {"node_type": "batchv2", "result_table_ids": [MOCK_PROCESSING_ID]},
                {"node_type": "scenario_app", "result_table_ids": [MOCK_PROCESSING_ID]},
            ]
        },
    )


def mock_bk_base_dataflow_batch_status_list():
    return mock.patch.object(
        DataflowBatchStatusList,
        'perform_request',
        lambda *args, **kwargs: [
            {
                'created_at': 1744158562000,
                'data_time': RISK_EVENT_TIMESTAMP,
                'err_msg': '',
                'execute_id': 382899815,
                'is_allowed': False,
                'schedule_time': 1744158540000,
                'started_at': 1744195083000,
                'status': 'finished',
                'status_str': '成功',
                'updated_at': 1744195143000,
            },
        ],
    )
