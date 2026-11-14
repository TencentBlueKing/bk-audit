"""处理同步DataSource、个人可见DataID及已有Asset纯重放。

DataSource与DataId分别保存真实引用，避免把同名视为同一资源。
停止声明与任务停稳分开，控制器未就绪的引用不能猜测。
纯重放保存单次写意图，未知写结果仅观察，不自动重发。
"""

import hashlib
import json
import re
import time
import uuid
from copy import deepcopy

from bk_resource import api
from bk_resource.exceptions import APIRequestError, ValidateException
from blueapps.utils.logger import logger
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Q

from apps.meta.models import ResourceType, System
from core.exceptions import LockError
from core.models import get_request_username
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    legacy_call,
    operation_result,
    reference,
    resource_lock,
    resource_params,
    snapshot_lock,
)
from services.web.bkbase.constants import (
    BKBASE_V4_MAX_POLLS,
    BKBASE_V4_PULL_RESULTS_PATH,
    BKBASE_V4_STORAGE_CLUSTER_KINDS,
    BKBaseVersion,
    DataSourceDesiredState,
    TaskState,
)
from services.web.bkbase.exceptions import BKBaseException, BKBaseResourceMappingError
from services.web.bkbase.permissions import require_user
from services.web.databus.constants import JoinDataType, SnapshotRunningStatus
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot

LEGACY_SCENARIO_BY_REPORT_TYPE = {"log_collection": "log", "rest_api": "http"}


def _source_list(payload):
    if not isinstance(payload, list) or not all(isinstance(x, dict) and x.get("kind") == "DataSource" for x in payload):
        raise BKBaseResourceMappingError(message="Expected DataSource ResourceGet array")
    return payload


def list_user_sources(context, *, bk_biz_id=None):
    """按真实用户取列表，业务过滤不能扩大用户可见范围。"""
    request = require_user(context)
    rows = _source_list(api.bk_base_v4.user_data_source_list(**resource_params(context), _request=request))
    if bk_biz_id is not None:
        rows = [r for r in rows if str(r.get("spec", {}).get("basic_info", {}).get("bk_biz_id")) == str(bk_biz_id)]
    return rows


def get_user_source(context, source_ref):
    """详情读取先验证同一用户列表可见性，不借平台查询。"""
    params = resource_params(context, source_ref, kind="DataSource")
    if source_ref not in [reference(r, context, "DataSource") for r in list_user_sources(context)]:
        raise BKBaseResourceMappingError(message="DataSource not in authenticated user scope")
    return api.bk_base_v4.user_data_source_get(**params, _request=require_user(context))


def _positive_raw_data_id(value):
    """只接受平台分配的十进制正整数标签；空值和非法值均不代表就绪。"""
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    return number if number > 0 else None


def _legacy_source(resource):
    spec = resource.get("spec", {})
    info = spec.get("basic_info", {})
    raw_id = _positive_raw_data_id(resource.get("metadata", {}).get("labels", {}).get("raw_data_id"))
    if raw_id is None:
        raise BKBaseResourceMappingError(message="DataSource raw_data_id not ready")
    result = {
        "id": raw_id,
        "raw_data_name": info.get("data_source_name", resource["metadata"]["name"]),
        "raw_data_alias": info.get("data_source_alias", ""),
        "bk_biz_id": info.get("bk_biz_id"),
        "description": info.get("description", ""),
    }
    report = spec.get("report_config")
    report_type = report.get("type") if isinstance(report, dict) else None
    if isinstance(report_type, str) and report_type.strip():
        result["data_scenario"] = LEGACY_SCENARIO_BY_REPORT_TYPE.get(report_type, report_type)
    for key in ("data_encoding",):
        if key in info:
            result[key] = info[key]
    for key in ("created_by", "updated_by", "created_at", "updated_at"):
        if spec.get(key):
            result[key] = spec[key]
    return result


def _source_binding(context, resource, raw_data_id):
    """仅从已查询的当前项目来源提取并校验真实引用。"""
    raw_id = _positive_raw_data_id(str(raw_data_id))
    label = (resource.get("metadata") or {}).get("labels", {}).get("raw_data_id")
    if raw_id is None or _positive_raw_data_id(label) != raw_id:
        raise BKBaseResourceMappingError(message="Invalid or mismatched raw_data_id")
    source_ref = reference(resource, context, "DataSource")
    if source_ref["namespace"] != context["namespace"]:
        raise BKBaseResourceMappingError(message="DataSource is outside the configured project")
    data_id = resource.get("spec", {}).get("data_id") or {}
    if not isinstance(data_id, dict) or data_id.get("kind") not in (None, "DataId"):
        raise BKBaseResourceMappingError(message="Invalid DataId reference")
    data_ref = {
        "kind": "DataId",
        "tenant": data_id.get("tenant", context["tenant"]),
        "namespace": data_id.get("namespace"),
        "name": data_id.get("name"),
    }
    resource_params(context, data_ref, kind="DataId")
    return {"data_source": source_ref, "data_id": data_ref, "source_raw_data_id": raw_id}


def bind_source(owner, binding):
    """保存服务端确认的来源，拒绝覆盖已有的不同 DataId 绑定。"""
    with transaction.atomic():
        current = type(owner).objects.select_for_update().get(pk=owner.pk)
        if isinstance(owner, CollectorPlugin) and any(
            getattr(current, key) != getattr(owner, key) for key in ("collector_plugin_name_en", "bkdata_biz_id")
        ):
            raise BKBaseResourceMappingError(message="Plugin identity changed during source discovery")
        saved = deepcopy(current.bkbase_v4_resources or {})
        keys = ("data_source", "data_id", "source_raw_data_id")
        if "source_bk_biz_id" in binding:
            keys += ("source_bk_biz_id",)
        if not isinstance(saved, dict) or any(
            saved.get(key) is not None and saved[key] != binding[key] for key in keys
        ):
            raise BKBaseResourceMappingError(message="Existing source binding conflicts with selected source")
        saved.update(deepcopy(binding))
        current.bkbase_v4_resources = saved
        current.save(update_fields=["bkbase_v4_resources"])
    owner.bkbase_v4_resources = saved
    return saved


def bound_source_raw_id(context, binding, *, require_ready=False):
    """核实已绑定的同租户来源；新发现绑定按需在同次GET核实就绪。"""
    ref = _replay_ref(context, binding.get("data_source"), "DataSource")
    data_ref = _replay_ref(context, binding.get("data_id"), "DataId")
    raw_id = _replay_raw_id(binding.get("source_raw_data_id"))
    resource = api.bk_base_v4.data_source_get(**resource_params(context, ref, kind="DataSource"))
    if _binding_resource_ref(context, resource, "DataSource") != ref:
        raise BKBaseResourceMappingError(message="Bound source identity changed")
    actual = _source_binding({**context, "namespace": ref["namespace"]}, resource, raw_id)
    if actual["data_source"] != ref or actual["data_id"] != data_ref:
        raise BKBaseResourceMappingError(message="Bound source DataId changed")
    if require_ready and (not isinstance(resource.get("status"), dict) or resource["status"].get("phase") != "Ok"):
        raise BKBaseResourceMappingError(message="Bound plugin DataSource is not ready")
    return raw_id


def verify_native_data_id(context, resource, *, data_ref, raw_data_id):
    """核实显式Native DataId的真实身份及数字ID，不从名称、标签或别名推导。"""
    ref = _replay_ref(context, data_ref, "DataId")
    raw_id = _replay_raw_id(raw_data_id)
    if _binding_resource_ref(context, resource, "DataId") != ref:
        raise BKBaseResourceMappingError(message="Native DataId identity changed")
    predefined = resource["spec"].get("predefined")
    actual = predefined.get("dataId") if isinstance(predefined, dict) else None
    if type(actual) is not int or actual <= 0 or actual != raw_id:
        raise BKBaseResourceMappingError(message="Native DataId requires matching spec.predefined.dataId")
    return raw_id


def bound_plugin_raw_id(context, binding, *, bk_biz_id=None):
    """插件显式绑定可直接引用Native DataId，已有Source键始终沿用完整Source核验。"""
    if "data_source" in binding:
        raw_id = bound_source_raw_id(context, binding, require_ready="source_bk_biz_id" in binding)
        if "source_bk_biz_id" in binding:
            saved_biz = _positive_raw_data_id(str(binding["source_bk_biz_id"]))
            if saved_biz is None or _positive_raw_data_id(str(bk_biz_id)) != saved_biz:
                raise BKBaseResourceMappingError(message="Plugin business conflicts with its verified source binding")
            _verify_plugin_data_id(context, binding["data_id"], raw_id=raw_id, bk_biz_id=saved_biz)
        return raw_id
    ref = _replay_ref(context, binding.get("data_id"), "DataId")
    raw_id = _replay_raw_id(binding.get("source_raw_data_id"))
    params = resource_params(context, ref, kind="DataId")
    params.pop("tenant")
    resource = api.bk_base_v4.data_id_get(**params)
    return verify_native_data_id(context, resource, data_ref=ref, raw_data_id=raw_id)


def get_my_rawdata_list(**params):
    """维持原列表分页外观；V4原生列表由审计分页。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_my_rawdata_list(**params)
    context = get_bkbase_context(user=get_request_username())
    rows = [
        _legacy_source(r)
        for r in list_user_sources(context, bk_biz_id=params.get("bk_biz_id"))
        if _positive_raw_data_id(r.get("metadata", {}).get("labels", {}).get("raw_data_id")) is not None
    ]
    size = int(params.get("page_size", 100))
    start = (int(params.get("page", 1)) - 1) * size
    return {"count": len(rows), "results": rows[start : start + size]}


def get_my_rawdata_list_bulk(requests):
    """V3保留SDK并发，V4个人上下文在当前线程顺序处理。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_my_rawdata_list.bulk_request(requests)
    return [get_my_rawdata_list(**params) for params in requests]


def _get_user_source_by_raw_id(bk_data_id):
    """读取真实用户唯一可见的来源并再次核对返回身份。"""
    context = get_bkbase_context(user=get_request_username())
    raw_id = _positive_raw_data_id(str(bk_data_id))
    if raw_id is None:
        raise BKBaseResourceMappingError(message="Invalid raw_data_id")
    rows = [
        row
        for row in list_user_sources(context)
        if _positive_raw_data_id(row.get("metadata", {}).get("labels", {}).get("raw_data_id")) == raw_id
    ]
    if len(rows) != 1:
        raise BKBaseResourceMappingError(message="User DataSource missing or ambiguous")
    ref = reference(rows[0], context, "DataSource")
    native = get_user_source(context, ref)
    if (
        reference(native, context, "DataSource") != ref
        or _positive_raw_data_id(native.get("metadata", {}).get("labels", {}).get("raw_data_id")) != raw_id
    ):
        raise BKBaseResourceMappingError(message="DataSource detail does not match selected identity")
    return context, native


