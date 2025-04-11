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
import time
from typing import Dict, List, Union

from bk_resource import api, resource
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q, QuerySet

from apps.feature.constants import FeatureTypeChoices
from apps.feature.handlers import FeatureHandler
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.fields import SYSTEM_ID
from services.web.analyze.constants import (
    BKBASE_ATTR_GROUP_FIELD_NAME,
    BKBASE_DEFAULT_BASELINE_LOCATION,
    BKBASE_DEFAULT_COUNT_FREQ,
    BKBASE_DEFAULT_OFFSET,
    BKBASE_DEFAULT_WINDOW_COLOR,
    BKBASE_GROUP_BY_FIELD_CONTAINER_TYPE,
    BKBASE_ORIGIN_DATA_FIELD,
    BKBASE_PLAN_PUBLISHED_STATUS,
    BKBASE_PLAN_TAG,
    BKBASE_STRATEGY_ID_FIELD,
    BKBASE_SYSTEM_FIELD_ROLE,
    BaseControlTypeChoices,
    ControlTypeChoices,
    FilterConnector,
    FilterOperator,
    FlowDataSourceNodeType,
    FlowSQLNodeType,
    OffsetUnit,
    OutputBaselineType,
    ScenePlanServingMode,
    WindowDependencyRule,
    WindowType,
)
from services.web.analyze.controls.base import BkbaseFlowController, Controller
from services.web.analyze.exceptions import ClusterNotExists
from services.web.analyze.models import Control, ControlVersion
from services.web.analyze.utils import calculate_offline_flow_start_time, is_asset
from services.web.databus.constants import DEFAULT_RETENTION, DEFAULT_STORAGE_CONFIG_KEY
from services.web.risk.constants import EventMappingFields
from services.web.risk.handlers import EventHandler
from services.web.strategy_v2.constants import MappingType, TableType
from services.web.strategy_v2.exceptions import FieldsEmptyError


