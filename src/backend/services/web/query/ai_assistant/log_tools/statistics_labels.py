"""统计类别名称与日志字段目录共用映射；仅处理返回值，不改变分组身份。"""
from services.web.query.constants import DEFAULT_TIMEDELTA
from services.web.query.utils.field_map import FieldMapHandler


def label_statistics_groups(groups, dimensions, namespace):
    """为声明根字段的实际返回值附名称；未知值与动态 JSON 路径保持空名称。"""
    fields = {d.id: d.field.raw_name for d in dimensions if not d.field.keys}
    maps = FieldMapHandler(fields=list(fields.values()), timedelta=DEFAULT_TIMEDELTA, namespace=namespace).field_map
    labels = {name: {str(item["id"]): str(item["name"]) for item in options} for name, options in maps.items()}
    return tuple(
        group.model_copy(
            update={
                "values": tuple(
                    value.model_copy(
                        update={"value_label": labels.get(fields.get(value.dimension_id), {}).get(str(value.value))}
                    )
                    for value in group.values
                )
            }
        )
        for group in groups
    )
