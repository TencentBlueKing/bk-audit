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
import re
import time
from typing import Any, Dict, List, Optional

from bk_resource import api
from blueapps.utils.logger import logger
from django.conf import settings

from api.bk_base.constants import StorageType
from services.web.databus.models import CollectorConfig

# 存储类型：Doris 面向检索，HDFS 面向离线 flow
STORAGE_TYPES = (StorageType.DORIS.value, StorageType.HDFS.value)

# 结果表 ID 白名单：只允许库名/标识符字符，防止把脏数据拼进 SQL
_TABLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)?$")

# 13 位毫秒阈值：>1e12 视为毫秒，毫秒有12个0，共13个数，秒有9个，共10个数
_MILLISECOND_THRESHOLD = 10**12


def _to_seconds(value: Any) -> Optional[int]:
    """统一成 10 位 unix 秒。
    BKBase 的 max() 结果可能是 int / float / str 全部容错；个别环境给出 13 位毫秒时降级为秒。
    """
    if value is None or value == "":
        return None
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return None
    return seconds // 1000 if seconds > _MILLISECOND_THRESHOLD else seconds


def _now_seconds() -> int:
    return int(time.time())


def build_storage_sql(collector: CollectorConfig, now: Optional[datetime.datetime] = None) -> Optional[str]:
    """拼存储侧水位 SQL；结果表 ID 非法时返回 None（由调用方置 query_ok=0）。

    ``thedate`` 用 Python 算出的整型字面量：Doris 与 Hive 的日期函数格式符不同
    （``%Y%m%d`` vs ``yyyyMMdd``），传字面量可彻底规避方言差异。
    必须带 ``collector_config_id`` 过滤：多个采集项可能写同一张结果表，
    否则整表最新会掩盖单采集项异常。
    """
    table_id = (collector.bkbase_table_id or "").strip()
    if not table_id or not _TABLE_ID_PATTERN.match(table_id):
        return None
    today = now or datetime.datetime.now()
    cutoff = (today - datetime.timedelta(days=settings.LOG_FLOW_STORAGE_LOOKBACK_DAYS)).strftime("%Y%m%d")
    return (
        f"SELECT max(bk_receive_time) AS m FROM {table_id} "
        f"WHERE collector_config_id = {int(collector.collector_config_id)} "
        f"AND thedate >= {int(cutoff)}"
    )


def sample_source(collector: CollectorConfig) -> Dict[str, Any]:
    """源端：BK Log tail，取 ``origin.time``。

    返回 ``{"query_ok": 0|1, "receive_time": int|None, "age_seconds": int|None}``。
    """
    collector_config_id = collector.collector_config_id
    try:
        # 注意：该资源 many_response_data=True，返回的是 list（不是 {"data": [...]}）
        tails = api.bk_log.get_collector_tail_log(collector_config_id=collector_config_id) or []
    except Exception:  # NOCC:broad-except(单采集项失败不能中断整轮)
        logger.exception("[LogFlowSourceFailed] CollectorConfigID => %s", collector_config_id)
        return {"query_ok": 0, "receive_time": None, "age_seconds": None}

    if not tails:
        # 接口成功但无日志（含 PARTITION 不存在被吞成 [] 的情况）：不补 0、不报时间
        return {"query_ok": 1, "receive_time": None, "age_seconds": None}

    origin_times: List[int] = [
        seconds
        for seconds in (_to_seconds((item.get("origin") or {}).get("time")) for item in tails if isinstance(item, dict))
        if seconds
    ]
    if not origin_times:
        # 拿到了日志却解析不出上报时间：本侧数据不可信，按不可信上报
        logger.warning(
            "[LogFlowSourceNoOriginTime] CollectorConfigID => %s; TailLogSample => %s",
            collector_config_id,
            tails[:1],
        )
        return {"query_ok": 0, "receive_time": None, "age_seconds": None}

    receive_time = max(origin_times)
    return {"query_ok": 1, "receive_time": receive_time, "age_seconds": _now_seconds() - receive_time}


def sample_storage(collector: CollectorConfig, storage_type: str) -> Dict[str, Any]:
    """存储端：Doris / HDFS 各查一次 ``max(bk_receive_time)``。

    返回 ``{"query_ok": 0|1, "has_watermark": 0|1, "receive_time": int|None}``。
    两侧互不影响：任一侧异常只影响自己的返回。
    """
    sql = build_storage_sql(collector)
    if sql is None:
        logger.warning(
            "[LogFlowStorageInvalidTable] CollectorConfigID => %s; BkBaseTableID => %s",
            collector.collector_config_id,
            collector.bkbase_table_id,
        )
        return {"query_ok": 0, "has_watermark": 0, "receive_time": None}

    try:
        resp = api.bk_base.query_sync(
            sql=sql,
            prefer_storage=storage_type,
            request_timeout=settings.LOG_FLOW_STORAGE_QUERY_TIMEOUT,
        )
    except Exception:  # NOCC:broad-except(单存储失败不能中断整轮)
        logger.exception(
            "[LogFlowStorageFailed] CollectorConfigID => %s; StorageType => %s",
            collector.collector_config_id,
            storage_type,
        )
        return {"query_ok": 0, "has_watermark": 0, "receive_time": None}

    # query_sync 的响应形如 {"list": [{"m": ...}]}
    rows = (resp or {}).get("list") or []
    receive_time = _to_seconds(rows[0].get("m")) if rows and isinstance(rows[0], dict) else None
    if receive_time is None:
        # 查询成功但窗口内无水位：不编延迟
        return {"query_ok": 1, "has_watermark": 0, "receive_time": None}
    return {"query_ok": 1, "has_watermark": 1, "receive_time": receive_time}