class AIOpsController(Controller, BkbaseFlowController):
    """
    Control BKBASE AIOPS Strategy
    """

    base_control_type = BaseControlTypeChoices.CONTROL

    @transaction.atomic()
    def _update_or_create_bkbase_flow(self) -> bool:
        # check create flow
        is_create = not self.strategy.backend_data.get("flow_id")
        if is_create:
            self._create_flow()
        # create or update node
        last_node_id = 0
        node_configs = self._build_flow_nodes()
        for index, node_config in enumerate(node_configs):
            node = {
                "flow_id": self.strategy.backend_data["flow_id"],
                "frontend_info": {"x": (index + 1) * 300, "y": 30},
                "from_links": self._describe_from_links(index, last_node_id),
                "node_type": node_config["node_type"],
                "config": node_config,
            }
            # 离线节点需要配置上游id
            if node["config"].get("inputs") and "id" in node["config"]["inputs"][0]:
                node["config"]["inputs"][0]["id"] = last_node_id
            if is_create:
                resp = api.bk_base.create_flow_node(**node)
            else:
                node["node_id"] = node_config["node_id"]
                resp = api.bk_base.update_flow_node(**node)
            last_node_id = resp["node_id"]
            logger.info(
                "[CreateOrUpdateBkBaseFlowNodeSuccess] FlowID => %s; NodeID => %s",
                self.strategy.backend_data["flow_id"],
                last_node_id,
            )
        return is_create

    def check_flow_status(self, strategy_id: int, success_status: str, failed_status: str, other_status: str):
        if not AiopsFeature(help_text="check_flow_status").available:
            return
        return super().check_flow_status(strategy_id, success_status, failed_status, other_status)

    def _create_flow(self) -> None:
        resp = api.bk_base.create_flow(project_id=settings.BKBASE_PROJECT_ID, flow_name=self.flow_name)
        self.strategy.backend_data["flow_id"] = resp["flow_id"]
        self.strategy.save(update_record=False, update_fields=["backend_data"])

    def _build_flow_nodes(self) -> List[dict]:
        """
        build flow node configs

        self.strategy.configs = {
            "data_source": {
                "source_type": "stream_source",
                "result_table_id": "",
                "filter_config": {},
                "fields": [{"field_name": "cmd", "source_field": "extend_data.cmd"}],
            }
        }
        """

        # init params
        flow_id = self.strategy.backend_data["flow_id"]
        project_id = settings.BKBASE_PROJECT_ID
        bk_biz_id = self.strategy.configs["data_source"]["result_table_id"].split("_", 1)[0]
        raw_table_name = self.strategy.backend_data.get("raw_table_name") or str(time.time_ns())
        self.strategy.backend_data["raw_table_name"] = raw_table_name
        self.strategy.save(update_record=False, update_fields=["backend_data"])

        # init nodes
        nodes = [
            self._build_data_source_node(),
            self._build_sql_node(
                bk_biz_id=bk_biz_id,
                raw_table_name=raw_table_name,
            ),
            self._build_scene_node(
                bk_biz_id=bk_biz_id,
                raw_table_name=raw_table_name,
                flow_id=flow_id,
                project_id=project_id,
            ),
            self._build_storage_node(bk_biz_id=bk_biz_id, raw_table_name=raw_table_name),
        ]

        # get exist nodes
        if self.strategy.backend_data.get("flow_id"):
            bkbase_nodes = api.bk_base.get_flow_graph(flow_id=self.strategy.backend_data["flow_id"])["nodes"]
            if bkbase_nodes:
                node_ids = [node["node_id"] for node in bkbase_nodes]
                for index, node in enumerate(nodes):
                    node["node_id"] = node_ids[index]

        return nodes

    def _build_data_source_node(self) -> dict:
        """
        build data source node
        """

        data_source = self.strategy.configs["data_source"]
        source_type = data_source["source_type"]

        if source_type == FlowDataSourceNodeType.BATCH:
            source_type = self.check_source_type(result_table_id=data_source["result_table_id"])

        return {
            "node_type": source_type,
            "from_result_table_ids": [data_source["result_table_id"]],
            "result_table_id": data_source["result_table_id"],
            "name": data_source["result_table_id"],
        }

    def check_source_type(self, result_table_id: str) -> str:
        """
        check batch / batch_join
        """

        result_table = api.bk_base.get_result_table(result_table_id=result_table_id)
        if is_asset(result_table):
            return FlowDataSourceNodeType.BATCH
        else:
            return FlowDataSourceNodeType.BATCH_REAL

    def _build_sql_node(self, bk_biz_id: int, raw_table_name: str) -> dict:
        """
        build sql node
        """

        # init params
        data_source = self.strategy.configs["data_source"]
        source_type = data_source["source_type"]
        plan_config = data_source.get("plan_config", {})
        aiops_config = self.strategy.configs.get("aiops_config", {})

        # check source type
        if source_type == FlowDataSourceNodeType.BATCH:
            source_type = self.check_source_type(result_table_id=data_source["result_table_id"])

        # init sql node
        sql_node_type = FlowSQLNodeType.get_sql_node_type(data_source["source_type"])
        sql_node_params = {
            "node_type": sql_node_type,
            "bk_biz_id": bk_biz_id,
            "from_result_table_ids": [data_source["result_table_id"]],
            "name": f"{sql_node_type}_{raw_table_name}",
            "table_name": f"{sql_node_type}_{raw_table_name}",
            "output_name": f"{sql_node_type}_{raw_table_name}",
        }
        # add realtime node
        if sql_node_type == FlowSQLNodeType.REALTIME:
            sql_node_params.update(
                {
                    "sql": self._build_sql(),
                }
            )
            return sql_node_params
        elif sql_node_type == FlowSQLNodeType.BATCH_V2:
            # 获取调度频率和周期
            count_freq = plan_config.get("count_freq") or aiops_config.get("count_freq", BKBASE_DEFAULT_COUNT_FREQ)
            schedule_period = plan_config.get("schedule_period") or aiops_config.get("schedule_period", OffsetUnit.HOUR)
            start_time_str = calculate_offline_flow_start_time(schedule_period)

            sql_node_params.update(
                {
                    "outputs": [
                        {
                            "bk_biz_id": bk_biz_id,
                            "table_name": sql_node_params["table_name"],
                            "output_name": sql_node_params["output_name"],
                        }
                    ],
                    "inputs": [{"id": 0, "from_result_table_ids": sql_node_params["from_result_table_ids"]}],
                    "dedicated_config": {
                        "sql": self._build_sql(),
                        "self_dependence": {
                            "self_dependency_config": {"fields": [], "dependency_rule": WindowDependencyRule.NO_FAILED},
                            "self_dependency": False,
                        },
                        "schedule_config": {
                            "count_freq": count_freq,
                            "schedule_period": schedule_period,
                            "start_time": start_time_str,
                        },
                        "output_config": {
                            "enable_customize_output": False,
                            "output_baseline_location": BKBASE_DEFAULT_BASELINE_LOCATION,
                            "output_offset": BKBASE_DEFAULT_OFFSET,
                            "output_offset_unit": OffsetUnit.HOUR,
                            "output_baseline_type": OutputBaselineType.SCHEDULE,
                            "output_baseline": "",
                        },
                    },
                    "window_info": [
                        {
                            "window_offset": plan_config.get("window_offset", BKBASE_DEFAULT_OFFSET),
                            "window_offset_unit": plan_config.get("window_offset_unit", OffsetUnit.HOUR),
                            "window_size": plan_config.get("window_size")
                            or plan_config.get("count_freq")
                            or aiops_config.get("count_freq", BKBASE_DEFAULT_COUNT_FREQ),
                            "window_size_unit": plan_config.get("window_size_unit")
                            or plan_config.get("schedule_period")
                            or aiops_config.get("schedule_period", OffsetUnit.HOUR),
                            "dependency_rule": plan_config.get("window_offset_unit", WindowDependencyRule.NO_FAILED),
                            "accumulate_start_time": start_time_str,
                            "result_table_id": sql_node_params["from_result_table_ids"][0],
                            "window_type": WindowType.WHOLE
                            if source_type == FlowDataSourceNodeType.BATCH
                            else WindowType.SCROLL,
                            "color": BKBASE_DEFAULT_WINDOW_COLOR,
                        }
                    ],
                }
            )
            return sql_node_params

    def _trans_fields_standard(self, fields: dict) -> List[dict]:
        """
        trans fields to standard fields
        """

        fields_data = {}
        for system_id, fields in fields.items():
            # 遍历所有字段，添加系统信息
            for field in fields:
                # 不存在则需要先创建
                field_name = field["field_name"]
                if field_name not in fields_data:
                    fields_data[field_name] = []
                # 初始化字段的系统信息
                for source_field in field["source_field"]:
                    source_field["system_id"] = system_id
                fields_data[field_name].extend(field["source_field"])
        return [
            {"field_name": field_name, "source_field": source_field} for field_name, source_field in fields_data.items()
        ]

    def _build_scene_node(self, bk_biz_id: int, raw_table_name: str, flow_id: int, project_id: int) -> dict:
        """
        build scene node
        """

        aiops_config = self.strategy.configs.get("aiops_config", {})
        input_config = self.strategy.control_version_inst.input_config
        extra_config = self.strategy.control_version_inst.extra_config
        data_source = self.strategy.configs["data_source"]
        sql_node_type = FlowSQLNodeType.get_sql_node_type(data_source["source_type"])
        variable_config = self.strategy.configs.get("variable_config") or []

        # 获取调度频率和周期
        count_freq = aiops_config.get("count_freq", BKBASE_DEFAULT_COUNT_FREQ)
        schedule_period = aiops_config.get("schedule_period", OffsetUnit.HOUR)
        start_time_str = calculate_offline_flow_start_time(schedule_period)

        return {
            "node_type": "scenario_app",
            "outputs": [{}],
            "inputs": [{}],
            "name": f"scenario_{raw_table_name}",
            "bk_biz_id": bk_biz_id,
            "table_name": f"scenario_{raw_table_name}",
            "output_name": f"scenario_{raw_table_name}",
            "dedicated_config": {
                "scene_id": extra_config["scene_id"],
                "scene_name": extra_config.get("scene_name", extra_config["scene_id"]),
                "plan_id": extra_config["plan_id"],
                "plan_version_id": extra_config["latest_plan_version_id"],
                "project_id": project_id,
                "flow_id": flow_id,
                "has_group": aiops_config.get("has_group", False),
                "input_mapping": {
                    _input_config["dataset_name"]: {
                        "has_group": False,
                        "group_dimension": [],
                        "mapping": self._build_field_mapping(_input_config["require_fields"]),
                        "input_dataset_id": "{}_{}_{}".format(bk_biz_id, sql_node_type, raw_table_name),
                    }
                    for _input_config in input_config
                },
                "variable_config": variable_config,
                "schedule_config": {
                    "count_freq": count_freq,
                    "schedule_period": schedule_period,
                    "start_time": start_time_str,
                }
                if sql_node_type == FlowSQLNodeType.BATCH_V2
                else {},
                "window_info": {
                    "window_offset": aiops_config.get("window_offset", BKBASE_DEFAULT_OFFSET),
                    "window_offset_unit": aiops_config.get("window_offset_unit", OffsetUnit.HOUR),
                    "window_size": aiops_config.get("window_size")
                    or aiops_config.get("count_freq", BKBASE_DEFAULT_COUNT_FREQ),
                    "window_size_unit": aiops_config.get("window_size_unit")
                    or aiops_config.get("schedule_period", OffsetUnit.HOUR),
                    "dependency_rule": aiops_config.get("window_offset_unit", WindowDependencyRule.NO_FAILED),
                    "accumulate_start_time": start_time_str,
                    "result_table_id": data_source["result_table_id"],
                    "window_type": WindowType.SCROLL,
                    "color": BKBASE_DEFAULT_WINDOW_COLOR,
                }
                if sql_node_type == FlowSQLNodeType.BATCH_V2
                else {},
                "execute_config": {"dropna_enabled": False},
            },
            "window_info": {},
            "from_result_table_ids": ["{}_{}_{}".format(bk_biz_id, sql_node_type, raw_table_name)],
            "from_biz_ids": [bk_biz_id],
            "serving_mode": ScenePlanServingMode.REALTIME
            if sql_node_type == FlowSQLNodeType.REALTIME
            else ScenePlanServingMode.BATCH,
        }

    def _build_storage_node(self, bk_biz_id: int, raw_table_name: str) -> dict:
        """
        build storage node
        """

        # add storage node
        # storage
        default_cluster_id = int(
            GlobalMetaConfig.get(
                DEFAULT_STORAGE_CONFIG_KEY,
                config_level=ConfigLevelChoices.NAMESPACE.value,
                instance_key=self.strategy.namespace,
            )
        )
        cluster_info = None
        clusters = resource.databus.storage.storage_list(namespace=self.strategy.namespace)
        for item in clusters:
            if item["cluster_config"]["cluster_id"] == default_cluster_id:
                cluster_info = item
        if cluster_info is None:
            raise ClusterNotExists()
        bkbase_cluster_id = cluster_info["cluster_config"].get("custom_option", {})["bkbase_cluster_id"]
        table_id = EventHandler.get_table_id().replace(".", "_")

        return {
            "node_type": "elastic_storage",
            "name": f"es_storage_{raw_table_name}",
            "result_table_id": f"{bk_biz_id}_scenario_{raw_table_name}",
            "bk_biz_id": bk_biz_id,
            "indexed_fields": [],
            "cluster": bkbase_cluster_id,
            "expires": DEFAULT_RETENTION,
            "has_replica": False,
            "has_unique_key": False,
            "storage_keys": [],
            "analyzed_fields": [],
            "doc_values_fields": [],
            "json_fields": [],
            "from_result_table_ids": [f"{bk_biz_id}_scenario_{raw_table_name}"],
            "physical_table_name": f"write_{{yyyyMMdd}}_{table_id}",
        }

    def _build_sql(self) -> str:
        """
        build flow sql
        """

        data_source = self.strategy.configs["data_source"]
        fields = data_source["fields"]

        if not fields:
            raise FieldsEmptyError()

        # 操作事件
        if self.strategy.configs["config_type"] == TableType.EVENT_LOG:
            fields = self._trans_fields_standard(fields)
            sql_fields = []
            system_ids = set()
            for field in fields:
                sql_whens = []
                for source_field in field["source_field"]:
                    system_ids.add(source_field["system_id"])
                    sql_whens.append(
                        "WHEN system_id = '{system_id}' {action_id} THEN {field_mapping}".format(
                            system_id=source_field["system_id"],
                            action_id="AND action_id = '{}'".format(source_field["action_id"])
                            if source_field["mapping_type"] == MappingType.ACTION
                            else "",
                            field_mapping=self._build_sql_fields(
                                field_mapping=[
                                    {"field_name": field["field_name"], "source_field": source_field["source_field"]}
                                ],
                                using_as=False,
                                add_strategy_id=False,
                            )[0],
                        )
                    )
                sql_fields.append("CASE \n{}\nELSE NULL \nEND as {}".format(" \n".join(sql_whens), field["field_name"]))
            sql_fields.append(self._build_sql_fields([], using_as=True, add_strategy_id=True)[0])
            system_filter = self._build_sql_filter(
                [{"key": SYSTEM_ID.field_name, "method": FilterOperator.EQUAL, "value": list(system_ids)}]
            )
            return "SELECT \n{fields}{origin_data_field} \nFROM {table} \n{where}".format(
                fields=", \n".join(sql_fields),
                origin_data_field=self._build_origin_data_field(data_source["result_table_id"]),
                table=data_source["result_table_id"],
                where=system_filter,
            )
        # 资产审计
        return "select {fields}{origin_data_field} from {table} {where}".format(
            fields=", ".join(self._build_sql_fields(data_source["fields"])),
            origin_data_field=self._build_origin_data_field(data_source["result_table_id"]),
            table=data_source["result_table_id"],
            where=self._build_sql_filter(data_source.get("filter_config", [])),
        )

    def _build_origin_data_field(self, result_table_id: str) -> str:
        """
        build origin data field
        """

        sql = ", {}('{{}}', {{}}) as {}".format(settings.BKBASE_UDF_BUILD_ORIGIN_DATA_FUNC, BKBASE_ORIGIN_DATA_FIELD)
        origin_fields = []
        origin_sqls = []

        for field in api.bk_base.get_rt_fields(result_table_id=result_table_id):
            if field["field_name"] == "timestamp":
                continue
            origin_fields.append(field["field_name"])
            origin_sqls.append("cast(`{}` as string)".format(field["field_name"]))
            origin_sqls.append("'{}'".format(settings.BKBASE_BUILD_ORIGIN_DATA_SEPERATOR))

        sql = sql.format(
            settings.BKBASE_BUILD_ORIGIN_DATA_SEPERATOR.join(origin_fields),
            "CONCAT_WS('', {})".format(",".join(origin_sqls[: len(origin_sqls) - 1])),
        )

        if origin_fields:
            return sql
        return ""

    @classmethod
    def _build_sql_filter(cls, filter_config: List[dict]) -> str:
        """
        build sql where
        """

        # empty filter
        if not filter_config:
            return ""

        # filter
        filter_string = "where "
        for index, _filter in enumerate(filter_config):
            _filter_conditions = []
            # 针对包含/不包含特殊处理
            if _filter["method"] in (FilterOperator.IN, FilterOperator.NOT_IN):
                values_str = ",".join(f'''"{v.replace("'", "''")}"''' for v in _filter["value"])
                condition = f"{_filter['key']} {_filter['method']} ({values_str})"
                _filter_conditions = [condition]
            elif _filter["method"] in (FilterOperator.IS_NULL, FilterOperator.NOT_NULL):
                condition = f"{_filter['key']} {_filter['method']}"
                _filter_conditions = [condition]
            else:
                _filter_conditions = [
                    "{} {} '{}'".format(_filter["key"], _filter["method"], _value.replace("'", "''"))
                    for _value in _filter["value"]
                ]

            filter_string = (
                filter_string
                + (_filter["connector"] if index else "")
                + " ("
                + f" {FilterConnector.OR.value} ".join(_filter_conditions)
                + ") "
            )
        return filter_string

    def _describe_from_links(self, index: int, last_node_id: int):
        if index == 0:
            return []

        return [
            {
                "source": {"node_id": last_node_id, "id": f"ch_{last_node_id}", "arrow": "Left"},
                "target": {"id": f"bk_node_{int(datetime.datetime.now().timestamp() * 1000)}", "arrow": "Left"},
            }
        ]

    def _build_sql_fields(
        self, field_mapping: List[dict], using_as: bool = True, add_strategy_id: bool = True
    ) -> List[str]:
        """
        build sql fields for realtime/batch node
        """

        fields = []

        for field in field_mapping:
            # 如果需要提取需要使用udf
            if field["source_field"].find(".") != -1:
                _parent_field, _child_field = field["source_field"].split(".", 1)
                fields.append(
                    "{}({}, '{}') {}".format(
                        settings.BKBASE_UDF_JSON_EXTRACT_FUNC,
                        _parent_field,
                        _child_field,
                        f"as {field['field_name']}" if using_as else "",
                    )
                )
                continue
            # 否则直接赋值
            fields.append("{} {}".format(field["source_field"], f"as {field['field_name']}" if using_as else ""))

        # 增加策略ID
        if add_strategy_id:
            fields.append("{} as {}".format(self.strategy.strategy_id, EventMappingFields.STRATEGY_ID.field_name))

        return fields

    def _build_field_mapping(self, input_fields: List[dict]) -> dict:
        """
        build field mapping
        1. 首先区分 field_container_type，如果这个字段存在(老版本可能不存在)， 且值为 group， 说明是字段组，初始不会有默认值，需要用户填
           充，填充保存后填入字段信息会在components中
        2. 条件1以外的情况，data_field_name 代表了字段的映射情况， 有值说明字段已经映射， 没有值说明字段没有被映射
        3. roles中包含了 system 角色的是系统字段， 默认会映射自身，且用户不可改（1中的字段组除外，应为字段组是往其中填充成员，而不是修改映射）
        """

        # 获取映射的结果表
        configured_fields = self.strategy.configs["data_source"]["fields"]
        if isinstance(configured_fields, list):
            configured_fields = [f["field_name"] for f in configured_fields]
        elif isinstance(configured_fields, dict):
            configured_fields = list({f["field_name"] for config in configured_fields.values() for f in config})
        else:
            configured_fields = []

        mapping = {}

        for field in input_fields:
            # 完整数据字段
            if field["field_name"] in [BKBASE_ORIGIN_DATA_FIELD, BKBASE_STRATEGY_ID_FIELD]:
                mapping[field["field_name"]] = {"input_field_name": field["field_name"]}
                continue
            # 透传字段
            if field["field_name"] == BKBASE_ATTR_GROUP_FIELD_NAME:
                mapping[field["field_name"]] = {"input_field_name": []}
                continue
            # 判断是否为分组字段
            if field.get("field_container_type") == BKBASE_GROUP_BY_FIELD_CONTAINER_TYPE:
                mapping[field["field_name"]] = {"input_field_name": []}
                continue
            # 判断是否有默认值
            data_field_name = field.get("data_field_name", "")
            if data_field_name:
                mapping[field["field_name"]] = {"input_field_name": data_field_name}
                continue
            # 系统字段赋值
            if BKBASE_SYSTEM_FIELD_ROLE in field.get("properties", {}).get("roles", []):
                mapping[field["field_name"]] = {"input_field_name": field["field_name"]}
                continue
            # 判断是否需要
            if field["field_name"] in configured_fields:
                mapping[field["field_name"]] = {"input_field_name": field["field_name"]}
                continue
            mapping[field["field_name"]] = {"input_field_name": ""}
        return mapping

    def _parse_field_name(self, field_name: str, field: dict) -> Union[str, list]:
        """
        parse field to bkbase field map
        """

        if field_name == BKBASE_ATTR_GROUP_FIELD_NAME:
            return []
        return field["field_name"]


