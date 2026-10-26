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
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime
from typing import Optional

from django.utils import timezone
from rest_framework.settings import api_settings


def parse_sops_time(value) -> Optional[datetime.datetime]:
    """
    解析 SOPS 状态里的时间字段（源格式或 ISO 格式，均可能出现在 JSONField 回读值中）

    统一返回当前时区 aware 时间：同一份状态里任务级时间常带 +0800 偏移、节点级常不带，
    一律补全时区后才能正确比较 / 求差（否则抛 can't compare/subtract naive and aware）。
    """
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.datetime.strptime(value, fmt)
            break
        except ValueError:
            continue
    else:
        try:
            parsed = datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        # 不带偏移的串按本地时间解释
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed.astimezone(timezone.get_current_timezone())


def format_sops_time(value) -> str:
    """
    SOPS 时间串 → 展示格式（本地墙钟 %Y-%m-%d %H:%M:%S，不带时区偏移）

    偏移仅用于解析确定时刻，展示统一去掉，与 start_time / risk_time 等平台展示格式对齐；
    解析失败时原样返回，避免吞数据。
    """
    if not value or not isinstance(value, str):
        return ""
    parsed = parse_sops_time(value)
    if parsed is None:
        return value.strip()
    return parsed.strftime(api_settings.DATETIME_FORMAT)


def calc_task_duration(status_info: dict) -> Optional[int]:
    """耗时（秒）：SOPS 任务实际 start_time/finish_time 之差；未结束/缺失返回 None

    部分场景（SOPS 版本差异/任务未回填任务级时间）下任务级 start_time/finish_time 为空，
    此时退化为取所有子节点的最早开始时间与最晚结束时间，避免耗时恒为 None。
    """
    status_info = status_info or {}
    start = parse_sops_time(status_info.get("start_time"))
    finish = parse_sops_time(status_info.get("finish_time"))
    if not (start and finish):
        children = status_info.get("children") or {}
        child_times = [
            (parse_sops_time(child.get("start_time")), parse_sops_time(child.get("finish_time")))
            for child in children.values()
            if isinstance(child, dict)
        ]
        starts = [item[0] for item in child_times if item[0]]
        finishes = [item[1] for item in child_times if item[1]]
        start = start or (min(starts) if starts else None)
        finish = finish or (max(finishes) if finishes else None)
    if start and finish:
        return int((finish - start).total_seconds())
    return None


def calc_task_finish_time(status_info: dict) -> str:
    """任务结束时间：优先任务级 finish_time，缺失时退化为子节点最晚结束时间

    与 calc_task_duration 同源：部分任务 SOPS 不回填任务级 finish_time，
    仅用任务级字段会让终态记录的结束时间展示为空。
    展示输出统一为本地 %Y-%m-%d %H:%M:%S（SOPS 原始串的时区偏移不透传）。
    """
    status_info = status_info or {}
    raw = status_info.get("finish_time")
    if raw:
        return format_sops_time(raw)
    children = status_info.get("children") or {}
    candidates = [
        child.get("finish_time") for child in children.values() if isinstance(child, dict) and child.get("finish_time")
    ]
    if not candidates:
        return ""
    parsed = [(parse_sops_time(value), value) for value in candidates]
    latest = max((item for item in parsed if item[0]), default=None)
    return format_sops_time(latest[1] if latest else candidates[-1])


def extract_attempt_records(status_info: dict) -> list:
    """从 SOPS 状态中提取子节点尝试记录（重试快照与执行记录详情共用同一形状）

    递归遍历：失败节点可能嵌套在子流程里，只取顶层 children 会漏掉真正的失败节点。
    error_message 由终态同步 / 重试前调用 fill_failure_info 回源写入。
    start_time/end_time 输出统一为本地 %Y-%m-%d %H:%M:%S（不带时区偏移）。
    """
    attempts = []

    def _walk(node: dict) -> None:
        for node_id, child in (node.get("children") or {}).items():
            if not isinstance(child, dict):
                continue
            attempts.append(
                {
                    "node_id": node_id,
                    "node_name": child.get("name") or "",
                    "state": child.get("state") or "",
                    "start_time": format_sops_time(child.get("start_time") or ""),
                    "end_time": format_sops_time(child.get("finish_time") or ""),
                    "duration": child.get("elapsed_time") or 0,
                    "error_message": child.get("error_message") or "",
                }
            )
            _walk(child)

    _walk(status_info or {})
    return attempts
