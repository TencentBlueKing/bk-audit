import json
from types import SimpleNamespace
from types import SimpleNamespace as _SN
from typing import List
from unittest import mock as _mock

from django.core.management.base import CommandError

from services.web.databus.collector.snapshot.join.base import AssetHandler
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
)
from services.web.databus.constants import (
    CLEAN_CONFIG_JSON_CONF_KEY,
    JsonSchemaFieldType,
    SnapshotRunningStatus,
    SnapShotStorageChoices,
)
from services.web.databus.management.commands.update_asset_etl import (
    Command as UpdateAssetEtlCommand,
)


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


def test_custom_conf_applies_to_json_config():
    schema = [
        {
            "id": "id",
            "type": JsonSchemaFieldType.STRING.value,
            "description": "实例ID",
        },
    ]
    handler = AssetEtlStorageHandler(
        data_id=1,
        system=SimpleNamespace(system_id="bk_system"),
        resource_type=SimpleNamespace(resource_type_id="bk_resource_type"),
        storage_type=SnapShotStorageChoices.REDIS.value,
        snapshot=SimpleNamespace(custom_config={CLEAN_CONFIG_JSON_CONF_KEY: {"timestamp_len": 13}}),
    )
    handler.__dict__["schema_fields"] = build_schema_fields(schema)
    config = json.loads(handler.json_config)

    assert config["conf"]["timestamp_len"] == 13
    # 未覆盖的字段保留默认值
    assert config["conf"]["time_format"] == "yyyy-MM-dd HH:mm:ss"


# ---------------------------------------------------------------------------
# AssetHandler.create_data_etl  update / create 分支测试
# ---------------------------------------------------------------------------


def _make_asset_handler_instance(bkbase_table_id: str = "") -> AssetHandler:
    """
    构造一个完全 mock 掉外部依赖的 AssetHandler 实例，
    跳过 __init__ 中的数据库查询。
    """
    handler = object.__new__(AssetHandler)
    handler.system_id = "bk_system"
    handler.resource_type_id = "bk_resource_type"
    handler.storage_type = SnapShotStorageChoices.HDFS.value
    handler.system = _SN(system_id="bk_system", namespace="default")
    handler.resource_type = _SN(resource_type_id="bk_resource_type")
    handler.collectors = []
    handler.snapshot = _SN(
        id=1,
        bkbase_data_id=100,
        bkbase_table_id=bkbase_table_id,
        bkbase_processing_id="proc_old" if bkbase_table_id else None,
        save=_mock.MagicMock(),
    )
    return handler


def test_create_data_etl_calls_create_clean_when_no_table_id():
    """没有已有清洗链路时，调用 create_clean() 不带 update 参数"""
    handler = _make_asset_handler_instance(bkbase_table_id="")

    mock_etl_handler = _mock.MagicMock()
    mock_etl_handler.create_clean.return_value = ("proc_new", "table_new")

    with _mock.patch.object(
        AssetHandler,
        "etl_storage_handler_cls",
        new_callable=lambda: property(lambda self: _mock.MagicMock(return_value=mock_etl_handler)),
    ):
        handler.create_data_etl()

    mock_etl_handler.create_clean.assert_called_once_with()
    assert handler.snapshot.bkbase_processing_id == "proc_new"
    assert handler.snapshot.bkbase_table_id == "table_new"


def test_create_data_etl_skips_create_clean_when_table_id_exists():
    """已有清洗链路时，不更新远端清洗配置"""
    handler = _make_asset_handler_instance(bkbase_table_id="existing_table")

    mock_etl_handler = _mock.MagicMock()

    with _mock.patch.object(
        AssetHandler,
        "etl_storage_handler_cls",
        new_callable=lambda: property(lambda self: _mock.MagicMock(return_value=mock_etl_handler)),
    ):
        handler.create_data_etl()

    mock_etl_handler.create_clean.assert_not_called()
    assert handler.snapshot.bkbase_table_id == "existing_table"


def test_create_data_storage_skips_update_when_storage_running():
    """已有运行中入库时，不更新远端入库配置"""
    handler = _make_asset_handler_instance(bkbase_table_id="existing_table")
    storage = _SN(status=SnapshotRunningStatus.RUNNING, save=_mock.MagicMock())
    handler.snapshot.storages = _SN(
        filter=_mock.MagicMock(return_value=_SN(first=_mock.MagicMock(return_value=storage)))
    )
    mock_etl_handler = _mock.MagicMock()

    with _mock.patch.object(
        AssetHandler,
        "etl_storage_handler_cls",
        new_callable=lambda: property(lambda self: _mock.MagicMock(return_value=mock_etl_handler)),
    ):
        handler.create_data_storage()

    mock_etl_handler.create_storage.assert_not_called()
    storage.save.assert_not_called()


