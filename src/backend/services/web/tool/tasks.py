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
from bk_resource.utils.logger import logger
from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab
from django.conf import settings
from django.db import transaction

from core.lock import lock
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.models import Tool


@periodic_task(run_every=crontab(minute=settings.BKVISION_UPDATE_HOUR))
@lock(load_lock_name=lambda **kwargs: "celery:update_bkvision_config")
def update_bkvision_config():
    """修改视图是否更新状态"""

    queryset = Tool.all_latest_tools().filter(tool_type=ToolTypeEnum.BK_VISION.value)
    updated_tools = []

    for tool in queryset:
        try:
            # 从 API 获取 BKVision 配置
            bkvision = api.bk_vision.query_meta(type="dashboard", id=tool.config.get("uid"))
            bkvision_updated_time = bkvision["data"].get("updated_time")
            tool_updated_time = tool.bkvision_config.bkvision_updated_at

            # 仅在更新时间更晚时才处理
            if bkvision_updated_time > tool_updated_time:
                tool.bkvision_config.updated_time = bkvision_updated_time
                tool.is_bkvision_updated = True
                updated_tools.append(tool)  # 记录需要更新的工具

        except Exception as e:
            logger.error(f"Error processing Tool {tool.uid}: {str(e)}", exc_info=True)

    if updated_tools:
        try:
            with transaction.atomic():
                for tool in updated_tools:
                    tool.bkvision_config.save()  # 更新工具的配置
                    tool.save()
            logger.info(f"Updated {len(updated_tools)} tools.")
        except Exception as e:
            logger.error(f"Error saving tools: {str(e)}", exc_info=True)
