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
from api.bk_iam.default import GetSystemInfo, GetSystemRoles, GetSystems
from api.bk_iam_v4.default import ListSystemResource, RetrieveSystemResource
from api.bk_paas.default import UniAppsQuery
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


def mock_iam_get_systems():
    return mock.patch.object(
        GetSystems,
        'perform_request',
        lambda *args, **kwargs: [{'id': 'test_system', 'name': 'IAM V3测试系统', 'name_en': 'test_system'}],
    )


def mock_iam_get_system_roles():
    return mock.patch.object(
        GetSystemRoles,
        'perform_request',
        lambda *args, **kwargs: {
            'description': 'xxx',
            'id': 'test_system_role',
            'members': [{'readonly': False, 'username': 'admin1'}],
            'name': 'test_system_role',
        },
    )


def mock_iam_get_system_info():
    return mock.patch.object(
        GetSystemInfo,
        'perform_request',
        lambda *args, **kwargs: {
            'actions': [
                {
                    'id': 'test_action',
                    'name': '测试动作',
                    'name_en': 'test_action',
                    'description': '',
                    'description_en': '',
                    'sensitivity': 0,
                    'auth_type': '',
                    'type': 'view',
                    'hidden': False,
                    'version': 1,
                    'related_resource_types': [
                        {
                            'system_id': 'test_system',
                            'id': 'system',
                            'name_alias': '',
                            'name_alias_en': '',
                            'selection_mode': 'instance',
                            'instance_selections': [
                                {
                                    'id': 'system_list',
                                    'ignore_iam_path': True,
                                    'is_dynamic': False,
                                    'name': '接入系统列表',
                                    'name_en': 'System List',
                                    'resource_type_chain': [{'id': 'system', 'system_id': 'test_system'}],
                                    'system_id': 'test_system',
                                }
                            ],
                        }
                    ],
                    'related_actions': [],
                    'related_environments': [],
                },
            ],
            'base_info': {
                'id': 'test_system',
                'name': 'IAM V3测试系统',
                'name_en': 'test_system',
                'description': 'IAM V3测试系统',
                'description_en': 'Test System',
                'clients': ['xxx'],
                'provider_config': {
                    'auth': 'basic',
                    'healthz': '',
                    'host': 'https://xxx.com',
                    'token': 'xxx',
                },
            },
            'common_actions': None,
            'feature_shield_rules': None,
            'instance_selections': [
                {
                    'id': 'system_list',
                    'name': '接入系统列表',
                    'name_en': 'System List',
                    'is_dynamic': False,
                    'resource_type_chain': [{'id': 'system', 'system_id': 'test_system'}],
                },
            ],
            'resource_types': [
                {
                    'id': 'system',
                    'name': '接入系统',
                    'name_en': 'Systems',
                    'description': '',
                    'description_en': '',
                    'sensitivity': 0,
                    'parents': [],
                    'provider_config': {'path': '/api/v1/iam/resources/'},
                    'version': 1,
                }
            ],
        },
    )


def mock_iam_v4_list_system():
    return mock.patch.object(
        ListSystemResource,
        'fetch_all',
        lambda *args, **kwargs: [
            {'id': 'test_system', 'name': 'IAM V4 测试系统'},
        ],
    )


def mock_iam_v4_retrieve_system():
    return mock.patch.object(
        RetrieveSystemResource,
        'perform_request',
        lambda *args, **kwargs: {
            'actions': [
                {'id': 'task_view', 'name': '查询任务', 'resource_type_id': 'task'},
                {'id': 'task_create', 'name': '创建任务', 'resource_type_id': 'project'},
                {'id': 'project_view', 'name': '查看项目', 'resource_type_id': 'project'},
                {'id': 'task_delete', 'name': '删除任务', 'resource_type_id': 'task'},
                {'id': 'task_edit', 'name': '编辑任务', 'resource_type_id': 'task'},
            ],
            'resource_types': [
                {'ancestors': ['project'], 'id': 'task', 'name': '任务'},
                {'ancestors': [], 'id': 'project', 'name': '项目'},
            ],
            'system_info': {
                'auth_token': 'xxx',
                'callback_url': 'https://xxx.com/api/resource/',
                'clients': ['app_code1', 'app_code2'],
                'description': 'IAM V4 测试系统',
                'id': 'test_system',
                'managers': ["admin"],
                'name': 'IAM V4 测试系统',
            },
        },
    )


def mock_bk_paas_uni_apps_query():
    return mock.patch.object(
        UniAppsQuery,
        "perform_request",
        lambda *args, **kwargs: [
            {
                "app_tenant_mode": "global",
                "code": "app_code1",
                "contact_info": {"latest_operator": "admin", "recent_deployment_operators": []},
                "created": "2024-07-23 08:47:04",
                "creator": "admin",
                "deploy_info": None,
                "developers": ["admin"],
                "logo_url": "https://app_code1.logo",
                "market_addres": {"enabled": False, "market_address": "https://app_code1.system"},
                "name": "app_code1",
                "name_en": "app_code1",
                "region": "ieod",
                "source": 1,
                "tenant_id": "default",
                "type": "engineless_app",
            },
            {
                "app_tenant_mode": "global",
                "code": "xxx",
                "contact_info": {"latest_operator": "admin", "recent_deployment_operators": []},
                "created": "2024-07-23 08:47:04",
                "creator": "admin",
                "deploy_info": None,
                "developers": ["admin"],
                "logo_url": "https://xxx.logo",
                "market_addres": {"enabled": False, "market_address": "https://xxx.system"},
                "name": "xxx",
                "name_en": "xxx",
                "region": "ieod",
                "source": 1,
                "tenant_id": "default",
                "type": "engineless_app",
            },
        ],
    )
