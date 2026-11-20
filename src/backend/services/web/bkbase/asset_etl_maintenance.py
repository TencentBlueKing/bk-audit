"""构建已有资产清洗和入库维护的 V4 请求。

维护操作仅使用已验证资源引用，不推导资源名称。
"""
import json
import time
import uuid
from copy import copy, deepcopy

from bk_resource import api
from django.db import transaction

from services.web.bkbase import clean, source, storage
from services.web.bkbase.common import (
    get_bkbase_context,
    reference,
    resource_lock,
    resource_params,
    snapshot_lock,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
)
from services.web.databus.constants import JoinDataType, SnapshotRunningStatus
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot


def _input_digest(snapshot, target_config, *, locked=False):
    """绑定业务配置、真实引用与待生效配置，不包含自身进度标记。"""
    binding = deepcopy(snapshot.bkbase_v4_resources or {})
    if not isinstance(binding, dict):
        raise BKBaseResourceMappingError(message="Invalid Asset resource bindings")
    binding.pop("asset_etl_maintenance", None)
    return source._replay_digest(
        {
            "snapshot": source._binding_snapshot_digest(snapshot, locked=locked, exclude_bindings=True),
            "binding": binding,
            "target_config": target_config,
        }
    )


def _checked_input(snapshot_id, expected, target_config, action):
    """短事务中重新校验真实输入后执行纯数据库状态变更。"""
    with transaction.atomic():
        snapshot = Snapshot.objects.select_for_update().get(pk=snapshot_id)
        if _input_digest(snapshot, target_config, locked=True) != expected:
            raise BKBaseResourceMappingError(message="Asset maintenance inputs changed")
        return action()


def _begin_operation(snapshot_id, input_digest, *, plan_digest=None):
    """短事务认领或恢复同一资产维护意图，不进行网络请求。"""
    with transaction.atomic():
        snapshot = Snapshot.objects.select_for_update().get(pk=snapshot_id)
        binding = deepcopy(snapshot.bkbase_v4_resources or {})
        if not isinstance(binding, dict):
            raise BKBaseResourceMappingError(message="Invalid Asset resource bindings")
        replay = binding.get("source_replay") or {}
        if not isinstance(replay, dict) or replay.get("active") or replay.get("outcome_unknown"):
            raise BKBaseResourceMappingError(message="Source operation is still pending")
        if binding.get("pending_action") or snapshot.status != SnapshotRunningStatus.RUNNING:
            raise BKBaseResourceMappingError(message="Snapshot is not available for maintenance")
        current = binding.get("asset_etl_maintenance") or {}
        if not isinstance(current, dict):
            raise BKBaseResourceMappingError(message="Invalid Asset maintenance operation")
        if current.get("active"):
            if current.get("input_digest") != input_digest:
                raise BKBaseResourceMappingError(message="Asset maintenance input changed")
            if plan_digest is not None and current.get("plan_digest") != plan_digest:
                raise BKBaseResourceMappingError(message="Asset maintenance plan changed")
            return current
        current = {"operation_id": uuid.uuid4().hex, "input_digest": input_digest, "active": True}
        if plan_digest is not None:
            current["plan_digest"] = plan_digest
        binding["asset_etl_maintenance"] = current
        snapshot.bkbase_v4_resources = binding
        snapshot.save(update_fields=["bkbase_v4_resources"])
        return current


def _claim_step(snapshot_id, operation_id, input_digest, step):
    """只认领一个尚未提交的写步骤；认领后调用方须在事务外发请求。"""
    with transaction.atomic():
        snapshot = Snapshot.objects.select_for_update().get(pk=snapshot_id)
        binding = deepcopy(snapshot.bkbase_v4_resources or {})
        operation = binding.get("asset_etl_maintenance") or {}
        if (
            snapshot.status != SnapshotRunningStatus.RUNNING
            or not operation.get("active")
            or operation.get("operation_id") != operation_id
            or operation.get("input_digest") != input_digest
            or operation.get("step")
            or binding.get("pending_action")
        ):
            raise BKBaseResourceMappingError(message="Asset maintenance operation changed or has an outstanding write")
        operation["step"] = {**deepcopy(step), "state": "claimed"}
        binding["asset_etl_maintenance"] = operation
        snapshot.bkbase_v4_resources = binding
        snapshot.save(update_fields=["bkbase_v4_resources"])


