"""在新 PULL Source 就绪后声明唯一的快照 Clean。

复用 Source provision 代次保存写意图；Source 继续停止，实际 ResultTable Ref 由下游验证。
"""
import time
from copy import deepcopy

from bk_resource import api
from bk_resource.exceptions import APIRequestError, ValidateException
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.db import transaction

from api.bk_base_v4.default import CleanCreateRejected
from apps.exceptions import CoreException
from apps.meta.models import ResourceType, System
from core.exceptions import LockError
from services.web.bkbase import clean, snapshot_restore, source, storage
from services.web.bkbase.common import (
    get_bkbase_context,
    get_resource_or_none,
    operation_result,
    resource_lock,
    resource_params,
    snapshot_lock,
)
from services.web.bkbase.constants import (
    BKBASE_V4_MAX_POLLS,
    CleanRole,
    CleanState,
    TaskState,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
    JoinDataEtlStorageHandler,
)
from services.web.databus.constants import JoinDataType, SnapshotRunningStatus
from services.web.databus.models import Snapshot


def _input_digest(snapshot, params, context, *, locked=False):
    """冻结已确认源绑定、快照配置和所选存储，避免过期操作发出或回写。"""
    binding = snapshot.bkbase_v4_resources
    operation = binding["source_provision"]
    if not source._provision_input_matches(snapshot, params, context, operation.get("digest")):
        raise BKBaseResourceMappingError(message="Snapshot PULL inputs changed after source provisioning")
    return source._replay_digest(
        {
            "snapshot": source._binding_snapshot_digest(snapshot, locked=locked, exclude_bindings=True),
            "identity": {key: binding.get(key) for key in ("data_source", "data_id", "raw_data_id", "clean")},
        }
    )


def _transition(
    snapshot,
    operation,
    patch,
    *,
    verify=None,
    terminal=None,
    confirmed=None,
    logical_id=None,
    storage_statuses=None,
    retry=False,
):
    """只在同代次且输入未变时保存认领或观察结果。"""
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
        binding = deepcopy(latest.bkbase_v4_resources or {})
        if (
            latest.status != (SnapshotRunningStatus.FAILED if retry else SnapshotRunningStatus.PREPARING)
            or not isinstance(binding, dict)
            or binding.get("source_provision") != operation
            or binding.get("pending_action")
        ):
            return None
        if verify:
            params, context, expected = verify
            if _input_digest(latest, params, context, locked=True) != expected:
                raise BKBaseResourceMappingError(message="Snapshot Clean provisioning inputs changed")
        current = {**operation, **patch}
        if confirmed:
            for key, value in confirmed.items():
                binding[key] = {**binding.get(key, {}), **value} if key == "storages" else value
        binding["source_provision"] = current
        latest.bkbase_v4_resources = binding
        fields = ["bkbase_v4_resources"]
        if logical_id is not None:
            latest.bkbase_table_id = logical_id
            fields.append("bkbase_table_id")
        if retry:
            latest.status, latest.status_msg = SnapshotRunningStatus.PREPARING, ""
            fields.extend(["status", "status_msg"])
        if terminal:
            latest.status, latest.status_msg = SnapshotRunningStatus.FAILED, terminal
            fields.extend(["status", "status_msg"])
        for kind, state in (storage_statuses or {}).items():
            latest.storages.filter(storage_type=kind).update(status=state)
        if verify and current.get("clean_step"):
            # 本事务产出的逻辑表和存储状态属于本代次输出，同步刷新其输入锚点。
            current["clean_step"] = {
                **current["clean_step"],
                "input_digest": _input_digest(latest, params, context, locked=True),
            }
        latest.save(update_fields=fields)
    return current


