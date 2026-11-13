"""核对普通/事件插件与采集项的存量V4资源，仅导入本地绑定。

所有身份来自明确清单和正式GET，不推测资源名、集群或共享表角色。
应用时在资源锁内重读远端，短事务比对全部本地旧值，保留V3字段与未知绑定键。
"""

from contextlib import ExitStack
from copy import deepcopy

from bk_resource import api
from django.db import transaction
from django.db.models import Q

from apps.meta.models import System
from services.web.bkbase import clean, metadata, plugin_storage_switch, source, storage
from services.web.bkbase.common import operation_result, resource_lock, resource_params
from services.web.bkbase.constants import CleanRole, TaskState
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import PluginSceneChoices, SnapShotStorageChoices
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot

MAX_BATCH_SIZE = 20
SCHEMA_VERSION = 1
OWNER_MODELS = {"plugin": CollectorPlugin, "event_plugin": CollectorPlugin, "collector": CollectorConfig}
MIGRATION_BINDING_KEY = "migration_import"
MIGRATION_MAINTENANCE_KEY = "migration_maintenance"
RESOURCE_KINDS = {"data_source": "DataSource", "data_id": "DataId", "clean": "Clean", "result_table": "ResultTable"}
STORAGE_KINDS = {"main": "ElasticSearch", "replica": "Doris"}
UNRESOLVED_KEYS = (
    MIGRATION_MAINTENANCE_KEY,
    "pending_action",
    "clean_pending_create",
    "clean_delete_requested",
    "pending_spec",
    "flow_write",
    "writer",
    "write_fence",
    "observing",
    "outcome_unknown",
)


def _text(value):
    """身份值必须明确且可安全用于资源路径或旧ID比较。"""
    return isinstance(value, str) and bool(value) and not any(char.isspace() or char in ",=/\\" for char in value)


def _positive_int(value):
    return type(value) is int and value > 0


def _storage_kinds(row):
    """事件单列主Doris；普通插件继续主ES、副Doris。"""
    return {"main": "Doris"} if row["owner"] == "event_plugin" else STORAGE_KINDS


def _ref(context, value, kind):
    """仅接受当前租户的完整引用，允许显式跨项目。"""
    if (
        not isinstance(value, dict)
        or set(value) != {"kind", "tenant", "namespace", "name"}
        or value.get("kind") != kind
        or value.get("tenant") != context.get("tenant")
        or not all(_text(value.get(key)) for key in ("tenant", "namespace", "name"))
    ):
        raise ValueError(f"{kind}必须为当前租户的完整资源引用")
    return deepcopy(value)