def _record_step(snapshot_id, operation_id, input_digest, state, *, history_id=None):
    """只记录当前操作的写回执，旧回调不能覆盖新意图。"""
    if state not in ("accepted", "unknown"):
        raise ValueError("Unsupported Asset maintenance write state")
    with transaction.atomic():
        snapshot = Snapshot.objects.select_for_update().get(pk=snapshot_id)
        binding = deepcopy(snapshot.bkbase_v4_resources or {})
        operation = binding.get("asset_etl_maintenance") or {}
        step = operation.get("step") or {}
        if (
            snapshot.status != SnapshotRunningStatus.RUNNING
            or not operation.get("active")
            or operation.get("operation_id") != operation_id
            or operation.get("input_digest") != input_digest
            or step.get("state") != "claimed"
            or binding.get("pending_action")
        ):
            return False
        step["state"] = state
        if history_id is not None:
            step["history_id"] = history_id
        operation["step"] = step
        binding["asset_etl_maintenance"] = operation
        snapshot.bkbase_v4_resources = binding
        snapshot.save(update_fields=["bkbase_v4_resources"])
        return True


def _legacy_processing_id(snapshot):
    """新V4资源可以没有旧ID；真实存在的旧ID仍须有效且参与身份核对。"""
    value = snapshot.bkbase_processing_id
    if value is None or value == "":
        return None
    if not isinstance(value, str) or any(char.isspace() or char in ",=" for char in value):
        raise BKBaseResourceMappingError(message="Invalid legacy Asset processing identity")
    return value


def _validate_binding(context, snapshot, binding, storage_types):
    """维护仅接受完整的现存绑定，不按逻辑表名推导引用。"""
    if not isinstance(binding, dict) or binding.get("clean_role") != "owner":
        raise BKBaseResourceMappingError(message="Asset Clean owner binding is required")
    if binding.get("clean_pending_create"):
        raise BKBaseResourceMappingError(message="Asset Clean has an unresolved creation")
    if source._positive_raw_data_id(str(snapshot.bkbase_data_id)) is None:
        raise BKBaseResourceMappingError(message="Missing Asset raw data identity")
    _legacy_processing_id(snapshot)
    if (
        not isinstance(snapshot.bkbase_table_id, str)
        or not snapshot.bkbase_table_id
        or any(char.isspace() or char in ",=" for char in snapshot.bkbase_table_id)
        or binding.get("result_table_id") != snapshot.bkbase_table_id
    ):
        raise BKBaseResourceMappingError(message="Asset logical result table identity mismatch")
    for key, kind in (
        ("clean", "Clean"),
        ("data_source", "DataSource"),
        ("data_id", "DataId"),
        ("result_table", "ResultTable"),
    ):
        ref = binding.get(key)
        if not isinstance(ref, dict):
            raise BKBaseResourceMappingError(message=f"Missing {kind} binding")
        resource_params(context, ref, kind=kind)
    refs = binding.get("storages")
    if not storage_types or len(storage_types) != len(set(storage_types)) or not isinstance(refs, dict):
        raise BKBaseResourceMappingError(message="Invalid Asset storage set")
    if set(refs) != set(storage_types):
        raise BKBaseResourceMappingError(message="Asset storage bindings do not match configured storage")
    for ref in refs.values():
        if not isinstance(ref, dict):
            raise BKBaseResourceMappingError(message="Missing DataStorage binding")
        resource_params(context, ref, kind="DataStorage")
    identities = {(ref["tenant"], ref["namespace"], ref["name"]) for ref in refs.values()}
    if len(identities) != len(refs):
        raise BKBaseResourceMappingError(message="Asset storage bindings must identify distinct tasks")


def _strict_reference(resource, context, kind):
    """只能使用响应明确给出的完整身份，不能由请求上下文补齐。"""
    if not isinstance(resource, dict) or not isinstance(resource.get("metadata"), dict):
        raise BKBaseResourceMappingError(message="Invalid Asset resource metadata")
    metadata = resource["metadata"]
    if any(
        not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in ("tenant", "namespace", "name")
    ):
        raise BKBaseResourceMappingError(message="Incomplete Asset resource identity")
    return reference(resource, context, kind)


