"""处理已有同步DataSource及个人可见DataID。

DataSource与DataId分别保存真实引用，避免把同名视为同一资源。
停止声明与任务停稳分开，控制器未就绪的引用不能猜测。
"""

from copy import deepcopy

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger

from core.exceptions import LockError
from core.models import get_request_username
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    operation_result,
    pending_call,
    reference,
    resource_lock,
    resource_params,
    update_owner_binding,
)
from services.web.bkbase.constants import BKBASE_V4_MAX_POLLS, BKBaseVersion, TaskState
from services.web.bkbase.exceptions import BKBaseException, BKBaseResourceMappingError
from services.web.bkbase.permissions import require_user
from services.web.databus.constants import SnapshotRunningStatus
from services.web.databus.models import Snapshot


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


def _legacy_source(resource):
    spec = resource.get("spec", {})
    info = spec.get("basic_info", {})
    raw_id = resource.get("metadata", {}).get("labels", {}).get("raw_data_id")
    if raw_id is None:
        raise BKBaseResourceMappingError(message="DataSource raw_data_id not ready")
    result = {
        "id": int(raw_id),
        "raw_data_name": info.get("data_source_name", resource["metadata"]["name"]),
        "raw_data_alias": info.get("data_source_alias", ""),
        "bk_biz_id": info.get("bk_biz_id"),
        "description": info.get("description", ""),
    }
    for key in ("data_encoding",):
        if key in info:
            result[key] = info[key]
    for key in ("created_by", "updated_by", "created_at", "updated_at"):
        if spec.get(key):
            result[key] = spec[key]
    return result


def get_my_rawdata_list(**params):
    """维持原列表分页外观；V4原生列表由审计分页。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_my_rawdata_list(**params)
    context = get_bkbase_context(user=get_request_username())
    rows = [
        _legacy_source(r)
        for r in list_user_sources(context, bk_biz_id=params.get("bk_biz_id"))
        if r.get("metadata", {}).get("labels", {}).get("raw_data_id") is not None
    ]
    size = int(params.get("page_size", 100))
    start = (int(params.get("page", 1)) - 1) * size
    return {"count": len(rows), "results": rows[start : start + size]}


def get_my_rawdata_list_bulk(requests):
    """V3保留SDK并发，V4个人上下文在当前线程顺序处理。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_my_rawdata_list.bulk_request(requests)
    return [get_my_rawdata_list(**params) for params in requests]


