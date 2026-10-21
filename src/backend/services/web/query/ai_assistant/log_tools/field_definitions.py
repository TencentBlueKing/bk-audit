"""日志工具共享的内置字段定义解析。

仅解析已有可查询字段及其 property.sub_keys，不添加新的字段白名单。
字段目录、详情列和统计标题共用声明别名；动态路径由各消费者回退到实际 key。
"""

from apps.meta.utils.fields import START_TIME, SubKey
from services.web.query.ai_assistant.log_tools.schemas import LogFieldRef
from services.web.query.constants import COLLECT_SEARCH_CONFIG


def get_declared_field(field: LogFieldRef) -> SubKey | None:
    """沿内置 sub_keys 解析字段声明；合法但未声明的动态路径返回 None。"""
    config = COLLECT_SEARCH_CONFIG.query_field_map.get(field.raw_name)
    root = config.field if config else START_TIME if field.raw_name == START_TIME.field_name else None
    if root is None:
        return None
    definition = SubKey(
        field_name=root.field_name,
        field_type=root.field_type,
        field_alias=str(root.description or root.alias_name or root.field_name),
        property=root.property,
    )
    for key in field.keys:
        children = (definition.get("property") or {}).get("sub_keys", [])
        definition = next((child for child in children if child["field_name"] == key), None)
        if definition is None:
            return None
    return definition