def _check_local_owners(snapshot, binding):
    """拒绝其他本地写者声明同一 Clean、存储任务或 owner 结果表。"""

    def identity(ref):
        if not isinstance(ref, dict):
            return None
        keys = ("kind", "tenant", "namespace", "name")
        value = tuple(ref.get(key) for key in keys)
        return value if all(isinstance(item, str) and item for item in value) else None

    owned_clean = identity(binding.get("clean"))
    owned_rt = identity(binding.get("result_table"))
    owned_storages = {identity(ref) for ref in binding.get("storages", {}).values()} - {None}
    for model, plugin in ((Snapshot, False), (CollectorConfig, False), (CollectorPlugin, True)):
        queryset = model.objects.all()
        if model is Snapshot:
            queryset = queryset.exclude(pk=snapshot.pk)
        for other in queryset.values_list("bkbase_v4_resources", flat=True).iterator():
            if not isinstance(other, dict):
                raise BKBaseResourceMappingError(message="Invalid local owner binding")
            storages = other.get("storages") or {}
            if not isinstance(storages, dict):
                raise BKBaseResourceMappingError(message="Invalid local owner storage bindings")
            if (
                (owned_clean and identity(other.get("clean")) == owned_clean)
                or (owned_storages & {identity(ref) for ref in storages.values()})
                or (
                    owned_rt
                    and (plugin or other.get("clean_role") == "owner")
                    and identity(other.get("result_table")) == owned_rt
                )
            ):
                raise BKBaseResourceMappingError(message="Asset resources have another local writer")


def _load_existing(context, binding):
    """仅读取已绑定资源，不发现、创建或猜测资源。"""
    resources = {}
    for key, target, kind, endpoint, generic in (
        ("data_source", "source", "DataSource", api.bk_base_v4.data_source_get, False),
        ("data_id", "data_id", "DataId", api.bk_base_v4.data_id_get, True),
        ("clean", "clean", "Clean", api.bk_base_v4.clean_get, False),
        ("result_table", "rt", "ResultTable", api.bk_base_v4.result_table_resource_get, True),
    ):
        params = resource_params(context, binding[key], kind=kind)
        if generic:
            params.pop("tenant")
        resources[target] = endpoint(**params)
    resources["storages"] = {
        kind: api.bk_base_v4.data_storage_get(**resource_params(context, ref, kind="DataStorage"))
        for kind, ref in binding["storages"].items()
    }
    return resources


def _build_plan(context, snapshot, system, resource_type, target_config, *, retry_unknown=False):
    """完成本地及远端预检并在内存构造所有维护目标。"""
    binding = deepcopy(snapshot.bkbase_v4_resources or {})
    types = list(snapshot.storages.values_list("storage_type", flat=True))
    _validate_binding(context, snapshot, binding, types)
    _check_local_owners(snapshot, binding)
    resources = _load_existing(context, binding)
    candidate = copy(snapshot)
    candidate.custom_config = deepcopy(target_config)
    handlers = {
        kind: AssetEtlStorageHandler(
            data_id=snapshot.bkbase_data_id,
            system=system,
            resource_type=resource_type,
            storage_type=kind,
            snapshot=candidate,
            pull_report_config=resources["source"]["spec"].get("report_config"),
        )
        for kind in types
    }
    sampled_fields = deepcopy(next(iter(handlers.values())).schema_fields)
    for handler in handlers.values():
        handler.__dict__["schema_fields"] = deepcopy(sampled_fields)
    configs = {kind: handler.storage_config for kind, handler in handlers.items()}
    clusters = {
        kind: storage.resolve_storage_cluster(
            context, audit_namespace=system.namespace, storage_type=kind, legacy_cluster_id=config["storage_cluster"]
        )
        for kind, config in configs.items()
    }
    _validate_remote_resources(context, snapshot, binding, resources, clusters)
    operation = binding.get("asset_etl_maintenance") or {}
    step = operation.get("step") or {}

    def acceptable_phase(value, ref):
        phase = (value.get("status") or {}).get("phase")
        return phase == "Ok" or (phase == "Failed" and retry_unknown and step.get("ref") == ref)

    clean_spec = resources["clean"].get("spec") or {}
    if (
        not acceptable_phase(resources["clean"], binding["clean"])
        or (
            (resources["clean"].get("status") or {}).get("phase") == "Ok"
            and str(clean_spec.get("current_status", "")).lower() != "running"
        )
        or clean_spec.get("config_revision") != clean_spec.get("deploy_revision")
    ):
        raise BKBaseResourceMappingError(message="Asset Clean is not ready for maintenance")
    if any(not acceptable_phase(value, binding["storages"][kind]) for kind, value in resources["storages"].items()):
        raise BKBaseResourceMappingError(message="Asset DataStorage is not ready for maintenance")
    clean_params = next(iter(handlers.values())).clean_config
    raw = clean_params["json_config"]
    raw = json.loads(raw) if isinstance(raw, str) else raw
    patch = {"rules": clean.convert_rules(raw, fields=clean_params.get("fields", ()))}
    if "join" in raw:
        patch["join"] = deepcopy(raw["join"])
    return {
        "resources": resources,
        "clean_patch": patch,
        "storage_configs": configs,
        "storage_specs": {
            kind: _desired_storage_spec(resources["storages"][kind]["spec"], config) for kind, config in configs.items()
        },
        "clusters": clusters,
    }


