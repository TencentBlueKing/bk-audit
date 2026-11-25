"""创建并观察审计自身的 V4 IAM 系统快照。

每类配置保存唯一创建意图，平台调用在短事务之外进行。
未知写结果只读回原引用，全部下游就绪后才首次启动来源。
"""
import json
import time
import uuid
from copy import deepcopy
from typing import Callable
from urllib.parse import urlsplit

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction

from services.web.bkbase import clean, metadata, source, storage
from services.web.bkbase.common import operation_result, resource_params
from services.web.bkbase.constants import (
    BKBASE_V4_PULL_RESULTS_PATH,
    CleanRole,
    TaskState,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.snapshot.system import v4 as bindings
from services.web.databus.collector.snapshot.system.clean import PullCleanHandler
from services.web.databus.collector.snapshot.system.pull import HttpPullHandler

OWNER_ANNOTATION = "bkaudit_iam_operation"


def _get_snapshot_resource_or_none(getter: Callable, **params) -> dict | None:
    """命名快照详情仅接受 SDK 验证过的 HTTP 200 原生业务缺失，网关 404 仍抛错。"""
    try:
        return getter(**params)
    except APIRequestError as error:
        if getattr(error, "http_status", None) == 200 and getattr(error, "resource_not_found", False):
            return None
        raise


def _proven_not_dispatched(error: APIRequestError) -> bool:
    """只接受直达写端保留的原始网关路由拒绝证据，不解析异常消息。"""
    return getattr(error, "http_status", None) == 404 and getattr(error, "gateway_error_code", None) == "1640401"


def _create_config(kind, context):
    config = getattr(settings, "BKBASE_V4_SYSTEM_SNAPSHOT_CREATE", {})
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except (TypeError, ValueError) as error:
            raise BKBaseResourceMappingError(message="Invalid IAM V4 create configuration JSON") from error
    entry = bindings._mapping(config).get(kind)
    if entry is None:
        return None
    return bindings._explicit_ref(context, bindings._mapping(entry).get("redis"), "Redis", in_project=False)


def _save(kind, context, expected, record):
    config_key, _ = bindings.SYSTEM_SNAPSHOT_KEYS[kind]
    with transaction.atomic():
        config = bindings._locked_config(config_key)
        root = bindings._mapping({} if config.config_value is None else config.config_value)
        if bindings._scoped_binding(root, context) != expected:
            raise BKBaseResourceMappingError(message="IAM V4 creation changed concurrently; rerun the command")
        bindings._store_binding(config, root, context, deepcopy(record))
    return record


def _params(kind, operation):
    return HttpPullHandler(kind, raw_data_name=operation["name"]).build_params()


def _input_digest(kind, params, redis, *, report_config=None):
    template = PullCleanHandler(
        None,
        params["access_raw_data"]["raw_data_name"],
        kind,
        pull_report_config={"data_path": None} if report_config is None else report_config,
    ).config
    return source._replay_digest(
        {
            "request": params["access_conf_info"],
            "biz_id": params["bk_biz_id"],
            "raw_data": params["access_raw_data"],
            "schema": template["fields"],
            "rules": template["json_config"],
            "redis": redis,
        }
    )


def _planned_pull_report(kind, params, operation, redis):
    """用已登记摘要恢复旧版列表/本版完整响应计划，不重签旧意图或猜自定义路径。"""
    for path in (None, BKBASE_V4_PULL_RESULTS_PATH):
        report = {"data_path": path}
        if _input_digest(kind, params, redis, report_config=report) == operation.get("input_digest"):
            return report
    raise BKBaseResourceMappingError(message="IAM V4 creation inputs or PULL input shape changed; preserve its claim")


def _new_record(kind, context, redis):
    operation_id = uuid.uuid4().hex
    # BKBase 资源名最多 60 字符；缩短类型前缀，给最长的 _source 后缀留空间并保留完整 UUID。
    name_kind = "rtype" if kind == "resource_type" else kind
    name = f"audit_iam_{name_kind}_{operation_id}"
    refs = {
        key: {
            "kind": resource_kind,
            "tenant": context["tenant"],
            "namespace": context["namespace"],
            "name": name + suffix,
        }
        for key, resource_kind, suffix in (
            ("connection", "DataConn", "_conn"),
            ("data_source", "DataSource", "_source"),
            ("clean", "Clean", "_clean"),
            ("storage", "DataStorage", "_redis"),
        )
    }
    operation = {
        "operation_id": operation_id,
        "name": name,
        "logical_id": f"{settings.DEFAULT_BK_BIZ_ID}_{name}",
        "revision": int(time.time() * 1000),
        "redis": redis,
        "refs": refs,
        "steps": {},
    }
    params = _params(kind, operation)
    operation["input_digest"] = _input_digest(kind, params, redis)
    return {"snapshot_type": kind, "creation": operation, "ready": False}


def _owned(context, operation, ref, resource):
    if source._binding_resource_ref(context, resource, ref["kind"]) != ref:
        raise BKBaseResourceMappingError(message="IAM V4 created resource identity changed")
    if resource["metadata"].get("annotations", {}).get(OWNER_ANNOTATION) != operation["operation_id"]:
        raise BKBaseResourceMappingError(message="IAM V4 resource belongs to another creation operation")
    return resource


def _matches_data_source_spec(desired, actual):
    """回读只核对业务归属、连接和拉取契约，平台补充字段不影响续跑。"""
    report = actual.get("report_config")
    if not isinstance(report, dict):
        return False
    wanted = desired["report_config"]
    for expected, observed, fields in (
        (desired, actual, ("desired_status",)),
        (desired["basic_info"], actual.get("basic_info"), ("bk_biz_id",)),
        (desired["data_conn"], actual.get("data_conn"), ("kind", "tenant", "namespace", "name")),
        (wanted, report, ("type", "http_mode", "data_conn_name", "method", "path", "body", "data_path")),
        (wanted["increment_field"], report.get("increment_field"), ("type", "time_format")),
        (wanted["pagination"], report.get("pagination"), ("start_offset", "limit", "total_path")),
    ):
        # data_path 缺失和显式 null 的含义不同，不能当作同一个值。
        if not isinstance(observed, dict) or any(
            key not in observed or observed[key] != expected[key] for key in fields
        ):
            return False
    return True


def _matches_spec(kind, desired, resource):
    if kind == "DataSource":
        return _matches_data_source_spec(desired, resource["spec"])
    actual, wanted = deepcopy(resource["spec"]), deepcopy(desired)
    if kind == "DataConn":
        headers = wanted["conn_info"]["headers"]
        if not source._pull_headers_match(headers, resource, preserve_encrypted_auth=True):
            return False
        wanted["conn_info"]["headers"].pop("Authorization", None)
        actual["conn_info"]["headers"].pop("Authorization", None)
    if kind == "Clean":
        if not clean._same_clean_rules(wanted.pop("rules"), actual.pop("rules", None), strict_types=True):
            return False
    return source._replay_digest(storage._merge_spec(actual, wanted)) == source._replay_digest(actual)


def _ready(resource, ref, expected_state=None):
    status = resource.get("status")
    phase = status.get("phase") if isinstance(status, dict) else None
    if phase in ("Failed", "Terminating"):
        raise BKBaseResourceMappingError(message=f"IAM V4 created {ref['kind']} is {phase}; inspect the same resource")
    if phase != "Ok":
        return False
    if expected_state is None:
        return True
    state = operation_result(resource, ref, "observe")["task_state"]
    if state != expected_state:
        if state in (TaskState.RUNNING, TaskState.STOPPED):
            raise BKBaseResourceMappingError(message=f"IAM V4 created {ref['kind']} is in an unexpected state")
        return False
    return True


def _ensure_resource(kind, context, record, key, desired, getter, creator, expected_state=None):
    """先按原引用观察，仅有明确未下发证据时通过 CAS 认领下一次原样创建。"""
    operation = record["creation"]
    ref = operation["refs"][key]
    step = operation["steps"].get(key)
    params = resource_params(context, ref, kind=ref["kind"])
    current = _get_snapshot_resource_or_none(getter, **params)
    digest = source._replay_digest(desired)
    if step is None:
        if current is not None:
            raise BKBaseResourceMappingError(message=f"IAM V4 {ref['kind']} exists without this creation claim")
    else:
        if step.get("target_digest") != digest:
            raise BKBaseResourceMappingError(message=f"IAM V4 {ref['kind']} creation inputs changed")
        if current is not None:
            _owned(context, operation, ref, current)
            if not _matches_spec(ref["kind"], desired, current):
                raise BKBaseResourceMappingError(message=f"IAM V4 created {ref['kind']} no longer matches its target")
            return (current if _ready(current, ref, expected_state) else None), record
        if step.get("not_dispatched", False) is not True:
            logger.warning(
                "IAM V4 创建结果未确认，仅观察原 %s：tenant=%s namespace=%s name=%s",
                ref["kind"],
                ref["tenant"],
                ref["namespace"],
                ref["name"],
            )
            return None, record
    operation = deepcopy(operation)
    operation["steps"][key] = {
        **(step or {}),
        "target_digest": digest,
        "attempt": (step or {}).get("attempt", 0) + 1,
        "not_dispatched": False,
    }
    record = _save(kind, context, record, {**record, "creation": operation})
    metadata_value = {**params, "annotations": {OWNER_ANNOTATION: operation["operation_id"]}}
    try:
        creator(
            tenant=context["tenant"], namespace=context["namespace"], metadata=metadata_value, spec=desired, status=None
        )
    except APIRequestError as error:
        if _proven_not_dispatched(error):
            operation = deepcopy(operation)
            operation["steps"][key]["not_dispatched"] = True
            _save(kind, context, record, {**record, "creation": operation})
        raise
    return None, record


def _source_spec(params, operation, *, report_config=None):
    (scope,) = params["access_conf_info"]["resource"]["scope"]
    url = urlsplit(scope["url"])
    if url.scheme not in ("http", "https") or not url.netloc or url.username or url.password or url.fragment:
        raise BKBaseResourceMappingError(message="IAM V4 callback URL is invalid")
    base = f"{url.scheme}://{url.netloc}"
    if not url.path:
        scope = {**scope, "url": base + "/" + ("?" + url.query if url.query else "")}
        params = deepcopy(params)
        params["access_conf_info"]["resource"]["scope"] = [scope]
    connection = {
        "data_conn_alias": operation["refs"]["connection"]["name"],
        "conn_info": {"type": "rest_api", "url": base, "healthcheck_url": "/", "headers": deepcopy(scope["headers"])},
    }
    report = source.build_pull_report_config(params, operation["refs"]["connection"]["name"], base)
    if report_config is not None:
        report["data_path"] = source.pull_report_data_path(report_config)
    source._set_pull_replay_history(report)
    spec = {
        "basic_info": {
            "data_source_name": operation["refs"]["data_source"]["name"],
            "data_source_alias": params["access_raw_data"]["raw_data_alias"],
            "data_encoding": "UTF-8",
            "bk_biz_id": params["bk_biz_id"],
            "time_zone": "Asia/Shanghai",
            "tags": [],
            "description": params["description"],
        },
        "data_conn": operation["refs"]["connection"],
        "desired_status": "Stopped",
        "report_config": report,
    }
    return connection, spec


def _verify_activation_binding(context, record, current):
    """启用意图不能重绑已登记的 RawData、DataId 或 DataSource。"""
    observed = source._source_binding(context, current, record["source_raw_data_id"])
    if any(record.get(key) != value for key, value in observed.items()):
        raise BKBaseResourceMappingError(message="IAM V4 Source binding changed after its activation claim")


def _running_source(context, record):
    """观察目标态；只有原配置确认未下发且已停稳时才允许继续复查下游。"""
    operation = record["creation"]
    ref = operation["refs"]["data_source"]
    current = _get_snapshot_resource_or_none(api.bk_base_v4.data_source_get, **resource_params(context, ref))
    if current is None:
        return None
    _owned(context, operation, ref, current)
    _verify_activation_binding(context, record, current)
    intent = operation["source_start"]
    digest = source._replay_resource_digest(current)
    if digest == intent["target_digest"]:
        expected_state = TaskState.RUNNING
    elif not intent.get("before_digest"):
        return None
    elif digest != intent["before_digest"]:
        raise BKBaseResourceMappingError(message="IAM V4 Source changed after its activation claim")
    elif intent.get("not_dispatched", False) is True:
        expected_state = TaskState.STOPPED
    else:
        return None
    if not _ready(current, ref):
        return None
    return current if operation_result(current, ref, "observe")["task_state"] == expected_state else None


def _request_source_activation(kind, context, record, current):
    """下游复核后重读原来源，通过本地 CAS 认领并发送唯一一次启用请求。"""
    operation = record["creation"]
    intent = operation.get("source_start")
    before_digest = source._replay_resource_digest(current)
    desired = deepcopy(current)
    desired["spec"]["desired_status"] = "Running"
    target_digest = source._replay_resource_digest(desired)
    if intent and (
        intent.get("not_dispatched", False) is not True
        or before_digest != intent.get("before_digest")
        or target_digest != intent["target_digest"]
    ):
        raise BKBaseResourceMappingError(message="IAM V4 Source activation intent changed")
    ref = operation["refs"]["data_source"]
    latest = _get_snapshot_resource_or_none(api.bk_base_v4.data_source_get, **resource_params(context, ref))
    if latest is None:
        return "DataSource"
    _owned(context, operation, ref, latest)
    _verify_activation_binding(context, record, latest)
    latest_digest = source._replay_resource_digest(latest)
    if latest_digest != before_digest:
        if latest_digest == target_digest:
            return "DataSource"
        raise BKBaseResourceMappingError(message="IAM V4 Source changed before its activation request")
    if not _ready(latest, ref) or operation_result(latest, ref, "observe")["task_state"] != TaskState.STOPPED:
        return "DataSource"
    desired = deepcopy(latest)
    desired["spec"]["desired_status"] = "Running"
    operation = {
        **operation,
        "source_start": {
            **(intent or {}),
            "target_digest": target_digest,
            "before_digest": before_digest,
            "attempt": (intent or {}).get("attempt", 0) + 1,
            "not_dispatched": False,
        },
    }
    record = _save(kind, context, record, {**record, "creation": operation})
    try:
        api.bk_base_v4.data_source_update(
            **resource_params(context, ref),
            metadata=desired["metadata"],
            spec=desired["spec"],
            status=None,
        )
    except APIRequestError as error:
        if _proven_not_dispatched(error):
            operation = {
                **operation,
                "source_start": {**operation["source_start"], "not_dispatched": True},
            }
            _save(kind, context, record, {**record, "creation": operation})
        raise
    return "DataSource"


def _advance(kind, context, record, redis):
    if transaction.get_connection().in_atomic_block:
        raise BKBaseResourceMappingError(message="IAM V4 creation requires no outer database transaction")
    operation = record["creation"]
    params = _params(kind, operation)
    if operation.get("redis") != redis:
        raise BKBaseResourceMappingError(
            message="IAM V4 creation configuration changed; preserve and inspect its resources"
        )
    planned_report = _planned_pull_report(kind, params, operation, redis)
    sdk = api.bk_base_v4
    connection_spec, source_spec = _source_spec(params, operation, report_config=planned_report)
    connection, record = _ensure_resource(
        kind, context, record, "connection", connection_spec, sdk.data_conn_get, sdk.data_conn_create
    )
    if connection is None:
        return "DataConn"
    if operation.get("source_start"):
        current = _running_source(context, record)
    else:
        current, record = _ensure_resource(
            kind,
            context,
            record,
            "data_source",
            source_spec,
            sdk.data_source_get,
            sdk.data_source_create,
            TaskState.STOPPED,
        )
    if current is None:
        return "DataSource"
    source_binding = source._source_binding(context, current, current["metadata"].get("labels", {}).get("raw_data_id"))
    updates = {**source_binding, "redis": redis}
    if any(record.get(key) != value for key, value in updates.items()):
        record = _save(kind, context, record, {**record, **updates})
    operation = record["creation"]
    config = PullCleanHandler(
        record["source_raw_data_id"],
        operation["name"],
        kind,
        pull_report_config=current["spec"].get("report_config"),
    ).config
    clean_spec = clean.build_clean_spec(
        config, data_ref=record["data_id"], logical_id=operation["logical_id"], rt_owner=True
    )
    clean_spec.update(
        config_revision=operation["revision"], deploy_revision=operation["revision"], desired_status="Running"
    )
    cleaner, record = _ensure_resource(
        kind, context, record, "clean", clean_spec, sdk.clean_get, sdk.clean_create, TaskState.RUNNING
    )
    if cleaner is None:
        return "Clean"
    table_info = bindings._result_table_info(sdk, context, operation["logical_id"])
    if table_info is None:
        return "ResultTable"
    table, logical_id = metadata.result_table_identity(context, table_info)
    if logical_id != operation["logical_id"] or table["namespace"] != context["namespace"]:
        raise BKBaseResourceMappingError(message="IAM V4 Clean output resolved to another result table")
    updates = {"clean": operation["refs"]["clean"], "result_table_id": logical_id, "result_table": table}
    if any(record.get(key) != value for key, value in updates.items()):
        if operation.get("source_start"):
            raise BKBaseResourceMappingError(message="IAM V4 ResultTable changed after its activation claim")
        record = _save(kind, context, record, {**record, **updates})
    storage_spec = storage.convert_storage_config(
        {"expires": "-1", "fields": PullCleanHandler.get_fields(kind), "config": {"storage_type": "join"}}
    )
    storage_spec["tableInfo"].update(source=table, storage=redis)
    stored, record = _ensure_resource(
        kind, context, record, "storage", storage_spec, sdk.data_storage_get, sdk.data_storage_create, TaskState.RUNNING
    )
    if stored is None:
        return "DataStorage"
    redis_binding = bindings._verified_redis_binding(table_info, table, redis)
    if redis_binding is None:
        return "RedisBinding"
    operation = record["creation"]
    intent = operation.get("source_start")
    if not intent or source._replay_resource_digest(current) != intent["target_digest"]:
        return _request_source_activation(kind, context, record, current)
    keys = bindings._redis_keys(kind, stored["spec"]["taskFieldSetting"]["key_fields"])
    final = {
        **record,
        "creation": {**operation, "completed": True},
        "storages": {"redis": operation["refs"]["storage"]},
        "clean_role": CleanRole.OWNER,
        "redis_binding": redis_binding,
        "redis_key_fields": list(keys),
        "ready": True,
    }
    _save(kind, context, record, final)
    return None


def ensure_system_snapshot(kind, migration_binding=None):
    """Route explicit migration, ongoing creation and enabled new creation through the real entrypoints."""
    context = bindings._system_context()
    config_key, _ = bindings.SYSTEM_SNAPSHOT_KEYS[kind]
    current = bindings._scoped_binding(bindings._read_config(config_key), context)
    creation = current.get("creation") if isinstance(current, dict) else None
    if migration_binding is not None:
        if creation and not creation.get("completed"):
            raise BKBaseResourceMappingError(message="IAM V4 creation is active; migration cannot replace it")
        return bindings.ensure_system_snapshot(kind, migration_binding)
    if (current is not None and not creation) or (creation and creation.get("completed")):
        return bindings.ensure_system_snapshot(kind)
    redis = _create_config(kind, context)
    if redis is None:
        if creation:
            raise BKBaseResourceMappingError(message="IAM V4 creation target configuration was removed")
        return bindings.ensure_system_snapshot(kind)
    if current is None:
        record = _new_record(kind, context, redis)
        current = _save(kind, context, None, record)
    return _advance(kind, context, current, redis)