def get_rawdata_detail(*, bk_data_id):
    """按当前用户可见DataID唯一匹配详情。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_rawdata_detail(bk_data_id=bk_data_id)
    _, native = _get_user_source_by_raw_id(bk_data_id)
    return _legacy_source(native)


def get_user_source_for_apply(*, bk_data_id):
    """从同一次已校验的正式GET取得接入机制与绑定。"""
    context, native = _get_user_source_by_raw_id(bk_data_id)
    return _legacy_source(native), _source_binding(context, native, bk_data_id)


def resolve_synced_source(context, collector, *, raw_data_id=None):
    """唯一定位BKLog同步资源并保存实际DataId关联，不重复创建源。"""
    raw_id = (
        raw_data_id
        if raw_data_id is not None
        else (getattr(collector, "bk_data_id", None) or getattr(collector, "bkbase_data_id", None))
    )
    if isinstance(raw_id, bool) or _positive_raw_data_id(str(raw_id)) is None:
        raise BKBaseResourceMappingError(message="Invalid synced raw DataID")
    rows = _source_list(
        api.bk_base_v4.data_source_list(**resource_params(context), label_selector=f"raw_data_id={raw_id}")
    )
    matches = [r for r in rows if str(r.get("metadata", {}).get("labels", {}).get("raw_data_id")) == str(raw_id)]
    if len(matches) != 1:
        raise BKBaseResourceMappingError()
    return bind_source(collector, _source_binding(context, matches[0], raw_id))


def _source_desires_stopped(resource):
    """仅归一观测值；写入使用DataSource的期望态枚举。"""
    desired = resource.get("spec", {}).get("desired_status")
    return isinstance(desired, str) and desired.lower() == TaskState.STOPPED


def stop_source(context, source_ref):
    """GET后全量PUT期望停止，保留其他配置，实际态单独返回。"""
    params = resource_params(context, source_ref, kind="DataSource")
    with resource_lock(context, source_ref):
        old = api.bk_base_v4.data_source_get(**params)
        if _source_desires_stopped(old):
            return operation_result(old, source_ref, "stop")
        payload = deepcopy(old)
        payload["spec"]["desired_status"] = DataSourceDesiredState.STOPPED
        result = api.bk_base_v4.data_source_update(
            **params, metadata=payload["metadata"], spec=payload["spec"], status=None
        )
    observed = operation_result(result, source_ref, "stop")
    if observed["task_state"] != TaskState.FAILED:
        # PUT只确认期望态已提交；旧current_status不能证明本次停止已调和。
        observed["task_state"] = None
    return observed


def stop_snapshot(snapshot, params, *, multiple_storage=False):
    """V4先持久化停止意图；只在事务外提交请求并按token回写。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        stop_collector(**params)
        stopped = True
        if stopped and not multiple_storage:
            snapshot.status = SnapshotRunningStatus.CLOSED
            snapshot.save(update_fields=["status"])
        return stopped
    context = get_bkbase_context()
    ref = _replay_ref(context, (snapshot.bkbase_v4_resources or {}).get("data_source"), "DataSource")
    with snapshot_lock(snapshot.system_id, snapshot.resource_type_id):
        with transaction.atomic():
            latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
            binding = deepcopy(latest.bkbase_v4_resources or {})
            maintenance = binding.get("asset_etl_maintenance") or {} if isinstance(binding, dict) else None
            if not isinstance(maintenance, dict) or maintenance.get("active"):
                raise BKBaseResourceMappingError(message="Asset maintenance is still active")
            replay = binding.get("source_replay") or {}
            if (
                latest.status == SnapshotRunningStatus.PREPARING
                or not isinstance(replay, dict)
                or replay.get("active")
                or replay.get("outcome_unknown")
            ):
                raise BKBaseResourceMappingError(message="Snapshot source replay is still active or unresolved")
            if binding.get("data_source") != ref:
                raise BKBaseResourceMappingError(message="Snapshot DataSource binding changed")
            if binding.get("pending_action"):
                return False
            token = uuid.uuid4().hex
            status_at_claim = latest.status
            binding.update(pending_action="stop", source_stop_token=token, source_poll_count=0, source_message="")
            latest.bkbase_v4_resources = binding
            latest.save(update_fields=["bkbase_v4_resources"])
        result = stop_source(context, ref)
        stopped = result["task_state"] == TaskState.STOPPED
        failed = result["task_state"] == TaskState.FAILED
        with transaction.atomic():
            latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
            binding = deepcopy(latest.bkbase_v4_resources or {})
            if (
                latest.status != status_at_claim
                or binding.get("source_stop_token") != token
                or binding.get("pending_action") != "stop"
                or binding.get("data_source") != ref
                or (binding.get("asset_etl_maintenance") or {}).get("active")
            ):
                return False
            binding.update(
                source_message=result.get("message", ""), pending_action=None if stopped or failed else "stop"
            )
            latest.bkbase_v4_resources = binding
            updates = ["bkbase_v4_resources"]
            if failed:
                latest.status = SnapshotRunningStatus.FAILED
                latest.status_msg = result.get("message", "")
                updates.extend(["status", "status_msg"])
            elif stopped and not multiple_storage:
                latest.status = SnapshotRunningStatus.CLOSED
                updates.append("status")
            latest.save(update_fields=updates)
        snapshot.refresh_from_db()
        return stopped


def poll_source_operations():
    """按快照锁观察停止；旧回包不能覆盖新的停止意图。"""
    if get_bkbase_version() != BKBaseVersion.V4:
        return
    context = get_bkbase_context()
    for candidate in Snapshot.objects.filter(bkbase_v4_resources__pending_action="stop"):
        try:
            with snapshot_lock(candidate.system_id, candidate.resource_type_id):
                snapshot = Snapshot.objects.filter(pk=candidate.pk).first()
                if snapshot is None:
                    continue
                binding = snapshot.bkbase_v4_resources or {}
                maintenance = binding.get("asset_etl_maintenance") or {}
                if (
                    not isinstance(maintenance, dict)
                    or maintenance.get("active")
                    or binding.get("pending_action") != "stop"
                ):
                    continue
                ref, token = binding.get("data_source"), binding.get("source_stop_token")
                observed_status = snapshot.status
                count = binding.get("source_poll_count", 0) + 1
                message, state, desired_stopped = "", None, False
                try:
                    current = api.bk_base_v4.data_source_get(**resource_params(context, ref, kind="DataSource"))
                    observed = operation_result(current, ref, "stop")
                    state, message = observed["task_state"], observed["message"]
                    desired_stopped = _source_desires_stopped(current)
                except (APIRequestError, BKBaseException, LockError) as error:
                    message = str(error)
                    logger.exception("BKBase V4 DataSource observation failed: %s", snapshot.pk)
                done = desired_stopped and state == TaskState.STOPPED
                failed = state == TaskState.FAILED or count >= BKBASE_V4_MAX_POLLS
                if count >= BKBASE_V4_MAX_POLLS and not done:
                    message = "DataSource stop timed out: " + message
                with transaction.atomic():
                    latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
                    current_binding = deepcopy(latest.bkbase_v4_resources or {})
                    current_maintenance = current_binding.get("asset_etl_maintenance") or {}
                    if (
                        latest.status != observed_status
                        or current_binding.get("pending_action") != "stop"
                        or current_binding.get("source_stop_token") != token
                        or current_binding.get("data_source") != ref
                        or not isinstance(current_maintenance, dict)
                        or current_maintenance.get("active")
                    ):
                        continue
                    current_binding.update(
                        source_poll_count=count,
                        source_message=message,
                        pending_action=None if done or failed else "stop",
                    )
                    latest.bkbase_v4_resources = current_binding
                    fields = ["bkbase_v4_resources"]
                    if done or failed:
                        latest.status = SnapshotRunningStatus.CLOSED if done else SnapshotRunningStatus.FAILED
                        latest.status_msg = message
                        fields.extend(["status", "status_msg"])
                    latest.save(update_fields=fields)
        except LockError:
            continue


def tail_source(context, data_id_ref):
    """取样使用DataId；把V4原文数组还原为审计value结构，不推断topic或时间。"""
    params = resource_params(context, data_id_ref, kind="DataId")
    result = api.bk_base_v4.data_id_tail(namespace=params["namespace"], name=params["name"])
    if not isinstance(result, list) or not all(isinstance(value, str) for value in result):
        raise BKBaseResourceMappingError(message="Unsupported Kafka sample response")
    return [{"value": value} for value in result]


def _replay_digest(value):
    """只持久化摘要，避免记录连接认证信息。"""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _source_intent_inputs(value):
    """V4 不提交源敏感级别；保留其余配置参与意图校验。"""
    result = deepcopy(value)
    if isinstance(result, dict):
        result.pop("sensitivity", None)
        if isinstance(result.get("access_raw_data"), dict):
            result["access_raw_data"].pop("sensitivity", None)
    return result


def _replay_ref(context, value, kind):
    """只接受完整单资源引用，不从数字或展示名推导。"""
    if not isinstance(value, dict):
        raise BKBaseResourceMappingError(message="Replay requires explicit resource bindings")
    return {"kind": kind, **resource_params(context, value, kind=kind)}


def _replay_raw_id(value):
    """仅归一正整数ID及其十进制文本，布尔值和未知类型不能充当身份。"""
    if isinstance(value, bool) or not (
        isinstance(value, int) or isinstance(value, str) and value.isascii() and value.isdecimal()
    ):
        raise BKBaseResourceMappingError(message="Replay requires a positive numeric raw DataID")
    value = int(value)
    if value <= 0:
        raise BKBaseResourceMappingError(message="Replay requires a positive numeric raw DataID")
    return value


def _snapshot_processing_id(snapshot):
    """完整 V4 绑定可无旧 PID；已有旧 PID 必须合法，不能推算或补写。"""
    value = snapshot.bkbase_processing_id
    if value is None or value == "":
        return None
    if not isinstance(value, str) or any(char.isspace() or char in ",=" for char in value):
        raise BKBaseResourceMappingError(message="Invalid Snapshot legacy processing identity")
    return value


def _snapshot_clean_identity_matches(snapshot, resource):
    """已知旧 PID 严格比对；缺省 raw/结果表标签允许，既存标签不能冲突。"""
    processing_id = _snapshot_processing_id(snapshot)
    labels = resource["metadata"].get("labels", {})
    if not isinstance(labels, dict):
        return False
    expected = {"raw_data_id": str(snapshot.bkbase_data_id), "result_table_id": snapshot.bkbase_table_id}
    return (processing_id is None or labels.get("processing_id") == processing_id) and all(
        key not in labels or (isinstance(labels[key], str) and labels[key] == value) for key, value in expected.items()
    )


def _replay_inputs(snapshot, params, context, *, legacy=False, restore=False):
    """校验本地纯重放前置，摘要覆盖配置、绑定和全部存储集合。"""
    binding = snapshot.bkbase_v4_resources or {}
    if not isinstance(binding, dict):
        raise BKBaseResourceMappingError(message="Replay bindings must be an object")
    if (
        snapshot.join_data_type not in (JoinDataType.ASSET, JoinDataType.BASIC)
        or not snapshot.bkbase_data_id
        or binding.get("pending_action")
    ):
        raise BKBaseResourceMappingError(message="Replay requires an existing Asset or Basic without another operation")
    basic = snapshot.join_data_type == JoinDataType.BASIC
    if basic or restore:
        _snapshot_processing_id(snapshot)
        if binding.get("clean_pending_create"):
            raise BKBaseResourceMappingError(message="Snapshot Clean has an unresolved creation")
    if (basic or restore) and (
        context["tenant"] != "default"
        or binding.get("clean_role") not in ("owner", "existing")
        or any(
            not isinstance(value, str) or not value or any(c.isspace() or c in ",=" for c in value)
            for value in (snapshot.bkbase_table_id,)
        )
        or snapshot.bkbase_table_id != binding.get("result_table_id")
    ):
        raise BKBaseResourceMappingError(
            message="Snapshot maintenance requires verified default-tenant identity and explicit role"
        )
    raw_id = _replay_raw_id(snapshot.bkbase_data_id)
    if "raw_data_id" in binding and _replay_raw_id(binding["raw_data_id"]) != raw_id:
        raise BKBaseResourceMappingError(message="Replay snapshot and binding raw DataID conflict")
    if basic and not restore and Snapshot.objects.filter(bkbase_data_id=raw_id).exclude(pk=snapshot.pk).exists():
        raise BKBaseResourceMappingError(
            message="Basic Source is shared by another local Snapshot; source-only impact is not verified"
        )
    for key, kind in (
        ("data_source", "DataSource"),
        ("data_id", "DataId"),
        ("clean", "Clean"),
        ("result_table", "ResultTable"),
    ):
        _replay_ref(context, binding.get(key), kind)
        if basic and key in ("data_source", "clean") and binding[key]["namespace"] != context["namespace"]:
            raise BKBaseResourceMappingError(message="Basic Source and Clean require the configured trusted project")
    storages = dict(snapshot.storages.values_list("storage_type", "status"))
    if not storages or (not restore and any(state != SnapshotRunningStatus.RUNNING for state in storages.values())):
        raise BKBaseResourceMappingError(message="Replay cannot provision or recover snapshot storage")
    if not isinstance(binding.get("storages"), dict) or set(storages) != set(binding["storages"]):
        raise BKBaseResourceMappingError(message="Replay bindings must cover every required storage")
    for ref in binding["storages"].values():
        _replay_ref(context, ref, "DataStorage")
        if basic and ref["namespace"] != context["namespace"]:
            raise BKBaseResourceMappingError(message="Basic storage task project has not been verified")
    if not isinstance(binding.get("result_table_id"), str) or not binding["result_table_id"]:
        raise BKBaseResourceMappingError(message="Replay requires the verified logical result table ID")
    system = (
        System.objects.filter(system_id=snapshot.system_id).values("callback_url", "auth_token", "namespace").first()
    )
    resource_type = (
        ResourceType.objects.filter(system_id=snapshot.system_id, resource_type_id=snapshot.resource_type_id)
        .values("path")
        .first()
    )
    if system is None or resource_type is None:
        raise BKBaseResourceMappingError(message="Replay source configuration no longer exists")
    return _replay_digest(
        {
            "params": params if legacy else _source_intent_inputs(params),
            "pull_type": snapshot.pull_type,
            "pull_config": snapshot.pull_config if legacy else _source_intent_inputs(snapshot.pull_config),
            "custom_config": snapshot.custom_config,
            "raw_id": snapshot.bkbase_data_id,
            **({"legacy_ids": [snapshot.bkbase_processing_id, snapshot.bkbase_table_id]} if basic or restore else {}),
            **({"join_data_type": snapshot.join_data_type, "data_conn": binding.get("data_conn")} if restore else {}),
            "storages": sorted(storages),
            "bindings": {
                key: binding.get(key)
                for key in (
                    "data_source",
                    "data_id",
                    "raw_data_id",
                    "clean",
                    "clean_role",
                    "result_table_id",
                    "result_table",
                    "storages",
                )
            },
            "local_source": {"system": system, "resource_type": resource_type},
        }
    )