def validate_manifest(payload, *, context, limit=MAX_BATCH_SIZE):
    """先验证整批显式身份与唯一性，不读取本地或远端资源。"""
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH_SIZE:
        raise ValueError(f"limit必须在1–{MAX_BATCH_SIZE}之间")
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "mappings"}
        or type(payload.get("schema_version")) is not int
        or payload["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError("迁移清单必须为schema_version=1和mappings组成的JSON对象")
    rows = payload["mappings"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= limit:
        raise ValueError(f"每批必须包含1–{limit}条，不自动截断")
    owners, cleans = set(), set()
    required = {"owner", "owner_pk", "audit_namespace", "legacy", "storages", *RESOURCE_KINDS}
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != required
            or not isinstance(row.get("owner"), str)
            or row["owner"] not in OWNER_MODELS
            or not _positive_int(row.get("owner_pk"))
            or not _text(row.get("audit_namespace"))
        ):
            raise ValueError("映射必须明确plugin/event_plugin/collector、本地主键、审计namespace、旧身份和完整资源清单")
        legacy = row["legacy"]
        if (
            not isinstance(legacy, dict)
            or set(legacy) != {"raw_data_id", "processing_id", "result_table_id"}
            or not _positive_int(legacy.get("raw_data_id"))
            or not all(_text(legacy.get(key)) for key in ("processing_id", "result_table_id"))
        ):
            raise ValueError("旧身份必须包含正整数raw_data_id、processing_id和逻辑result_table_id")
        for key, kind in RESOURCE_KINDS.items():
            _ref(context, row[key], kind)
        storages = row["storages"]
        storage_kinds = _storage_kinds(row)
        if not isinstance(storages, dict) or set(storages) - storage_kinds.keys():
            raise ValueError("Storage只接受明确的main/replica用途")
        storage_refs = set()
        for purpose, entry in storages.items():
            if (
                not isinstance(entry, dict)
                or not {"resource", "cluster"} <= set(entry)
                or set(entry) - {"resource", "cluster", "physical_table_name"}
            ):
                raise ValueError(f"{purpose}必须声明Storage资源与集群引用")
            storage_ref = _ref(context, entry["resource"], "DataStorage")
            _ref(context, entry["cluster"], storage_kinds[purpose])
            if "physical_table_name" in entry:
                try:
                    storage.normalize_physical_table_name(
                        "es" if storage_kinds[purpose] == "ElasticSearch" else "doris", entry["physical_table_name"]
                    )
                except BKBaseResourceMappingError as error:
                    raise ValueError(f"{purpose}物理目标必须为明确的ES模板或Doris库.表") from error
            identity = tuple(storage_ref[key] for key in ("tenant", "namespace", "name"))
            if identity in storage_refs:
                raise ValueError("主副用途不能指向同一个Storage")
            storage_refs.add(identity)
        owner = row["owner"], row["owner_pk"]
        clean_ref = tuple(row["clean"][key] for key in ("tenant", "namespace", "name"))
        if owner in owners or clean_ref in cleans:
            raise ValueError("同批本地对象或Clean引用重复")
        owners.add(owner)
        cleans.add(clean_ref)
    return deepcopy(rows)


def _load_owner(row, *, locked=False):
    """使用不隐藏软删记录的管理器，随后显式拒绝已删除对象。"""
    manager = OWNER_MODELS[row["owner"]]._objects
    return (manager.select_for_update() if locked else manager).get(pk=row["owner_pk"])


def _snapshot(owner):
    """捕获所有持久化字段，防止预检后配置或归属变化被遗漏。"""
    return deepcopy({field.attname: getattr(owner, field.attname) for field in owner._meta.concrete_fields})


def _assert_settled(binding):
    """不通过导入清除未决写入、删除或结果未知凭据。"""
    if not isinstance(binding, dict):
        raise ValueError("既有V4绑定结构无效")
    if any(binding.get(key) for key in UNRESOLVED_KEYS):
        raise ValueError("对象存在未决或结果未知操作，不能导入绑定")
    for key in (plugin_storage_switch.SWITCH_KEY, plugin_storage_switch.UPDATE_KEY):
        operation = binding.get(key)
        if operation is None or operation == {}:
            continue
        # 成功操作会移除活动key；failed切换是唯一保留的终止记录。
        terminal = (
            key == plugin_storage_switch.SWITCH_KEY
            and isinstance(operation, dict)
            and operation.get("failed") is True
            and not operation.get("bklog_started")
        )
        if not terminal:
            raise ValueError("对象存储切换/更新仍有未决操作，不能导入绑定")
    for key in ("replay", "pure_operation", "source_provision"):
        operation = binding.get(key)
        if operation is None:
            continue
        if not isinstance(operation, dict) or any(
            operation.get(flag) for flag in ("active", "writer", "write_fence", "observing", "outcome_unknown")
        ):
            raise ValueError("对象存在未决或无效操作凭据，不能导入绑定")
        if key == "source_provision" and operation and operation.get("stage") not in ("ready", "clean_ready"):
            raise ValueError("对象来源初始化尚未完成，不能导入绑定")


def _shared_plugin(row, owner, *, locked=False):
    """采集项必须唯一归属于已导入共享表身份的普通插件。"""
    if row["owner"] != "collector":
        return None
    manager = CollectorPlugin._objects
    candidates = list(
        (manager.select_for_update() if locked else manager).filter(collector_plugin_id=owner.collector_plugin_id)
    )
    if len(candidates) != 1:
        raise ValueError("采集项所属插件无法唯一定位")
    return candidates[0]


def _validate_local(owner, row, plugin):
    """旧字段、共享归属与主副用途必须与明确清单一致。"""
    if getattr(owner, "is_deleted", False):
        raise ValueError("已删除采集项不能导入绑定")
    namespace = (
        owner.namespace if row["owner"] != "collector" else System.objects.get(system_id=owner.system_id).namespace
    )
    processing = owner.bkbase_processing_id if row["owner"] != "collector" else owner.processing_id
    legacy = row["legacy"]
    if (
        namespace != row["audit_namespace"]
        or processing != legacy["processing_id"]
        or owner.bkbase_table_id != legacy["result_table_id"]
    ):
        raise ValueError("本地审计namespace、旧processing或逻辑表与清单不一致")
    _assert_settled(owner.bkbase_v4_resources)
    if row["owner"] != "collector":
        event = row["owner"] == "event_plugin"
        scene = PluginSceneChoices.EVENT if event else PluginSceneChoices.COLLECTOR
        if owner.plugin_scene != scene:
            raise ValueError("插件场景与清单类型不一致；事件插件必须显式使用event_plugin")
        expected = {
            purpose
            for purpose, enabled in (("main", owner.has_storage), ("replica", owner.has_replica_storage))
            if enabled
        }
        if (owner.has_replica_storage and not owner.has_storage) or set(row["storages"]) != expected:
            raise ValueError("清单Storage用途与本地主副存储标记不一致")
        if event:
            if expected != {"main"} or "physical_table_name" not in row["storages"]["main"]:
                raise ValueError("事件插件必须声明唯一主Doris及已知物理目标")
            saved_rt = clean.GlobalMetaConfig.get(
                clean.DORIS_EVENT_BKBASE_RT_ID_KEY,
                config_level=clean.ConfigLevelChoices.NAMESPACE.value,
                instance_key=namespace,
            )
            saved_target = clean.GlobalMetaConfig.get(
                clean.DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
                config_level=clean.ConfigLevelChoices.NAMESPACE.value,
                instance_key=namespace,
            )
            if not saved_target:
                saved_config = (
                    clean.GlobalMetaConfig.get(
                        clean.DORIS_EVENT_STORAGE_CONFIG_KEY,
                        config_level=clean.ConfigLevelChoices.NAMESPACE.value,
                        instance_key=namespace,
                        default={},
                    )
                    or {}
                )
                saved_target = saved_config.get("physical_table_name")
            if saved_rt and saved_rt != legacy["result_table_id"]:
                raise ValueError("事件插件逻辑RT与既有GlobalMeta不一致")
            if saved_target and storage.normalize_physical_table_name(
                "doris", saved_target
            ) != storage.normalize_physical_table_name("doris", row["storages"]["main"]["physical_table_name"]):
                raise ValueError("事件插件物理目标与既有GlobalMeta不一致")
        for purpose, entry in row["storages"].items():
            if entry["cluster"].get("kind") != _storage_kinds(row)[purpose]:
                raise ValueError("Storage类型与插件场景不一致")
    else:
        if owner.bk_data_id != legacy["raw_data_id"] or row["storages"]:
            raise ValueError("采集项原DataID不一致，或错误声明了共享Storage")
        binding = plugin.bkbase_v4_resources
        _assert_settled(binding)
        if (
            plugin.namespace != namespace
            or plugin.plugin_scene != PluginSceneChoices.COLLECTOR
            or plugin.bkbase_table_id != legacy["result_table_id"]
            or binding.get("clean_role") != CleanRole.OWNER
            or binding.get("result_table_id") != legacy["result_table_id"]
            or binding.get("result_table") != row["result_table"]
            or any(not binding.get(key) for key in ("data_source", "data_id", "source_raw_data_id", "clean"))
        ):
            raise ValueError("所属插件未导入完整owner身份，或共享ResultTable与采集项不一致；请先导入插件")


def _identity_patch(row):
    """身份补丁不包含运行态，Collector不认领插件的Storage。"""
    patch = {key: deepcopy(row[key]) for key in RESOURCE_KINDS}
    patch.update(
        source_raw_data_id=row["legacy"]["raw_data_id"],
        result_table_id=row["legacy"]["result_table_id"],
        clean_role=CleanRole.EXISTING if row["owner"] == "collector" else CleanRole.OWNER,
    )
    # 保存显式导入依据，供后台只读核验；一般新建绑定不能代替迁移凭据。
    patch[MIGRATION_BINDING_KEY] = deepcopy(row)
    if row["storages"]:
        patch["storages"] = {purpose: deepcopy(entry["resource"]) for purpose, entry in row["storages"].items()}
        targets = {
            purpose: storage.normalize_physical_table_name(
                "es" if _storage_kinds(row)[purpose] == "ElasticSearch" else "doris", entry["physical_table_name"]
            )
            for purpose, entry in row["storages"].items()
            if "physical_table_name" in entry
        }
        if targets:
            patch["physical_targets"] = targets
    return patch


def _merged_binding(owner, row):
    """保留未知键，冲突拒绝；新补身份使旧就绪标记重新接受正常确认。"""
    before = owner.bkbase_v4_resources
    after = deepcopy(before)
    for key, value in _identity_patch(row).items():
        if key in ("storages", "physical_targets"):
            current = after.setdefault(key, {})
            if not isinstance(current, dict):
                raise ValueError("既有Storage绑定结构无效")
            for purpose, ref in value.items():
                if current.get(purpose) not in (None, ref):
                    raise ValueError(f"既有{purpose} Storage绑定冲突")
                current[purpose] = ref
        else:
            if before.get(key) not in (None, value):
                raise ValueError(f"既有V4 {key}身份绑定冲突")
            after[key] = value
    if before != after:
        for key in ("ready", "clean_ready"):
            if key in after:
                after[key] = False
    return after


def _reference_match(binding_key, ref):
    """逐字段比较完整Ref，不依赖JSON对象的键顺序。"""
    return Q(
        **{f"bkbase_v4_resources__{binding_key}__{key}": ref[key] for key in ("kind", "tenant", "namespace", "name")}
    )


def _reject_aliases(owner, row, plugin):
    """跨插件、采集项及快照排除写者，包括软删及其他审计namespace。"""
    for model in (CollectorPlugin, CollectorConfig, Snapshot):
        field = "processing_id" if model is CollectorConfig else "bkbase_processing_id"
        query = Q(**{field: row["legacy"]["processing_id"]}) | _reference_match("clean", row["clean"])
        table_owner = _reference_match("result_table", row["result_table"])
        if model is CollectorPlugin:
            table_owner |= Q(bkbase_table_id=row["legacy"]["result_table_id"])
            if plugin is not None:
                # 采集项的唯一所属插件是合法owner；其Clean等其他写目标仍须独立排除。
                table_owner &= ~Q(pk=plugin.pk)
        else:
            table_owner &= Q(bkbase_v4_resources__clean_role=CleanRole.OWNER)
        query |= table_owner
        for entry in row["storages"].values():
            for purpose in (*STORAGE_KINDS, *SnapShotStorageChoices.values):
                query |= _reference_match(f"storages__{purpose}", entry["resource"])
        candidates = model._objects.filter(query)
        if model is OWNER_MODELS[row["owner"]]:
            candidates = candidates.exclude(pk=owner.pk)
        if candidates.exists():
            raise ValueError("旧processing、Clean、owner结果表或Storage已有其他本地归属，拒绝导入")


def _get(context, ref, kind, getter):
    """每个显式引用均正式GET并严格核对返回身份，不将错误视为不存在。"""
    _ref(context, ref, kind)
    params = resource_params(context, ref, kind=kind)
    if kind in ("DataId", "ResultTable"):
        params.pop("tenant")
    value = getter(**params)
    if source._binding_resource_ref(context, value, kind) != ref:
        raise ValueError(f"正式{kind} GET返回身份与清单不一致")
    return value


def _verify_identity(context, row, role):
    """交叉核实旧processing、数字DataID、实际输入和逻辑结果表。"""
    legacy = row["legacy"]
    current_source = _get(context, row["data_source"], "DataSource", api.bk_base_v4.data_source_get)
    if (
        source._positive_raw_data_id(current_source["metadata"].get("labels", {}).get("raw_data_id"))
        != legacy["raw_data_id"]
        or current_source["spec"].get("data_id") != row["data_id"]
    ):
        raise ValueError("DataSource缺少匹配的raw_data_id标签或DataId关联")
    current_data = _get(context, row["data_id"], "DataId", api.bk_base_v4.data_id_get)
    current_clean = _get(context, row["clean"], "Clean", api.bk_base_v4.clean_get)
    labels = current_clean["metadata"].get("labels", {})
    if labels.get("processing_id") != legacy["processing_id"]:
        raise ValueError("Clean缺少与本地旧processing严格匹配的processing_id标签")
    source_role = "new" if role == CleanRole.OWNER else "existing"
    if current_clean["spec"].get("result_table_source") != source_role:
        raise ValueError("Clean必须明确声明与本地归属一致的new/existing角色")
    logical_id = clean._existing_clean_table_id(
        context,
        row["clean"],
        current_clean,
        raw_id=legacy["raw_data_id"],
        data_ref=row["data_id"],
        source_role=source_role,
    )
    if logical_id != legacy["result_table_id"]:
        raise ValueError("Clean逻辑结果表与旧字段不一致")
    for key in ("raw_data_id", "result_table_id"):
        if key in labels and str(labels[key]) != str(legacy[key]):
            raise ValueError(f"Clean {key}标签与声明冲突")
    current_table = _get(context, row["result_table"], "ResultTable", api.bk_base_v4.result_table_resource_get)
    if metadata.result_table_identity(context, current_table) != (row["result_table"], legacy["result_table_id"]):
        raise ValueError("ResultTable正式身份或逻辑ID与旧表不一致")
    observed = operation_result(current_clean, row["clean"], "observe")
    observed["source_observation"] = operation_result(current_source, row["data_source"], "observe")
    observed["dependencies_ready"] = (
        observed["source_observation"]["task_state"] == TaskState.RUNNING
        and current_data.get("status", {}).get("phase") == "Ok"
        and current_table.get("status", {}).get("phase") == "Ok"
        and current_clean["spec"].get("config_revision") == current_clean["spec"].get("deploy_revision")
    )
    return observed


def _verify_remote(context, row, plugin):
    """只读取资源身份及观察状态，Storage Ok不被解释为存在业务数据。"""
    role = CleanRole.EXISTING if row["owner"] == "collector" else CleanRole.OWNER
    observed = {"clean": _verify_identity(context, row, role), "storages": {}}
    if plugin is not None:
        binding = plugin.bkbase_v4_resources
        parent = {key: binding[key] for key in RESOURCE_KINDS}
        parent["legacy"] = {
            "raw_data_id": binding["source_raw_data_id"],
            "processing_id": plugin.bkbase_processing_id,
            "result_table_id": plugin.bkbase_table_id,
        }
        observed["plugin_clean"] = _verify_identity(context, parent, CleanRole.OWNER)
    for purpose, entry in row["storages"].items():
        ref = entry["resource"]
        current = _get(context, ref, "DataStorage", api.bk_base_v4.data_storage_get)
        table = current["spec"].get("tableInfo")
        if (
            not isinstance(table, dict)
            or table.get("source") != row["result_table"]
            or table.get("storage") != entry["cluster"]
        ):
            raise ValueError(f"{purpose} Storage的ResultTable或目标集群与清单不一致")
        if "physical_table_name" in entry and table.get("physical_table_name") is not None:
            kind = "es" if _storage_kinds(row)[purpose] == "ElasticSearch" else "doris"
            if storage.normalize_physical_table_name(
                kind, entry["physical_table_name"]
            ) != storage.normalize_physical_table_name(kind, table["physical_table_name"]):
                raise ValueError(f"{purpose} Storage的物理目标与清单不一致")
        for container in (current["metadata"].get("labels", {}), current["metadata"].get("annotations", {})):
            if "result_table_id" in container and container["result_table_id"] != row["legacy"]["result_table_id"]:
                raise ValueError(f"{purpose} Storage逻辑表标签与旧表冲突")
        observed["storages"][purpose] = operation_result(current, ref, "observe")
    return observed


def observe_imported_resource(context, owner):
    """只读核对迁移凭据、身份和运行态，不配置或启动导入资源。"""
    row = deepcopy(owner.bkbase_v4_resources[MIGRATION_BINDING_KEY])
    if not isinstance(row, dict) or row.get("owner") not in OWNER_MODELS or row.get("owner_pk") != owner.pk:
        raise BKBaseResourceMappingError(message="Imported plugin receipt does not match its owner")
    try:
        validate_manifest({"schema_version": SCHEMA_VERSION, "mappings": [row]}, context=context)
        plugin = _shared_plugin(row, owner)
        _validate_local(owner, row, plugin)
        if _merged_binding(owner, row) != owner.bkbase_v4_resources:
            raise ValueError("迁移绑定不完整或已改变")
        observed = _verify_remote(context, row, plugin)
    except ValueError as error:
        raise BKBaseResourceMappingError(message=str(error)) from error
    results = [observed["clean"]["source_observation"], observed["clean"], *observed["storages"].values()]
    running = observed["clean"]["dependencies_ready"] and all(r["task_state"] == TaskState.RUNNING for r in results)
    patch = {
        "clean_ready": observed["clean"]["task_state"] == TaskState.RUNNING and observed["clean"]["dependencies_ready"]
    }
    if row["owner"] != "collector":
        patch["ready"] = running
    clean.update_owner_binding(owner, patch)
    if running:
        return observed["clean"]
    result = next(
        (r for state in (TaskState.FAILED, TaskState.STOPPED) for r in results if r["task_state"] == state),
        next((r for r in results if r["task_state"] != TaskState.RUNNING), observed["clean"]),
    )
    return {
        **result,
        "task_state": result["task_state"] if result["task_state"] != TaskState.RUNNING else None,
        "message": "Imported resources are observed only; readiness is not confirmed",
    }


def preview_mapping(context, row):
    """只读预检本地归属与正式资源，返回精确before/after绑定。"""
    owner = _load_owner(row)
    plugin = _shared_plugin(row, owner)
    _validate_local(owner, row, plugin)
    after = _merged_binding(owner, row)
    _reject_aliases(owner, row, plugin)
    observed = _verify_remote(context, row, plugin)
    return {
        "before_binding": deepcopy(owner.bkbase_v4_resources),
        "after_binding": after,
        "local_snapshot": _snapshot(owner),
        "plugin_snapshot": _snapshot(plugin) if plugin is not None else None,
        "observed": observed,
        "action": "unchanged" if owner.bkbase_v4_resources == after else "bind",
    }


def apply_mapping(context, row, plan, *, before_save):
    """资源锁内重读远端，短事务CAS后仅写本地绑定，写前先持久化恢复证据。"""
    owner = _load_owner(row)
    plugin = _shared_plugin(row, owner)
    _validate_local(owner, row, plugin)
    refs = [row["clean"], row["result_table"], *(entry["resource"] for entry in row["storages"].values())]
    if plugin is not None:
        refs.append(plugin.bkbase_v4_resources["clean"])
    targets = {tuple(ref[key] for key in ("kind", "tenant", "namespace", "name")): ref for ref in refs}
    with ExitStack() as locks:
        # 同Ref导入共享同一现有资源锁；锁竞争沿原语快速失败，不等待重试。
        for identity in sorted(targets):
            locks.enter_context(resource_lock(context, targets[identity]))
        _verify_remote(context, row, plugin)
        with transaction.atomic():
            # 合流先锁owner插件，所有路径的数据库锁顺序保持一致。
            current_plugin = _shared_plugin(row, owner, locked=True)
            current = _load_owner(row, locked=True)
            if (
                _snapshot(current) != plan["local_snapshot"]
                or (_snapshot(current_plugin) if current_plugin is not None else None) != plan["plugin_snapshot"]
            ):
                raise ValueError("预检后本地对象或所属插件已改变，拒绝覆盖；请重新预检")
            _validate_local(current, row, current_plugin)
            _reject_aliases(current, row, current_plugin)
            after = _merged_binding(current, row)
            if after == current.bkbase_v4_resources:
                return "unchanged"
            before_save()
            current.bkbase_v4_resources = after
            current.save(update_record=False, update_fields=["bkbase_v4_resources"])
    return "updated"