def _verify_source(snapshot, params, context, operation):
    """核对本代次停止的Source/DataId及已存清洗入口；就绪时返回真实Source，否则None。"""
    binding = snapshot.bkbase_v4_resources
    ref = source._replay_ref(context, binding.get("data_source"), "DataSource")
    data_ref = source._replay_ref(context, binding.get("data_id"), "DataId")
    raw_id = source._replay_raw_id(snapshot.bkbase_data_id)
    if operation.get("accepted_source") != ref or source._replay_raw_id(binding.get("raw_data_id")) != raw_id:
        raise BKBaseResourceMappingError(message="Source provision identity conflicts with Snapshot")
    current = api.bk_base_v4.data_source_get(**resource_params(context, ref, kind="DataSource"))
    if source._binding_resource_ref(context, current, "DataSource") != ref:
        raise BKBaseResourceMappingError(message="Source provision DataSource identity changed")
    spec = current["spec"]
    conn = source._replay_ref(context, spec.get("data_conn"), "DataConn")
    if (
        source._replay_raw_id(current["metadata"].get("labels", {}).get("raw_data_id")) != raw_id
        or source._replay_ref(context, spec.get("data_id"), "DataId") != data_ref
        or (conn["namespace"], conn["name"]) != (ref["namespace"], operation.get("conn_name"))
        or not isinstance(current.get("status"), dict)
        or not source._source_desires_stopped(current)
        or operation_result(current, ref, "observe")["task_state"] != TaskState.STOPPED
    ):
        raise BKBaseResourceMappingError(message="Snapshot Clean requires the verified stopped source")
    source.validate_source_provision_report(snapshot, params, conn["name"], spec.get("report_config"))
    step = operation.get("clean_step")
    if step:
        clean.validate_pull_clean_input(spec["report_config"], step["target_spec"]["rules"])
    data = api.bk_base_v4.data_id_get(namespace=data_ref["namespace"], name=data_ref["name"])
    if source._binding_resource_ref(context, data, "DataId") != data_ref:
        raise BKBaseResourceMappingError(message="Source provision DataId identity changed")
    status = data.get("status")
    phase = status.get("phase") if isinstance(status, dict) else None
    if phase in ("Failed", "Terminating"):
        raise BKBaseResourceMappingError(message="Source provision DataId failed")
    return current if phase == "Ok" else None


def _build_spec(snapshot, report_config):
    """复用既有 Asset/Basic 规则构造，每个快照只声明一个 Clean。"""
    system = System.objects.get(system_id=snapshot.system_id)
    resource_type = ResourceType.objects.get(system_id=snapshot.system_id, resource_type_id=snapshot.resource_type_id)
    handler_class = {JoinDataType.ASSET: AssetEtlStorageHandler, JoinDataType.BASIC: JoinDataEtlStorageHandler}
    handler = handler_class[snapshot.join_data_type](
        snapshot.bkbase_data_id, system, resource_type, None, snapshot=snapshot, pull_report_config=report_config
    )
    config = handler.clean_config
    spec = clean.build_clean_spec(
        config,
        data_ref=snapshot.bkbase_v4_resources["data_id"],
        logical_id=clean.declared_result_table_id(config),
        rt_owner=True,
    )
    revision = int(time.time() * 1000)
    spec.update(config_revision=revision, deploy_revision=revision, desired_status=CleanState.RUNNING)
    return spec


def _wait(snapshot, operation, verify=None):
    count = operation.get("clean_poll_count", 0) + 1
    patch = {"clean_poll_count": count}
    message = None
    if count >= BKBASE_V4_MAX_POLLS:
        downstream = bool(snapshot.bkbase_v4_resources.get("clean_ready"))
        patch["stage"] = "clean_ready" if downstream else "clean_failed"
        message = (
            "Snapshot storage provisioning observation timed out"
            if downstream
            else "Snapshot Clean provisioning observation timed out"
        )
        steps = operation.get("storage_steps", {}).values() if downstream else [operation.get("clean_step", {})]
        if any(step and step.get("accepted") is None for step in steps):
            message += "; creation outcome unknown, automatic retry disabled"
            if not downstream:
                patch["stage"] = "clean_unknown"
    _transition(snapshot, operation, patch, verify=verify, terminal=message)


