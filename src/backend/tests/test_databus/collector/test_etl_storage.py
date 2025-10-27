import json
from types import SimpleNamespace
from typing import List

from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
)
from services.web.databus.constants import JsonSchemaFieldType, SnapShotStorageChoices


def build_schema_fields(entries: List[dict]) -> List[dict]:
    """
    根据 schema 配置构建 AssetEtlStorageHandler.schema_fields 的缓存结果。
    """
    return [
        {
            "field_name": entry["id"],
            "field_type": JsonSchemaFieldType.get_bkbase_field_type(entry["type"]),
            "field_alias": entry.get("description") or entry["id"],
            "is_dimension": False,
            "is_key": False,
            "field_index": index,
            "is_json": entry["type"] in [JsonSchemaFieldType.OBJECT.value, JsonSchemaFieldType.ARRAY.value],
            "is_original_json": entry["type"] in [JsonSchemaFieldType.JSON.value],
        }
        for index, entry in enumerate(entries)
    ]


def make_asset_handler(schema_entries: List[dict]) -> AssetEtlStorageHandler:
    handler = AssetEtlStorageHandler(
        data_id=1,
        system=SimpleNamespace(system_id="bk_system"),
        resource_type=SimpleNamespace(resource_type_id="bk_resource_type"),
        storage_type=SnapShotStorageChoices.REDIS.value,
    )
    handler.__dict__["schema_fields"] = build_schema_fields(schema_entries)
    return handler


def test_asset_fields_preserve_builtin_metadata():
    schema = [
        {
            "id": "id",
            "type": JsonSchemaFieldType.STRING.value,
            "description": "自定义ID",
        },
        {
            "id": "operator",
            "type": JsonSchemaFieldType.STRING.value,
            "description": "负责人字段",
        },
    ]

    handler = make_asset_handler(schema)
    fields = {field["field_name"]: field for field in handler.result_table_fields}

    assert fields["id"]["field_alias"] == "实例ID"
    assert fields["operator"]["field_alias"] == "负责人字段"


def test_asset_json_config_deduplicates_assignments():
    schema = [
        {
            "id": "operator",
            "type": JsonSchemaFieldType.OBJECT.value,
            "description": "负责人字段",
        },
        {
            "id": "bk_bak_operator",
            "type": JsonSchemaFieldType.STRING.value,
            "description": "备份负责人字段",
        },
        {
            "id": "custom",
            "type": JsonSchemaFieldType.STRING.value,
            "description": "自定义字段",
        },
    ]

    handler = make_asset_handler(schema)
    config = json.loads(handler.json_config)

    extract_nodes = config["extract"]["next"]["next"]
    iterate_branch = extract_nodes[3]["next"]["next"]["next"]["next"]["next"]

    assign_keys = [item["key"] for item in iterate_branch["next"][0]["assign"]]
    data_branch = iterate_branch["next"][1]["next"]
    assign_nodes = data_branch["next"]
    non_json_assign = next(node for node in assign_nodes if node["subtype"] == "assign_obj")
    json_assign = next(node for node in assign_nodes if node["subtype"] == "assign_json")

    non_json_keys = [item["key"] for item in non_json_assign["assign"]]
    json_assign_map = {item["key"]: item["type"] for item in json_assign["assign"]}

    assert "operator" not in assign_keys
    assert "bk_bak_operator" not in assign_keys
    assert {"bk_bak_operator", "custom"} <= set(non_json_keys)
    assert {"operator"} <= set(json_assign_map.keys())
