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
import logging
from typing import List, Optional, Set

from bk_resource import api
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy
from rest_framework.settings import api_settings

from apps.sops.constants import SOPSTaskStatus

logger = logging.getLogger("celery")


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


def extract_attempt_records(status_info: dict, retried_node_ids: Optional[Set[str]] = None) -> list:
    """从 SOPS 状态中提取子节点尝试记录（重试快照与执行记录详情共用同一形状）

    递归遍历：失败节点可能嵌套在子流程里，只取顶层 children 会漏掉真正的失败节点。
    error_message 由终态同步 / 重试前调用 fill_failure_info 回源写入。
    start_time/end_time 输出统一为本地 %Y-%m-%d %H:%M:%S（不带时区偏移）。

    retried_node_ids：被重试的节点 ID 集合，命中则该条记录 retried=True。
    - 重试快照传入"本次实际重试的节点"，标记本次重试命中了谁；
    - 执行记录详情传入"历史上被重试过的节点"并集，标记该节点是否被重试过。
    快照保持全量（含成功/未执行节点），仅用该标记区分，避免丢失首次执行的完整现场。
    """
    attempts = []
    retried_node_ids = set(retried_node_ids or ())

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
                    # 重试写入侧用的是 child["id"]，这里遍历用的是 children 的 key，
                    # 理论上两者相同，仍按任一命中处理，避免口径差异导致标记丢失
                    "retried": node_id in retried_node_ids or child.get("id") in retried_node_ids,
                }
            )
            _walk(child)

    _walk(status_info or {})
    return attempts


DEFAULT_FAILURE_HINT = gettext_lazy("任务执行失败")
FAILURE_HINT_MAX_LEN = 200
# 回源取节点错误时最多查询的失败节点数（避免子流程里大量失败节点打爆 SOPS）
MAX_FETCH_ERROR_NODES = 5


def iter_status_nodes(node: dict):
    """深度遍历 SOPS 任务状态树（失败节点可能嵌套在子流程里）"""
    for child in (node.get("children") or {}).values():
        if not isinstance(child, dict):
            continue
        yield child
        yield from iter_status_nodes(child)


def fill_failure_info(status: dict, task_id: str = "", generic=DEFAULT_FAILURE_HINT) -> str:
    """
    补全失败信息：回写逐节点错误 + 返回记录级失败提示（原地修改 status 并返回提示文本）

    一次完成两件事（写入点共用：终态同步 / 重试前快照 / 建单 / 测试轮询）：
    - 写 error_message：SOPS get_task_status 不返回错误文本（只在 get_node_data 的 ex_data 里），
      对失败节点回源取错误并写入 status.children[].error_message，
      供执行记录详情 / 重试快照的 attempts 展示逐节点失败原因；
    - 写 failure_hint：返回第一个取到错误的失败节点文本（截 FAILURE_HINT_MAX_LEN）作记录级摘要，
      由写入点落库 TicketNode.process_result["failure_hint"]，查询层只读该字段。

    语义边界：已回写过 error_message 的节点不再回源（读已存优先）；单节点回源失败静默跳过；
    全部取不到返回 generic；最多回源 MAX_FETCH_ERROR_NODES 个失败节点。
    """

    def _extract_error_texts(node_data: dict) -> List[str]:
        """get_node_data 响应里的错误文本：真实错误在顶层 ex_data / error_message；
        outputs 可能是 [{key, value}] 或 {key: value}，仅取错误类键"""
        texts: List[str] = []
        for key in ("ex_data", "error_message"):
            value = str(node_data.get(key) or "").strip()
            if value:
                texts.append(value)
        outputs = node_data.get("outputs") or {}
        if isinstance(outputs, list):
            items = [(item.get("key"), item.get("value")) for item in outputs if isinstance(item, dict)]
        else:
            items = list(outputs.items())
        for key, value in items:
            value = str(value or "").strip()
            if value and ("error" in str(key).lower() or "ex_data" in str(key).lower()):
                texts.append(value)
        return texts

    if not status:
        return str(generic)
    failed_states = {s.value for s in SOPSTaskStatus.get_failed_status()}
    failed_children = [
        child for child in iter_status_nodes(status) if child.get("state") in failed_states and child.get("id")
    ]
    hint = ""
    fetch_quota = MAX_FETCH_ERROR_NODES
    for child in failed_children:
        error_message = str(child.get("error_message") or "").strip()
        if not error_message and task_id and fetch_quota > 0:
            fetch_quota -= 1
            try:
                node_data = (
                    api.bk_sops.get_node_data(
                        task_id=task_id, bk_biz_id=settings.DEFAULT_BK_BIZ_ID, node_id=str(child["id"])
                    )
                    or {}
                )
            except Exception:  # NOCC:broad-except(单节点取错失败不影响其余节点)
                logger.warning("[FailureHint] Fetch node data failed, task_id=%s node_id=%s", task_id, child["id"])
                node_data = {}
            texts = _extract_error_texts(node_data)
            if texts:
                error_message = "\n".join(dict.fromkeys(texts)).strip()
                child["error_message"] = error_message
        if error_message and not hint:
            hint = error_message
    return hint[:FAILURE_HINT_MAX_LEN] if hint else str(generic)
