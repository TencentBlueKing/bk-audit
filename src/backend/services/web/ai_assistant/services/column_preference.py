# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""
用户展示字段偏好服务（AI 日志检索列自定义）。

产品口径：
- 九个固定列（SNAPSHOT_DEFAULT_COLUMNS）锁死不可增减、顺序固定在前；
- 其余字段（与日志检索页字段清单同源 LOG_SEARCH_ALL_FIELDS）用户自主增减；
- 偏好按用户隔离持久化，跨设备同步；检索快照执行时按偏好输出 columns 并固化。
"""

import logging
from typing import Dict, List

from django.db.models import Q

from services.web.ai_assistant.models import UserColumnPreference
from services.web.query.ai_assistant.constants import SNAPSHOT_DEFAULT_COLUMNS
from services.web.query.utils.field import LOG_SEARCH_ALL_FIELDS, LOG_SEARCH_ALL_FIELDS_MAP

logger = logging.getLogger(__name__)

# 九个锁死列 raw_name（顺序即产品展示顺序）
LOCKED_COLUMN_NAMES: List[str] = [raw_name for raw_name, _ in SNAPSHOT_DEFAULT_COLUMNS]
LOCKED_COLUMN_NAME_SET = set(LOCKED_COLUMN_NAMES)
# 九列产品文案（raw_name -> display_name）
LOCKED_COLUMN_DISPLAY_MAP: Dict[str, str] = dict(SNAPSHOT_DEFAULT_COLUMNS)


class ColumnPreferenceService:
    """用户展示字段偏好（按用户隔离）"""

    def __init__(self, username: str):
        self.username = username

    # ------------------------------------------------------------------
    # 查询（接口一：可选字段 + 已选字段）
    # ------------------------------------------------------------------

    def list_columns(self) -> Dict[str, list]:
        """返回当前用户的可选字段与已选字段。

        available_fields：与日志检索页同源的全量字段（含锁死列，前端据此渲染选择器）；
        selected_fields：用户已选 raw_name（无偏好记录时为九个固定列）。
        """

        available_fields = [
            {
                "raw_name": field.field_name,
                "display_name": LOCKED_COLUMN_DISPLAY_MAP.get(field.field_name) or str(field.description or ""),
                "is_locked": field.field_name in LOCKED_COLUMN_NAME_SET,
            }
            for field in LOG_SEARCH_ALL_FIELDS
        ]
        return {
            "available_fields": available_fields,
            "selected_fields": self.get_selected_fields(),
        }

    def get_selected_fields(self) -> List[str]:
        """已选字段（无偏好记录时返回九个固定列）。"""

        preference = UserColumnPreference.objects.filter(created_by=self.username).first()
        if not preference:
            return list(LOCKED_COLUMN_NAMES)
        return self._normalize(list(preference.selected_fields or []))

    # ------------------------------------------------------------------
    # 应用（接口二：保存选择）
    # ------------------------------------------------------------------

    def apply_columns(self, fields: List[str]) -> List[str]:
        """保存用户选择并返回规范化后的已选字段。

        规范化规则：白名单过滤（非法字段忽略）→ 去重保序 → 九个固定列兜底补齐
        且顺序固定在前 → 自选列按提交顺序追加。
        """

        normalized = self._normalize(fields)
        UserColumnPreference.objects.update_or_create(
            created_by=self.username, defaults={"selected_fields": normalized, "updated_by": self.username}
        )
        logger.info(
            "[ColumnPreferenceService] columns applied, username=%s, fields=%s",
            self.username,
            normalized,
        )
        return normalized

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(fields: List[str]) -> List[str]:
        """白名单过滤 + 去重保序 + 九列固定在前。"""

        valid_fields = [field for field in dict.fromkeys(fields) if field in LOG_SEARCH_ALL_FIELDS_MAP]
        # 防御：历史记录中可能缺失固定列（如九列口径调整），读取时同样兜底补齐
        return LOCKED_COLUMN_NAMES + [field for field in valid_fields if field not in LOCKED_COLUMN_NAME_SET]
