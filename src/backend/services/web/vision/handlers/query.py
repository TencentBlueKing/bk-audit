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
import abc
import json
from typing import Optional, Type

from bk_resource import api
from bk_resource.utils.common_utils import get_md5
from django.conf import settings
from django.core.cache import cache

from services.web.vision.constants import KeyVariable, PanelType
from services.web.vision.handlers.filter import (
    DataFilter,
    DeptFilter,
    ScenarioViewFilter,
    SingleSystemDiagnosisFilter,
    SystemDiagnosisFilter,
    TagFilter,
)


def modify_panel_meta(handler: DataFilter, chart_config: dict, vision_data: dict, uid: str):
    """基于自定义的图表处理器结果，修改面板元数据"""
    # 获取数据
    chart_config["json"] = handler.get_data()
    # 设置默认值
    chart_config["default"] = chart_config["json"][0]["value"] if chart_config["json"] else []
    # 替换外层默认值
    vision_data["filters"][uid] = chart_config["default"]


class VariablesBasedDataSetQueryCacheMixIn:
    """基于panel_id+variables进行缓存的数据集查询"""

    def query_dataset(self, params: dict) -> dict:
        option = params.get("option", {})
        variables = option.get("variables", {})
        panel_id = params.get("panel_uid")
        cache_key = self._generate_cache_key(variables, panel_id)
        if cache_key:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data

        # 如果没有命中缓存，则执行查询
        result = super().query_dataset(params)
        if cache_key:
            cache.set(cache_key, result, timeout=settings.VISION_CACHE_TIMEOUT)
        return result

    def _generate_cache_key(self, variables: dict, panel_id) -> Optional[str]:
        """根据variables生成缓存键"""
        cache_key = json.dumps(variables, sort_keys=True) + '_' + panel_id
        return "variables_based_data_set_query_cache_" + get_md5(cache_key.encode())


class VisionHandler:
    """
    审计报表数据处理器
    """

    def query_meta(self, params: dict) -> dict:
        return api.bk_vision.query_meta(**params)

    def query_dataset(self, params: dict) -> dict:
        return api.bk_vision.query_dataset(**params)

    def query_field_data(self, params: dict) -> dict:
        return api.bk_vision.query_field_data(**params)

    def query_variable_data(self, params: dict) -> dict:
        return api.bk_vision.query_variable_data(**params)

    def query_test_variable(self, params: dict) -> dict:
        return api.bk_vision.query_test_variable(**params)


class BasicVisionHandlerMixIn(abc.ABC):
    """基础审计报表数据处理器，支持某种action的基础过滤"""

    def query_meta(self, params: dict) -> dict:
        vision_data = super().query_meta(params)
        for panel in vision_data["data"]["panels"]:
            category = panel.get("category")
            if category != PanelType.ACTION:
                continue
            # 图表配置
            uid = panel["uid"]
            chart_config = panel.get("chartConfig") or {}
            match chart_config.get("flag"):
                case self.action_key_variable:
                    modify_panel_meta(self.filter_handler_class(params), chart_config, vision_data, uid)
        return vision_data

    def query_dataset(self, params: dict) -> dict:
        option = params.get("option", {})
        # 检测过滤条件是否合法
        variables = option.get("variables", {})
        for variable_config in variables:
            match variable_config["flag"]:
                case self.action_key_variable:
                    variable_config["value"] = self.filter_handler_class(params).check_data(variable_config["value"])
        return super().query_dataset(params)

    @property
    @abc.abstractmethod
    def action_key_variable(self):
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def filter_handler_class(self) -> Type[DataFilter]:
        raise NotImplementedError()


class CommonVisionHandler(VisionHandler):
    """通用审计报表数据处理器，支持通用组织架构和标签过滤"""

    def parse_flag(self, flag: str) -> str:
        if flag == KeyVariable.DEPARTMENT_NAME:
            return KeyVariable.DEPARTMENT
        return flag

    def query_meta(self, params: dict) -> dict:
        vision_data = super().query_meta(params)
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
                    modify_panel_meta(DeptFilter(params), chart_config, vision_data, uid)
                # 标签
                case KeyVariable.TAG:
                    modify_panel_meta(TagFilter(params), chart_config, vision_data, uid)
        return vision_data

    def query_dataset(self, params: dict) -> dict:
        option = params.get("option", {})
        # 检测过滤条件是否合法
        variables = option.get("variables", {})
        for variable_config in variables:
            match self.parse_flag(variable_config["flag"]):
                # 组织架构
                case KeyVariable.DEPARTMENT:
                    variable_config["value"] = DeptFilter(params).check_data(variable_config["value"])
                # 标签
                case KeyVariable.TAG:
                    variable_config["value"] = TagFilter(params).check_data(variable_config["value"])
        return api.bk_vision.query_dataset(**params)


class ScenarioViewHandler(BasicVisionHandlerMixIn, VisionHandler):
    """场景视图数据处理器"""

    action_key_variable = KeyVariable.TAG
    filter_handler_class = ScenarioViewFilter


class SystemDiagnosisVisionHandler(VariablesBasedDataSetQueryCacheMixIn, BasicVisionHandlerMixIn, VisionHandler):
    """系统诊断审计报表数据处理器，支持基于独立诊断权限的系统过滤"""

    action_key_variable = KeyVariable.SYSTEM_ID
    filter_handler_class = SystemDiagnosisFilter


class SingleSystemDiagnosisVisionHandler(VariablesBasedDataSetQueryCacheMixIn, BasicVisionHandlerMixIn, VisionHandler):
    """单系统诊断审计报表数据处理器，支持基于管理员权限的系统过滤"""

    action_key_variable = KeyVariable.SYSTEM_ID
    filter_handler_class = SingleSystemDiagnosisFilter
