"""创建并观察审计自身的 V4 IAM 系统快照。

每类配置保存唯一创建意图，平台调用在短事务之外进行。
未知写结果只读回原引用，全部下游就绪后才首次启动来源。
"""
import json
import time
import uuid
from copy import deepcopy
from urllib.parse import urlsplit

from bk_resource import api
from django.conf import settings
from django.db import transaction

from services.web.bkbase import clean, metadata, source, storage
from services.web.bkbase.common import (
    get_resource_or_none,
    operation_result,
    resource_params,
)
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
    name = f"audit_iam_{kind}_{operation_id}"
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


def _matches_spec(kind, desired, resource):
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
    operation = record["creation"]
    ref = operation["refs"][key]
    step = operation["steps"].get(key)
    params = resource_params(context, ref, kind=ref["kind"])
    current = get_resource_or_none(getter, **params)
    digest = source._replay_digest(desired)
    if step is None:
        if current is not None:
            raise BKBaseResourceMappingError(message=f"IAM V4 {ref['kind']} exists without this creation claim")
        operation = deepcopy(operation)
        operation["steps"][key] = {"target_digest": digest}
        record = _save(kind, context, record, {**record, "creation": operation})
        metadata_value = {**params, "annotations": {OWNER_ANNOTATION: operation["operation_id"]}}
        creator(
            tenant=context["tenant"], namespace=context["namespace"], metadata=metadata_value, spec=desired, status=None
        )
        return None, record
    if step.get("target_digest") != digest:
        raise BKBaseResourceMappingError(message=f"IAM V4 {ref['kind']} creation inputs changed")
    if current is None:
        return None, record
    _owned(context, operation, ref, current)
    if not _matches_spec(ref["kind"], desired, current):
        raise BKBaseResourceMappingError(message=f"IAM V4 created {ref['kind']} no longer matches its target")
    return (current if _ready(current, ref, expected_state) else None), record


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


def _running_source(context, record):
    operation = record["creation"]
    ref = operation["refs"]["data_source"]
    current = get_resource_or_none(api.bk_base_v4.data_source_get, **resource_params(context, ref))
    if current is None:
        return None
    _owned(context, operation, ref, current)
    if source._replay_resource_digest(current) != operation["source_start"]["target_digest"]:
        raise BKBaseResourceMappingError(message="IAM V4 Source changed after its activation claim")
    return current if _ready(current, ref, TaskState.RUNNING) else None


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
    if not operation.get("source_start"):
        desired = deepcopy(current)
        desired["spec"]["desired_status"] = "Running"
        operation = {**operation, "source_start": {"target_digest": source._replay_resource_digest(desired)}}
        record = _save(kind, context, record, {**record, "creation": operation})
        sdk.data_source_update(
            **resource_params(context, operation["refs"]["data_source"]),
            metadata=desired["metadata"],
            spec=desired["spec"],
            status=None,
        )
        return "DataSource"
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
