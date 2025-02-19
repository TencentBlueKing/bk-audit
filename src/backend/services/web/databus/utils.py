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

from bk_resource import api
from bk_resource.settings import bk_resource_settings


def stop_bkbase_clean(bkbase_result_table_id: str, processing_id: str, username: str = None) -> None:
    """停止清洗任务"""

    api.bk_base.databus_tasks_delete(
        result_table_id=bkbase_result_table_id,
        storages=["clean"],
        processing_id=processing_id,
        bk_username=username or bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
    )


def start_bkbase_clean(bkbase_result_table_id: str, processing_id: str, username: str = None) -> None:
    """
    启动清洗任务
    """

    api.bk_base.databus_tasks_post(
        result_table_id=bkbase_result_table_id,
        processing_id=processing_id,
        storages=["kafka"],
        bk_username=username or bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
    )


def restart_bkbase_clean(bkbase_result_table_id: str, processing_id: str, username: str = None) -> None:
    """
    重启清洗任务
    """
    stop_bkbase_clean(bkbase_result_table_id, processing_id, username=username)
    start_bkbase_clean(bkbase_result_table_id, processing_id, username=username)