def test_create_clean_update_calls_put_and_restart():
    """JoinDataEtlStorageHandler.create_clean(update=True) 调用 put 接口和 restart"""
    from services.web.databus.collector.snapshot.join.etl_storage import (
        JoinDataEtlStorageHandler,
    )

    snapshot = _SN(
        bkbase_processing_id="proc_123",
        bkbase_table_id="table_abc",
    )
    etl_handler = JoinDataEtlStorageHandler(
        data_id=1,
        system=_SN(system_id="bk_system"),
        resource_type=_SN(resource_type_id="bk_resource_type"),
        storage_type=SnapShotStorageChoices.REDIS.value,
        snapshot=snapshot,
    )

    with (
        _mock.patch(
            "services.web.databus.collector.snapshot.join.etl_storage.api.bk_base.databus_cleans_put"
        ) as mock_put,
        _mock.patch("services.web.databus.collector.snapshot.join.etl_storage.restart_bkbase_clean") as mock_restart,
    ):
        processing_id, table_id = etl_handler.create_clean(update=True)

    mock_put.assert_called_once()
    mock_restart.assert_called_once_with("table_abc", "proc_123")
    assert processing_id == "proc_123"
    assert table_id == "table_abc"


def test_create_clean_create_calls_post_and_start():
    """JoinDataEtlStorageHandler.create_clean() 调用 post 接口和 start"""
    from services.web.databus.collector.snapshot.join.etl_storage import (
        JoinDataEtlStorageHandler,
    )

    etl_handler = JoinDataEtlStorageHandler(
        data_id=1,
        system=_SN(system_id="bk_system"),
        resource_type=_SN(resource_type_id="bk_resource_type"),
        storage_type=SnapShotStorageChoices.REDIS.value,
    )

    with (
        _mock.patch(
            "services.web.databus.collector.snapshot.join.etl_storage.api.bk_base.databus_cleans_post",
            return_value={"processing_id": "proc_new", "result_table_id": "table_new"},
        ) as mock_post,
        _mock.patch("services.web.databus.collector.snapshot.join.etl_storage.start_bkbase_clean") as mock_start,
    ):
        processing_id, table_id = etl_handler.create_clean()

    mock_post.assert_called_once()
    mock_start.assert_called_once_with("table_new", "proc_new")
    assert processing_id == "proc_new"
    assert table_id == "table_new"


def test_update_asset_etl_command_updates_snapshot_custom_config():
    """update_asset_etl 支持写入自定义配置后手动刷新清洗和入库"""
    storage = _SN(storage_type=SnapShotStorageChoices.HDFS.value)
    snapshot = _SN(
        id=1,
        bkbase_data_id=100,
        bkbase_processing_id="proc_123",
        custom_config={},
        save=_mock.MagicMock(),
        storages=_SN(all=_mock.MagicMock(return_value=[storage])),
    )
    mock_handler = _mock.MagicMock()
    custom_config = {CLEAN_CONFIG_JSON_CONF_KEY: {"timestamp_len": 13}}

    with (
        _mock.patch(
            "services.web.databus.management.commands.update_asset_etl.Snapshot.objects.get",
            return_value=snapshot,
        ),
        _mock.patch(
            "services.web.databus.management.commands.update_asset_etl.System.objects.get",
            return_value=_SN(system_id="bk_system"),
        ),
        _mock.patch(
            "services.web.databus.management.commands.update_asset_etl.ResourceType.objects.get",
            return_value=_SN(resource_type_id="bk_resource_type"),
        ),
        _mock.patch(
            "services.web.databus.management.commands.update_asset_etl.AssetEtlStorageHandler",
            return_value=mock_handler,
        ) as mock_handler_cls,
    ):
        UpdateAssetEtlCommand().handle(
            system_id="bk_system",
            resource_type_id="bk_resource_type",
            custom_config=json.dumps(custom_config),
        )

    assert snapshot.custom_config == custom_config
    snapshot.save.assert_called_once_with(update_fields=["custom_config"])
    mock_handler_cls.assert_called_once_with(
        data_id=100,
        system=_mock.ANY,
        resource_type=_mock.ANY,
        storage_type=SnapShotStorageChoices.HDFS.value,
        snapshot=snapshot,
    )
    mock_handler.create_clean.assert_called_once_with(update=True)
    mock_handler.create_storage.assert_called_once_with(update=True)


def test_update_asset_etl_command_rejects_invalid_custom_config():
    """custom_config 必须是 JSON 对象"""
    with _mock.patch(
        "services.web.databus.management.commands.update_asset_etl.Snapshot.objects.get",
        return_value=_SN(),
    ):
        try:
            UpdateAssetEtlCommand().handle(
                system_id="bk_system",
                resource_type_id="bk_resource_type",
                custom_config="[1, 2, 3]",
            )
        except CommandError as err:
            assert "custom-config" in str(err)
        else:
            raise AssertionError("CommandError not raised")
