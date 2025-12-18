# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from django.conf import settings

from services.web.analyze.constants import ControlTypeChoices

MOCK_INDEX_SET_ID = 1

BKM_CONTROL_DATA = {"control_name": ControlTypeChoices.BKM.value, "control_type_id": ControlTypeChoices.BKM.value}
BKM_CONTROL_VERSION_DATA = {"control_version": 1}

STRATEGY_TAGS = ["BkAudit"]
STRATEGY_DATA = {
    "namespace": settings.DEFAULT_NAMESPACE,
    "control_id": 0,
    "control_version": 0,
    "configs": {},
    "tags": STRATEGY_TAGS,
}
BKM_STRATEGY_DATA = {
    **STRATEGY_DATA,
    "strategy_name": "test_bkm_strategy",
    "configs": {
        "agg_condition": [{"key": "username", "value": ["admin"], "method": "eq", "condition": "and"}],
        "agg_dimension": ["username"],
        "algorithms": [{"method": "gt", "threshold": 0}],
        "agg_interval": 300,
        "detects": {"count": 1, "alert_window": 1},
    },
}
CREATE_BKM_DATA_RESULT = {"strategy_id": 1, "strategy_name": BKM_STRATEGY_DATA["strategy_name"]}
UPDATE_BKM_DATA_RESULT = {**CREATE_BKM_DATA_RESULT}

# 日志 RT 信息
COLLECTOR_GET_RESULT_TABLE_DATA = {
    'processing_type': 'clean',
    'result_table_type': None,
    'sensitivity': 'private',
    'storages': {
        'doris': {},
        'es': {},
        'hdfs': {},
        'kafka': {},
    },
}

# 资产表 RT 信息
ASSET_GET_RESULT_TABLE_DATA = {
    'processing_type': 'clean',
    'result_table_type': 'upsert_static',
    'storages': {
        'doris': {},
        'hdfs': {},
        'ignite': {},
        'kafka': {},
    },
}

# 其他数据-实时流水表
OTHERS_REAL_GET_RESULT_TABLE_DATA = {
    'processing_type': 'clean',
    'result_table_type': None,
    'storages': {
        'kafka': {},
    },
}

# 其他数据-离线流水表
OTHERS_BATCH_GET_RESULT_TABLE_DATA = {
    'processing_type': 'batch',
    'result_table_type': None,
    'storages': {'hdfs': {}},
}

# 其他数据-资产
OTHERS_BATCH_REAL_GET_RESULT_TABLE_DATA = {
    'processing_type': 'clean',
    'result_table_type': 'upsert_static',
    'storages': {
        'doris': {},
        'hdfs': {},
        'ignite': {},
        'kafka': {},
    },
}