def _submit(snapshot, context, operation, ref, verify, spec):
    if snapshot.bkbase_v4_resources.get("clean"):
        raise BKBaseResourceMappingError(message="New Snapshot already has another Clean binding")
    params = resource_params(context, ref, kind="Clean")
    if get_resource_or_none(api.bk_base_v4.clean_get, **params) is not None:
        raise BKBaseResourceMappingError(message="Clean exists without this Snapshot provision intent")
    step = {
        "ref": ref,
        "input_digest": verify[2],
        "target_keys": sorted(spec),
        "target_digest": source._replay_digest(spec),
        "target_spec": deepcopy(spec),
        "accepted": None,
    }
    claimed = _transition(snapshot, operation, {"clean_step": step, "clean_poll_count": 0}, verify=verify)
    if not claimed:
        return
    try:
        result = api.bk_base_v4.clean_create(
            tenant=params["tenant"], namespace=params["namespace"], metadata=params, spec=spec, status=None
        )
    except CleanCreateRejected as error:
        rejected = {**step, "accepted": False, "rejection": error.rejection}
        _transition(
            snapshot,
            claimed,
            {"stage": "clean_failed", "clean_step": rejected},
            verify=verify,
            terminal=str(error),
        )
        return
    except (APIRequestError, ValidateException):
        # 此处已持久化认领；重入只读取该 Ref。
        return
    if not clean.clean_create_receipt_matches(ref, result):
        return
    status = result.get("status")
    receipt = {**step, "accepted": True, "history_id": (status or {}).get("history_id")}
    _transition(snapshot, claimed, {"clean_step": receipt}, verify=verify)


def _matches_clean_target(step, actual):
    """只归一已确认的算子默认回显，旧认领没有声明原像时仍严格比较。"""
    observed = {key: actual.get(key) for key in step["target_keys"]}
    declared = step.get("target_spec")
    if not isinstance(declared, dict):
        return source._replay_digest(observed) == step["target_digest"]
    if sorted(declared) != step["target_keys"] or source._replay_digest(declared) != step["target_digest"]:
        return False
    expected_fields = {key: value for key, value in declared.items() if key != "rules"}
    actual_fields = {key: value for key, value in observed.items() if key != "rules"}
    return source._replay_digest(expected_fields) == source._replay_digest(actual_fields) and clean._same_clean_rules(
        declared.get("rules"), observed.get("rules"), strict_types=True
    )


def _observe(snapshot, context, operation, ref, verify):
    step = operation["clean_step"]
    current = get_resource_or_none(api.bk_base_v4.clean_get, **resource_params(context, ref, kind="Clean"))
    if current is None or not isinstance(current.get("status"), dict):
        _wait(snapshot, operation, verify)
        return
    binding = snapshot.bkbase_v4_resources
    logical_id = clean._existing_clean_table_id(
        context, ref, current, raw_id=snapshot.bkbase_data_id, data_ref=binding["data_id"], source_role="new"
    )
    if not _matches_clean_target(step, current["spec"]):
        raise BKBaseResourceMappingError(message="Snapshot Clean differs from its declared configuration")
    state = operation_result(current, ref, "observe")["task_state"]
    # history_id是最新历史记录，运行收敛会改变它；就绪按本代声明和实际状态确认。
    if state == TaskState.FAILED:
        _transition(snapshot, operation, {"stage": "clean_failed"}, verify=verify, terminal="Snapshot Clean failed")
    elif state == TaskState.RUNNING:
        rt_ref = clean._verified_result_table_ref(context, binding, logical_id)
        _transition(
            snapshot,
            operation,
            {"stage": "clean_ready"},
            verify=verify,
            logical_id=logical_id,
            confirmed={
                "clean": ref,
                "clean_role": CleanRole.OWNER,
                "clean_ready": True,
                "result_table_id": logical_id,
                "result_table": rt_ref,
            },
        )
    else:
        _wait(snapshot, operation, verify)


def _storage_handler(snapshot, kind):
    """复用实际资产或基础快照 Handler 的字段、周期及集群选择。"""
    system = System.objects.get(system_id=snapshot.system_id)
    resource_type = ResourceType.objects.get(system_id=snapshot.system_id, resource_type_id=snapshot.resource_type_id)
    handler = AssetEtlStorageHandler if snapshot.join_data_type == JoinDataType.ASSET else JoinDataEtlStorageHandler
    return handler(snapshot.bkbase_data_id, system, resource_type, kind, snapshot=snapshot)