def _clean_identity_labels_match(snapshot, binding, metadata):
    """Clean 标签可缺省，但已有 raw/结果表标签必须与已核身份一致。"""
    labels = metadata.get("labels", {})
    if not isinstance(labels, dict):
        return False
    expected = {"raw_data_id": str(snapshot.bkbase_data_id), "result_table_id": binding["result_table_id"]}
    return all(
        key not in labels or (isinstance(labels[key], str) and labels[key] == value) for key, value in expected.items()
    )


def _validate_remote_resources(context, snapshot, binding, resources, clusters):
    """核对已绑定资源身份与关联；其他独立资源并不构成写冲突。"""
    for key, name, kind in (
        ("data_source", "source", "DataSource"),
        ("data_id", "data_id", "DataId"),
        ("clean", "clean", "Clean"),
        ("result_table", "rt", "ResultTable"),
    ):
        actual = resources.get(name)
        if _strict_reference(actual, context, kind) != binding.get(key):
            raise BKBaseResourceMappingError(message=f"Asset {kind} identity mismatch")
    source_value, clean_value, rt_value = resources["source"], resources["clean"], resources["rt"]
    processing_id = _legacy_processing_id(snapshot)
    clean_spec = clean_value.get("spec") or {}
    source_spec = source_value.get("spec") or {}
    if (
        source_spec.get("data_id") != binding["data_id"]
        or str(source_spec.get("desired_status", "")).lower() != "running"
        or str(source_spec.get("current_status", "")).lower() != "running"
        or (source_value.get("status") or {}).get("phase") != "Ok"
        or (resources["data_id"].get("status") or {}).get("phase") != "Ok"
        or (rt_value.get("status") or {}).get("phase") != "Ok"
        or str(source_value["metadata"].get("labels", {}).get("raw_data_id")) != str(snapshot.bkbase_data_id)
        or clean_spec.get("data_id") != binding["data_id"]
        or str(clean_spec.get("raw_data_id")) != str(snapshot.bkbase_data_id)
        or clean_spec.get("result_table_id") != binding["result_table_id"]
        or clean_spec.get("result_table_source") != "new"
        or str(clean_spec.get("desired_status", "")).lower() != "running"
        or not _clean_identity_labels_match(snapshot, binding, clean_value["metadata"])
        or (
            processing_id is not None
            and clean_value["metadata"].get("labels", {}).get("processing_id") != processing_id
        )
        or rt_value["metadata"].get("labels", {}).get("result_table_id") != binding["result_table_id"]
    ):
        raise BKBaseResourceMappingError(message="Asset source, Clean or result table identity mismatch")
    for kind, ref in binding["storages"].items():
        value = resources.get("storages", {}).get(kind)
        if _strict_reference(value, context, "DataStorage") != ref:
            raise BKBaseResourceMappingError(message="Asset DataStorage identity mismatch")
        table = (value.get("spec") or {}).get("tableInfo") or {}
        metadata = value.get("metadata") or {}
        if (
            table.get("source") != binding["result_table"]
            or table.get("storage") != clusters.get(kind)
            or metadata.get("labels", {}).get("result_table_id") not in (None, binding["result_table_id"])
            or str(metadata.get("annotations", {}).get("task_stopped", "false")).lower() == "true"
        ):
            raise BKBaseResourceMappingError(message="Asset DataStorage source, cluster or state mismatch")


def _asset_storage_patch(params):
    """冻结受管配置；HDFS/Redis 不消费旧索引字段。"""
    desired = storage.convert_storage_config(params)
    if params.get("storage_type") in ("hdfs", "redis"):
        desired.get("taskFieldSetting", {}).pop("index_fields", None)
    return desired


def _desired_storage_spec(current, params):
    """将受管配置合并到锁内最新存储配置。"""
    desired = _asset_storage_patch(params)
    if params.get("storage_type") in ("hdfs", "redis"):
        current = deepcopy(current)
        current.get("taskFieldSetting", {}).pop("index_fields", None)
    return storage._merge_spec(current, desired)


def _plan_digest(plan):
    """仅冻结规则、受管存储配置和集群，不包含非受管的远端属性。"""
    return source._replay_digest(
        {
            "clean_patch": plan["clean_patch"],
            "storage_patches": {kind: _asset_storage_patch(config) for kind, config in plan["storage_configs"].items()},
            "clusters": plan["clusters"],
        }
    )


