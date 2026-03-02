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
from typing import Dict, List, Optional

from django.conf import settings

from core.utils.service import get_service_name

__all__ = ["Event"]


class Event:
    name: str = ""  # 事件名称
    labelnames: List[str] = []  # 维度字段列表
    documentation: str = ""  # 事件说明

    # 监控平台鉴权信息
    data_id: int = settings.ALERT_DATA_ID
    access_token: str = settings.ALERT_ACCESS_TOKEN

    def __init__(self, target: str, context: Dict, extra: Optional[Dict] = None):
        self.target = target
        self.timestamp = int(time.time() * 1000)

        # 构建维度
        self.dimension = {field: str(context.get(field, "")) for field in self.labelnames}
        self.dimension["job"] = get_service_name()

        # 构建内容
        if extra:
            detail = ", ".join(f"{k}={v}" for k, v in extra.items())
            self.content = f"{self.documentation or self.name}: {detail}"
        else:
            self.content = self.documentation or self.name

    def to_json(self) -> Dict:
        return {
            "data_id": self.data_id,
            "access_token": self.access_token,
            "data": [
                {
                    "event_name": str(self.name),
                    "event": {"content": self.content},
                    "target": self.target,
                    "dimension": self.dimension,
                    "timestamp": self.timestamp,
                }
            ],
        }
