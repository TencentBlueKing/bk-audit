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

import json
import traceback
from typing import List, Optional, Type

from blueapps.utils.logger import logger
from django.utils import timezone
from django.utils.translation import gettext

from apps.notice.aggregators import AGGREGATORS
from apps.notice.aggregators.base import Aggregator
from apps.notice.builders import BUILDERS
from apps.notice.builders.base import Builder
from apps.notice.models import NoticeLogV2
from apps.notice.senders import SENDERS
from apps.notice.senders.base import Sender


class NoticeHandler:
    """
    消息通知基类
    """

    def __init__(
        self,
        schedule_time: float,
        relate_type: str,
        agg_key: str,
        notice_logs: List[NoticeLogV2],
    ):
        """
        需要注意：notice_logs 应当为按照 relate_type 和 agg_key 聚合后的一组消息内容
        """

        self.schedule_time = schedule_time
        self.relate_type = relate_type
        self.agg_key = agg_key
        self.notice_logs = notice_logs

    def send(self) -> None:
        """
        发送消息
        """

        # 获取聚合器
        aggregator_cls: Optional[Type[Aggregator]] = AGGREGATORS.get(self.agg_key, None)
        if not aggregator_cls:
            aggregator_cls = Aggregator

        # 实例化聚合器
        aggregator = aggregator_cls(
            schedule_time=self.schedule_time, agg_key=self.agg_key, relate_type=self.relate_type
        )

        # 获取聚合配置
        send_times = 0
        need_schedule, duration, max_send_times = aggregator.load_agg_config()
        logger.info(
            "[NoticeAggConfig] RelateType: %s, AggKey: %s, AggConfig: %s",
            self.relate_type,
            self.agg_key,
            (need_schedule, duration, max_send_times),
        )

        # 没有达到聚合周期直接跳过
        if not need_schedule:
            return

        # 聚合的通知记录
        agg_notice_log = None

        # 逐个处理
        for notice_log in self.notice_logs:
            # 已有聚合通知记录不再发送
            if agg_notice_log is not None:
                self.done(
                    notice_log=notice_log,
                    debug_info=json.dumps({"AggNoticeLogID": agg_notice_log.id}, ensure_ascii=False),
                )
                continue
            # 无聚合周期或未达到最大发送次数时直接发送
            if duration <= 0 or send_times < max_send_times:
                self._send(notice_log=notice_log, need_agg=False)
                send_times += 1
                continue
            # 达到最大聚合次数时，再发送一次，并更新聚合记录
            agg_notice_log = notice_log
            self._send(notice_log=notice_log, need_agg=True, agg_count=len(self.notice_logs) - max_send_times)

        # 更新调度时间
        aggregator.update_agg_time()

    def _send(self, notice_log: NoticeLogV2, need_agg: bool, agg_count: int = None) -> None:
        """
        发送消息
        """

        # 没有接收人或没有通知方式直接完成
        if not notice_log.receivers or not notice_log.msg_type:
            self.done(notice_log=notice_log)

        # 获取构造器
        builder_cls: Optional[Type[Builder]] = BUILDERS.get(self.relate_type.lower(), None)
        if not builder_cls:
            self.fail(notice_log=notice_log, debug_info=gettext("消息构造器不存在"))
            return

        # 实例化构造器
        builder: Builder = builder_cls(notice_log=notice_log, need_agg=need_agg, agg_count=agg_count)

        # 逐个消息类型处理
        errors = []
        debug_info = []
        title, content, button = "", "", None
        for msg_type in notice_log.msg_type:
            try:
                # 获取发送器
                sender: Type[Sender] = SENDERS[msg_type]
                # 构造消息内容
                title, content, button, configs = builder.build_msg(msg_type=msg_type)
                # 发送消息
                debug_info.append(
                    sender(
                        receivers=notice_log.receivers, title=title, content=content, button=button, **configs
                    ).send()
                )
            except Exception as err:  # NOCC:broad-except(需要处理所有错误)
                # 记录错误信息
                errors.append(err)
                debug_info.append({"Error": str(err), "Traceback": str(traceback.format_exc())})

        # 存储记录
        self.done(
            notice_log=notice_log,
            errors=errors,
            debug_info=json.dumps(debug_info, ensure_ascii=False),
            title=title,
            content=content,
        )

    @classmethod
    def done(
        cls, notice_log: NoticeLogV2, errors: list = None, debug_info: str = "", title: str = "", content: str = ""
    ) -> None:
        """
        将消息标记为完成
        """

        errors = errors or []

        notice_log.title = title if title else notice_log.title
        notice_log.content = content if content else notice_log.content
        notice_log.schedule_at = timezone.now()
        notice_log.schedule_result = bool(
            any([len(notice_log.msg_type) <= 0, len(notice_log.msg_type) > len(errors)])  # 没有通知渠道  # 错误数小于通知渠道数
        )
        notice_log.debug_info = debug_info
        notice_log.save(update_fields=["title", "content", "schedule_at", "schedule_result", "debug_info"])

    @classmethod
    def fail(cls, notice_log: NoticeLogV2, debug_info: str = "") -> None:
        """
        将消息标记为失败
        """

        notice_log.schedule_at = timezone.now()
        notice_log.schedule_result = False
        notice_log.debug_info = debug_info
        notice_log.save(update_fields=["schedule_at", "schedule_result", "debug_info"])
