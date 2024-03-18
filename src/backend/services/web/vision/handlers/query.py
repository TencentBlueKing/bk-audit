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

from services.web.vision.constants import KeyVariable, PanelType
from services.web.vision.handlers.filter import DeptFilterHandler


class VisionHandler:
    """
    审计报表
    """

    def parse_flag(self, flag: str) -> str:
        if flag == KeyVariable.DEPARTMENT_NAME:
            return KeyVariable.DEPARTMENT
        return flag

    def query_meta(self, params: dict) -> dict:
        # 重新构造过滤条件
        vision_data = api.bk_vision.query_meta(**params)
        for panel in vision_data["data"]["panels"]:
            category = panel.get("category")
            if category != PanelType.ACTION:
                continue
            # 图表配置
            uid = panel["uid"]
            chart_config = panel.get("chartConfig") or {}
            match self.parse_flag(chart_config.get("flag")):
                # 组织架构
                case KeyVariable.DEPARTMENT:
                    # 获取数据
                    chart_config["json"] = DeptFilterHandler().get_data()
                    # 设置默认值
                    chart_config["default"] = chart_config["json"][0]["value"] if chart_config["json"] else []
                    # 替换外层默认值
                    vision_data["filters"][uid] = chart_config["default"]
        return vision_data

    def query_dataset(self, params: dict) -> dict:
        option = params.get("option", {})
        # 检测过滤条件是否合法
        variables = option.get("variables", {})
        for variable_config in variables:
            match self.parse_flag(variable_config["flag"]):
                # 组织架构
                case KeyVariable.DEPARTMENT:
                    DeptFilterHandler().check_data(variable_config["value"])
        return api.bk_vision.query_dataset(**params)
