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

from bk_resource import api

from services.web.vision.constants import KeyVariable
from services.web.vision.handlers.filter import DeptFilterHandler


class VisionHandler:
    """
    审计报表
    """

    def query_meta(self, params: dict) -> dict:
        # 重新构造过滤条件
        vision_data = api.bk_vision.query_meta(**params)
        for f in vision_data["data"]["filters"]:
            if f["name"] == KeyVariable.DEPARTMENT:
                # 获取枚举数据
                f["query_data"] = DeptFilterHandler().get_data()
                # 设置默认值
                f["value"] = f["query_data"][0]["value"] if f["query_data"] else ""
        return vision_data

    def query_data(self, params: dict) -> dict:
        option = params.get("option", {})
        # 检测过滤条件是否合法
        variables = option.get("variables", {})
        for key, val in variables.items():
            if key == KeyVariable.DEPARTMENT:
                DeptFilterHandler().check_data(val)
        return api.bk_vision.query_data(**params)