def _canonical_spec(spec, kind):
    """归一 Clean 服务端字段及 HDFS/Redis 空索引；其他 null 保持原样。"""
    value = deepcopy(spec)
    if kind == "Clean":
        for field in ("current_status", "created_by", "created_at", "updated_by", "updated_at"):
            value.pop(field, None)
    elif kind == "DataStorage":
        cluster = (value.get("tableInfo") or {}).get("storage") or {}
        fields = value.get("taskFieldSetting")
        if (
            cluster.get("kind") in ("Hdfs", "Redis")
            and isinstance(fields, dict)
            and fields.get("index_fields", False) is None
        ):
            fields.pop("index_fields")
    return value


def _validate_writable_resource(snapshot, binding, current, kind, cluster=None):
    """资源锁内复核写目标的归属，不能接管变更后的资源。"""
    spec = current.get("spec") or {}
    metadata = current.get("metadata") or {}
    if kind == "clean":
        processing_id = _legacy_processing_id(snapshot)
        if (
            spec.get("data_id") != binding["data_id"]
            or str(spec.get("raw_data_id")) != str(snapshot.bkbase_data_id)
            or spec.get("result_table_id") != binding["result_table_id"]
            or spec.get("result_table_source") != "new"
            or str(spec.get("desired_status", "")).lower() != "running"
            or not _clean_identity_labels_match(snapshot, binding, metadata)
            or (processing_id is not None and metadata.get("labels", {}).get("processing_id") != processing_id)
        ):
            raise BKBaseResourceMappingError(message="Asset Clean ownership changed")
    else:
        table = spec.get("tableInfo") or {}
        if (
            table.get("source") != binding["result_table"]
            or table.get("storage") != cluster
            or metadata.get("labels", {}).get("result_table_id") not in (None, binding["result_table_id"])
            or str(metadata.get("annotations", {}).get("task_stopped", "false")).lower() == "true"
        ):
            raise BKBaseResourceMappingError(message="Asset DataStorage source or cluster changed")


def _clean_patch_matches(spec, patch):
    """只对规则复用已证默认回显比较，其他维护字段仍按原值核对。"""
    return all(
        clean._same_clean_rules(value, spec.get(key)) if key == "rules" else spec.get(key) == value
        for key, value in patch.items()
    )


def _observe_target(resource, ref, desired_spec, *, history_id=None):
    """通过新的 GET 校验身份、期望配置与运行状态；不可用于 PUT 回包。"""
    context = {"tenant": ref.get("tenant"), "namespace": ref.get("namespace")}
    if _strict_reference(resource, context, ref["kind"]) != ref:
        raise BKBaseResourceMappingError(message="Asset maintenance observation identity mismatch")
    phase = (resource.get("status") or {}).get("phase")
    if phase == "Failed":
        return "failed"
    if phase != "Ok":
        return "pending"
    actual = deepcopy(resource.get("spec") or {})
    if ref["kind"] == "Clean":
        current = str(actual.pop("current_status", "")).lower()
        desired = _canonical_spec(desired_spec, "Clean")
        if not clean._same_clean_rules(desired.pop("rules", None), actual.pop("rules", None)):
            return "different"
        if _canonical_spec(actual, "Clean") != desired:
            return "different"
        if current != "running" or str(actual.get("desired_status", "")).lower() != "running":
            return "pending"
    elif ref["kind"] == "DataStorage":
        if _canonical_spec(actual, "DataStorage") != _canonical_spec(desired_spec, "DataStorage"):
            return "different"
        if history_id is not None and (resource.get("status") or {}).get("history_id") != history_id:
            return "pending"
        annotations = (resource.get("metadata") or {}).get("annotations") or {}
        if str(annotations.get("task_stopped", "false")).lower() == "true":
            return "pending"
    else:
        raise BKBaseResourceMappingError(message="Unsupported Asset maintenance resource kind")
    return "confirmed"


def _decide_step(step, observed, current_digest, *, retry=False):
    """已认领的写在重新 GET 后判断；未知结果默认绝不重发。"""
    if not isinstance(step, dict) or step.get("state") not in ("unknown", "claimed", "accepted"):
        raise BKBaseResourceMappingError(message="Invalid Asset maintenance step state")
    if observed == "confirmed":
        return "advance"
    if observed == "pending":
        return "wait"
    if observed == "failed":
        if retry:
            if step.get("target_digest") and current_digest == step["target_digest"]:
                return "retry_applied_failed"
            if step.get("before_digest") and current_digest == step["before_digest"]:
                return "retry"
            raise BKBaseResourceMappingError(message="Failed Asset resource changed; explicit retry refused")
        return "failed"
    if observed != "different":
        raise BKBaseResourceMappingError(message="Unknown Asset maintenance observation")
    if not retry:
        return "wait"
    if not step.get("before_digest") or current_digest != step["before_digest"]:
        raise BKBaseResourceMappingError(message="Asset resource changed; explicit retry refused")
    return "retry"


