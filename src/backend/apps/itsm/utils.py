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
"""
ITSM V4 -> V3 结构适配。

V4 的 workflows() 返回的是「流程启用版本详情」，字段定义散落在
form_canvas_data.jsonschema.properties（类型/选项/表格列）与
form_canvas_data.form_data.layout[].list[]（组件类型/描述/校验）两处，
且 key 带 ticket__ 命名空间前缀；而 V3 的 get_service_detail 返回的是
顶层带 fields 列表的服务详情。本模块负责把前者适配成后者，
使下游（前端审批字段配置、ProcessApplication.approve_config）无需改动。
"""

# V4 表单字段 key 的命名空间前缀（如 ticket__title）
TICKET_FIELD_PREFIX = "ticket__"

# V3 校验类型
VALIDATE_TYPE_REQUIRE = "REQUIRE"
VALIDATE_TYPE_EMPTY = "EMPTY"

# V4 表单组件类型（form_canvas_data.form_data.layout[].list[].type）-> V3 字段类型
V4_LAYOUT_TYPE_TO_V3 = {
    "text": "STRING",
    "input": "STRING",
    "textarea": "TEXTAREA",
    "richtext": "RICHTEXT",
    "int": "INT",
    "number": "INT",
    "float": "DOUBLE",
    "select": "SELECT",
    "multiselect": "MULTISELECT",
    "radio": "RADIO",
    "checkbox": "CHECKBOX",
    "date": "DATE",
    "datetime": "DATETIME",
    "time": "TIME",
    "table": "CUSTOMTABLE",
    "customtable": "CUSTOMTABLE",
    "user": "MEMBER",
    "member": "MEMBER",
    "file": "FILE",
    "link": "LINK",
    "bool": "BOOLEAN",
    "switch": "BOOLEAN",
}

# V4 jsonschema type -> V3 字段类型（组件类型缺失时的兜底）
V4_JSONSCHEMA_TYPE_TO_V3 = {
    "string": "STRING",
    "integer": "INT",
    "number": "INT",
    "boolean": "BOOLEAN",
    "array": "MULTISELECT",
    "object": "STRING",
}


def strip_ticket_prefix(key: str) -> str:
    """
    去掉 V4 字段 key 的 ticket__ 命名空间前缀。

    V4 提单 form_data 需要带前缀的 key（ticket__title），
    而前端展示与 approve_config 使用的是裸键（title）。
    """

    if key.startswith(TICKET_FIELD_PREFIX):
        return key[len(TICKET_FIELD_PREFIX) :]
    return key.split("__", 1)[-1]


def build_layout_field_map(form_data: dict) -> dict:
    """
    把 form_canvas_data.form_data.layout 拉平成 {字段key: 字段配置}。
    """

    result = {}
    for row in (form_data or {}).get("layout") or []:
        for item in row.get("list") or []:
            if item.get("key"):
                result[item["key"]] = item
    return result


def get_form_properties(workflow: dict) -> dict:
    """
    取流程表单的 jsonschema.properties（V4 字段定义的权威来源）。
    """

    form_canvas_data = (workflow or {}).get("form_canvas_data") or {}
    return ((form_canvas_data.get("jsonschema") or {}).get("properties")) or {}


def normalize_choice(options) -> list:
    """
    把 V4 的 itsm_options 归一化为 V3 的 choice：[{"key":..., "name":...}]。
    """

    if not options:
        return []
    return [{"key": item.get("key", ""), "name": item.get("name", "")} for item in options if isinstance(item, dict)]


def resolve_field_type(prop: dict, layout_item: dict) -> str:
    """
    推断 V3 字段类型。优先级：表格列 > layout 组件类型 > 选项 > jsonschema type。
    """

    prop = prop or {}
    # 自定义表格：jsonschema 里带 columns
    if prop.get("columns"):
        return "CUSTOMTABLE"
    # layout 里的组件类型最贴近 V3 的字段类型
    layout_type = (layout_item.get("type") or "").lower()
    if layout_type in V4_LAYOUT_TYPE_TO_V3:
        return V4_LAYOUT_TYPE_TO_V3[layout_type]
    # 带选项的字段：数组为多选，其余为单选
    if prop.get("itsm_options"):
        return "MULTISELECT" if prop.get("type") == "array" else "SELECT"
    # jsonschema type / format 兜底
    js_type = (prop.get("type") or "").lower()
    if js_type == "string":
        if prop.get("format") == "date":
            return "DATE"
        if prop.get("format") == "date-time":
            return "DATETIME"
    return V4_JSONSCHEMA_TYPE_TO_V3.get(js_type, "STRING")


def parse_v4_workflow_fields(workflow: dict) -> list:
    """
    把 V4 workflow 的表单定义解析为 V3 的 fields 列表。

    返回结构与 V3 get_service_detail 的 data.fields 保持一致：
    {"id", "key", "type", "name", "desc", "choice", "validate_type", "regex", "meta"}
    """

    properties = get_form_properties(workflow)
    layout_map = build_layout_field_map(((workflow or {}).get("form_canvas_data") or {}).get("form_data"))

    fields = []
    for index, (key, prop) in enumerate(properties.items(), start=1):
        prop = prop or {}
        layout_item = layout_map.get(key) or {}
        verification = layout_item.get("verification") or {}
        required = (verification.get("required") or {}).get("enabled", False)
        # 嵌套子表单（如对象类型字段）透传到 meta，避免前端丢字段
        meta = {}
        if prop.get("columns"):
            meta["columns"] = prop["columns"]
        if prop.get("properties"):
            meta["properties"] = prop["properties"]
        fields.append(
            {
                "id": index,
                "key": strip_ticket_prefix(key),
                "type": resolve_field_type(prop, layout_item),
                "name": prop.get("title") or (layout_item.get("title") or {}).get("value") or strip_ticket_prefix(key),
                "desc": layout_item.get("desc") or layout_item.get("tips") or "",
                "choice": normalize_choice(prop.get("itsm_options")),
                "validate_type": VALIDATE_TYPE_REQUIRE if required else VALIDATE_TYPE_EMPTY,
                "regex": (verification.get("formatLimit") or {}).get("expression") or VALIDATE_TYPE_EMPTY,
                "meta": meta,
            }
        )
    return fields


def adapt_v4_workflow_to_service_detail(workflow: dict, name: str = "") -> dict:
    """
    把 V4 workflows().items[i] 适配成 V3 get_service_detail 的返回结构。

    :param workflow: V4 流程启用版本详情（workflows().items[i]）
    :param name: 流程名称。V4 workflows 响应不含名称，需由调用方从
                 system_workflow_list 带回；拿不到时降级为 workflow_key。
    """

    if not workflow:
        return {}
    workflow_key = workflow.get("workflow_key") or ""
    return {
        "service_id": workflow_key,
        "workflow_id": workflow.get("key") or "",
        "name": name or workflow_key,
        "service_type": "event",
        "desc": workflow.get("desc") or "",
        "fields": parse_v4_workflow_fields(workflow),
    }
