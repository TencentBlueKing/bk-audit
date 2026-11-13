"""恢复已绑定的 V4 快照，先恢复下游再打开拉取。
沿用快照的 source_replay 互斥槽，每次写前持久化目标摘要与认领。
仅以正式 GET 观察实际生效，后台不会重发未确认的写入。
"""
import uuid
from copy import deepcopy

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Q

from apps.exceptions import SnapshotPreparingException
from apps.meta.models import System
from core.exceptions import LockError
from services.web.bkbase import basic_snapshot_link, metadata, source
from services.web.bkbase.asset_etl_maintenance import _canonical_spec
from services.web.bkbase.common import (
    get_bkbase_context,
    operation_result,
    resource_lock,
    resource_params,
    snapshot_lock,
)
from services.web.bkbase.constants import (
    BKBASE_V4_MAX_POLLS,
    BKBASE_V4_STORAGE_CLUSTER_KINDS,
    CleanState,
    DataSourceDesiredState,
    TaskState,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import (
    JoinDataType,
    SnapshotRunningStatus,
    SnapShotStorageChoices,
)
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot

RESTORE_MODE = "restore"


def check_available(snapshot):
    """核对恢复能否独占已有快照的操作槽。"""
    binding = snapshot.bkbase_v4_resources
    if not isinstance(binding, dict):
        raise BKBaseResourceMappingError(message="Invalid Snapshot resource bindings")
    replay = binding.get("source_replay", {})
    maintenance = binding.get("asset_etl_maintenance") or {}
    provision = binding.get("source_provision") or {}
    if not all(isinstance(item, dict) for item in (replay, maintenance, provision)):
        raise BKBaseResourceMappingError(message="Invalid Snapshot resource operation")
    if (
        binding.get("pending_action")
        or replay.get("active")
        or maintenance.get("active")
        or provision
        and provision.get("stage") != "ready"
    ):
        raise SnapshotPreparingException()
    if replay.get("outcome_unknown") and replay.get("mode") != RESTORE_MODE:
        raise BKBaseResourceMappingError(message="Previous Snapshot source write is unresolved")
    return replay


def _input_digest(snapshot, params, context):
    return source._replay_inputs(snapshot, params, context, restore=True)


def _check_ownership(snapshot):
    """只检查确实声明了相同写目标的本地记录。"""
    binding = snapshot.bkbase_v4_resources
    storages = binding["storages"]
    if set(storages) - set(SnapShotStorageChoices.values) or len(
        {(ref["tenant"], ref["namespace"], ref["name"]) for ref in storages.values()}
    ) != len(storages):
        raise BKBaseResourceMappingError(message="Invalid Snapshot storage bindings")
    conflicts = Q(bkbase_v4_resources__data_source=binding["data_source"]) | Q(
        bkbase_v4_resources__clean=binding["clean"]
    )
    if binding["clean_role"] == "owner":
        conflicts |= Q(
            bkbase_v4_resources__result_table=binding["result_table"], bkbase_v4_resources__clean_role="owner"
        )
    for ref in storages.values():
        for purpose in (*SnapShotStorageChoices.values, "main", "replica"):
            conflicts |= Q(**{f"bkbase_v4_resources__storages__{purpose}": ref})
    if (
        Snapshot.objects.filter(conflicts).exclude(pk=snapshot.pk).exists()
        or CollectorConfig.objects.filter(conflicts).exists()
        or CollectorPlugin.objects.filter(conflicts).exists()
    ):
        raise BKBaseResourceMappingError(message="Snapshot resources have another local writer")


def _get(context, ref, endpoint):
    kind = ref["kind"]
    params = resource_params(context, ref, kind=kind)
    if kind in ("DataId", "ResultTable"):
        params.pop("tenant")
    value = endpoint(**params)
    if source._binding_resource_ref(context, value, kind) != ref or not isinstance(value.get("status"), dict):
        raise BKBaseResourceMappingError(message=f"Snapshot {kind} response identity or status changed")
    return value


def _check_stopped_source(snapshot, current, conn_ref):
    if (
        not source._source_desires_stopped(current)
        or _state(current) != TaskState.STOPPED
        or current["spec"].get("data_conn") != conn_ref
        or current["spec"].get("data_id") != snapshot.bkbase_v4_resources["data_id"]
        or source._replay_raw_id(current["metadata"].get("labels", {}).get("raw_data_id")) != snapshot.bkbase_data_id
    ):
        raise BKBaseResourceMappingError(message="Callback update requires the matching stopped DataSource")


def _read(context, snapshot, params, *, configure_source=False, reconnect=None):
    """只读完整绑定及其关联，写入前验证所有资源的归属。"""
    binding = snapshot.bkbase_v4_resources
    source_value = _get(context, binding["data_source"], api.bk_base_v4.data_source_get)
    spec = source_value["spec"]
    conn_ref = source._replay_ref(context, spec.get("data_conn"), "DataConn")
    if binding.get("data_conn", conn_ref) != conn_ref or spec.get("data_id") != binding["data_id"]:
        raise BKBaseResourceMappingError(message="Snapshot DataSource input or connection changed")
    connection = _get(context, conn_ref, api.bk_base_v4.data_conn_get)
    if reconnect is None:
        base = System.objects.get(system_id=snapshot.system_id).callback_url.rstrip("/")
        conn_info = connection["spec"].get("conn_info")
        reconnect = isinstance(conn_info, dict) and conn_info.get("url") != base
        if reconnect:
            _check_stopped_source(snapshot, source_value, conn_ref)
    conn_target = src_target = None
    if reconnect:
        source.check_pull_connection_writer(snapshot, context, conn_ref)
        conn_target = source._configured_pull_connection(snapshot, connection, params)
        src_target = source._configured_pull_source(source_value, conn_target, params)
        source._validate_replay_pull(params, src_target["spec"], conn_target)
    elif configure_source:
        src_target = source._configured_pull_mode(source_value, connection, params)
    else:
        source._validate_replay_pull(params, spec, connection, preserve_encrypted_auth=True)
    clean = _get(context, binding["clean"], api.bk_base_v4.clean_get)
    data_id = _get(context, binding["data_id"], api.bk_base_v4.data_id_get)
    table = _get(context, binding["result_table"], api.bk_base_v4.result_table_resource_get)
    logical_id = snapshot.bkbase_table_id
    table_ref, table_id = metadata.result_table_identity(context, table)
    if table_ref != binding["result_table"]:
        raise BKBaseResourceMappingError(message="Snapshot ResultTable reference changed")
    raw_id = snapshot.bkbase_data_id
    clean_spec = clean["spec"]
    if (
        source._replay_raw_id(source_value["metadata"].get("labels", {}).get("raw_data_id")) != raw_id
        or source._replay_raw_id(clean_spec.get("raw_data_id")) != raw_id
        or clean_spec.get("data_id") != binding["data_id"]
        or clean_spec.get("result_table_id") != logical_id
        or clean_spec.get("result_table_source") != {"owner": "new", "existing": "existing"}[binding["clean_role"]]
        or not source._snapshot_clean_identity_matches(snapshot, clean)
        or table_id != logical_id
        or (snapshot.join_data_type == JoinDataType.ASSET and binding["clean_role"] != "owner")
    ):
        raise BKBaseResourceMappingError(message="Snapshot Source, Clean or ResultTable identity conflicts")
    resources = {"connection": connection, "data_id": data_id, "result_table": table, "clean": clean}
    for kind, ref in sorted(binding["storages"].items()):
        value = _get(context, ref, api.bk_base_v4.data_storage_get)
        info = value["spec"].get("tableInfo") or {}
        if (
            not isinstance(info, dict)
            or info.get("source") != binding["result_table"]
            or any(
                value["metadata"].get(key, {}).get("result_table_id") not in (None, logical_id)
                for key in ("labels", "annotations")
            )
        ):
            raise BKBaseResourceMappingError(message="Snapshot DataStorage ResultTable conflicts")
        source._replay_ref(context, info.get("storage"), BKBASE_V4_STORAGE_CLUSTER_KINDS[kind])
        resources[kind] = value
    resources["data_source"] = source_value
    return resources, conn_target, src_target


def _read_collectors(context, snapshot, resources, plan=None, writes=None):
    """Append Basic collector Clean resources after the Source replay step."""
    collectors = basic_snapshot_link.collectors(snapshot, plan, writes)
    if not collectors:
        return {}, None
    join = basic_snapshot_link.join_config(snapshot.bkbase_table_id, resources.get(SnapShotStorageChoices.REDIS))
    for key, (collector, _) in collectors.items():
        resources[key] = basic_snapshot_link.read(context, collector, _get)
    return collectors, join


def _plan_collectors(context, snapshot, resources, previous=None):
    """Verify unlinked collectors and record their current and desired Clean configurations."""
    collectors, join = _read_collectors(context, snapshot, resources)
    plan = {}
    for key, (collector, step) in collectors.items():
        value = resources[key]
        if _state(value) != TaskState.RUNNING:
            raise BKBaseResourceMappingError(message="Basic collector Clean has not confirmed running")
        writer = {
            "writer_digest": basic_snapshot_link.writer_digest(collector),
            "logical_output": value["spec"]["result_table_id"],
        }
        prior = (previous or {}).get(key)
        if prior and any(prior.get(name) != identity for name, identity in writer.items()):
            raise BKBaseResourceMappingError(message="Basic collector writer identity changed")
        plan[key] = {
            **writer,
            "baseline": _digest(value),
            "target": _digest(basic_snapshot_link.desired(value, join)),
            "collector": step,
        }
    return plan, collectors, join


def _failed_collectors(plan, writes):
    """Only explicitly attributed failed publishes can be replaced on a new request."""
    return {
        key
        for key, write in writes.items()
        if "collector" in plan.get(key, {}) and write.get("observed") == TaskState.FAILED and not write.get("linked")
    }


def _desired(resource, *, configured=None):
    """计算状态恢复的 PUT 全量载荷，保留现有规则和表配置。"""
    desired = deepcopy(resource if configured is None else configured)
    kind, spec = desired["kind"], desired["spec"]
    if kind == "Clean":
        config, deploy = spec.get("config_revision", 0), spec.get("deploy_revision", 0)
        if type(config) is not int or config < 0 or type(deploy) is not int or config != deploy:
            raise BKBaseResourceMappingError(message="Snapshot Clean has unpublished or invalid revisions")
        if spec.get("desired_status") == CleanState.STOPPED:
            spec.update(desired_status=CleanState.RUNNING, config_revision=config + 1, deploy_revision=config + 1)
        elif spec.get("desired_status") != CleanState.RUNNING:
            raise BKBaseResourceMappingError(message="Snapshot Clean is not in a recoverable desired state")
    elif kind == "DataStorage":
        annotations = desired["metadata"].get("annotations") or {}
        if annotations.get("task_stopped") == "true":
            annotations["task_stopped"] = "false"
            desired["metadata"]["annotations"] = annotations
    elif kind == "DataSource":
        if source._source_desires_stopped(resource):
            spec["desired_status"] = DataSourceDesiredState.CREATED
        elif str(spec.get("desired_status")).lower() != TaskState.RUNNING:
            raise BKBaseResourceMappingError(message="Snapshot DataSource is not in a recoverable desired state")
        source._set_pull_replay_history(spec["report_config"])
    return desired


def _digest(resource):
    """比较业务配置，忽略服务器观测字段和启动时 Created→Running 的转换。"""
    kind = resource["kind"]
    if kind == "DataConn":
        return source.pull_connection_digest(resource)
    if kind not in ("Clean", "DataStorage", "DataSource"):
        return source._replay_resource_digest(resource)
    normalized = deepcopy(resource)
    normalized["spec"] = _canonical_spec(normalized["spec"], kind)
    if kind == "DataSource":
        desired = str(normalized["spec"].get("desired_status")).lower()
        normalized["spec"]["desired_status"] = "running" if desired == "created" else desired
    elif kind == "DataStorage":
        # GET 反映本次操作者，其他入库注解仍属于业务配置。
        normalized["metadata"].get("annotations", {}).pop("bk_username", None)
    return source._replay_resource_digest(normalized)


def _public_connection_digest(resource):
    """连接回执只允许 Authorization 及其加密标记发生正式转换。"""
    return source.pull_connection_digest(resource, public=True)


def _start_target(resource, *, initial_start=False, configured=None):
    """首次只激活原配置；已有快照恢复继续使用显式历史重放语义。"""
    if initial_start and resource["kind"] == "DataSource":
        desired = deepcopy(resource if configured is None else configured)
        if source._source_desires_stopped(resource):
            desired["spec"]["desired_status"] = DataSourceDesiredState.CREATED
        elif str(resource["spec"].get("desired_status")).lower() not in ("created", TaskState.RUNNING):
            raise BKBaseResourceMappingError(message="Initial DataSource is not in a startable state")
        return desired
    return _desired(resource, configured=configured)


def prepare(snapshot, request_data, pull_handler, pre_check, *, initial_start=False):
    """持快照锁只读预检，成功后登记待后台推进的恢复或首次启动意图。"""
    try:
        params = pull_handler.config
    except (AttributeError, TypeError, ValueError) as error:
        raise BKBaseResourceMappingError(message="Snapshot pull configuration is unavailable") from error
    return _prepare(snapshot, request_data, params, pre_check, initial_start=initial_start)


def prepare_initial(snapshot, params):
    """存储已逐项确认后转交既有 Source/Basic 观察编排，不重放历史。"""
    request_data = {
        "join_data_type": snapshot.join_data_type,
        "storage_type": list(snapshot.storages.values_list("storage_type", flat=True)),
        "pull_type": snapshot.pull_type,
        "custom_config": snapshot.custom_config,
    }
    return _prepare(snapshot, request_data, params, lambda: None, initial_start=True)


def _prepare(snapshot, request_data, params, pre_check, *, initial_start=False):
    """建立同代计划；首次启动与恢复共享认领、观测及 Basic 关联提交。"""
    previous = check_available(snapshot)
    storages = set(snapshot.storages.values_list("storage_type", flat=True))
    if (
        request_data["join_data_type"] != snapshot.join_data_type
        or set(request_data["storage_type"]) != storages
        or request_data.get("custom_config") not in (None, snapshot.custom_config)
    ):
        raise BKBaseResourceMappingError(
            message="Snapshot restore requires the existing pull and storage configuration"
        )
    provision = snapshot.bkbase_v4_resources.get("source_provision") or {}
    provision_id = provision.get("operation_id") if initial_start else None
    if initial_start and (
        not isinstance(provision_id, str)
        or not provision_id
        or not provision.get("handoff_ready")
        or provision.get("completed")
        or previous.get("initial_start")
        and previous.get("initial_provision_id") != provision_id
    ):
        raise BKBaseResourceMappingError(message="Initial Snapshot start requires its verified provision generation")
    context = get_bkbase_context()
    fingerprint = _input_digest(snapshot, params, context)
    if initial_start and previous.get("initial_start") and previous.get("input_digest") != fingerprint:
        raise BKBaseResourceMappingError(message="Initial Snapshot retry inputs changed")
    _check_ownership(snapshot)
    target_pull_type = request_data["pull_type"] if request_data["pull_type"] != snapshot.pull_type else None
    old_plan, old_writes = previous.get("plan", {}), previous.get("writes", {})
    failed_collectors = _failed_collectors(old_plan, old_writes)
    continuing_links = (
        snapshot.status == SnapshotRunningStatus.FAILED
        and old_writes.get("data_source", {}).get("observed") == TaskState.RUNNING
        and (previous.get("awaiting_collectors") or failed_collectors)
    )
    unresolved = previous.get("outcome_unknown") or (
        previous.get("mode") == RESTORE_MODE
        and (continuing_links or any(write.get("observed") == TaskState.PENDING for write in old_writes.values()))
    )
    old_conn, old_conn_write = old_plan.get("connection", {}), old_writes.get("connection", {})
    retry_conn = (
        not unresolved
        and snapshot.status == SnapshotRunningStatus.FAILED
        and previous.get("mode") == RESTORE_MODE
        and previous.get("input_digest") == fingerprint
        and old_conn.get("public_target")
        and old_conn_write.get("accepted") is True
        and old_conn_write.get("connection_digest")
        and old_conn_write.get("observed") == TaskState.FAILED
    )
    resources, conn_target, src_target = _read(
        context,
        snapshot,
        params,
        configure_source=target_pull_type is not None,
        reconnect=bool(old_conn.get("public_target")) if unresolved or retry_conn else None,
    )
    if retry_conn:
        if _observed(resources["connection"], old_conn, old_conn_write) != TaskState.FAILED:
            # 旧目标重新调和时继续观察，避免另发一次相同配置。
            unresolved, retry_conn = True, False
        else:
            conn_ref = source._binding_resource_ref(context, resources["connection"], "DataConn")
            _check_stopped_source(snapshot, resources["data_source"], conn_ref)
            if _public_connection_digest(conn_target) != old_conn["public_target"]:
                raise BKBaseResourceMappingError(message="Failed DataConn retry requires the previous target")
    if unresolved:
        if previous["input_digest"] != fingerprint:
            raise BKBaseResourceMappingError(message="Unresolved Snapshot restore input has changed")
        plan = old_plan
        writes = {key: write for key, write in old_writes.items() if key not in failed_collectors}
        for key, value in resources.items():
            _observed(value, plan[key], writes.get(key, {}))
    else:
        configured = {"connection": conn_target, "data_source": src_target}
        plan = {
            key: {
                "baseline": _digest(value),
                "target": _digest(_start_target(value, initial_start=initial_start, configured=configured.get(key))),
            }
            for key, value in resources.items()
        }
        if conn_target is not None:
            plan["connection"]["public_target"] = _public_connection_digest(conn_target)
        if retry_conn:
            plan["connection"].update(retry_failed=True, start_time=resources["connection"]["status"].get("start_time"))
        plan["data_source"]["start_time"] = resources["data_source"]["status"].get("start_time")
        if initial_start and resources["data_source"]["status"].get("phase") == "Failed":
            plan["data_source"].update(retry_failed=True)
        for key in snapshot.bkbase_v4_resources["storages"]:
            storage_status = resources[key]["status"]
            if storage_status.get("phase") == "Failed":
                plan[key].update(retry_failed=True, start_time=storage_status.get("start_time"))
        writes = {}
        drafted, _, _ = _plan_collectors(context, snapshot, resources)
        plan.update(drafted)
    pre_check()
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
        if (
            latest.status != snapshot.status
            or check_available(latest) != previous
            or _input_digest(latest, params, context) != fingerprint
            or initial_start
            and (latest.bkbase_v4_resources.get("source_provision") or {}).get("operation_id") != provision_id
        ):
            raise BKBaseResourceMappingError(message="Snapshot restore inputs changed")
        if not unresolved:
            basic_snapshot_link.collectors(latest, plan, writes, locked=True)
        latest.bkbase_v4_resources["source_replay"] = {
            "operation_id": uuid.uuid4().hex,
            "mode": RESTORE_MODE,
            "active": True,
            "input_digest": fingerprint,
            "outcome_unknown": bool(previous.get("outcome_unknown")),
            "plan": plan,
            "writes": writes,
            "poll_count": 0,
        }
        if initial_start:
            latest.bkbase_v4_resources["source_replay"].update(initial_start=True, initial_provision_id=provision_id)
        if target_pull_type is not None:
            latest.bkbase_v4_resources["source_replay"]["target_pull_type"] = target_pull_type
        if unresolved and (previous.get("awaiting_collectors") or failed_collectors):
            latest.bkbase_v4_resources["source_replay"]["awaiting_collectors"] = True
        latest.status, latest.status_msg = SnapshotRunningStatus.PREPARING, ""
        latest.save(update_fields=["bkbase_v4_resources", "status", "status_msg", "updated_at"])
        latest.storages.update(status=SnapshotRunningStatus.PREPARING)
    return latest


def _matches_initial_generation(snapshot, operation):
    """首次启动的旧认领不得为另一 provision 代次写回或继续调用。"""
    return not operation.get("initial_start") or (
        isinstance(operation.get("initial_provision_id"), str)
        and (snapshot.bkbase_v4_resources.get("source_provision") or {}).get("operation_id")
        == operation["initial_provision_id"]
    )


def _save(
    snapshot,
    params,
    context,
    operation,
    patch,
    *,
    status=SnapshotRunningStatus.PREPARING,
    storages=None,
    collector_key=None,
    confirm_link=False,
):
    """只提交匹配代次和快照输入的状态，旧回包无法覆盖后续操作。"""
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
        binding = latest.bkbase_v4_resources
        if (
            latest.status != SnapshotRunningStatus.PREPARING
            or not isinstance(binding, dict)
            or binding.get("source_replay") != operation
            or not _matches_initial_generation(latest, operation)
            or binding.get("pending_action")
            or (binding.get("asset_etl_maintenance") or {}).get("active")
        ):
            return False
        collector_step = operation["plan"][collector_key]["collector"] if collector_key is not None else None
        if status == SnapshotRunningStatus.RUNNING:
            # 在输入摘要建立 repeatable-read 视图前复核集合。当前确认项随后由本事务单独锁定。
            if basic_snapshot_link.has_unlinked(latest, excluding=collector_step["id"] if confirm_link else None):
                status = SnapshotRunningStatus.PREPARING
                patch = {**patch, "awaiting_collectors": True, "poll_count": 0}
            elif operation.get("awaiting_collectors"):
                patch = {**patch, "awaiting_collectors": False}
            basic_snapshot_link.check_completed(latest, operation["plan"], operation["writes"])
        if _input_digest(latest, params, context) != operation["input_digest"]:
            raise BKBaseResourceMappingError(message="Snapshot restore inputs changed")
        if "plan" in patch:
            added = {key: step for key, step in patch["plan"].items() if step != operation["plan"].get(key)}
            basic_snapshot_link.collectors(latest, added, locked=True)
        if collector_step is not None:
            basic_snapshot_link.lock_input(latest, collector_step, confirm=confirm_link)
        updated = {**operation, **patch, "active": status == SnapshotRunningStatus.PREPARING}
        binding["source_replay"] = updated
        if status == SnapshotRunningStatus.RUNNING and operation.get("initial_start"):
            binding["source_provision"] = {**binding["source_provision"], "stage": "ready", "completed": True}
        latest.status, latest.status_msg = status, updated.get("message", "")
        fields = ["bkbase_v4_resources", "status", "status_msg", "updated_at"]
        if status == SnapshotRunningStatus.RUNNING and operation.get("target_pull_type") is not None:
            latest.pull_type = operation["target_pull_type"]
            fields.append("pull_type")
        latest.save(update_fields=fields)
        for kind, state in (storages or {}).items():
            latest.storages.filter(storage_type=kind).update(status=state)
        return updated


def _state(resource):
    kind = resource["kind"]
    if kind in ("DataSource", "Clean", "DataStorage"):
        return operation_result(resource, {"kind": kind}, "observe")["task_state"]
    return {"Ok": TaskState.RUNNING, "Failed": TaskState.FAILED}.get(resource["status"].get("phase"))


def _new_generation(resource, plan, write):
    start_time = resource["status"].get("start_time")
    if plan.get("retry_failed") and start_time and plan.get("start_time"):
        # 开始时间标记提交；看到新 Pending 后也不能接受旧代次终态。
        return write.get("accepted") is True and start_time != plan["start_time"]
    return write.get("accepted") is True and (
        write.get("saw_transition") or (start_time and start_time != plan.get("start_time"))
    )


def _observed(resource, plan, write):
    """按已登记摘要及回执确认，受理及旧状态不能代替当前 GET。"""
    current = _digest(resource)
    if plan.get("public_target"):
        accepted_digest = write.get("connection_digest")
        history = write.get("history_id")
        if accepted_digest and current == accepted_digest:
            if (history is None or resource["status"].get("history_id") == history) and (
                not plan.get("retry_failed") or _new_generation(resource, plan, write)
            ):
                return _state(resource) or TaskState.PENDING
            return TaskState.PENDING
        if current == plan["baseline"] or (
            not accepted_digest and _public_connection_digest(resource) == plan["public_target"]
        ):
            return TaskState.PENDING
        raise BKBaseResourceMappingError(message="Snapshot DataConn configuration drifted")
    if current not in (plan["baseline"], plan["target"]):
        raise BKBaseResourceMappingError(message=f"Snapshot {resource['kind']} configuration drifted")
    state = _state(resource)
    history = write.get("history_id")
    phase = resource["status"].get("phase")
    # Clean/Source控制器会更新状态或spec；历史记录号不是这次启动的稳定票据。
    history_matches = (
        resource["kind"] in ("Clean", "DataSource")
        or history is None
        or resource["status"].get("history_id") == history
    )
    if plan.get("retry_failed") and (
        (not write and phase == "Failed")
        or (
            write
            and (
                phase == "Terminating"
                or not history_matches
                or current != plan["target"]
                or not _new_generation(resource, plan, write)
            )
        )
    ):
        return TaskState.PENDING
    if state == TaskState.FAILED or phase == "Terminating":
        if "collector" in plan and (phase != "Failed" or current != plan["target"] or not history_matches):
            return TaskState.PENDING
        return TaskState.FAILED
    if resource["kind"] == "DataSource" and plan["baseline"] == plan["target"]:
        # 相同配置可能复用历史编号；必须确认受理并观察到新一代状态。
        if not _new_generation(resource, plan, write):
            return TaskState.PENDING
    if current == plan["target"] and state == TaskState.RUNNING and history_matches:
        if resource["kind"] != "DataSource" or str(resource["spec"].get("desired_status")).lower() == TaskState.RUNNING:
            return TaskState.RUNNING
    return TaskState.PENDING


def _can_submit(resource, step):
    state = _state(resource)
    if "collector" in step:
        return _digest(resource) == step["baseline"] and state == TaskState.RUNNING
    return _digest(resource) == step["baseline"] and (
        state == TaskState.STOPPED
        or (resource["kind"] == "DataSource" and state == TaskState.RUNNING)
        or (step.get("public_target") and state == TaskState.RUNNING)
        or (
            step.get("retry_failed")
            and resource["status"].get("phase") == "Failed"
            and resource["status"].get("start_time") == step.get("start_time")
        )
    )


def _submit(snapshot, params, context, operation, key, current, storages, writes, *, collector=None, join=None):
    """持资源锁重新 GET 并认领唯一发送；写回只记录是否受理。"""
    getter, updater = {
        "DataConn": (api.bk_base_v4.data_conn_get, api.bk_base_v4.data_conn_update),
        "Clean": (api.bk_base_v4.clean_get, api.bk_base_v4.clean_update),
        "DataStorage": (api.bk_base_v4.data_storage_get, api.bk_base_v4.data_storage_update),
        "DataSource": (api.bk_base_v4.data_source_get, api.bk_base_v4.data_source_update),
    }[current["kind"]]
    ref = source._binding_resource_ref(context, current, current["kind"])
    with resource_lock(context, ref):
        step = operation["plan"][key]
        latest = basic_snapshot_link.read(context, collector, _get) if collector else _get(context, ref, getter)
        if not _can_submit(latest, step):
            return
        configured = None
        conn_step = operation["plan"]["connection"]
        reconnect = bool(conn_step.get("public_target"))
        if latest["kind"] == "DataConn":
            source.check_pull_connection_writer(snapshot, context, ref)
            source_value = _get(context, snapshot.bkbase_v4_resources["data_source"], api.bk_base_v4.data_source_get)
            _check_stopped_source(snapshot, source_value, ref)
            configured = source._configured_pull_connection(snapshot, latest, params)
        elif latest["kind"] == "DataSource" and (reconnect or operation.get("target_pull_type") is not None):
            conn_ref = source._replay_ref(context, latest["spec"].get("data_conn"), "DataConn")
            connection = _get(context, conn_ref, api.bk_base_v4.data_conn_get)
            if _observed(connection, conn_step, writes.get("connection", {})) != TaskState.RUNNING:
                return
            if reconnect:
                connection = source._configured_pull_connection(snapshot, connection, params)
                configured = source._configured_pull_source(latest, connection, params)
            else:
                configured = source._configured_pull_mode(latest, connection, params)
        desired = (
            basic_snapshot_link.desired(latest, join)
            if collector
            else _start_target(latest, initial_start=operation.get("initial_start", False), configured=configured)
        )
        if _digest(desired) != step["target"]:
            raise BKBaseResourceMappingError(message="Snapshot restore target changed")
        writes = {**writes, key: {"accepted": None, "observed": TaskState.PENDING}}
        claimed = _save(
            snapshot,
            params,
            context,
            operation,
            {"writes": writes, "outcome_unknown": True, "poll_count": 0},
            storages=storages,
            collector_key=key if collector else None,
        )
        if not claimed:
            return
        try:
            result = updater(
                **resource_params(context, ref), metadata=desired["metadata"], spec=desired["spec"], status=None
            )
        except APIRequestError:
            return
        if not isinstance(result, dict) or not isinstance(result.get("status"), dict):
            return
        if step.get("retry_failed") and (
            result["status"].get("phase") != "Pending"
            or not isinstance(result.get("metadata"), dict)
            or any(result["metadata"].get(field) != ref[field] for field in ("tenant", "namespace", "name"))
        ):
            return
        receipt = {**writes[key], "accepted": True, "history_id": result["status"].get("history_id")}
        if step.get("public_target"):
            digest = source.accepted_pull_connection_digest(context, ref, result, desired, step["public_target"])
            if not digest:
                return
            receipt["connection_digest"] = digest
        _save(snapshot, params, context, claimed, {"writes": {**writes, key: receipt}, "outcome_unknown": False})


def _confirm_link(snapshot, params, context, operation, key, collector, progress, storages, *, complete):
    """Verify the target again under the writer lock before committing the local link."""
    step = operation["plan"][key]
    ref = collector.bkbase_v4_resources["clean"]
    with resource_lock(context, ref):
        latest = basic_snapshot_link.read(context, collector, _get)
        writes = progress["writes"]
        if _observed(latest, step, writes.get(key, {})) != TaskState.RUNNING:
            _wait(snapshot, params, context, operation, storages=storages)
            return
        confirmed = {**writes, key: {**writes.get(key, {}), "linked": True, "observed": TaskState.RUNNING}}
        _save(
            snapshot,
            params,
            context,
            operation,
            {**progress, "writes": confirmed, "poll_count": 0, "message": ""},
            status=SnapshotRunningStatus.RUNNING if complete else SnapshotRunningStatus.PREPARING,
            storages=storages,
            collector_key=key,
            confirm_link=True,
        )


def _advance(snapshot, params, context, operation):
    if not _matches_initial_generation(snapshot, operation):
        return
    if _input_digest(snapshot, params, context) != operation["input_digest"]:
        raise BKBaseResourceMappingError(message="Snapshot restore inputs changed")
    _check_ownership(snapshot)
    plan, writes = operation["plan"], operation["writes"]
    resources, _, _ = _read(
        context,
        snapshot,
        params,
        configure_source=operation.get("target_pull_type") is not None,
        reconnect=bool(plan["connection"].get("public_target")),
    )
    states = {key: _observed(value, plan[key], writes.get(key, {})) for key, value in resources.items()}
    collectors = {}
    if all(state == TaskState.RUNNING for state in states.values()):
        claimed = {
            key: plan[key] for key, write in writes.items() if "collector" in plan[key] and not write.get("linked")
        }
        collectors, _ = _read_collectors(context, snapshot, resources, claimed, writes)
        states.update({key: _observed(resources[key], plan[key], writes[key]) for key in collectors})
    writes = {key: {**write, "observed": states[key]} if key in states else write for key, write in writes.items()}
    source_write = writes.get("data_source")
    if source_write and resources["data_source"]["status"].get("phase") in ("Pending", "Reconciling"):
        source_write["saw_transition"] = True
    for key in (*snapshot.bkbase_v4_resources["storages"], "connection"):
        write = writes.get(key)
        current = resources[key]
        if (
            write
            and plan[key].get("retry_failed")
            and current["status"].get("phase") in ("Pending", "Reconciling")
            and (write.get("history_id") is None or current["status"].get("history_id") == write["history_id"])
            and _digest(current) == write.get("connection_digest", plan[key]["target"])
        ):
            write["saw_transition"] = True
    progress = {
        "writes": writes,
        "outcome_unknown": any(
            write.get("accepted", False) is None
            and not write.get("linked")
            and write["observed"] != TaskState.RUNNING
            and not (
                write["observed"] == TaskState.FAILED
                and plan[key]["baseline"] != plan[key]["target"]
                and (key not in states or _digest(resources[key]) == plan[key]["target"])
            )
            for key, write in writes.items()
        ),
    }
    storages = {key: states[key] for key in snapshot.bkbase_v4_resources["storages"]}
    storage_statuses = {
        key: SnapshotRunningStatus.RUNNING
        if state == TaskState.RUNNING
        else SnapshotRunningStatus.FAILED
        if state == TaskState.FAILED
        else SnapshotRunningStatus.PREPARING
        for key, state in storages.items()
    }
    failed = next((key for key, state in states.items() if state == TaskState.FAILED), None)
    if failed is not None:
        _save(
            snapshot,
            params,
            context,
            operation,
            {**progress, "message": f"Snapshot restore {failed} failed"},
            status=SnapshotRunningStatus.FAILED,
            storages=storage_statuses,
        )
        return
    pending = [key for key, state in states.items() if state != TaskState.RUNNING or key in collectors]
    if not pending:
        _advance_unclaimed(snapshot, params, context, operation, progress, resources, storage_statuses)
        return
    key = pending[0]
    collector = collectors[key][0] if key in collectors else None
    if collector and states[key] == TaskState.RUNNING:
        _confirm_link(
            snapshot,
            params,
            context,
            operation,
            key,
            collector,
            progress,
            storage_statuses,
            complete=len(pending) == 1,
        )
        return
    current = resources[key]
    step = plan[key]
    if (
        key not in writes
        and (key == "data_source" or step.get("retry_failed") or step["baseline"] != step["target"])
        and _can_submit(current, step)
    ):
        _submit(snapshot, params, context, operation, key, current, storage_statuses, writes)
        return
    _wait(snapshot, params, context, operation, storages=storage_statuses, progress=progress)


def _advance_unclaimed(snapshot, params, context, operation, progress, resources, storages):
    """Persist the observed writes before building collector drafts from current ETL."""
    plan = operation["plan"]
    writes = progress["writes"]
    retained = {key: step for key, step in plan.items() if "collector" not in step or key in writes}
    had_draft = retained.keys() != plan.keys()
    if not had_draft and not operation.get("awaiting_collectors"):
        _save(
            snapshot,
            params,
            context,
            operation,
            {**progress, "message": ""},
            status=SnapshotRunningStatus.RUNNING,
            storages=storages,
        )
        return
    if not operation.get("awaiting_collectors") or any(operation.get(key) != value for key, value in progress.items()):
        operation = _save(
            snapshot, params, context, operation, {**progress, "awaiting_collectors": True}, storages=storages
        )
        if not operation:
            return
    basic_snapshot_link.check_completed(snapshot, plan, writes)
    drafted, collectors, join = _plan_collectors(context, snapshot, resources, plan)
    if not drafted:
        _save(
            snapshot,
            params,
            context,
            operation,
            {**progress, "plan": retained, "message": ""},
            status=SnapshotRunningStatus.RUNNING,
            storages=storages,
        )
        return
    next_plan = {**retained, **drafted}
    if next_plan != plan:
        operation = _save(snapshot, params, context, operation, {"plan": next_plan, "poll_count": 0}, storages=storages)
        if not operation or not had_draft:
            return
    key = next(iter(drafted))
    collector = collectors[key][0]
    current = resources[key]
    if _observed(current, drafted[key], {}) == TaskState.RUNNING:
        _confirm_link(
            snapshot, params, context, operation, key, collector, progress, storages, complete=len(drafted) == 1
        )
    else:
        _submit(snapshot, params, context, operation, key, current, storages, writes, collector=collector, join=join)


def _wait(snapshot, params, context, operation, *, storages=None, progress=None):
    count = operation["poll_count"] + 1
    failed = count >= BKBASE_V4_MAX_POLLS
    patch = {**(progress or {}), "poll_count": count}
    if failed:
        patch["message"] = "Snapshot restore observation timed out"
        if patch.get("outcome_unknown", operation.get("outcome_unknown")):
            patch["message"] += "; previous write outcome is unknown"
    _save(
        snapshot,
        params,
        context,
        operation,
        patch,
        status=SnapshotRunningStatus.FAILED if failed else SnapshotRunningStatus.PREPARING,
        storages=storages,
    )


def advance(snapshot, params):
    """逐次推进已有绑定，不影响同批其他快照，也不回退到 V3 建链。"""
    try:
        with snapshot_lock(snapshot.system_id, snapshot.resource_type_id):
            snapshot.refresh_from_db()
            binding = snapshot.bkbase_v4_resources or {}
            operation = binding.get("source_replay") or {}
            if (
                snapshot.status != SnapshotRunningStatus.PREPARING
                or not isinstance(operation, dict)
                or operation.get("mode") != RESTORE_MODE
                or not operation.get("active")
                or not isinstance(operation.get("operation_id"), str)
                or not operation["operation_id"]
                or binding.get("pending_action")
                or (binding.get("asset_etl_maintenance") or {}).get("active")
            ):
                return
            try:
                context = get_bkbase_context()
                try:
                    _advance(snapshot, params, context, operation)
                except APIRequestError:
                    _wait(snapshot, params, context, operation)
            except (BKBaseResourceMappingError, ImproperlyConfigured, AttributeError, KeyError, TypeError, ValueError):
                source.fail_snapshot_replay(
                    snapshot,
                    operation_id=operation.get("operation_id"),
                    message="Snapshot restore inputs or platform resource bindings changed",
                )
    except (LockError, Snapshot.DoesNotExist):
        return