def _spec_digest(spec, kind):
    return source._replay_digest(_canonical_spec(spec, kind))


def _clear_step(snapshot_id, operation_id, target_digest):
    """只清除同一代次且目标一致的已观察步骤。"""
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().get(pk=snapshot_id)
        binding = deepcopy(latest.bkbase_v4_resources or {})
        operation = binding.get("asset_etl_maintenance") or {}
        if (
            operation.get("operation_id") != operation_id
            or (operation.get("step") or {}).get("target_digest") != target_digest
        ):
            raise BKBaseResourceMappingError(message="Asset maintenance step changed")
        operation.pop("step", None)
        binding["asset_etl_maintenance"] = operation
        latest.bkbase_v4_resources = binding
        latest.save(update_fields=["bkbase_v4_resources"])


def _retry_step(snapshot_id, operation_id, target_digest, *, new_target_digest=None, new_revision=None):
    """显式重试时原子重新认领，未知意图始终保留。"""
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().get(pk=snapshot_id)
        binding = deepcopy(latest.bkbase_v4_resources or {})
        operation = binding.get("asset_etl_maintenance") or {}
        step = operation.get("step") or {}
        if (
            operation.get("operation_id") != operation_id
            or not operation.get("active")
            or step.get("target_digest") != target_digest
            or step.get("state") not in ("claimed", "unknown", "accepted")
        ):
            raise BKBaseResourceMappingError(message="Asset maintenance retry step changed")
        step["state"] = "claimed"
        if new_target_digest is not None:
            if (
                type(new_revision) is not int
                or type(step.get("revision")) is not int
                or new_revision <= step["revision"]
            ):
                raise BKBaseResourceMappingError(message="Invalid Asset Clean retry revision")
            step.update(before_digest=target_digest, target_digest=new_target_digest, revision=new_revision)
        step.pop("history_id", None)
        operation["step"] = step
        binding["asset_etl_maintenance"] = operation
        latest.bkbase_v4_resources = binding
        latest.save(update_fields=["bkbase_v4_resources"])


def _finish(snapshot_id, operation_id, target_config):
    """确认所有步骤后才写入本地配置。"""
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().get(pk=snapshot_id)
        binding = deepcopy(latest.bkbase_v4_resources or {})
        operation = binding.get("asset_etl_maintenance") or {}
        if operation.get("operation_id") != operation_id or not operation.get("active") or operation.get("step"):
            raise BKBaseResourceMappingError(message="Asset maintenance is not complete")
        operation["active"] = False
        binding["asset_etl_maintenance"] = operation
        latest.bkbase_v4_resources = binding
        latest.custom_config = deepcopy(target_config)
        latest.save(update_fields=["bkbase_v4_resources", "custom_config"])


def _checked(snapshot_id, digest, target_config, action):
    return _checked_input(snapshot_id, digest, target_config, action)