def _storage_target(snapshot, context, handler):
    """与 configure_storage 使用同一转换及稳定引用，配置映射变化必须显式处理。"""
    params = handler.v4_storage_config
    cluster = storage.resolve_storage_cluster(
        context,
        audit_namespace=handler.system.namespace,
        storage_type=handler.storage_type,
        legacy_cluster_id=params["storage_cluster"],
    )
    rt_ref = snapshot.bkbase_v4_resources["result_table"]
    ref = storage.storage_ref(context, snapshot, rt_ref=rt_ref, cluster_ref=cluster, purpose=handler.storage_type)
    config = storage.convert_storage_config(params)
    if "auto_offset_reset" not in params:
        config.pop("autoOffsetReset", None)
    config.setdefault("tableInfo", {}).update(source=rt_ref, storage=cluster)
    return ref, config


def _create_storage(snapshot, context, operation, kind, handler, ref, target, verify, *, retry_failed=False):
    """存储锁内写前认领；超时或旧回包均不能重新创建或回写绑定。"""
    claimed = None
    step = None

    def claim(actual_ref, actual_target, old):
        nonlocal claimed, step
        if actual_ref != ref or actual_target != target:
            raise BKBaseResourceMappingError(message="Snapshot storage configuration changed before claim")
        if old is not None and not retry_failed:
            raise BKBaseResourceMappingError(message="DataStorage exists without this Snapshot provision intent")
        if retry_failed and (
            old is None
            or (old.get("status") or {}).get("phase") != "Failed"
            or storage._merge_spec(old["spec"], target) != old["spec"]
        ):
            raise BKBaseResourceMappingError(message="Failed storage retry requires the exact previous target")
        step = {"ref": ref, "target": target, "accepted": None}
        if retry_failed:
            step.update(retry_failed=True, previous_status=deepcopy(old["status"]), saw_transition=False)
        steps = {**operation.get("storage_steps", {}), kind: step}
        claimed = _transition(snapshot, operation, {"storage_steps": steps, "clean_poll_count": 0}, verify=verify)
        if not claimed:
            raise BKBaseResourceMappingError(message="Snapshot storage operation was superseded")

    try:
        result = handler.create_storage(_before_write=claim, _bind_owner=False, _retry_failed=retry_failed)
    except (APIRequestError, ValidateException):
        return
    if claimed:
        receipt = {**step, "accepted": True}
        if retry_failed and result.get("resource_phase") != "Pending":
            return
        _transition(snapshot, claimed, {"storage_steps": {**claimed["storage_steps"], kind: receipt}}, verify=verify)