class AiopsFeature:
    def __init__(self, help_text: str):
        self.help_text = help_text

    @property
    def available(self) -> bool:
        if FeatureHandler(FeatureTypeChoices.BKBASE_AIOPS).check() and settings.BKBASE_PROJECT_ID:
            return True
        logger.info(
            "[AiopsFeatureCheckFailed] BkBase Aiops Not Supported or Project ID Unset; HelpText => %s", self.help_text
        )
        return False


class AiopsPlanSyncHandler:
    """
    处理AIOPS方案同步
    """

    def sync(self) -> None:
        """
        同步
        """

        # 获取数据库中已经存储的AIOPS控件列表以及其对应的最新版本
        control_versions: List[ControlVersion] = list(self.load_control_from_db())
        db_plans = {cv.extra_config["plan_id"]: cv for cv in control_versions}
        db_plan_ids = set(db_plans.keys())
        # 获取BKBASE的所有方案
        bkbase_plans = self.load_plan_from_bkbase()
        bkbase_plan_map = {plan["plan_id"]: plan for plan in bkbase_plans}
        bkbase_plan_ids = set(bkbase_plan_map.keys())
        # 删除不存在的
        self.delete_control(
            control_versions=self.filter_control_by_plan(
                plan_control_map=db_plans, plan_ids=(db_plan_ids - bkbase_plan_ids)
            )
        )
        # 更新或创建
        self.update_or_create_control(bkbase_plans=bkbase_plans, control_versions=db_plans)

    def load_control_from_db(self) -> QuerySet:
        """
        从数据库中加载已经存在的
        """

        # 获取所有AIOPS控件，一个控件对应一个AIOPS方案
        aiops_controls = Control.objects.filter(control_type_id=ControlTypeChoices.AIOPS.value)
        # 没有时直接返回
        if not aiops_controls:
            return ControlVersion.objects.none()
        # 获取每个控件的最新版本
        latest_versions = (
            ControlVersion.objects.filter(control_id__in=aiops_controls.values("control_id"))
            .values("control_id")
            .annotate(control_version=Max("control_version"))
        )
        # 组装查询参数
        q = Q()
        for _v in latest_versions:
            q |= Q(control_id=_v["control_id"], control_version=_v["control_version"])
        # 获取所有控件的最新版本
        return ControlVersion.objects.filter(q)

    def load_plan_from_bkbase(self) -> List:
        """
        从BKBASE拉取所有的方案
        """

        # 获取所有带标签的方案，并且需要是启用状态
        return [
            plan
            for plan in api.bk_base.get_scene_plans(tags=BKBASE_PLAN_TAG)
            if plan["status"] == BKBASE_PLAN_PUBLISHED_STATUS
        ]

    def update_or_create_control(self, bkbase_plans: List[dict], control_versions: Dict[int, ControlVersion]) -> None:
        """
        创建或删除控件
        """

        for plan in bkbase_plans:
            plan_id = plan["plan_id"]
            plan_detail = api.bk_base.get_plan_detail(plan_id=plan_id)
            # 方案不存在则创建
            if not control_versions.get(plan_id):
                self.create_control_and_control_version(plan_detail)
                continue
            # 方案存在需要比较方案版本号，相同则跳过，不同则创建
            control_version = control_versions[plan_id]
            if control_version.extra_config["latest_plan_version_id"] == plan_detail["latest_plan_version_id"]:
                continue
            self.create_control_and_control_version(plan_detail, control_version)

    @transaction.atomic()
    def create_control_and_control_version(self, plan_detail: dict, control_version: ControlVersion = None) -> None:
        """
        创建控件和控件版本
        """

        control = self.create_or_update_control(control_name=plan_detail["plan_alias"], control_version=control_version)
        self.create_control_version(control=control, plan_detail=plan_detail)

    def create_or_update_control(self, control_name: str, control_version: ControlVersion = None) -> Control:
        """
        创建或更新控件信息
        """

        if control_version:
            control = Control.objects.get(control_id=control_version.control_id)
            control.control_name = control_name
            control.save(update_fields=["control_name"])
            return control
        return Control.objects.create(control_name=control_name, control_type_id=ControlTypeChoices.AIOPS.value)

    def create_control_version(self, control: Control, plan_detail: dict) -> None:
        """
        创建控件版本
        """

        ControlVersion.objects.create(
            control_id=control.control_id,
            control_version=plan_detail["version_no"][1:],
            input_config=plan_detail["io_info"]["input_config"],
            output_config=plan_detail["io_info"]["output_config"],
            variable_config=plan_detail["variable_info"],
            extra_config=plan_detail,
        )

    def delete_control(self, control_versions: List[ControlVersion]) -> None:
        """
        删除不存在的控件
        """

        for cv in control_versions:
            # 事务删除
            with transaction.atomic():
                # 删除控件版本
                ControlVersion.objects.filter(control_id=cv.control_id).delete()
                # 删除控件
                Control.objects.filter(control_id=cv.control_id).delete()

    def filter_control_by_plan(self, plan_control_map: dict, plan_ids: Union[list, tuple, set]) -> List[ControlVersion]:
        """
        由方案ID获取对应的控件版本
        """

        return [control_version for plan_id, control_version in plan_control_map.items() if plan_id in plan_ids]
