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
            bkvision = api.bk_vision.query_meta(type="dashboard", share_uid=tool.config.get("uid"))
            if _should_update_bkvision_tool(tool, bkvision):
                tool.is_bkvision = True
                updated_tools.append(tool)  # 记录需要更新的工具
        except Exception as e:
            logger.error(f"Error processing Tool {tool.uid}: {str(e)}", exc_info=True)

    if updated_tools:
        try:
            with transaction.atomic():
                for tool in updated_tools:
                    tool.save(update_record=False)
        except Exception as e:
            logger.error(f"Error saving tools: {str(e)}", exc_info=True)


def _values_equal(lhs, rhs) -> bool:
    """以 JSON 方式比较两个默认值，避免 list / dict 顺序差异导致误判。"""
    if lhs == rhs:
        return True
    try:
        return json.dumps(lhs, sort_keys=True, ensure_ascii=False) == json.dumps(
            rhs, sort_keys=True, ensure_ascii=False
        )
    except TypeError:
        return False


def _should_update_bkvision_tool(tool: Tool, bkvision_meta: dict) -> bool:
    """
    基于 QueryMeta 与工具配置的差异判断是否需要更新工具。

    对比策略：
    1. 工具端以 `description` 作为字段唯一标识，记录是否使用默认值及默认值内容；
    2. QueryMeta 端从 filters / variables / constants 中收集交互组件和非内置变量的默认值；
    3. 任意字段缺失、默认值不一致或 QueryMeta 新增字段均视为“需要更新”。
    """

    def mark_should_update(reason: str, detail: dict | None = None) -> bool:
        extra = {"tool_uid": tool.uid, "reason": reason}
        if detail:
            extra.update(detail)
        logger.info("BKVision差异检测触发更新", extra=extra)
        return True

    config = tool.config or {}
    input_variables = config.get("input_variable") or []
    if not isinstance(input_variables, list):
        input_variables = []

    bkvision_data = bkvision_meta.get("data") or {}
    variables = bkvision_data.get("variables") or []
    filters = bkvision_meta.get("filters") or {}
    constants = bkvision_meta.get("constants") or {}

    # 记录 meta 中的变量配置，key 为变量 UID（交互组件或变量 UID 均适用）
    variable_by_uid = {}
    # 非内置变量 UID 集合（需要检查 constants 中的默认值）
    non_builtin_variable_uids = set()
    # meta 中的默认值映射：包含 filters 的默认值，稍后补充非内置 constants
    meta_defaults = {uid: value for uid, value in filters.items() if uid}

    for variable in variables:
        if not isinstance(variable, dict):
            continue
        uid = variable.get("uid")
        if not uid:
            continue
        variable_by_uid[uid] = variable
        if not variable.get("build_in"):
            non_builtin_variable_uids.add(uid)
            flag = variable.get("flag")
            if flag and flag in constants:
                meta_defaults[uid] = constants[flag]

    # filters 中的 UID 集合（交互组件）
    filter_uids = set(filters.keys())

    # 工具端字段配置，key 为 description(uid)，记录是否使用默认值及默认值内容
    tool_fields = {}
    for field in input_variables:
        if not isinstance(field, dict):
            continue
        uid = field.get("description")
        if not uid:
            continue
        uses_default = bool(field.get("is_default_value"))
        tool_fields[uid] = {
            "uses_default": uses_default,
            "default_value": field.get("default_value") if uses_default else None,
        }

    # QueryMeta 中真正需要维护默认值的字段集合
    required_uids = filter_uids | non_builtin_variable_uids

    for uid in required_uids:
        # 工具配置缺少 QueryMeta 中声明的字段，视为差异
        if uid not in tool_fields:
            return mark_should_update("missing_tool_field", {"field_uid": uid})

    for uid, field in tool_fields.items():
        if uid in filter_uids or uid in non_builtin_variable_uids:
            # 对于使用默认值的字段比对默认值内容
            if field["uses_default"]:
                if uid not in meta_defaults:
                    return mark_should_update("missing_meta_default", {"field_uid": uid})
                if not _values_equal(field["default_value"], meta_defaults[uid]):
                    return mark_should_update(
                        "default_value_changed",
                        {
                            "field_uid": uid,
                            "tool_default": field["default_value"],
                            "meta_default": meta_defaults[uid],
                        },
                    )
            continue

        meta_variable = variable_by_uid.get(uid)
        if meta_variable is None and uid not in filter_uids:
            return mark_should_update("meta_field_not_found", {"field_uid": uid})
        if meta_variable and not meta_variable.get("build_in"):
            # QueryMeta 将字段标记为非内置变量，而工具未声明默认值
            return mark_should_update("non_builtin_without_default", {"field_uid": uid})

    return False