def get_rawdata_detail(*, bk_data_id):
    """按当前用户可见DataID唯一匹配详情。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_rawdata_detail(bk_data_id=bk_data_id)
    context = get_bkbase_context(user=get_request_username())
    rows = [
        r
        for r in list_user_sources(context)
        if str(r.get("metadata", {}).get("labels", {}).get("raw_data_id")) == str(bk_data_id)
    ]
    if len(rows) != 1:
        raise BKBaseResourceMappingError()
    return _legacy_source(get_user_source(context, reference(rows[0], context, "DataSource")))


def resolve_synced_source(context, collector, *, raw_data_id=None):
    """唯一定位BKLog同步资源并保存实际DataId关联，不重复创建源。"""
    raw_id = raw_data_id or getattr(collector, "bk_data_id", None) or getattr(collector, "bkbase_data_id", None)
    if raw_id is None:
        raise BKBaseResourceMappingError(message="Missing synced raw DataID")
    rows = _source_list(
        api.bk_base_v4.data_source_list(**resource_params(context), label_selector=f"raw_data_id={raw_id}")
    )
    matches = [r for r in rows if str(r.get("metadata", {}).get("labels", {}).get("raw_data_id")) == str(raw_id)]
    if len(matches) != 1:
        raise BKBaseResourceMappingError()
    resource = matches[0]
    source_ref = reference(resource, context, "DataSource")
    data_id = resource.get("spec", {}).get("data_id") or {}
    data_id_ref = {
        "kind": "DataId",
        "tenant": data_id.get("tenant", context["tenant"]),
        "namespace": data_id.get("namespace"),
        "name": data_id.get("name"),
    }
    resource_params(context, data_id_ref, kind="DataId")
    binding = deepcopy(collector.bkbase_v4_resources or {})
    binding.update(data_source=source_ref, data_id=data_id_ref)
    return update_owner_binding(collector, {"data_source": source_ref, "data_id": data_id_ref})


def stop_source(context, source_ref):
    """GET后全量PUT期望停止，保留其他配置，实际态单独返回。"""
    params = resource_params(context, source_ref, kind="DataSource")
    with resource_lock(context, source_ref):
        old = api.bk_base_v4.data_source_get(**params)
        if old["spec"].get("current_status") == TaskState.STOPPED:
            return operation_result(old, source_ref, "stop")
        payload = deepcopy(old)
        payload["spec"]["desired_status"] = TaskState.STOPPED
        result = api.bk_base_v4.data_source_update(
            **params, metadata=payload["metadata"], spec=payload["spec"], status=None
        )
    return operation_result(result, source_ref, "stop")


def stop_snapshot(snapshot, params, *, multiple_storage=False):
    """保留V3同步停止；V4收到实际Stopped后才关闭本地快照。"""
    result = stop_collector(**params)
    if get_bkbase_version() == BKBaseVersion.V3:
        stopped = True
    else:
        stopped = result["task_state"] == TaskState.STOPPED
        update_owner_binding(
            snapshot,
            {
                "data_source": result["ref"],
                "pending_action": None if stopped else "stop",
                "source_poll_count": 0,
                "source_message": result.get("message", ""),
            },
        )
    if stopped and not multiple_storage:
        snapshot.status = SnapshotRunningStatus.CLOSED
        snapshot.save(update_fields=["status"])
    return stopped


def poll_source_operations():
    """每次只观测一次停止，错误不影响其他快照，超时保留诊断信息。"""
    if get_bkbase_version() != BKBaseVersion.V4:
        return
    context = get_bkbase_context()
    for snapshot in Snapshot.objects.filter(bkbase_v4_resources__pending_action="stop"):
        binding = snapshot.bkbase_v4_resources
        count = binding.get("source_poll_count", 0) + 1
        message, state = "", None
        try:
            ref = binding["data_source"]
            current = api.bk_base_v4.data_source_get(**resource_params(context, ref, kind="DataSource"))
            observed = operation_result(current, ref, "stop")
            state, message = observed["task_state"], observed["message"]
        except (APIRequestError, BKBaseException, LockError) as error:
            message = str(error)
            logger.exception("BKBase V4 DataSource observation failed: %s", snapshot.pk)
        done = state == TaskState.STOPPED
        failed = state == TaskState.FAILED or count >= BKBASE_V4_MAX_POLLS
        if count >= BKBASE_V4_MAX_POLLS and not done:
            message = "DataSource stop timed out: " + message
        update_owner_binding(
            snapshot,
            {
                "source_poll_count": count,
                "source_message": message,
                "pending_action": None if done or failed else "stop",
            },
        )
        if done or failed:
            snapshot.status = SnapshotRunningStatus.CLOSED if done else SnapshotRunningStatus.FAILED
            snapshot.status_msg = message
            snapshot.save(update_fields=["status", "status_msg"])


def tail_source(context, data_id_ref):
    """取样使用DataId；把V4原文数组还原为审计value结构，不推断topic或时间。"""
    params = resource_params(context, data_id_ref, kind="DataId")
    result = api.bk_base_v4.data_id_tail(namespace=params["namespace"], name=params["name"])
    if not isinstance(result, list) or not all(isinstance(value, str) for value in result):
        raise BKBaseResourceMappingError(message="Unsupported Kafka sample response")
    return [{"value": value} for value in result]


def create_deploy_plan(request_data=None, **params):
    """V4关键契约待B04，V3调用保持。"""
    return pending_call("create_deploy_plan", "B04", request_data, **params)


def update_deploy_plan(request_data=None, **params):
    """V4关键契约待B04，V3调用保持。"""
    return pending_call("update_deploy_plan", "B04", request_data, **params)


def _find_source(context, raw_data_id):
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


def get_rawdata_list(**params):
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_rawdata_list(**params)
    context = get_bkbase_context()
    rows = _source_list(api.bk_base_v4.data_source_list(**resource_params(context)))
    name = str(params.get("raw_data_name__icontains", "")).lower()
    return [
        _legacy_source(r)
        for r in rows
        if name in r.get("spec", {}).get("basic_info", {}).get("data_source_name", "").lower()
        and (
            params.get("bk_biz_id") is None
            or str(r.get("spec", {}).get("basic_info", {}).get("bk_biz_id")) == str(params["bk_biz_id"])
        )
    ]


def get_rawdata_tail(**params):
    if get_bkbase_version() == BKBaseVersion.V3:
        return api.bk_base.get_rawdata_tail(**params)
    context = get_bkbase_context()
    resource = _find_source(context, params["bk_data_id"])
    data_id = resource.get("spec", {}).get("data_id") or {}
    ref = {
        "kind": "DataId",
        "tenant": data_id.get("tenant", context["tenant"]),
        "namespace": data_id.get("namespace"),
        "name": data_id.get("name"),
    }
    return tail_source(context, ref)