def _advance_storages(snapshot, params, context, operation, verify):
    """每项存储以正式 GET 确认；全部就绪才转交首次 Source/Basic 启动。"""
    binding = snapshot.bkbase_v4_resources
    ref = binding["clean"]
    current = api.bk_base_v4.clean_get(**resource_params(context, ref, kind="Clean"))
    logical_id = clean._existing_clean_table_id(
        context, ref, current, raw_id=snapshot.bkbase_data_id, data_ref=binding["data_id"], source_role="new"
    )
    step = operation["clean_step"]
    if (
        logical_id != snapshot.bkbase_table_id
        or logical_id != binding["result_table_id"]
        or not _matches_clean_target(step, current["spec"])
        or clean._verified_result_table_ref(context, binding, logical_id) != binding["result_table"]
    ):
        raise BKBaseResourceMappingError(message="Snapshot Clean or ResultTable changed before activation")
    state = operation_result(current, ref, "observe")["task_state"]
    if state == TaskState.FAILED:
        _transition(snapshot, operation, {}, verify=verify, terminal="Snapshot Clean failed before Source activation")
        return
    if state != TaskState.RUNNING:
        _wait(snapshot, operation, verify)
        return
    selected = dict(snapshot.storages.values_list("storage_type", "status"))
    steps = operation.get("storage_steps", {})
    if (
        not selected
        or not isinstance(steps, dict)
        or not isinstance(binding.get("storages", {}), dict)
        or set(steps) - set(selected)
        or set(binding.get("storages", {})) - set(selected)
    ):
        raise BKBaseResourceMappingError(message="Snapshot storage selection is empty or changed")
    all_ready = True
    for kind in sorted(selected):
        handler = _storage_handler(snapshot, kind)
        ref, target = _storage_target(snapshot, context, handler)
        step = steps.get(kind)
        if step is None:
            _create_storage(snapshot, context, operation, kind, handler, ref, target, verify)
            return
        if not isinstance(step, dict) or step.get("ref") != ref or step.get("target") != target:
            raise BKBaseResourceMappingError(message="Snapshot storage claim or cluster mapping changed")
        current = get_resource_or_none(
            api.bk_base_v4.data_storage_get, **resource_params(context, ref, kind="DataStorage")
        )
        if current is None:
            all_ready = False
            # 未知受理先定位该 Ref；不对其他存储发新写。
            _wait(snapshot, operation, verify)
            return
        if (
            source._binding_resource_ref(context, current, "DataStorage") != ref
            or not isinstance(current.get("status"), dict)
            or storage._merge_spec(current["spec"], target) != current["spec"]
        ):
            raise BKBaseResourceMappingError(message="Snapshot DataStorage differs from the declared target")
        state = operation_result(current, ref, "observe")["task_state"]
        if step.get("retry_allowed"):
            if state == TaskState.FAILED:
                _create_storage(snapshot, context, operation, kind, handler, ref, target, verify, retry_failed=True)
                return
            step = {key: value for key, value in step.items() if key != "retry_allowed"}
        if step.get("retry_failed"):
            previous = step["previous_status"]
            status = current["status"]
            if status.get("phase") in ("Pending", "Reconciling"):
                step = {**step, "saw_transition": True}
            new_time = status.get("start_time") and status.get("start_time") != previous.get("start_time")
            new_history = status.get("history_id") is not None and status.get("history_id") != previous.get(
                "history_id"
            )
            if not (step.get("accepted") is True and (new_time or new_history or step.get("saw_transition"))):
                state = None
        local = (
            SnapshotRunningStatus.RUNNING
            if state == TaskState.RUNNING
            else SnapshotRunningStatus.FAILED
            if state == TaskState.FAILED
            else SnapshotRunningStatus.PREPARING
        )
        next_step = {**step, "observed": state}
        if state == TaskState.RUNNING:
            next_step["accepted"] = True
        if next_step != steps[kind] or selected[kind] != local or binding.get("storages", {}).get(kind) != ref:
            _transition(
                snapshot,
                operation,
                {"storage_steps": {**steps, kind: next_step}, "clean_poll_count": 0},
                verify=verify,
                confirmed={"storages": {kind: ref}},
                storage_statuses={kind: local},
                terminal=f"Snapshot {kind} storage failed" if state == TaskState.FAILED else None,
            )
            return
        all_ready = all_ready and state == TaskState.RUNNING
    if not all_ready:
        _wait(snapshot, operation, verify)
        return
    if _transition(snapshot, operation, {"stage": "ready", "handoff_ready": True}, verify=verify):
        snapshot.refresh_from_db()
        snapshot_restore.prepare_initial(snapshot, params)


def _rejected_clean_spec(step):
    """限定明确创建拒绝的重试使用原声明。"""
    rejection = step.get("rejection")
    code = rejection.get("code") if isinstance(rejection, dict) else None
    spec = step.get("target_spec")
    if (
        step.get("accepted") is not False
        or not isinstance(code, str)
        or code not in CleanCreateRejected.REASONS
        or not isinstance(spec, dict)
        or spec.get("result_table_source") != "new"
        or sorted(spec) != step.get("target_keys")
        or source._replay_digest(spec) != step.get("target_digest")
    ):
        raise BKBaseResourceMappingError(message="Initial Snapshot retry requires a verified Clean create rejection")
    return spec