def _replay_resource(context, ref, kind, endpoint):
    """GET并核对实际资源身份；不接受不完整的返回元信息。"""
    ref = _replay_ref(context, ref, kind)
    value = endpoint(**resource_params(context, ref, kind=kind))
    if not isinstance(value, dict) or value.get("kind") != kind:
        raise BKBaseResourceMappingError(message="Replay resource kind mismatch")
    actual = {
        "kind": value["kind"],
        **{key: value.get("metadata", {}).get(key) for key in ("tenant", "namespace", "name")},
    }
    if actual != ref:
        raise BKBaseResourceMappingError(message="Replay resource identity mismatch")
    return value


def _replay_input_matches(snapshot, params, context, expected):
    """兼容升级前持久化的摘要；旧摘要只能在原输入未变时继续。"""
    return (
        _replay_inputs(snapshot, params, context) == expected
        or _replay_inputs(snapshot, params, context, legacy=True) == expected
    )


def _replay_resource_digest(value):
    """排除观测值及已证实的Source更新时间，保留业务配置和注解。"""
    ignored = {"current_status"}
    if value.get("kind") == "DataSource":
        # 正式PUT会更新这个顶层审计字段；report_config内同名业务字段仍须比较。
        ignored.update(("updated_at", "updated_by"))
    spec = {key: val for key, val in value["spec"].items() if key not in ignored}
    return _replay_digest({"spec": spec, "annotations": value["metadata"].get("annotations", {})})


def pull_connection_digest(resource, *, public=False):
    """连接摘要保留配置和标签，公开目标允许平台加密 Authorization。"""
    normalized = deepcopy(resource)
    for field in ("updated_at", "updated_by"):
        normalized["spec"].pop(field, None)
    if public:
        normalized["spec"]["conn_info"]["headers"].pop("Authorization", None)
        normalized["metadata"].get("annotations", {}).pop("conn_info_encrypted", None)
    return _replay_digest([_replay_resource_digest(normalized), normalized["metadata"].get("labels", {})])


def accepted_pull_connection_digest(context, ref, result, desired, public_target):
    """核对正式 DataConn 受理回执，返回后续独立 GET 使用的密文摘要。"""
    try:
        result = {"kind": "DataConn", **result}
        submitted_auth = desired["spec"]["conn_info"]["headers"].get("Authorization")
        saved_auth = result["spec"]["conn_info"]["headers"].get("Authorization")
        if (
            result["status"].get("phase") == "Pending"
            and _binding_resource_ref(context, result, "DataConn") == ref
            and pull_connection_digest(result, public=True) == public_target
            and (
                not submitted_auth
                or (
                    isinstance(saved_auth, str)
                    and bool(saved_auth)
                    and result["metadata"].get("annotations", {}).get("conn_info_encrypted") == "true"
                )
            )
        ):
            return pull_connection_digest(result)
    except (AttributeError, KeyError, TypeError, BKBaseResourceMappingError):
        pass
    return None


def check_pull_connection_writer(snapshot, context, conn_ref):
    """确认独占连接归属，Basic 必须有本应用自建记录。"""
    binding = snapshot.bkbase_v4_resources
    source_ref = binding["data_source"]
    provision = binding.get("source_provision") or {}
    if not isinstance(provision, dict) or conn_ref["namespace"] != source_ref["namespace"]:
        raise BKBaseResourceMappingError(message="Callback update requires matching DataSource and DataConn scope")
    if snapshot.join_data_type == JoinDataType.BASIC:
        if (
            source_ref["namespace"] != context["namespace"]
            or not isinstance(provision.get("operation_id"), str)
            or not provision["operation_id"]
            or provision.get("stage") not in ("ready", "clean_ready")
            or provision.get("source_name") != source_ref["name"]
            or provision.get("conn_name") != conn_ref["name"]
            or provision.get("accepted_source") != source_ref
            or binding.get("data_conn", conn_ref) != conn_ref
        ):
            raise BKBaseResourceMappingError(message="Callback update requires a verified exclusive Basic DataConn")
    elif snapshot.join_data_type != JoinDataType.ASSET or binding["clean_role"] != "owner":
        raise BKBaseResourceMappingError(message="Callback update requires an exclusive Asset DataConn")
    elif provision.get("stage") == "ready" and (
        provision.get("conn_name") != conn_ref["name"] or provision.get("accepted_source") != source_ref
    ):
        raise BKBaseResourceMappingError(message="Asset DataConn provisioning identity conflicts")
    identity_keys = ("tenant", "namespace", "name")
    claimed = Q(**{f"bkbase_v4_resources__data_conn__{key}": conn_ref[key] for key in identity_keys})
    if snapshot.join_data_type == JoinDataType.BASIC:
        claimed |= Q(**{f"bkbase_v4_resources__data_source__{key}": source_ref[key] for key in identity_keys})
    provisioned = Q(
        bkbase_v4_resources__source_provision__conn_name=conn_ref["name"],
        bkbase_v4_resources__data_source__namespace=conn_ref["namespace"],
        bkbase_v4_resources__data_source__tenant=conn_ref["tenant"],
    )
    if (
        Snapshot.objects.filter(claimed | provisioned).exclude(pk=snapshot.pk).exists()
        or CollectorConfig.objects.filter(claimed).exists()
        or CollectorPlugin.objects.filter(claimed).exists()
    ):
        raise BKBaseResourceMappingError(message="DataConn has another local writer")


def _configured_pull_connection(snapshot, connection, params):
    """使用当前系统配置，保留GET返回的其余完整字段。

    Authorization来自系统可信配置，明文相同则平台沿用原密文，变化则重新加密。
    不用占位符替换密码，也不从连接名猜测Source或项目。
    """
    desired = deepcopy(connection)
    try:
        (scope,) = params["access_conf_info"]["resource"]["scope"]
        conn = desired["spec"]["conn_info"]
        if conn["type"] != "rest_api" or not isinstance(scope["headers"], dict):
            raise BKBaseResourceMappingError(message="PULL maintenance requires a REST API connection")
        base = System.objects.get(system_id=snapshot.system_id).callback_url.rstrip("/")
        if not base or not scope["url"].startswith(base + "/"):
            raise BKBaseResourceMappingError(message="PULL endpoint does not match the current system callback URL")
        headers = deepcopy(conn.get("headers") or {})
        if not isinstance(headers, dict):
            raise BKBaseResourceMappingError(message="Invalid existing REST API headers")
        headers.update(scope["headers"])
        conn.update(url=base, headers=headers)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise BKBaseResourceMappingError(message="Incomplete PULL connection configuration") from error
    return desired


def _pull_headers_match(expected, connection, *, preserve_encrypted_auth=False):
    """只对正式标记的 Authorization 密文允许沿用已保存值。"""
    headers = connection["spec"]["conn_info"]["headers"]
    auth = headers.get("Authorization")
    keep_ciphertext = (
        preserve_encrypted_auth
        and connection["metadata"].get("annotations", {}).get("conn_info_encrypted") == "true"
        and isinstance(auth, str)
        and bool(auth)
    )
    return all(
        (key == "Authorization" and keep_ciphertext) or headers.get(key) == value for key, value in expected.items()
    )


def _configured_pull_source(current, connection, params, *, preserve_encrypted_auth=False):
    """维护Source明确字段；connection为已核验的目标连接配置。

    旧delay已废弃，忽略占位且不映射到V4。
    """
    try:
        (scope,) = params["access_conf_info"]["resource"]["scope"]
        body, conn = scope["body"], connection["spec"]["conn_info"]
        base = conn["url"]
        report = current["spec"]["report_config"]
        if conn["type"] != "rest_api" or not _pull_headers_match(
            scope["headers"], connection, preserve_encrypted_auth=preserve_encrypted_auth
        ):
            raise BKBaseResourceMappingError(
                message="DataConn authentication changes require exclusive ownership and secret contracts"
            )
        if not isinstance(base, str) or not base or not scope["url"].startswith(base.rstrip("/") + "/"):
            raise BKBaseResourceMappingError(
                message="DataConn base URL changes require an exclusive ownership contract"
            )
        old_path = report["path"]
        if not isinstance(old_path, str):
            raise BKBaseResourceMappingError(message="Existing PULL path is not defined")
        if scope["url"] != base + old_path and any(c in scope["url"] or c in base for c in "?#%"):
            raise BKBaseResourceMappingError(message="PULL query or encoded URL changes require an explicit mapping")
        path = old_path if scope["url"] == base + old_path else scope["url"][len(base) :]
        if base + path != scope["url"]:
            raise BKBaseResourceMappingError(message="PULL path does not reproduce the exact requested URL")
        period = params["access_conf_info"]["collection_model"]["period"]
        page = body["page"]
        if (
            not isinstance(period, int)
            or isinstance(period, bool)
            or period <= 0
            or not isinstance(page["limit"], int)
            or isinstance(page["limit"], bool)
            or page["limit"] <= 0
            or not isinstance(body["content"], str)
            or page["total_path"] != ".data.count"
        ):
            raise BKBaseResourceMappingError(message="Unsupported PULL period, pagination or body")
        desired = deepcopy(current)
        report = desired["spec"]["report_config"]
        if report["type"] != "rest_api" or report["http_mode"] != "PULL" or report["increment_field"]["type"] != "time":
            raise BKBaseResourceMappingError(
                message="Configuration maintenance requires an existing time-based HTTP PULL"
            )
        report.update(
            path=path,
            method=scope["method"].lower(),
            body=body["content"],
            period=period,
            period_unit="minute",
        )
        report["increment_field"]["time_format"] = "Unix Time Stamp(milliseconds)"
        pagination = report["pagination"]
        if not isinstance(pagination.get("total_path"), str) or not pagination["total_path"]:
            raise BKBaseResourceMappingError(message="Existing V4 pagination path is not defined")
        # 旧调用者固定的.data.count不是可编辑选项；保留V4原始拼写，不猜路径语法转换。
        pagination.update(start_offset=page["start_offset"], limit=page["limit"])
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise BKBaseResourceMappingError(message="Incomplete existing PULL configuration") from error
    return desired


def _set_pull_replay_history(report_config):
    """在单次Source配置提交中保留其余参数并请求从历史起点重放。"""
    report_config["increment_field"]["time_format"] = "Unix Time Stamp(milliseconds)"
    history = report_config.get("history_data")
    if history is None:
        history = {}
    if not isinstance(history, dict):
        raise BKBaseResourceMappingError(message="Replay history configuration must be an object")
    history["start_time"] = "0"
    report_config["history_data"] = history