class _MaintenanceRunner:
    """在已持有快照锁时串行处理已绑定资源。"""

    def __init__(self, snapshot, system, resource_type, target_config, retry_unknown):
        self.snapshot = snapshot
        self.system = system
        self.resource_type = resource_type
        self.target_config = target_config
        self.retry_unknown = retry_unknown
        self.context = get_bkbase_context()
        self.digest = None
        self.operation_id = None
        self.binding = None
        self.plan = None
        self.plan_digest = None

    def checked(self, action):
        return _checked(self.snapshot.pk, self.digest, self.target_config, action)

    def verify_previous(self, kind, ref, current):
        """恢复后须确认较早步骤仍符合目标且仍在运行。"""
        spec = current["spec"]
        if kind == "clean":
            patch = self.plan["clean_patch"]
            if (
                not _clean_patch_matches(spec, patch)
                or spec.get("config_revision") != spec.get("deploy_revision")
                or _observe_target(current, ref, spec) != "confirmed"
            ):
                raise BKBaseResourceMappingError(message="Earlier Asset step changed")
        elif (
            _observe_target(current, ref, _desired_storage_spec(spec, self.plan["storage_configs"][kind]))
            != "confirmed"
        ):
            raise BKBaseResourceMappingError(message="Earlier Asset storage changed")

    def desired_clean(self, current_spec, step):
        """旧规则不变不重复发布；重入时沿用已认领 revision。"""
        desired = deepcopy(current_spec)
        desired.update(deepcopy(self.plan["clean_patch"]))
        changed = not _clean_patch_matches(current_spec, self.plan["clean_patch"])
        changed = changed or current_spec.get("config_revision") != current_spec.get("deploy_revision")
        changed = changed or str(current_spec.get("desired_status", "")).lower() != "running"
        if step:
            revision = step.get("revision")
        elif changed:
            revision = max(int(current_spec.get("config_revision", 0)) + 1, int(time.time() * 1000))
        else:
            revision = current_spec.get("deploy_revision")
        if changed or step:
            desired.update(config_revision=revision, deploy_revision=revision, desired_status="Running")
        return desired, revision

    def send_and_observe(self, ref, kind, current, desired, target_digest, endpoint, updater):
        """PUT后记录回执，再通过新的GET确认目标；所有网络请求均在事务外。"""
        resource_kind = "Clean" if kind == "clean" else "DataStorage"
        try:
            payload = deepcopy(desired)
            if kind == "clean":
                payload.pop("current_status", None)
            response = updater(
                **resource_params(self.context, ref, kind=resource_kind),
                metadata=deepcopy(current["metadata"]),
                spec=payload,
                status=None,
            )
        except Exception:
            self.checked(lambda: _record_step(self.snapshot.pk, self.operation_id, self.digest, "unknown"))
            raise
        history_id = (response.get("status") or {}).get("history_id") if kind != "clean" else None
        if history_id == (current.get("status") or {}).get("history_id"):
            history_id = None
        recorded = self.checked(
            lambda: _record_step(self.snapshot.pk, self.operation_id, self.digest, "accepted", history_id=history_id)
        )
        if not recorded:
            raise BKBaseResourceMappingError(message="Asset maintenance write response was superseded")
        latest = endpoint(**resource_params(self.context, ref, kind=resource_kind))
        if _observe_target(latest, ref, desired, history_id=history_id) != "confirmed":
            raise BKBaseResourceMappingError(message="Asset maintenance accepted; observation pending")
        self.checked(lambda: _clear_step(self.snapshot.pk, self.operation_id, target_digest))

    def run_step(self, kind, ref):
        """锁内复核、认领或恢复单项；未知写默认不得自动重发。"""
        is_clean = kind == "clean"
        endpoint = api.bk_base_v4.clean_get if is_clean else api.bk_base_v4.data_storage_get
        updater = api.bk_base_v4.clean_update if is_clean else api.bk_base_v4.data_storage_update
        resource_kind = "Clean" if is_clean else "DataStorage"
        with resource_lock(self.context, ref):
            self.snapshot.refresh_from_db()
            if _input_digest(self.snapshot, self.target_config) != self.digest:
                raise BKBaseResourceMappingError(message="Asset maintenance inputs changed")
            _check_local_owners(self.snapshot, self.binding)
            current = endpoint(**resource_params(self.context, ref, kind=resource_kind))
            if _strict_reference(current, self.context, resource_kind) != ref:
                raise BKBaseResourceMappingError(message="Asset maintenance resource changed")
            _validate_writable_resource(self.snapshot, self.binding, current, kind, self.plan["clusters"].get(kind))
            current_spec = deepcopy(current["spec"])
            operation = (self.snapshot.bkbase_v4_resources or {}).get("asset_etl_maintenance") or {}
            step = operation.get("step")
            if step and step.get("ref") != ref:
                self.verify_previous(kind, ref, current)
                return
            if is_clean:
                desired, revision = self.desired_clean(current_spec, step)
            else:
                desired, revision = _desired_storage_spec(current_spec, self.plan["storage_configs"][kind]), None
            target_digest = _spec_digest(desired, resource_kind)
            if step and step.get("target_digest") != target_digest:
                raise BKBaseResourceMappingError(message="Asset maintenance target changed")
            observed = _observe_target(current, ref, desired, history_id=step.get("history_id") if step else None)
            claimed = False
            if step:
                decision = _decide_step(
                    step, observed, _spec_digest(current_spec, resource_kind), retry=self.retry_unknown
                )
                if decision == "advance":
                    self.checked(lambda: _clear_step(self.snapshot.pk, self.operation_id, target_digest))
                    return
                if decision not in ("retry", "retry_applied_failed"):
                    raise BKBaseResourceMappingError(message=f"Asset maintenance step {decision}")
                if is_clean and decision == "retry_applied_failed":
                    revision = (
                        max(
                            int(current_spec.get("config_revision", 0)),
                            int(current_spec.get("deploy_revision", 0)),
                            int(step.get("revision", 0)),
                            int(time.time() * 1000),
                        )
                        + 1
                    )
                    desired.update(config_revision=revision, deploy_revision=revision, desired_status="Running")
                    new_target_digest = _spec_digest(desired, resource_kind)
                    self.checked(
                        lambda: _retry_step(
                            self.snapshot.pk,
                            self.operation_id,
                            target_digest,
                            new_target_digest=new_target_digest,
                            new_revision=revision,
                        )
                    )
                    target_digest = new_target_digest
                else:
                    self.checked(lambda: _retry_step(self.snapshot.pk, self.operation_id, target_digest))
                claimed = True
            elif observed == "confirmed":
                return
            elif observed in ("pending", "failed"):
                raise BKBaseResourceMappingError(message=f"Asset maintenance resource {observed}")
            if not claimed:
                claim = {
                    "ref": deepcopy(ref),
                    "before_digest": _spec_digest(current_spec, resource_kind),
                    "target_digest": target_digest,
                    "revision": revision,
                }
                self.checked(lambda: _claim_step(self.snapshot.pk, self.operation_id, self.digest, claim))
            self.send_and_observe(ref, kind, current, desired, target_digest, endpoint, updater)

    def verify_final(self):
        """最后重读全部资源，再允许保存本地配置。"""
        self.snapshot.refresh_from_db()
        plan = _build_plan(self.context, self.snapshot, self.system, self.resource_type, self.target_config)
        if _plan_digest(plan) != self.plan_digest:
            raise BKBaseResourceMappingError(message="Asset maintenance plan changed")
        value = plan["resources"]["clean"]
        spec = value["spec"]
        if (
            not _clean_patch_matches(spec, plan["clean_patch"])
            or spec.get("config_revision") != spec.get("deploy_revision")
            or _observe_target(value, self.binding["clean"], spec) != "confirmed"
        ):
            raise BKBaseResourceMappingError(message="Asset Clean no longer matches the maintenance target")
        for kind, ref in self.binding["storages"].items():
            if _observe_target(plan["resources"]["storages"][kind], ref, plan["storage_specs"][kind]) != "confirmed":
                raise BKBaseResourceMappingError(message="Asset storage no longer matches the maintenance target")

    def verify_plan(self):
        """在事务外重新采样外部规则和本地集群配置，拒绝受管目标漂移。"""
        self.snapshot.refresh_from_db()
        self.system.refresh_from_db()
        self.resource_type.refresh_from_db()
        if _input_digest(self.snapshot, self.target_config) != self.digest:
            raise BKBaseResourceMappingError(message="Asset maintenance inputs changed")
        current = _build_plan(
            self.context,
            self.snapshot,
            self.system,
            self.resource_type,
            self.target_config,
            retry_unknown=self.retry_unknown,
        )
        self.snapshot.refresh_from_db()
        if _input_digest(self.snapshot, self.target_config) != self.digest or _plan_digest(current) != self.plan_digest:
            raise BKBaseResourceMappingError(message="Asset maintenance plan changed")

    def run(self):
        self.snapshot.refresh_from_db()
        if self.snapshot.join_data_type != JoinDataType.ASSET:
            raise BKBaseResourceMappingError(message="Asset maintenance requires an Asset snapshot")
        self.digest = _input_digest(self.snapshot, self.target_config)
        self.system.refresh_from_db()
        self.resource_type.refresh_from_db()
        self.plan = _build_plan(
            self.context,
            self.snapshot,
            self.system,
            self.resource_type,
            self.target_config,
            retry_unknown=self.retry_unknown,
        )
        self.plan_digest = _plan_digest(self.plan)
        self.snapshot.refresh_from_db()
        if _input_digest(self.snapshot, self.target_config) != self.digest:
            raise BKBaseResourceMappingError(message="Asset maintenance inputs changed during preflight")
        self.verify_plan()
        operation = self.checked(lambda: _begin_operation(self.snapshot.pk, self.digest, plan_digest=self.plan_digest))
        self.operation_id = operation["operation_id"]
        self.binding = self.snapshot.bkbase_v4_resources
        targets = [("clean", self.binding["clean"])] + [
            (kind, self.binding["storages"][kind]) for kind in sorted(self.binding["storages"])
        ]
        for kind, ref in targets:
            self.verify_plan()
            self.run_step(kind, ref)
        self.verify_final()
        self.checked(lambda: _finish(self.snapshot.pk, self.operation_id, self.target_config))
        return True


def run_maintenance(snapshot, system, resource_type, target_config, *, retry_unknown=False):
    """维护已有绑定；逐项 PUT 后只用新的 GET 确认。"""
    with snapshot_lock(snapshot.system_id, snapshot.resource_type_id):
        return _MaintenanceRunner(snapshot, system, resource_type, target_config, retry_unknown).run()