def retry(snapshot, request_data, pull_handler, pre_check):
    """按原代次显式继续首次启动；结果未知时继续观察原 Ref。"""
    binding = snapshot.bkbase_v4_resources or {}
    operation = binding.get("source_provision") or {}
    if (
        snapshot.status != SnapshotRunningStatus.FAILED
        or operation.get("completed")
        or binding.get("pending_action")
        or (binding.get("source_replay") or {}).get("active")
        or request_data["join_data_type"] != snapshot.join_data_type
        or request_data["pull_type"] != snapshot.pull_type
        or set(request_data["storage_type"]) != set(snapshot.storages.values_list("storage_type", flat=True))
        or request_data.get("custom_config") not in (None, snapshot.custom_config)
    ):
        raise BKBaseResourceMappingError(message="Initial Snapshot retry requires the unchanged failed operation")
    if operation.get("handoff_ready"):
        return snapshot_restore.prepare(snapshot, request_data, pull_handler, pre_check, initial_start=True)
    step = operation.get("clean_step") or {}
    context, params = get_bkbase_context(), pull_handler.config
    expected = _input_digest(snapshot, params, context)
    if step.get("input_digest") != expected:
        raise BKBaseResourceMappingError(message="Initial Snapshot retry inputs changed")
    pre_check()
    steps = {
        kind: {**step, "retry_allowed": True} if step.get("observed") == TaskState.FAILED else step
        for kind, step in operation.get("storage_steps", {}).items()
    }
    patch = {
        "stage": "clean_ready" if binding.get("clean_ready") else "ready",
        "clean_poll_count": 0,
        "storage_steps": steps,
    }
    if step.get("rejection") is not None or step.get("accepted") is False:
        if operation.get("stage") != "clean_failed" or not operation.get("operation_id") or binding.get("clean"):
            raise BKBaseResourceMappingError(message="Initial Snapshot retry requires a failed unbound Clean")
        _rejected_clean_spec(step)
        patch["clean_step"] = {**step, "retry_allowed": True}
    if not _transition(snapshot, operation, patch, verify=(params, context, expected), retry=True):
        raise BKBaseResourceMappingError(message="Initial Snapshot retry was superseded")
    snapshot.refresh_from_db()
    return snapshot


def advance(snapshot, params):
    """接力新 Clean、入库和首次启动；每次写先认领，观察失败独立隔离。"""
    if transaction.get_connection().in_atomic_block:
        raise BKBaseResourceMappingError(message="Snapshot Clean provisioning requires no outer DB transaction")
    try:
        with snapshot_lock(snapshot.system_id, snapshot.resource_type_id):
            snapshot.refresh_from_db()
            binding = snapshot.bkbase_v4_resources or {}
            operation = binding.get("source_provision") or {}
            if (
                snapshot.status != SnapshotRunningStatus.PREPARING
                or operation.get("stage") not in ("ready", "clean_ready")
                or not operation.get("operation_id")
                or operation.get("completed")
                or binding.get("pending_action")
                or (binding.get("source_replay") or {}).get("active")
            ):
                return
            verify = None
            try:
                context = get_bkbase_context()
                expected = _input_digest(snapshot, params, context)
                verify = (params, context, expected)
                step = operation.get("clean_step")
                if step is not None:
                    if not isinstance(step, dict) or step.get("input_digest") != expected:
                        raise BKBaseResourceMappingError(message="Snapshot Clean claim does not match current inputs")
                    ref = source._replay_ref(context, step.get("ref"), "Clean")
                    if ref["namespace"] != context["namespace"] or binding.get("clean") not in (None, ref):
                        raise BKBaseResourceMappingError(message="Snapshot Clean claim does not match its binding")
                current_source = _verify_source(snapshot, params, context, operation)
                if current_source is None:
                    _wait(snapshot, operation, verify)
                elif binding.get("clean_ready"):
                    _advance_storages(snapshot, params, context, operation, verify)
                elif step is not None:
                    with resource_lock(context, ref):
                        if step.get("retry_allowed") is True:
                            _submit(snapshot, context, operation, ref, verify, _rejected_clean_spec(step))
                        else:
                            _observe(snapshot, context, operation, ref, verify)
                else:
                    spec = _build_spec(snapshot, current_source["spec"]["report_config"])
                    ref = clean.new_owner_clean_ref(context, spec["result_table_id"])
                    with resource_lock(context, ref):
                        _submit(snapshot, context, operation, ref, verify, spec)
            except (APIRequestError, ValidateException):
                _wait(snapshot, operation, verify)
            except (CoreException, ImproperlyConfigured, ObjectDoesNotExist, KeyError, TypeError, ValueError) as error:
                message = (
                    error.message
                    if isinstance(error, BKBaseResourceMappingError)
                    else "Snapshot Clean inputs are invalid"
                )
                stage = "clean_ready" if binding.get("clean_ready") else "clean_failed"
                # 输入冲突仍保留原认领，显式重试不能绕过该摘要。
                _transition(snapshot, operation, {"stage": stage}, terminal=str(message))
    except (LockError, Snapshot.DoesNotExist):
        return
