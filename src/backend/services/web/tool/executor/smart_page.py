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
from typing import Any, Optional

from pymysql.converters import escape_string

from core.render import jinja2_environment
from services.web.tool.constants import (
    SMART_PAGE_BIND_OUTPUT_TYPE_ALIAS_MAPPING,
    SMART_PAGE_BOOL_FALSE_LITERALS,
    SMART_PAGE_BOOL_RENDER_MAPPING,
    SMART_PAGE_BOOL_TRUE_LITERALS,
    SmartPageBindOutputTypeEnum,
)
from services.web.tool.exceptions import (
    SmartPageBindParamMissingError,
    SmartPageSqlTemplateRenderError,
)


def _escape_sql_string_value(value: str) -> str:
    """复用 PyMySQL 的字符串转义逻辑，避免手写 SQL escaping。"""
    escaped_value = escape_string(value)
    if isinstance(escaped_value, (bytes, bytearray)):
        return escaped_value.decode()
    return escaped_value


def _normalize_bind_output_type(output_type: Optional[str]) -> SmartPageBindOutputTypeEnum:
    """将模板中声明的 output_type 规范化为内部枚举。"""
    if output_type is None or output_type == "":
        return SmartPageBindOutputTypeEnum.AUTO

    output_type_key = str(output_type).strip().lower()
    bind_output_type = SMART_PAGE_BIND_OUTPUT_TYPE_ALIAS_MAPPING.get(output_type_key)
    if bind_output_type is None:
        raise SmartPageSqlTemplateRenderError(detail=f"output_type {output_type} 不支持")
    return bind_output_type


def _cast_bind_scalar_value(value: Any, bind_output_type: SmartPageBindOutputTypeEnum) -> str:
    """将单值参数转换为 SQL 模板可安全拼接的裸字符串。"""
    if value is None:
        return "NULL"

    if bind_output_type == SmartPageBindOutputTypeEnum.AUTO:
        if isinstance(value, bool):
            return SMART_PAGE_BOOL_RENDER_MAPPING[value]
        if isinstance(value, (int, float)):
            return str(value)
        return _escape_sql_string_value(str(value))

    if bind_output_type == SmartPageBindOutputTypeEnum.STR:
        return _escape_sql_string_value(str(value))

    if bind_output_type == SmartPageBindOutputTypeEnum.INT:
        try:
            return str(int(value))
        except (TypeError, ValueError):
            raise SmartPageSqlTemplateRenderError(detail=f"参数值 {value} 无法转换为 int")

    if bind_output_type == SmartPageBindOutputTypeEnum.FLOAT:
        try:
            return str(float(value))
        except (TypeError, ValueError):
            raise SmartPageSqlTemplateRenderError(detail=f"参数值 {value} 无法转换为 float")

    if bind_output_type == SmartPageBindOutputTypeEnum.BOOL:
        if isinstance(value, bool):
            bool_value = value
        elif isinstance(value, str):
            lower_value = value.strip().lower()
            if lower_value in SMART_PAGE_BOOL_TRUE_LITERALS:
                bool_value = True
            elif lower_value in SMART_PAGE_BOOL_FALSE_LITERALS:
                bool_value = False
            else:
                raise SmartPageSqlTemplateRenderError(detail=f"参数值 {value} 无法转换为 bool")
        elif isinstance(value, (int, float)):
            bool_value = bool(value)
        else:
            raise SmartPageSqlTemplateRenderError(detail=f"参数值 {value} 无法转换为 bool")

        return SMART_PAGE_BOOL_RENDER_MAPPING[bool_value]

    raise SmartPageSqlTemplateRenderError(detail=f"output_type {bind_output_type} 不支持")


def _render_bind_value(value: Any, output_type: Optional[str] = None) -> str:
    """将模板参数渲染为 SQL 片段，列表场景按项拼接。"""
    bind_output_type = _normalize_bind_output_type(output_type)

    if isinstance(value, (list, tuple, set)):
        if len(value) == 0:
            return ""
        rendered_items = []
        for item in value:
            rendered_item = _cast_bind_scalar_value(item, bind_output_type)
            if bind_output_type == SmartPageBindOutputTypeEnum.STR:
                rendered_items.append(f"'{rendered_item}'" if rendered_item != "NULL" else rendered_item)
                continue
            if bind_output_type == SmartPageBindOutputTypeEnum.AUTO and isinstance(item, str):
                rendered_items.append(f"'{rendered_item}'")
                continue
            rendered_items.append(rendered_item)
        return ", ".join(rendered_items)

    return _cast_bind_scalar_value(value, bind_output_type)


def render_sql_template(sql_template: str, params: dict) -> str:
    """
    使用 Jinja2 SandboxedEnvironment 渲染 SQL 模板。

    模板中可用:
    - has(key): 判断参数是否存在且非空
    - bind(key, output_type=None): 参数转为裸字符串，output_type 为可选枚举
    """
    env = jinja2_environment(autoescape=False)

    def has(key: str) -> bool:
        return key in params and params.get(key) not in (None, "")

    def bind(key: str, output_type: Optional[str] = None) -> str:
        if key not in params:
            raise SmartPageBindParamMissingError(key)
        return _render_bind_value(params[key], output_type=output_type)

    try:
        template = env.from_string(sql_template)
        return template.render(params=params, has=has, bind=bind)
    except (SmartPageBindParamMissingError, SmartPageSqlTemplateRenderError):
        raise
    except Exception as e:
        raise SmartPageSqlTemplateRenderError(detail=str(e))