def _validate_replay_pull(params, spec, connection, *, preserve_encrypted_auth=False):
    """验证现有PULL连接与采集配置，供只改变生命周期的快照操作复用。"""
    try:
        (scope,) = params["access_conf_info"]["resource"]["scope"]
        body, report, conn = scope["body"], spec["report_config"], connection["spec"]["conn_info"]
        base, path, page, expected_page = conn["url"], report["path"], report["pagination"], body["page"]
        valid = (
            report["type"] == "rest_api"
            and report["http_mode"] == "PULL"
            and conn["type"] == "rest_api"
            and report["data_conn_name"] == spec["data_conn"]["name"]
            and base + path == scope["url"] == base.rstrip("/") + "/" + path.lstrip("/")
            and _pull_headers_match(scope["headers"], connection, preserve_encrypted_auth=preserve_encrypted_auth)
            and report["method"].lower() == scope["method"].lower() == "post"
            and report["body"] == body["content"]
            and report["increment_field"]["type"] == "time"
            and body["time"]["enabled"] is True
            and body["time"]["format"] == "Unix Time Stamp(milliseconds)"
            and report["period"] == params["access_conf_info"]["collection_model"]["period"]
            and report["period_unit"] == "minute"
            and expected_page["enabled"] is True
            and page["start_offset"] == expected_page["start_offset"]
            and page["limit"] == expected_page["limit"]
            and page["total_path"].lstrip(".") == expected_page["total_path"].lstrip(".")
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        valid = False
    if not valid:
        raise BKBaseResourceMappingError(message="Replay cannot change the existing PULL endpoint or configuration")


def _configured_pull_mode(current, connection, params):
    """仅更新模式决定的请求体和周期，沿用已绑定连接与请求路径。"""
    desired = deepcopy(current)
    config = params["access_conf_info"]
    (scope,) = config["resource"]["scope"]
    desired["spec"]["report_config"].update(body=scope["body"]["content"], period=config["collection_model"]["period"])
    _validate_replay_pull(params, desired["spec"], connection, preserve_encrypted_auth=True)
    return desired


def _configure_replay_pull(snapshot, params, context, current, connection, conn_ref):
    """Basic 无独占连接时只允许原连接可直接表达的 Source 配置。"""
    desired_connection = _configured_pull_connection(snapshot, connection, params)
    if desired_connection != connection:
        try:
            check_pull_connection_writer(snapshot, context, conn_ref)
        except BKBaseResourceMappingError as ownership_error:
            if snapshot.join_data_type != JoinDataType.BASIC:
                raise
            try:
                return _configured_pull_source(current, connection, params, preserve_encrypted_auth=True), connection
            except BKBaseResourceMappingError:
                raise ownership_error
    return _configured_pull_source(current, desired_connection, params), desired_connection


def _replay_preflight(snapshot, params, context, *, observing=False, configure=False, source_only=False):
    """读取最新连接与下游，构造 Source 及独占 DataConn 的完整 PUT。"""
    binding = snapshot.bkbase_v4_resources
    current = _replay_resource(context, binding["data_source"], "DataSource", api.bk_base_v4.data_source_get)
    spec = current["spec"]
    if _replay_ref(context, spec.get("data_id"), "DataId") != _replay_ref(context, binding["data_id"], "DataId"):
        raise BKBaseResourceMappingError(message="Replay source DataId mismatch")
    conn_ref = _replay_ref(context, spec.get("data_conn"), "DataConn")
    connection = _replay_resource(context, conn_ref, "DataConn", api.bk_base_v4.data_conn_get)
    if not isinstance(connection.get("status"), dict):
        raise BKBaseResourceMappingError(message="DataConn observation status is unavailable")
    actual_connection = connection
    actual = current
    if source_only:
        if connection.get("status", {}).get("phase") != "Ok":
            raise BKBaseResourceMappingError(message="PULL mode update requires a ready existing DataConn")
        current = _configured_pull_mode(current, connection, params)
    else:
        if configure:
            current, connection = _configure_replay_pull(snapshot, params, context, current, connection, conn_ref)
        _validate_replay_pull(
            params,
            current["spec"],
            connection,
            # 仅沿用本次正式 GET 的原连接时保留密文；改写连接仍校验目标明文凭据。
            preserve_encrypted_auth=connection is actual_connection,
        )
    spec = current["spec"]
    if str(spec.get("desired_status")).lower() != TaskState.RUNNING:
        raise BKBaseResourceMappingError(message="Replay requires an existing running source")
    clean = _replay_resource(context, binding["clean"], "Clean", api.bk_base_v4.clean_get)
    clean_spec = clean["spec"]
    raw_id = _replay_raw_id(snapshot.bkbase_data_id)
    source_raw_id = current["metadata"].get("labels", {}).get("raw_data_id")
    basic = snapshot.join_data_type == JoinDataType.BASIC
    role = clean_spec.get("result_table_source") if basic else clean_spec.get("result_table_source", "new")
    if (
        _replay_raw_id(clean_spec.get("raw_data_id")) != raw_id
        or (source_raw_id is not None and _replay_raw_id(source_raw_id) != raw_id)
        or _replay_ref(context, clean_spec.get("data_id"), "DataId")
        != _replay_ref(context, binding["data_id"], "DataId")
        or clean_spec.get("result_table_id") != binding["result_table_id"]
        or role != {"owner": "new", "existing": "existing"}.get(binding.get("clean_role"))
        or (basic and (source_raw_id is None or not _snapshot_clean_identity_matches(snapshot, clean)))
        or operation_result(clean, binding["clean"], "observe")["task_state"] != TaskState.RUNNING
        or str(clean_spec.get("desired_status") if basic else clean_spec.get("desired_status", "running")).lower()
        != TaskState.RUNNING
        or clean_spec.get("config_revision") != clean_spec.get("deploy_revision")
    ):
        raise BKBaseResourceMappingError(
            message="Replay requires an existing running Clean with matching input and output"
        )
    baseline = {"connection": _replay_resource_digest(actual_connection), "clean": _replay_resource_digest(clean)}
    if basic:
        for key, kind, endpoint in (
            ("data_id", "DataId", api.bk_base_v4.data_id_get),
            ("result_table", "ResultTable", api.bk_base_v4.result_table_resource_get),
        ):
            ref = binding[key]
            value = endpoint(namespace=ref["namespace"], name=ref["name"])
            if _binding_resource_ref(context, value, kind) != ref:
                raise BKBaseResourceMappingError(message="Basic resource does not match existing formal identity")
            if (
                key == "result_table"
                and value["metadata"].get("labels", {}).get("result_table_id") != snapshot.bkbase_table_id
            ):
                raise BKBaseResourceMappingError(message="Basic ResultTable does not match legacy logical identity")
            baseline[key] = _replay_resource_digest(value)
    for storage_type, ref in binding["storages"].items():
        value = _replay_resource(context, ref, "DataStorage", api.bk_base_v4.data_storage_get)
        if basic:
            _binding_resource_ref(context, value, "DataStorage")
            logical_ids = [
                container["result_table_id"]
                for container in (value["metadata"].get("labels", {}), value["metadata"].get("annotations", {}))
                if "result_table_id" in container
            ]
            if not logical_ids or any(logical_id != snapshot.bkbase_table_id for logical_id in logical_ids):
                raise BKBaseResourceMappingError(message="Basic storage logical ResultTable identity mismatch")
        table = value["spec"].get("tableInfo", {})
        kind = BKBASE_V4_STORAGE_CLUSTER_KINDS.get(storage_type)
        if (
            not kind
            or _replay_ref(context, table.get("source"), "ResultTable")
            != _replay_ref(context, binding["result_table"], "ResultTable")
            or operation_result(value, ref, "observe")["task_state"] != TaskState.RUNNING
        ):
            raise BKBaseResourceMappingError(message="Replay requires every existing storage to remain running")
        _replay_ref(context, table.get("storage"), kind)
        baseline[storage_type] = _replay_resource_digest(value)
    if (
        not observing
        and operation_result(current, binding["data_source"], "observe")["task_state"] != TaskState.RUNNING
    ):
        raise BKBaseResourceMappingError(message="Replay requires an existing running source")
    desired = deepcopy(current)
    _set_pull_replay_history(desired["spec"]["report_config"])
    changed_connection = connection if connection != actual_connection else None
    return actual, desired, baseline, changed_connection, actual_connection


def _binding_snapshot_digest(snapshot, *, locked=False, exclude_bindings=False):
    """覆盖绑定摄入期间不能漂移的旧锚点、配置、存储集合与操作意图。"""
    systems = System.objects
    resource_types = ResourceType.objects
    storages = snapshot.storages
    if locked:
        systems = systems.select_for_update()
        resource_types = resource_types.select_for_update()
        storages = storages.select_for_update()
    system = systems.filter(system_id=snapshot.system_id).values("callback_url", "auth_token", "namespace").first()
    resource_type = (
        resource_types.filter(system_id=snapshot.system_id, resource_type_id=snapshot.resource_type_id)
        .values("path")
        .first()
    )
    if system is None or resource_type is None:
        raise BKBaseResourceMappingError(message="Snapshot configuration no longer exists")
    context = get_bkbase_context()
    return _replay_digest(
        {
            "snapshot": {
                key: _source_intent_inputs(getattr(snapshot, key)) if key == "pull_config" else getattr(snapshot, key)
                for key in (
                    "system_id",
                    "resource_type_id",
                    "status",
                    "join_data_type",
                    "bkbase_data_id",
                    "bkbase_processing_id",
                    "bkbase_table_id",
                    "pull_type",
                    "pull_config",
                    "custom_config",
                    "bkbase_v4_resources",
                )
                if not (exclude_bindings and key == "bkbase_v4_resources")
            },
            "storages": list(storages.order_by("pk").values_list("pk", "storage_type", "status")),
            "system": system,
            "resource_type": resource_type,
            "scope": [context["version"], context["tenant"], context["namespace"]],
        }
    )


def configuration_request_digest(snapshot):
    """保存拒绝反馈的配置代次；允许同一请求先补齐正式绑定。"""
    return _binding_snapshot_digest(snapshot, exclude_bindings=True)


def record_configuration_rejection(snapshot, baseline, error):
    """沿现有status_msg显式反馈未应用；不覆盖后来配置、绑定或维护意图。"""
    if baseline is None:
        return
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().filter(pk=snapshot.pk).first()
        if latest is None or latest.status != SnapshotRunningStatus.RUNNING:
            return
        binding = latest.bkbase_v4_resources
        previous = binding.get("source_replay", {}) if isinstance(binding, dict) else None
        if (
            not isinstance(previous, dict)
            or previous.get("active")
            or previous.get("outcome_unknown")
            or binding.get("pending_action")
            or not isinstance(binding.get("asset_etl_maintenance") or {}, dict)
            or (binding.get("asset_etl_maintenance") or {}).get("active")
            or binding != snapshot.bkbase_v4_resources
            or latest.status_msg != snapshot.status_msg
        ):
            return
        try:
            if _binding_snapshot_digest(latest, locked=True, exclude_bindings=True) != baseline:
                return
        except BKBaseResourceMappingError:
            return
        # 上游异常可能包含请求/响应详情，不将连接、认证或完整错误回包持久化。
        reason = str(error.message) if isinstance(error, BKBaseResourceMappingError) else "平台读取或配置预检失败"
        latest.status_msg = "新的PULL配置未应用；原资源运行态未据此改变：" + reason
        latest.save(update_fields=["status_msg"])


def _binding_resource_ref(context, resource, kind):
    """发现只接受完整真实身份；不能用调用上下文补齐缺失元信息。"""
    if not isinstance(resource, dict) or not isinstance(resource.get("spec"), dict):
        raise BKBaseResourceMappingError(message="Invalid binding resource")
    metadata = resource.get("metadata")
    if not isinstance(metadata, dict) or any(
        not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in ("tenant", "namespace", "name")
    ):
        raise BKBaseResourceMappingError(message="Incomplete binding resource identity")
    if any(not isinstance(metadata.get(key, {}), dict) for key in ("labels", "annotations")):
        raise BKBaseResourceMappingError(message="Invalid binding labels or annotations")
    return _replay_ref(
        context, {"kind": resource.get("kind"), **{key: metadata[key] for key in ("tenant", "namespace", "name")}}, kind
    )


def _binding_list(context, endpoint, kind, selector):
    """仅查询可信配置项目；零、多候选的选择策略由业务身份校验决定。"""
    rows = endpoint(**resource_params(context), label_selector=selector)
    if not isinstance(rows, list):
        raise BKBaseResourceMappingError(message="Expected binding resource array")
    for row in rows:
        ref = _binding_resource_ref(context, row, kind)
        if ref["namespace"] != context["namespace"]:
            raise BKBaseResourceMappingError(message="Binding list escaped configured project")
    return rows


def _binding_single(context, endpoint, getter, kind, selector):
    """列表唯一命中后再读详情，最终身份/业务关联仍由调用者核对。"""
    rows = _binding_list(context, endpoint, kind, selector)
    if len(rows) != 1:
        raise BKBaseResourceMappingError(message=f"Expected one existing {kind} in configured project")
    ref = _binding_resource_ref(context, rows[0], kind)
    value = _replay_resource(context, ref, kind, getter)
    _binding_resource_ref(context, value, kind)
    return ref, value


def _discover_snapshot_binding(snapshot, context, storage_types):
    """沿正式存量关联构造完整绑定，不推断名字、集群或运行态。"""
    raw_id = _replay_raw_id(snapshot.bkbase_data_id)
    processing_id, logical_id = snapshot.bkbase_processing_id, snapshot.bkbase_table_id
    if any(
        not isinstance(value, str) or not value or any(c.isspace() or c in ",=" for c in value)
        for value in (processing_id, logical_id)
    ):
        raise BKBaseResourceMappingError(message="Missing or invalid legacy snapshot identity")
    source_ref, source_value = _binding_single(
        context,
        api.bk_base_v4.data_source_list,
        api.bk_base_v4.data_source_get,
        "DataSource",
        f"raw_data_id={raw_id}",
    )
    if _replay_raw_id(source_value["metadata"].get("labels", {}).get("raw_data_id")) != raw_id:
        raise BKBaseResourceMappingError(message="Source legacy DataID mismatch")
    data_ref = _replay_ref(context, source_value["spec"].get("data_id"), "DataId")
    clean_ref, clean = _binding_single(
        context,
        api.bk_base_v4.clean_list,
        api.bk_base_v4.clean_get,
        "Clean",
        f"raw_data_id={raw_id},result_table_id={logical_id},processing_id={processing_id}",
    )
    spec = clean["spec"]
    clean_role = {"new": "owner", "existing": "existing"}.get(spec.get("result_table_source"))
    if (
        clean["metadata"].get("labels", {}).get("processing_id") != processing_id
        or _replay_raw_id(spec.get("raw_data_id")) != raw_id
        or spec.get("result_table_id") != logical_id
        or _replay_ref(context, spec.get("data_id"), "DataId") != data_ref
        or clean_role is None
        # Asset保持原有owner约束；Basic保留已存在Clean的显式new/existing。
        or (snapshot.join_data_type == JoinDataType.ASSET and clean_role != "owner")
    ):
        raise BKBaseResourceMappingError(message="Snapshot Clean legacy identity or explicit role mismatch")
    rows = _binding_list(context, api.bk_base_v4.data_storage_list, "DataStorage", f"result_table_id={logical_id}")
    grouped = {storage_type: [] for storage_type in storage_types}
    rt_ref = None
    for row in rows:
        ref = _binding_resource_ref(context, row, "DataStorage")
        value = _replay_resource(context, ref, "DataStorage", api.bk_base_v4.data_storage_get)
        _binding_resource_ref(context, value, "DataStorage")
        metadata, table = value["metadata"], value["spec"].get("tableInfo", {})
        labels, annotations = metadata.get("labels", {}), metadata.get("annotations", {})
        logical_values = [
            container["result_table_id"] for container in (labels, annotations) if "result_table_id" in container
        ]
        if not logical_values or any(value != logical_id for value in logical_values):
            raise BKBaseResourceMappingError(message="Storage logical ResultTable identity mismatch")
        current_rt = _replay_ref(context, table.get("source"), "ResultTable")
        if rt_ref is not None and current_rt != rt_ref:
            raise BKBaseResourceMappingError(message="Storage ResultTable references disagree")
        rt_ref = current_rt
        cluster = table.get("storage")
        if not isinstance(cluster, dict) or cluster.get("kind") not in BKBASE_V4_STORAGE_CLUSTER_KINDS.values():
            raise BKBaseResourceMappingError(message="Storage cluster reference is missing")
        _replay_ref(context, cluster, cluster.get("kind"))
        for storage_type in storage_types:
            if cluster.get("kind") == BKBASE_V4_STORAGE_CLUSTER_KINDS[storage_type]:
                grouped[storage_type].append(ref)
    if any(len(refs) != 1 for refs in grouped.values()):
        raise BKBaseResourceMappingError(message="Expected one task per required storage in configured project")
    for ref, kind, getter in (
        (data_ref, "DataId", api.bk_base_v4.data_id_get),
        (rt_ref, "ResultTable", api.bk_base_v4.result_table_resource_get),
    ):
        value = getter(namespace=ref["namespace"], name=ref["name"])
        if _binding_resource_ref(context, value, kind) != ref:
            raise BKBaseResourceMappingError(message="Generic resource identity mismatch")
        if kind == "ResultTable" and value["metadata"].get("labels", {}).get("result_table_id") != logical_id:
            raise BKBaseResourceMappingError(message="ResultTable logical identity mismatch")
    return {
        "raw_data_id": raw_id,
        "data_source": source_ref,
        "data_id": data_ref,
        "clean": clean_ref,
        "clean_role": clean_role,
        "result_table_id": logical_id,
        "result_table": rt_ref,
        "storages": {key: refs[0] for key, refs in grouped.items()},
    }


def ingest_snapshot_binding(snapshot, context):
    """从可信default项目摄入存量Asset/Basic身份；HTTP外置，条件短事务保存。

    已有字段必须一致，任何配置/集合/操作变化都拒绝本次旧发现结果。
    不以资源或任务运行态决定是否保存正确身份；实际重放另行预检。
    """
    resource_params(context)
    if context["tenant"] != "default" or snapshot.join_data_type not in (JoinDataType.ASSET, JoinDataType.BASIC):
        raise BKBaseResourceMappingError(
            message="Snapshot discovery supports configured default-tenant Assets and Basics only"
        )
    binding = snapshot.bkbase_v4_resources
    previous = binding.get("source_replay", {}) if isinstance(binding, dict) else None
    if (
        snapshot.status != SnapshotRunningStatus.RUNNING
        or not isinstance(previous, dict)
        or previous.get("active")
        or previous.get("outcome_unknown")
        or binding.get("pending_action")
    ):
        raise BKBaseResourceMappingError(message="Snapshot discovery conflicts with current operation")
    baseline = _binding_snapshot_digest(snapshot)
    storage_types = set(snapshot.storages.values_list("storage_type", flat=True))
    if not storage_types or not storage_types.issubset(BKBASE_V4_STORAGE_CLUSTER_KINDS):
        raise BKBaseResourceMappingError(message="Snapshot required storage set is unsupported")
    discovered = _discover_snapshot_binding(snapshot, context, storage_types)
    merged = deepcopy(binding)
    for key, value in discovered.items():
        old = merged.get(key)
        if key == "raw_data_id" and old is not None:
            old = _replay_raw_id(old)
        if key == "storages" and isinstance(old, dict):
            if any(name not in value or value[name] != ref for name, ref in old.items()):
                raise BKBaseResourceMappingError(message="Existing snapshot storage binding conflicts")
        elif old not in (None, "", {}) and old != value:
            raise BKBaseResourceMappingError(message="Existing snapshot binding conflicts")
        merged[key] = value
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
        if _binding_snapshot_digest(latest, locked=True) != baseline:
            raise BKBaseResourceMappingError(message="Snapshot changed during resource discovery")
        latest.bkbase_v4_resources = merged
        latest.save(update_fields=["bkbase_v4_resources"])
    snapshot.bkbase_v4_resources = deepcopy(merged)


def prepare_snapshot_replay(snapshot, params, *, configure=False):
    """先持快照锁，再判断持久维护标记；锁竞争不发起重放。"""
    if get_bkbase_version() != BKBaseVersion.V4:
        return False
    try:
        with snapshot_lock(snapshot.system_id, snapshot.resource_type_id):
            snapshot.refresh_from_db()
            binding = snapshot.bkbase_v4_resources or {}
            maintenance = binding.get("asset_etl_maintenance") or {} if isinstance(binding, dict) else None
            if not isinstance(maintenance, dict) or maintenance.get("active"):
                return False
            return _prepare_snapshot_replay_locked(snapshot, params, configure=configure)
    except LockError:
        return False


def can_retry_failed_pull_connection(snapshot):
    """识别已证实运行态连接失败且从未认领 Source 的意图。"""
    binding = snapshot.bkbase_v4_resources or {}
    operation = binding.get("source_replay") if isinstance(binding, dict) else None
    return (
        snapshot.status == SnapshotRunningStatus.FAILED
        and isinstance(operation, dict)
        and operation.get("mode") == "configure"
        and isinstance(operation.get("connection_plan"), dict)
        and operation.get("connection_attempted") is True
        and operation.get("connection_accepted") is True
        and operation.get("connection_phase") == "Failed"
        and operation.get("attempted") is False
        and not operation.get("active")
        and not operation.get("outcome_unknown")
    )


def _prepare_snapshot_replay_locked(
    snapshot, params, *, configure=False, target_pull_type=None, retry_connection=False
):
    """排队已有Asset/Basic重放或明确配置维护；GET在短事务外执行。"""
    context = get_bkbase_context()
    expected_status = SnapshotRunningStatus.FAILED if retry_connection else SnapshotRunningStatus.RUNNING
    if (
        get_bkbase_version() != BKBaseVersion.V4
        or snapshot.status != expected_status
        or (retry_connection and not (configure and can_retry_failed_pull_connection(snapshot)))
    ):
        return False
    if configure and (
        context["tenant"] != "default" or snapshot.join_data_type not in (JoinDataType.ASSET, JoinDataType.BASIC)
    ):
        raise BKBaseResourceMappingError(
            message="PULL configuration maintenance supports default-tenant Assets and Basics only"
        )
    binding = snapshot.bkbase_v4_resources or {}
    if not isinstance(binding, dict) or not isinstance(binding.get("source_replay", {}), dict):
        raise BKBaseResourceMappingError(message="Invalid snapshot operation structure")
    previous = binding.get("source_replay", {})
    if previous.get("active") or previous.get("outcome_unknown"):
        return False
    if target_pull_type is not None:
        _replay_inputs(snapshot, params, context)
    if not all(
        (snapshot.bkbase_v4_resources or {}).get(key)
        for key in (
            "data_source",
            "data_id",
            "clean",
            "clean_role",
            "result_table_id",
            "result_table",
            "storages",
        )
    ):
        ingest_snapshot_binding(snapshot, context)
    fingerprint = _replay_inputs(snapshot, params, context)
    if retry_connection and fingerprint != previous["input_digest"]:
        raise BKBaseResourceMappingError(message="Failed DataConn retry requires the previous configuration")
    with resource_lock(context, snapshot.bkbase_v4_resources["data_source"]):
        current, desired, baseline, connection, observed_connection = _replay_preflight(
            snapshot, params, context, configure=configure, source_only=target_pull_type is not None
        )
        if retry_connection:
            ref = _binding_resource_ref(context, observed_connection, "DataConn")
            check_pull_connection_writer(snapshot, context, ref)
            connection = connection or observed_connection
            failed_generation = _connection_generation(observed_connection["status"])
            if (
                _confirmed_pull_connection_phase(previous, observed_connection) != "Failed"
                or not any(failed_generation)
                or pull_connection_digest(connection, public=True) != previous["connection_plan"]["public_target"]
                or _replay_resource_digest(current) != previous["source_digest"]
                or _replay_resource_digest(desired) != previous["desired_digest"]
                or any(value != previous["baseline"].get(key) for key, value in baseline.items() if key != "connection")
            ):
                raise BKBaseResourceMappingError(message="DataConn no longer matches the confirmed failure")
        with transaction.atomic():
            latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
            latest_operation = (latest.bkbase_v4_resources or {}).get("source_replay", {})
            if (
                latest.status != expected_status
                or not isinstance((latest.bkbase_v4_resources or {}).get("asset_etl_maintenance") or {}, dict)
                or ((latest.bkbase_v4_resources or {}).get("asset_etl_maintenance") or {}).get("active")
                or latest_operation.get("active")
                or latest_operation.get("outcome_unknown")
                or (retry_connection and latest_operation != previous)
                or _replay_inputs(latest, params, context) != fingerprint
            ):
                return False
            binding = deepcopy(latest.bkbase_v4_resources)
            binding["source_replay"] = {
                "operation_id": uuid.uuid4().hex,
                "active": True,
                "input_digest": fingerprint,
                "source_digest": _replay_resource_digest(current),
                "desired_digest": _replay_resource_digest(desired),
                "baseline": baseline,
                "attempted": False,
                "accepted": None,
                "outcome_unknown": False,
                "source_state": None,
                "data_completed": None,
                "poll_count": 0,
            }
            if configure:
                binding["source_replay"]["mode"] = "configure"
                binding["source_replay"]["connection_required"] = connection is not None
                if connection is not None:
                    binding["source_replay"]["connection_plan"] = {
                        "baseline": pull_connection_digest(observed_connection),
                        "public_target": pull_connection_digest(connection, public=True),
                    }
                    if retry_connection:
                        binding["source_replay"]["connection_plan"]["failed_generation"] = failed_generation
            if target_pull_type is not None:
                binding["source_replay"].update(
                    target_pull_type=target_pull_type, start_time=current.get("status", {}).get("start_time")
                )
            latest.bkbase_v4_resources = binding
            latest.status, latest.status_msg = SnapshotRunningStatus.PREPARING, ""
            latest.save(update_fields=["bkbase_v4_resources", "status", "status_msg", "updated_at"])
    return True


def fail_snapshot_replay(snapshot, *, operation_id, message):
    """只终结仍在准备中的匹配意图；取消不依赖已经失效的输入或上下文。

    operation_id为空时只拒绝无有效活动意图的入口。停止中或新代次的状态不能被旧结果覆盖。
    """
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
        if latest.status != SnapshotRunningStatus.PREPARING:
            return False
        binding = deepcopy(latest.bkbase_v4_resources or {})
        operation = binding.get("source_replay") if isinstance(binding, dict) else None
        stopping = isinstance(binding, dict) and binding.get("pending_action") == "stop"
        update_fields = []
        if operation_id is None:
            if stopping or (
                isinstance(operation, dict)
                and operation.get("active")
                and isinstance(operation.get("operation_id"), str)
                and operation["operation_id"]
            ):
                return False
        else:
            if (
                not isinstance(operation, dict)
                or operation.get("operation_id") != operation_id
                or not operation.get("active")
            ):
                return False
            if operation.get("attempted") and operation.get("accepted") is None:
                operation["outcome_unknown"] = True
            if operation.get("outcome_unknown"):
                message += "; previous request outcome remains unknown and will not be retried"
            operation.update(active=False, message=message)
            latest.bkbase_v4_resources = binding
            update_fields.append("bkbase_v4_resources")
        if not stopping:
            latest.status, latest.status_msg = SnapshotRunningStatus.FAILED, message
            update_fields.extend(["status", "status_msg"])
        latest.save(update_fields=[*update_fields, "updated_at"])
    return True


def _save_snapshot_replay(snapshot, params, context, operation_id, patch, *, status, claim=None, connection_ref=None):
    """按代次和输入条件合并，旧回包不能覆盖后来的配置或操作。"""
    with transaction.atomic():
        latest = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
        binding = deepcopy(latest.bkbase_v4_resources or {})
        operation = binding.get("source_replay", {})
        if (
            operation.get("operation_id") != operation_id
            or not operation.get("active")
            or latest.status != SnapshotRunningStatus.PREPARING
            or not isinstance(binding.get("asset_etl_maintenance") or {}, dict)
            or (binding.get("asset_etl_maintenance") or {}).get("active")
        ):
            return False
        if claim and operation.get(claim):
            return False
        try:
            unchanged = _replay_input_matches(latest, params, context, operation["input_digest"])
        except BKBaseResourceMappingError:
            unchanged = False
        if not unchanged:
            fail_snapshot_replay(
                snapshot, operation_id=operation_id, message="Replay inputs changed; this operation was cancelled"
            )
            return False
        if connection_ref:
            check_pull_connection_writer(latest, context, connection_ref)
        operation.update(patch)
        latest.bkbase_v4_resources = binding
        latest.status, latest.status_msg = status, operation.get("message", "")
        fields = ["bkbase_v4_resources", "status", "status_msg", "updated_at"]
        if status == SnapshotRunningStatus.RUNNING and operation.get("target_pull_type") is not None:
            latest.pull_type = operation["target_pull_type"]
            fields.append("pull_type")
        latest.save(update_fields=fields)
    return True


def advance_snapshot_replay(snapshot, params):
    """按快照维度串行推进，锁竞争和资产维护不消耗观察次数。"""
    try:
        with snapshot_lock(snapshot.system_id, snapshot.resource_type_id):
            snapshot.refresh_from_db()
            binding = snapshot.bkbase_v4_resources or {}
            maintenance = binding.get("asset_etl_maintenance") or {} if isinstance(binding, dict) else None
            if not isinstance(maintenance, dict) or maintenance.get("active"):
                return
            return _advance_snapshot_replay_locked(snapshot, params)
    except LockError:
        return


def _connection_generation(status):
    return [status.get("history_id"), status.get("start_time")]


def _confirmed_pull_connection_phase(operation, current):
    """识别当前 GET 是否仍对应已受理的连接目标及其代次。"""
    plan = operation["connection_plan"]
    observed = pull_connection_digest(current)
    accepted = operation.get("connection_digest")
    if not accepted or observed != accepted:
        return None
    current_history, start_time = _connection_generation(current["status"])
    history = operation.get("connection_history_id")
    if history is not None:
        matches = current_history == history
    else:
        matches = observed != plan["baseline"] or (start_time and start_time != operation.get("connection_start_time"))
    if plan.get("failed_generation"):
        old_history, old_start = plan["failed_generation"]
        matches = matches and (
            (history is not None and history != old_history) or (start_time and start_time != old_start)
        )
    return current["status"].get("phase") if matches else None


def _advance_replay_connection(snapshot, params, context, operation, current, desired):
    """单独认领连接，只有匹配该回执的独立 GET 确认后才放行 Source。"""
    ref = _binding_resource_ref(context, current, "DataConn")
    check_pull_connection_writer(snapshot, context, ref)
    plan = operation["connection_plan"]
    operation_id = operation["operation_id"]
    if not operation.get("connection_attempted"):
        failed_generation = plan.get("failed_generation")
        if failed_generation:
            desired = desired or current
        if desired is None or pull_connection_digest(desired, public=True) != plan["public_target"]:
            raise BKBaseResourceMappingError(message="DataConn configuration target changed")
        with resource_lock(context, ref):
            latest = _replay_resource(context, ref, "DataConn", api.bk_base_v4.data_conn_get)
            status = latest.get("status")
            if not isinstance(status, dict) or pull_connection_digest(latest) != plan["baseline"]:
                raise BKBaseResourceMappingError(message="DataConn configuration baseline changed or is not ready")
            expected_phase = "Failed" if failed_generation else "Ok"
            if status.get("phase") != expected_phase or (
                failed_generation and _connection_generation(status) != failed_generation
            ):
                raise BKBaseResourceMappingError(message="DataConn configuration phase or generation changed")
            if not _save_snapshot_replay(
                snapshot,
                params,
                context,
                operation_id,
                {
                    "connection_attempted": True,
                    "connection_start_time": latest["status"].get("start_time"),
                    "outcome_unknown": True,
                    "message": "DataConn update outcome unknown; automatic retry disabled",
                },
                status=SnapshotRunningStatus.PREPARING,
                claim="connection_attempted",
                connection_ref=ref,
            ):
                return False
            try:
                result = api.bk_base_v4.data_conn_update(
                    **resource_params(context, ref),
                    metadata=desired["metadata"],
                    spec=desired["spec"],
                    status=None,
                )
            except (APIRequestError, ValidateException):
                return False
            digest = accepted_pull_connection_digest(context, ref, result, desired, plan["public_target"])
            if digest:
                _save_snapshot_replay(
                    snapshot,
                    params,
                    context,
                    operation_id,
                    {
                        "connection_accepted": True,
                        "connection_digest": digest,
                        "connection_history_id": result["status"].get("history_id"),
                        "outcome_unknown": False,
                        "message": "",
                    },
                    status=SnapshotRunningStatus.PREPARING,
                )
        return False

    observed = pull_connection_digest(current)
    accepted = operation.get("connection_digest")
    if observed not in (plan["baseline"], accepted) and (
        accepted or pull_connection_digest(current, public=True) != plan["public_target"]
    ):
        raise BKBaseResourceMappingError(message="DataConn configuration drifted during observation")
    phase = _confirmed_pull_connection_phase(operation, current)
    if phase == "Ok":
        return True
    count = operation["poll_count"] + 1
    failed = phase == "Failed" or count >= BKBASE_V4_MAX_POLLS
    _save_snapshot_replay(
        snapshot,
        params,
        context,
        operation_id,
        {
            "connection_phase": phase,
            "poll_count": count,
            "active": not failed,
            "message": "DataConn configuration failed or observation timed out; request will not be repeated"
            if failed
            else operation.get("message", ""),
        },
        status=SnapshotRunningStatus.FAILED if failed else SnapshotRunningStatus.PREPARING,
    )
    return False


def _advance_snapshot_replay_locked(snapshot, params):
    """每Snapshot推进一次请求或观察；未知写结果永不自动重发。"""
    snapshot.refresh_from_db()
    operation = deepcopy((snapshot.bkbase_v4_resources or {}).get("source_replay", {}))
    if not operation.get("active") or snapshot.status != SnapshotRunningStatus.PREPARING:
        return
    operation_id = operation["operation_id"]
    try:
        context = get_bkbase_context()
        if not _replay_input_matches(snapshot, params, context, operation["input_digest"]):
            fail_snapshot_replay(
                snapshot, operation_id=operation_id, message="Replay inputs changed; this operation was cancelled"
            )
            return
        with resource_lock(context, snapshot.bkbase_v4_resources["data_source"]):
            snapshot.refresh_from_db()
            operation = deepcopy((snapshot.bkbase_v4_resources or {}).get("source_replay", {}))
            if (
                operation.get("operation_id") != operation_id
                or not operation.get("active")
                or snapshot.status != SnapshotRunningStatus.PREPARING
                or not isinstance((snapshot.bkbase_v4_resources or {}).get("asset_etl_maintenance") or {}, dict)
                or ((snapshot.bkbase_v4_resources or {}).get("asset_etl_maintenance") or {}).get("active")
            ):
                return
            if not _replay_input_matches(snapshot, params, context, operation["input_digest"]):
                fail_snapshot_replay(
                    snapshot, operation_id=operation_id, message="Replay inputs changed; this operation was cancelled"
                )
                return
            current, desired, baseline, connection, observed_connection = _replay_preflight(
                snapshot,
                params,
                context,
                observing=operation["attempted"],
                configure=operation.get("mode") == "configure",
                source_only=operation.get("target_pull_type") is not None,
            )
            connection_phase = (observed_connection.get("status") or {}).get("phase")
            expected_baseline = operation["baseline"]
            if operation.get("connection_plan"):
                baseline.pop("connection")
                expected_baseline = {key: value for key, value in expected_baseline.items() if key != "connection"}
            if baseline != expected_baseline:
                raise BKBaseResourceMappingError(message="Replay downstream or connection configuration changed")
            if not operation["attempted"] and _replay_resource_digest(current) != operation["source_digest"]:
                raise BKBaseResourceMappingError(message="Replay source configuration changed")
            if operation.get("connection_plan") and not _advance_replay_connection(
                snapshot, params, context, operation, observed_connection, connection
            ):
                return
            if not operation["attempted"]:
                if not operation.get("connection_plan") and (
                    connection is not None or operation.get("connection_required")
                ):
                    raise BKBaseResourceMappingError(message="Replay DataConn write plan is missing")
                if not _save_snapshot_replay(
                    snapshot,
                    params,
                    context,
                    operation_id,
                    {"attempted": True, "outcome_unknown": True, "poll_count": 0},
                    status=SnapshotRunningStatus.PREPARING,
                    claim="attempted",
                    connection_ref=current["spec"]["data_conn"] if operation.get("connection_plan") else None,
                ):
                    return
                try:
                    accepted_source = api.bk_base_v4.data_source_update(
                        **resource_params(context, snapshot.bkbase_v4_resources["data_source"], kind="DataSource"),
                        metadata=desired["metadata"],
                        spec=desired["spec"],
                        status=None,
                    )
                except (APIRequestError, ValidateException):
                    patch = {
                        "outcome_unknown": True,
                        "message": (
                            "DataSource update outcome unknown; earlier accepted steps are retained; "
                            "automatic retry disabled"
                        ),
                    }
                else:
                    patch = {"accepted": True, "outcome_unknown": False}
                    if operation.get("target_pull_type") is not None:
                        patch["history_id"] = (accepted_source.get("status") or {}).get("history_id")
                _save_snapshot_replay(
                    snapshot, params, context, operation_id, patch, status=SnapshotRunningStatus.PREPARING
                )
                return
            observed = operation_result(current, snapshot.bkbase_v4_resources["data_source"], "observe")
            configured = _replay_resource_digest(current) == operation["desired_digest"]
            running = observed["task_state"] == TaskState.RUNNING and (
                configured or (operation["outcome_unknown"] and operation.get("mode") != "configure")
            )
            if operation.get("target_pull_type") is not None:
                if operation["source_digest"] == operation["desired_digest"]:
                    start_time = current.get("status", {}).get("start_time")
                    running = (
                        running
                        and operation.get("accepted") is True
                        and (
                            operation.get("saw_transition")
                            or (start_time and start_time != operation.get("start_time"))
                        )
                    )
            if operation.get("connection_required"):
                running = running and operation.get("accepted") is True and connection_phase == "Ok"
            connection_failed = operation.get("connection_required") and connection_phase == "Failed"
            count = operation["poll_count"] + 1
            failed = (
                connection_failed
                or observed["task_state"] == TaskState.FAILED
                or (count >= BKBASE_V4_MAX_POLLS and not running)
            )
            patch = {
                "source_state": observed["task_state"],
                "config_observed": configured,
                "poll_count": count,
                "active": not (running or failed),
            }
            if operation.get("target_pull_type") is not None:
                patch["saw_transition"] = operation.get("saw_transition") or observed["resource_phase"] in (
                    "Pending",
                    "Reconciling",
                )
                if running:
                    patch["outcome_unknown"] = False
            if operation.get("connection_required"):
                patch["connection_phase"] = connection_phase
            status = (
                SnapshotRunningStatus.RUNNING
                if running
                else SnapshotRunningStatus.FAILED
                if failed
                else SnapshotRunningStatus.PREPARING
            )
            if failed:
                patch["message"] = (
                    "DataConn configuration failed; accepted updates are retained; automatic recovery not attempted"
                    if connection_failed
                    else "Replay source failed or observation timed out; request will not be repeated"
                )
            _save_snapshot_replay(snapshot, params, context, operation_id, patch, status=status)
    except (BKBaseResourceMappingError, ImproperlyConfigured):
        fail_snapshot_replay(
            snapshot,
            operation_id=operation_id,
            message="Replay preconditions are invalid; this operation was cancelled",
        )
    except APIRequestError:
        count = operation["poll_count"] + 1
        failed = count >= BKBASE_V4_MAX_POLLS
        _save_snapshot_replay(
            snapshot,
            params,
            context,
            operation_id,
            {
                "poll_count": count,
                "active": not failed,
                "message": "Replay observation unavailable; no write will be retried",
            },
            status=SnapshotRunningStatus.FAILED if failed else SnapshotRunningStatus.PREPARING,
        )
    except LockError:
        # 锁竞争没有观测和写副作用，不消耗观测预算。
        return


def _provision_digest(snapshot, params, context, *, legacy=False):
    """计算本地输入摘要，不持久化认证信息。"""
    system = (
        System.objects.filter(system_id=snapshot.system_id).values("callback_url", "auth_token", "namespace").first()
    )
    resource = (
        ResourceType.objects.filter(system_id=snapshot.system_id, resource_type_id=snapshot.resource_type_id)
        .values("path")
        .first()
    )
    return _replay_digest(
        {
            "params": params if legacy else _source_intent_inputs(params),
            "tenant": context["tenant"],
            "namespace": context["namespace"],
            "pull_config": snapshot.pull_config if legacy else _source_intent_inputs(snapshot.pull_config),
            "pull_type": snapshot.pull_type,
            "join_data_type": snapshot.join_data_type,
            "system": system,
            "resource": resource,
        }
    )


def require_new_pull_sensitivity():
    """兼容旧调用；V4 不提交源敏感级别。"""
    return None


def _provision_input_matches(snapshot, params, context, expected):
    """兼容升级前未变更的旧摘要，仍对真实业务输入进行校验。"""
    return (
        _provision_digest(snapshot, params, context) == expected
        or _provision_digest(snapshot, params, context, legacy=True) == expected
    )


def prepare_source_provision(snapshot, params):
    """只登记意图；允许调用方处于事务中，禁止在这里发起网络请求。"""
    context = get_bkbase_context()
    resource_params(context)
    with transaction.atomic():
        current = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
        binding = deepcopy(current.bkbase_v4_resources or {})
        if (
            current.status != SnapshotRunningStatus.PREPARING
            or binding.get("pending_action")
            or current.join_data_type not in (JoinDataType.ASSET, JoinDataType.BASIC)
            or (binding.get("source_replay") or {}).get("active")
        ):
            raise BKBaseResourceMappingError(message="Snapshot is not available for PULL provisioning")
        operation = binding.get("source_provision")
        if operation:
            if not _provision_input_matches(current, params, context, operation.get("digest")):
                raise BKBaseResourceMappingError(message="PULL provisioning configuration changed")
            return None
        if current.bkbase_data_id or binding.get("data_source") or binding.get("data_id"):
            raise BKBaseResourceMappingError(message="Existing source cannot be adopted by new PULL provisioning")
        operation_id = uuid.uuid4().hex
        binding["source_provision"] = {
            "operation_id": operation_id,
            "stage": "new",
            "digest": _provision_digest(current, params, context),
            "conn_name": "audit_conn_" + operation_id,
            "source_name": "audit_source_" + operation_id,
        }
        current.bkbase_v4_resources = binding
        current.save(update_fields=["bkbase_v4_resources"])
    snapshot.bkbase_v4_resources = binding
    return None


def _provision_transition(
    snapshot,
    params,
    context,
    operation_id,
    expected,
    stage,
    *,
    patch=None,
    ready=None,
    failure=None,
    accepted_source=None,
):
    """短事务校验代次、状态和输入后提交本地状态。"""
    with transaction.atomic():
        current = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
        binding = deepcopy(current.bkbase_v4_resources or {})
        operation = binding.get("source_provision") or {}
        if (
            current.status != SnapshotRunningStatus.PREPARING
            or binding.get("pending_action")
            or current.bkbase_data_id is not None
            or binding.get("data_id")
            or binding.get("data_source") != operation.get("accepted_source")
            or operation.get("operation_id") != operation_id
            or operation.get("stage") != expected
            or not _provision_input_matches(current, params, context, operation.get("digest"))
        ):
            return False
        operation.update(patch or {})
        operation["stage"] = stage
        if accepted_source:
            operation["accepted_source"] = deepcopy(accepted_source)
            binding["data_source"] = deepcopy(accepted_source)
        if ready:
            binding.update(data_source=ready["source"], data_id=ready["data_id"], raw_data_id=ready["raw_id"])
            current.bkbase_data_id = ready["raw_id"]
            # 下一次定时任务接力创建 Clean；Source 仍保持停止。
            current.status_msg = ""
        elif failure:
            current.status = SnapshotRunningStatus.FAILED
            current.status_msg = failure
        current.bkbase_v4_resources = binding
        current.save(update_fields=["bkbase_v4_resources", "bkbase_data_id", "status", "status_msg"])
    snapshot.refresh_from_db()
    return True


def fail_source_provision(snapshot, operation_id, expected_stage, expected_digest, params, *, blocker=None):
    """后台异常仅终止仍属于同一代次的启动。"""
    with transaction.atomic():
        current = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
        binding = current.bkbase_v4_resources or {}
        operation = binding.get("source_provision") or {}
        if (
            current.status != SnapshotRunningStatus.PREPARING
            or binding.get("pending_action")
            or operation.get("operation_id") != operation_id
            or operation.get("stage") != expected_stage
            or operation.get("digest") != expected_digest
        ):
            return
        current.status = SnapshotRunningStatus.FAILED
        if operation_id and params is None:
            current.status_msg = "PULL provisioning inputs unavailable; operation cancelled"
        else:
            current.status_msg = "PULL provisioning failed or outcome unknown; automatic retry disabled"
        current.save(update_fields=["status", "status_msg"])


def _provision_report_config(snapshot, params, conn_name):
    """从快照拉取参数构造正式 Source 的 HTTP 声明。"""
    base = System.objects.get(system_id=snapshot.system_id).callback_url.rstrip("/")
    return build_pull_report_config(params, conn_name, base)


def build_pull_report_config(params, conn_name, base):
    """从既有 HTTP 拉取声明构造 V4 模板，保留调用方选择的可信 URL 边界。"""
    config = params["access_conf_info"]
    (scope,) = config["resource"]["scope"]
    if not base or not scope["url"].startswith(base + "/"):
        raise BKBaseResourceMappingError(message="PULL URL does not match trusted system callback")
    body = scope["body"]
    return {
        "type": "rest_api",
        "http_mode": "PULL",
        "data_conn_name": conn_name,
        "method": scope["method"].lower(),
        "path": scope["url"][len(base) :],
        "body": body["content"],
        "increment_field": {"type": "time", "time_format": body["time"]["format"]},
        "data_path": None,
        "period": config["collection_model"]["period"],
        "period_unit": "minute",
        "history_data": None,
        "pagination": {
            "start_offset": body["page"]["start_offset"],
            "limit": body["page"]["limit"],
            "total_path": body["page"]["total_path"],
        },
    }


def pull_report_data_path(report):
    """区分已证的完整响应与列表输入；缺失/自定义路径不能推测为某种形状。"""
    if not isinstance(report, dict) or "data_path" not in report:
        raise BKBaseResourceMappingError(message="PULL input shape is unknown; confirm Source report_config.data_path")
    path = report["data_path"]
    if path is not None and path != BKBASE_V4_PULL_RESULTS_PATH:
        raise BKBaseResourceMappingError(message="PULL custom data_path input shape requires verification")
    return path


def validate_source_provision_report(snapshot, params, conn_name, report):
    """从 GET 结果核对本代次声明的采集字段，允许服务端补充字段。"""
    expected = _provision_report_config(snapshot, params, conn_name)
    # data_path是既有Source的封装选择，不用本版新建默认值改写已受理来源。
    expected["data_path"] = pull_report_data_path(report)
    if isinstance(report, dict):
        observed = {key: report.get(key) for key in expected}
        for key in ("increment_field", "pagination"):
            if isinstance(observed[key], dict):
                observed[key] = {field: observed[key].get(field) for field in expected[key]}
        if observed == expected:
            return
    raise BKBaseResourceMappingError(message="DataSource PULL report configuration drifted")


def advance_source_provision(snapshot, params):  # noqa: C901
    """后台推进一次创建或观察，未知写入不重试，也不采纳同名资源。"""
    if transaction.get_connection().in_atomic_block:
        raise BKBaseResourceMappingError(message="PULL provisioning network operation requires no outer transaction")
    snapshot.refresh_from_db()
    context = get_bkbase_context()
    operation = deepcopy((snapshot.bkbase_v4_resources or {}).get("source_provision") or {})
    op_id, stage = operation.get("operation_id"), operation.get("stage")
    if not op_id:
        return None
    if stage in ("conn_inflight", "source_inflight"):
        if time.time() < operation.get("claim_expires", 0):
            return None
        fail_source_provision(snapshot, op_id, stage, operation.get("digest"), params)
        return None
    if stage == "ready":
        return None
    if stage in ("failed", "conn_unknown", "source_unknown"):
        with transaction.atomic():
            current = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
            binding = current.bkbase_v4_resources or {}
            active = binding.get("source_provision") or {}
            if (
                current.status == SnapshotRunningStatus.PREPARING
                and not binding.get("pending_action")
                and active.get("operation_id") == op_id
                and active.get("stage") == stage
            ):
                current.status = SnapshotRunningStatus.FAILED
                if stage in ("conn_unknown", "source_unknown"):
                    current.status_msg = "PULL creation outcome unknown; automatic retry disabled"
                else:
                    current.status_msg = current.status_msg or "PULL provisioning failed; automatic retry disabled"
                current.save(update_fields=["status", "status_msg"])
        return None
    if not _provision_input_matches(snapshot, params, context, operation.get("digest")):
        with transaction.atomic():
            current = Snapshot.objects.select_for_update().get(pk=snapshot.pk)
            binding = current.bkbase_v4_resources or {}
            if (
                current.status == SnapshotRunningStatus.PREPARING
                and not binding.get("pending_action")
                and (binding.get("source_provision") or {}).get("operation_id") == op_id
            ):
                current.status = SnapshotRunningStatus.FAILED
                current.status_msg = "PULL provisioning inputs changed; operation cancelled"
                current.save(update_fields=["status", "status_msg"])
        return None
    conn_ref = {
        "kind": "DataConn",
        "tenant": context["tenant"],
        "namespace": context["namespace"],
        "name": operation["conn_name"],
    }
    src_ref = {
        "kind": "DataSource",
        "tenant": context["tenant"],
        "namespace": context["namespace"],
        "name": operation["source_name"],
    }

    def wait_for_ready():
        count = operation.get("poll_count", 0) + 1
        if count >= BKBASE_V4_MAX_POLLS:
            _provision_transition(
                snapshot,
                params,
                context,
                op_id,
                stage,
                "failed",
                patch={"poll_count": count},
                failure="PULL provisioning observation timed out",
            )
        else:
            _provision_transition(snapshot, params, context, op_id, stage, stage, patch={"poll_count": count})

    if stage == "new":
        (scope,) = params["access_conf_info"]["resource"]["scope"]
        base = System.objects.get(system_id=snapshot.system_id).callback_url.rstrip("/")
        if not base or not scope["url"].startswith(base + "/"):
            raise BKBaseResourceMappingError(message="PULL URL does not match trusted system callback")
        spec = {
            "data_conn_alias": operation["conn_name"],
            "conn_info": {
                "type": "rest_api",
                "url": base,
                "healthcheck_url": "/",
                "headers": deepcopy(scope["headers"]),
            },
        }
        if not _provision_transition(
            snapshot, params, context, op_id, stage, "conn_inflight", patch={"claim_expires": time.time() + 300}
        ):
            return None
        result = api.bk_base_v4.data_conn_create(
            **resource_params(context), metadata=resource_params(context, conn_ref), spec=spec, status=None
        )
        if any(result.get("metadata", {}).get(key) != conn_ref[key] for key in ("tenant", "namespace", "name")):
            raise BKBaseResourceMappingError(message="DataConn creation receipt identity mismatch")
        _provision_transition(snapshot, params, context, op_id, "conn_inflight", "conn_accepted")
        return None
    if stage == "conn_accepted":
        try:
            conn = _replay_resource(context, conn_ref, "DataConn", api.bk_base_v4.data_conn_get)
        except APIRequestError:
            wait_for_ready()
            return None
        if (conn.get("status") or {}).get("phase") == "Failed":
            _provision_transition(
                snapshot, params, context, op_id, stage, "failed", failure="DataConn provisioning failed"
            )
            return None
        if (conn.get("status") or {}).get("phase") != "Ok":
            wait_for_ready()
            return None
        spec = {
            "basic_info": {
                "data_source_name": src_ref["name"],
                "data_source_alias": params["access_raw_data"]["raw_data_alias"],
                "data_encoding": "UTF-8",
                "bk_biz_id": params["bk_biz_id"],
                "time_zone": "Asia/Shanghai",
                "tags": [],
                "description": params["description"],
            },
            "data_conn": conn_ref,
            "desired_status": "Stopped",
            "report_config": _provision_report_config(snapshot, params, conn_ref["name"]),
        }
        if not _provision_transition(
            snapshot, params, context, op_id, stage, "source_inflight", patch={"claim_expires": time.time() + 300}
        ):
            return None
        result = api.bk_base_v4.data_source_create(
            **resource_params(context), metadata=resource_params(context, src_ref), spec=spec, status=None
        )
        if any(result.get("metadata", {}).get(key) != src_ref[key] for key in ("tenant", "namespace", "name")):
            raise BKBaseResourceMappingError(message="DataSource creation receipt identity mismatch")
        _provision_transition(
            snapshot, params, context, op_id, "source_inflight", "source_accepted", accepted_source=src_ref
        )
        return None
    if stage == "source_accepted":
        try:
            value = _replay_resource(context, src_ref, "DataSource", api.bk_base_v4.data_source_get)
        except APIRequestError:
            wait_for_ready()
            return None
        if (value.get("status") or {}).get("phase") == "Failed":
            _provision_transition(
                snapshot, params, context, op_id, stage, "failed", failure="DataSource provisioning failed"
            )
            return None
        if (value.get("status") or {}).get("phase") != "Ok":
            wait_for_ready()
            return None
        desired = str(value.get("spec", {}).get("desired_status", "")).lower()
        actual = str(value.get("spec", {}).get("current_status", "")).lower()
        if "running" in (desired, actual):
            _provision_transition(
                snapshot, params, context, op_id, stage, "failed", failure="DataSource stopped state drifted"
            )
            return None
        if desired != "stopped" or actual != "stopped":
            wait_for_ready()
            return None
        raw_id = _positive_raw_data_id(value.get("metadata", {}).get("labels", {}).get("raw_data_id"))
        data_id = value.get("spec", {}).get("data_id") or {}
        try:
            resource_params(context, data_id, kind="DataId")
        except BKBaseResourceMappingError:
            wait_for_ready()
            return None
        if raw_id is None or value.get("spec", {}).get("data_conn") != conn_ref:
            wait_for_ready()
            return None
        try:
            validate_source_provision_report(snapshot, params, conn_ref["name"], value["spec"].get("report_config"))
        except BKBaseResourceMappingError as error:
            _provision_transition(snapshot, params, context, op_id, stage, "failed", failure=str(error.message))
            return None
        _provision_transition(
            snapshot,
            params,
            context,
            op_id,
            stage,
            "ready",
            ready={"raw_id": raw_id, "source": src_ref, "data_id": data_id},
        )
    return None


def create_deploy_plan(request_data=None, *, snapshot=None, **params):
    """V3直接创建；V4只登记到所属 Snapshot 后由后台执行。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return legacy_call("create_deploy_plan", request_data, **params)
    if snapshot is None:
        raise BKBaseResourceMappingError(message="V4 PULL creation requires an owning Snapshot")
    return prepare_source_provision(snapshot, {**(request_data or {}), **params})


def update_deploy_plan(request_data=None, *, snapshot=None, **params):
    """旧更新入口接已有Snapshot配置维护；不新建数字ID或共享连接。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return legacy_call("update_deploy_plan", request_data, **params)
    data = {**(request_data or {}), **params}
    if snapshot is None or _replay_raw_id(data.get("bkbase_data_id")) != _replay_raw_id(snapshot.bkbase_data_id):
        raise BKBaseResourceMappingError(message="PULL update requires the matching existing Snapshot")
    if data.get("reset_to_head") is not True:
        raise BKBaseResourceMappingError(message="Unsupported PULL update intent")
    # 旧路由数字ID已核对；维护任务按相同业务配置重建，不能将路由键混入配置摘要。
    data.pop("bkbase_data_id")
    if not prepare_snapshot_replay(snapshot, data, configure=True):
        raise BKBaseResourceMappingError(
            message="PULL configuration was not queued; existing operation or changed state must be observed"
        )
    return True


def _find_source(context, raw_data_id):
    if _positive_raw_data_id(str(raw_data_id)) is None:
        raise BKBaseResourceMappingError(message="Invalid raw_data_id")
    rows = _source_list(
        api.bk_base_v4.data_source_list(**resource_params(context), label_selector=f"raw_data_id={raw_data_id}")
    )
    matches = [r for r in rows if str(r.get("metadata", {}).get("labels", {}).get("raw_data_id")) == str(raw_data_id)]
    if len(matches) != 1:
        raise BKBaseResourceMappingError(message="Synced DataSource missing or ambiguous")
    return matches[0]


def stop_collector(**params):
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.stop_collector(**params)
    context = get_bkbase_context()
    return stop_source(context, reference(_find_source(context, params["bkbase_data_id"]), context, "DataSource"))


def _plugin_source_projects(context):
    """完整采用当前租户正式项目范围，失败不能跳过后冒充唯一命中。"""
    rows = api.bk_base_v4.namespaces_list(tenant=context["tenant"])
    if not isinstance(rows, list):
        raise BKBaseResourceMappingError(message="Expected platform Namespace resource array")
    projects = set()
    for row in rows:
        meta = row.get("metadata") if isinstance(row, dict) else None
        spec = row.get("spec") if isinstance(row, dict) else None
        status = row.get("status", {}) if isinstance(row, dict) else None
        if (
            not isinstance(meta, dict)
            or row.get("kind") != "Namespace"
            or meta.get("tenant") != context["tenant"]
            or meta.get("namespace") != "bkbase"
            or not isinstance(meta.get("name"), str)
            or not meta["name"]
            or not isinstance(spec, dict)
            or spec.get("name") not in (None, meta["name"])
            or not isinstance(status, dict)
        ):
            raise BKBaseResourceMappingError(message="Invalid platform Namespace identity")
        if status.get("phase") != "Terminating":
            projects.add(meta["name"])
    return sorted(projects)


def _plugin_source_matches(resource, *, name, bk_biz_id):
    """名称仅生成候选；复用既有BKLog标识，不按任意子串或固定业务前缀推导身份。"""
    info = resource["spec"].get("basic_info", {})
    if not isinstance(info, dict):
        raise BKBaseResourceMappingError(message="Invalid DataSource basic_info")
    identifiers = (name, CollectorPlugin.build_result_table_id(bk_biz_id, name))
    pattern = r"(?<![A-Za-z0-9_-])(?:" + "|".join(re.escape(value) for value in identifiers) + r")(?![A-Za-z0-9_-])"
    return any(
        isinstance(value, str) and re.search(pattern, value, flags=re.IGNORECASE)
        for value in (resource["metadata"]["name"], info.get("data_source_name"), info.get("data_source_alias"))
    )


def _verify_plugin_data_id(context, ref, *, raw_id, bk_biz_id):
    """Source项目业务不能替代来源归属，按实际DataId的数字ID及业务标记核对。"""
    params = resource_params(context, ref, kind="DataId")
    params.pop("tenant")
    actual = api.bk_base_v4.data_id_get(**params)
    verify_native_data_id(context, actual, data_ref=ref, raw_data_id=raw_id)
    labels = actual["metadata"].get("labels", {})
    if _positive_raw_data_id(str(labels.get("bk_biz_id"))) != bk_biz_id:
        raise BKBaseResourceMappingError(message="DataId origin business does not match the audit plugin")
    if not isinstance(actual.get("status"), dict) or actual["status"].get("phase") != "Ok":
        raise BKBaseResourceMappingError(message="Plugin DataId is not ready")


def _plugin_rawdata_list(context, *, name, bk_biz_id):
    """先完整范围消歧，再正式核验唯一Source及DataId，尚未核实的候选不能被过滤掉。"""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise BKBaseResourceMappingError(message="Plugin source discovery requires its full English name")
    biz_id = _positive_raw_data_id(str(bk_biz_id))
    if biz_id is None:
        raise BKBaseResourceMappingError(message="Plugin business must be a positive numeric ID")
    candidates = []
    for namespace in _plugin_source_projects(context):
        rows = _source_list(api.bk_base_v4.data_source_list(tenant=context["tenant"], namespace=namespace))
        for row in rows:
            ref = _binding_resource_ref(context, row, "DataSource")
            if ref["namespace"] != namespace:
                raise BKBaseResourceMappingError(message="DataSource list escaped its enumerated project")
            if _plugin_source_matches(row, name=name, bk_biz_id=biz_id):
                candidates.append(row)
    if len(candidates) != 1:
        raise BKBaseResourceMappingError(message=f"Expected one plugin DataSource; matched {len(candidates)}")
    selected = candidates[0]
    ref = _binding_resource_ref(context, selected, "DataSource")
    raw_id = _positive_raw_data_id(selected["metadata"].get("labels", {}).get("raw_data_id"))
    if raw_id is None:
        raise BKBaseResourceMappingError(message="Plugin DataSource numeric raw_data_id is not ready")
    actual = api.bk_base_v4.data_source_get(**resource_params(context, ref, kind="DataSource"))
    if _binding_resource_ref(context, actual, "DataSource") != ref:
        raise BKBaseResourceMappingError(message="Plugin DataSource GET identity changed")
    for resource in (selected, actual):
        data_ref = resource["spec"].get("data_id")
        if (
            not isinstance(data_ref, dict)
            or set(data_ref) != {"kind", "tenant", "namespace", "name"}
            or data_ref.get("kind") != "DataId"
        ):
            raise BKBaseResourceMappingError(message="Plugin DataSource requires a complete DataId reference")
    project_context = {**context, "namespace": ref["namespace"]}
    binding = _source_binding(project_context, selected, raw_id)
    if _source_binding(project_context, actual, raw_id) != binding or not _plugin_source_matches(
        actual, name=name, bk_biz_id=biz_id
    ):
        raise BKBaseResourceMappingError(message="Plugin DataSource identity changed after listing")
    if not isinstance(actual.get("status"), dict) or actual["status"].get("phase") != "Ok":
        raise BKBaseResourceMappingError(message="Plugin DataSource is not ready")
    _verify_plugin_data_id(context, binding["data_id"], raw_id=raw_id, bk_biz_id=biz_id)
    # 保存已核实的来源业务身份，重入时重新核验；不改Source或审计输出的项目业务。
    binding["source_bk_biz_id"] = biz_id
    return [{**_legacy_source(actual), "bk_biz_id": biz_id, "_bkbase_v4_binding": binding}]


def get_rawdata_list(*, include_binding=False, **params):
    """插件发现返回已核实绑定；普通列表保留配置项目内的旧投影。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_rawdata_list(**params)
    context = get_bkbase_context()
    if include_binding:
        return _plugin_rawdata_list(
            context, name=params.get("raw_data_name__icontains"), bk_biz_id=params.get("bk_biz_id")
        )
    rows = _source_list(api.bk_base_v4.data_source_list(**resource_params(context)))
    name = str(params.get("raw_data_name__icontains", "")).lower()
    return [
        _legacy_source(r)
        for r in rows
        if _positive_raw_data_id(r.get("metadata", {}).get("labels", {}).get("raw_data_id")) is not None
        and name in r.get("spec", {}).get("basic_info", {}).get("data_source_name", "").lower()
        and (
            params.get("bk_biz_id") is None
            or str(r.get("spec", {}).get("basic_info", {}).get("bk_biz_id")) == str(params["bk_biz_id"])
        )
    ]


def get_rawdata_tail(*, owner=None, **params):
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_rawdata_tail(**params)
    context = get_bkbase_context()
    if owner is not None:
        raw_id = _positive_raw_data_id(str(params.get("bk_data_id")))
        if raw_id is None or raw_id != getattr(owner, "bk_data_id", None):
            raise BKBaseResourceMappingError(message="DataId owner does not match raw_data_id")
        binding = getattr(owner, "bkbase_v4_resources", None) or {}
        if binding.get("source_raw_data_id") not in (None, raw_id):
            raise BKBaseResourceMappingError(message="DataId binding does not match raw_data_id")
        if binding.get("data_id"):
            return tail_source(context, binding["data_id"])
    resource = _find_source(context, params["bk_data_id"])
    data_id = resource.get("spec", {}).get("data_id") or {}
    ref = {
        "kind": "DataId",
        "tenant": data_id.get("tenant", context["tenant"]),
        "namespace": data_id.get("namespace"),
        "name": data_id.get("name"),
    }
    return tail_source(context, ref)
