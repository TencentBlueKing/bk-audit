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
import datetime

from rest_framework.settings import api_settings

from services.web.analyze.constants import OffsetUnit


def calculate_offline_flow_start_time(schedule_period: OffsetUnit):
    """
    计算离线任务的开始时间
    schedule_period: 调度周期类型
    """
    # 计算基准时间
    current_time = datetime.datetime.now()

    # 根据周期类型计算启动时间
    if schedule_period == OffsetUnit.DAY:
        # 第二天0点
        start_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    elif schedule_period == OffsetUnit.HOUR:
        # 下一整点小时
        start_time = current_time.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    else:
        # 其他情况保持当前时间
        start_time = current_time
    # 格式化时间字符串
    start_time_str = start_time.strftime(api_settings.DATETIME_FORMAT)
    return start_time_str
