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
import time

from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab

from apps.notice.handlers import NoticeHandler
from apps.notice.models import NoticeLogV2
from core.lock import lock


@periodic_task(queue="notice", run_every=(crontab(minute="*")))
@lock(lock_name="celery:send_notice_from_db")
def send_notice_from_db():
    """
    真实发送通知到用户
    """

    # 初始化调度时间
    schedule_time = time.time()

    # 获取聚合键
    schedule_configs = NoticeLogV2.objects.values("relate_type", "agg_key").distinct()

    # 逐个执行
    for schedule_config in schedule_configs:
        NoticeHandler(
            schedule_time=schedule_time,
            relate_type=schedule_config["relate_type"],
            agg_key=schedule_config["agg_key"],
            notice_logs=NoticeLogV2.objects.filter(
                relate_type=schedule_config["relate_type"],
                agg_key=schedule_config["agg_key"],
                schedule_at__isnull=True,
            ).order_by("create_at"),
        ).send()
