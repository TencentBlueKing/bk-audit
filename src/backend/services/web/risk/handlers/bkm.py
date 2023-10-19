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
import math
from typing import List

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.fields import STANDARD_FIELDS, USERNAME
from services.web.analyze.constants import ControlTypeChoices
from services.web.analyze.models import Control
from services.web.risk.constants import (
    BKM_ALERT_BATCH_SIZE,
    BKM_ALERT_SYNC_HOURS,
    EVENT_ESQUERY_DELAY_TIME,
    EVENT_SYNC_START_TIME_KEY,
    EventMappingFields,
    EventSourceTypeChoices,
)
from services.web.risk.serializers import CreateEventBKMSerializer
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


class BKMAlertSyncHandler:
    """
    同步BKM告警
    """

    @transaction.atomic()
    def sync(self) -> None:
        # 检测策略数量
        if not Strategy.objects.filter(self._build_db_filter()).exists():
            logger.info("[NoneStrategyNeedToSyncAlert] BKMAlertSyncHandler Stopped")
        # 初始化参数
        start_time_ts = GlobalMetaConfig.get(
            config_key=EVENT_SYNC_START_TIME_KEY,
            default=math.floor((datetime.datetime.now() - datetime.timedelta(hours=BKM_ALERT_SYNC_HOURS)).timestamp()),
        )
        start_time = datetime.datetime.fromtimestamp(start_time_ts)
        end_time = datetime.datetime.now() - datetime.timedelta(seconds=EVENT_ESQUERY_DELAY_TIME)
        # 预拉取获取数据量
        api_params = self._build_api_params(start_time=start_time, end_time=end_time, page=1, page_size=1)
        pre_data = self._call_api(**api_params)
        # 批量拉取
        request_params = [
            self._build_api_params(start_time=start_time, end_time=end_time, page=i + 1, page_size=BKM_ALERT_BATCH_SIZE)
            for i in range(math.ceil(pre_data["total"] / BKM_ALERT_BATCH_SIZE))
        ]
        data = self._batch_call_api(*request_params)
        # 存入数据库
        events = self._format_alert_as_event(data["alerts"])
        self._create_or_update_event(events)
        # 更新时间
        GlobalMetaConfig.set(config_key=EVENT_SYNC_START_TIME_KEY, config_value=math.floor(end_time.timestamp()))

    def _format_alert_as_event(self, data: List[dict]) -> List[dict]:
        # 获取BKM策略与审计策略映射关系
        strategy_map = {
            s.backend_data["id"]: s for s in Strategy.objects.filter(self._build_db_filter()) if "id" in s.backend_data
        }
        # 格式化
        return [
            {
                EventMappingFields.EVENT_ID.field_name: "{}-{}".format(
                    self._get_bkaudit_strategy_id(strategy_map, alert["strategy_id"]), alert["id"]
                ),
                EventMappingFields.EVENT_CONTENT.field_name: "{} {}".format(
                    " ".join(
                        [
                            "[{}]{}".format(dimension["display_key"], dimension["display_value"])
                            for dimension in alert["dimensions"]
                        ]
                    ),
                    alert["description"],
                ),
                EventMappingFields.RAW_EVENT_ID.field_name: str(alert["id"]),
                EventMappingFields.STRATEGY_ID.field_name: self._get_bkaudit_strategy_id(
                    strategy_map, alert["strategy_id"]
                ),
                EventMappingFields.EVENT_DATA.field_name: alert,
                EventMappingFields.EVENT_TIME.field_name: alert["create_time"] * 1000,
                EventMappingFields.EVENT_SOURCE.field_name: EventSourceTypeChoices.BKM.value,
                EventMappingFields.OPERATOR.field_name: self._get_alert_username(alert["tags"]),
            }
            for alert in data
        ]

    def _get_bkaudit_strategy_id(self, data: dict, strategy_id) -> int:
        """
        获取审计中心策略ID
        """

        strategy = data.get(strategy_id)
        if not strategy:
            return -1
        return strategy.strategy_id

    def _get_alert_username(self, tags: List[dict]) -> str:
        """
        获取责任人
        """

        for tag in tags:
            if tag["key"] == USERNAME.field_name:
                return tag["value"]
        return ""

    def _build_event_dimension(self, alert: dict, strategy: dict) -> dict:
        standard_fields = [field.field_name for field in STANDARD_FIELDS]
        dimensions = {}
        if strategy:
            dimensions.update(
                {
                    c["key"]: c["value"]
                    for c in strategy["items"][0]["query_configs"][0]["agg_condition"]
                    if c["key"] in standard_fields
                }
            )
        dimensions.update({tag["key"]: [tag["value"]] for tag in alert["tags"]})
        return dimensions

    def _create_or_update_event(self, data: List[dict]) -> None:
        # 校验数据
        serializer = CreateEventBKMSerializer(data=data, many=True)
        is_valid = serializer.is_valid()
        if not is_valid:
            logger.error("[FormatBKMAlertFailed] Err => %s", serializer.errors)
            return
        logger.info("[CreateOrUpdateEvnet] Total: %d", len(serializer.validated_data))
        # 创建审计事件
        from services.web.risk.tasks import add_event

        add_event.delay(serializer.validated_data)

    def _build_db_filter(self) -> Q:
        controls = Control.objects.filter(control_type_id=ControlTypeChoices.BKM.value)
        return Q(control_id__in=controls.values("control_id"), status=StrategyStatusChoices.RUNNING)

    def _build_bkm_filter(self) -> list:
        conditions = [
            {
                "key": "strategy_id",
                "value": [
                    s.backend_data["id"]
                    for s in Strategy.objects.filter(self._build_db_filter())
                    if "id" in s.backend_data
                ],
            }
        ]
        return conditions

    def _build_api_params(
        self, start_time: datetime.datetime, end_time: datetime.datetime, page: int, page_size: int
    ) -> dict:
        return {
            "bk_biz_ids": [settings.DEFAULT_BK_BIZ_ID],
            "start_time": math.floor(start_time.timestamp()),
            "end_time": math.floor(end_time.timestamp()),
            "page": page,
            "page_size": page_size,
            "show_overview": False,
            "show_aggs": False,
            "conditions": self._build_bkm_filter(),
            "ordering": [],
        }

    def _call_api(self, **params) -> dict:
        try:
            return api.bk_monitor.search_alert(**params)
        except APIRequestError as err:
            logger.error("[GetBKMAlertFailed] Params => %s; Err => %s", params, err)
            return {"total": 0, "alerts": []}

    def _batch_call_api(self, *params) -> dict:
        data = {"total": 0, "alerts": []}
        try:
            results = api.bk_monitor.search_alert.bulk_request(params)
        except APIRequestError as err:
            logger.error("[GetBKMAlertFailed] Params => %s; Err => %s", params, err)
            return {"total": 0, "alerts": []}
        for result in results:
            data["total"] += result["total"]
            data["alerts"].extend(result["alerts"])
        logger.info(
            "[BKMSyncResult] Total => %d; Sample => %s", data["total"], data["alerts"][0] if data["alerts"] else ""
        )
        return data
