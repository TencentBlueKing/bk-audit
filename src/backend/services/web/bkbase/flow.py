"""管理普通规则完整计算图及声明式运行流程。

命名Flow与MCP数字ID分别保存；后台任务推进停止、图更新、运行观测。
仅资源调和成功不能认定实际运行，未知引擎响应保持未就绪。
"""

from copy import deepcopy
from uuid import uuid4

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from bk_resource.settings import bk_resource_settings
from django.db import transaction

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.exceptions import LockError
from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.bkbase import metadata as metadata_service
from services.web.bkbase import storage as storage_service
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    get_resource_or_none,
    legacy_bulk,
    legacy_call,
    operation_result,
    pending_call,
    resource_lock,
    resource_params,
    stable_name,
)
from services.web.bkbase.constants import (
    BKBASE_V4_FLOW_CONFIG,
    BKBASE_V4_MAX_POLLS,
    BKBaseVersion,
    TaskState,
)
from services.web.bkbase.exceptions import (
    BKBaseCapabilityNotReady,
    BKBaseOperationSuperseded,
    BKBaseResourceMappingError,
)
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


def validate_graph(nodes):
    """整图节点名必须唯一，所有连边都必须存在。"""
    names = [n.get("name") for n in nodes]
    if not names or any(not n for n in names) or len(set(names)) != len(names):
        raise BKBaseResourceMappingError(message="Invalid or duplicate Flow node names")
    for node in nodes:
        inputs = node.get("inputs", []) + ([node["input"]] if node.get("input") else [])
        if any(source not in names for source in inputs):
            raise BKBaseResourceMappingError(message=f"Dangling Flow input for {node['name']}")


def build_rule_flow(strategy, *, rt_metadata, binding_map):
    """把已确认的V4节点配置组成稳定图，不通过旧节点API拼图。"""
    sources = binding_map["sources"]
    ids = [r["result_table_id"] for r in rt_metadata]
    if set(ids) != set(sources):
        raise BKBaseResourceMappingError(message="Flow inputs do not match RT metadata")
    nodes = []
    for rt_id in ids:
        node = deepcopy(sources[rt_id])
        node["name"] = stable_name("src", rt_id)
        nodes.append(node)
    sql = deepcopy(binding_map["sql_node"])
    sql.update(
        name=stable_name("sql", strategy.strategy_id),
        inputs=[n["name"] for n in nodes],
        biz_id=binding_map["biz_id"],
        output=binding_map["output"],
    )
    nodes.append(sql)
    for storage in binding_map.get("storages", []):
        node = deepcopy(storage)
        node["input"] = sql["name"]
        nodes.append(node)
    validate_graph(nodes)
    return {
        "alias": ("Audit " + strategy.strategy_name)[:100],
        "description": "",
        "maintainers": [bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME],
        "operation_config": deepcopy(binding_map.get("operation_config", {"start_position": "continue"})),
        "nodes": nodes,
    }


def _save_binding(strategy, patch, *, remove=(), expected_operation_id=None):
    """短事务合并V4绑定并校验原操作身份，保留旧ID和其他backend_data。"""
    with transaction.atomic():
        current = Strategy.objects.select_for_update().get(pk=strategy.pk)
        backend = deepcopy(current.backend_data or {})
        binding = backend.setdefault("bkbase_v4", {})
        if expected_operation_id is not None and binding.get("operation_id") != expected_operation_id:
            raise BKBaseOperationSuperseded()
        binding.update(deepcopy(patch))
        for key in remove:
            binding.pop(key, None)
        current.backend_data = backend
        current.save(update_record=False, update_fields=["backend_data"])
    strategy.backend_data = backend
    return binding


def _save_operation_binding(context, strategy, patch, *, remove=()):
    """异步推进的每次绑定写入都校验原操作，不能污染新操作阶段和预算。"""
    return _save_binding(strategy, patch, remove=remove, expected_operation_id=context.get("operation_id"))


def resolve_engine_flow_id(context, ref, *, allow_pending=False):
    """按当前MCP项目和精确名称唯一匹配，分页查全后再判定。"""
    resource_params(context, ref, kind="Flow")
    if not context.get("mcp_project_id"):
        raise BKBaseResourceMappingError(message="Missing verified MCP project ID")
    rows, page = [], 1
    while True:
        payload = api.bk_base_v4.flows(
            project_id=int(context["mcp_project_id"]), search=ref["name"], page=page, page_size=100
        )
        if isinstance(payload, list):
            rows.extend(payload)
            break
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("results"), list)
            or not isinstance(payload.get("count"), int)
        ):
            raise BKBaseResourceMappingError(message="Unsupported MCP Flow list response")
        rows.extend(payload["results"])
        if len(rows) >= payload["count"]:
            break
        if not payload["results"]:
            raise BKBaseResourceMappingError(message="Incomplete MCP Flow list")
        page += 1
    matches = [r for r in rows if r.get("flow_name") == ref["name"]]
    if not matches and allow_pending:
        return None
    if len(matches) != 1 or not isinstance(matches[0].get("flow_id"), int):
        raise BKBaseResourceMappingError(message="MCP Flow ID missing or ambiguous")
    return matches[0]["flow_id"]


def get_rule_flow_status(context, strategy):
    """合并CR与MCP实际观测，未识别状态不能当成运行成功。"""
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    ref = binding.get("flow") or {}
    params = resource_params(context, ref, kind="Flow")
    resource = api.bk_base_v4.flow_get(**params)
    result = operation_result(resource, ref, "observe")
    if result["resource_phase"] != "Ok":
        return result
    engine_id = resolve_engine_flow_id(context, ref, allow_pending=True)
    if engine_id is None:
        return result
    actual = api.bk_base_v4.flow_status(flow_id=engine_id)
    deploy = api.bk_base_v4.flow_latest_deploy(flow_id=engine_id, process_logs=1)
    engine_state = actual.get("flow_status")
    deploy_state = deploy.get("status")
    if engine_state == "failure" or deploy_state == "failure":
        result["task_state"] = TaskState.FAILED
        if not result.get("message"):
            result["message"] = (
                "Flow deployment reported failure." if deploy_state == "failure" else "Flow engine reported failure."
            )
    elif deploy_state == "success":
        result["task_state"] = {"running": TaskState.RUNNING, "no-start": TaskState.STOPPED}.get(engine_state)
    result.update(engine_flow_id=engine_id, engine=actual, deployment=deploy)
    return result


def operate_rule_flow(context, strategy, *, action, start_position=None):
    """启停由CR单一入口控制，稳定无配置变更的重启才用MCP。"""
    ref = (strategy.backend_data or {}).get("bkbase_v4", {}).get("flow") or {}
    params = resource_params(context, ref, kind="Flow")
    if start_position is not None and start_position not in ("continue", "from_head", "from_tail"):
        raise BKBaseResourceMappingError(message="Invalid Flow consumption position")
    if action == "restart":
        if start_position is not None:
            current = api.bk_base_v4.flow_get(**params)
            if current["spec"].get("operation_config", {}).get("start_position", "continue") != start_position:
                spec = deepcopy(current["spec"])
                spec.setdefault("operation_config", {})["start_position"] = start_position
                _save_operation_binding(context, strategy, {"pending_spec": spec, "operation": "wait_stopped"})
                return operate_rule_flow(context, strategy, action="stop")
        observed = get_rule_flow_status(context, strategy)
        if observed["task_state"] != TaskState.RUNNING:
            return observed
        engine_id = observed["engine_flow_id"]
        api.bk_base_v4.flow_restart(flow_id=engine_id, consuming_mode=start_position or "continue")
        _save_operation_binding(
            context, strategy, {"restart_baseline": observed.get("deployment", {}), "restart_waiting": True}
        )
        return {**observed, "task_state": None, "requested_action": "restart"}
    if action not in ("start", "stop"):
        raise BKBaseResourceMappingError(message="Unsupported Flow action")
    if start_position is not None and start_position not in ("continue", "from_head", "from_tail"):
        raise BKBaseResourceMappingError(message="Invalid Flow consumption position")
    with resource_lock(context, ref):
        current = api.bk_base_v4.flow_get(**params)
        metadata, spec = deepcopy(current["metadata"]), deepcopy(current["spec"])
        metadata.setdefault("annotations", {})["task_stopped"] = "true" if action == "stop" else "false"
        if start_position is not None:
            spec.setdefault("operation_config", {})["start_position"] = start_position
        result = api.bk_base_v4.flow_update(**params, metadata=metadata, spec=spec, status=None)
    return operation_result(result, ref, action)


def _merged_spec(old, desired, managed):
    """保留非本次修改字段和非审计管理的节点，检查删除产生的悬空引用。"""
    spec = deepcopy(old)
    existing = {n["name"]: n for n in old.get("nodes", [])}
    nodes = [{**deepcopy(existing.get(n["name"], {})), **deepcopy(n)} for n in desired["nodes"]]
    nodes.extend(
        deepcopy(n) for name, n in existing.items() if name not in managed and name not in {x["name"] for x in nodes}
    )
    spec.update({k: deepcopy(v) for k, v in desired.items() if k not in ("nodes", "operation_config")})
    spec["nodes"] = nodes
    spec.setdefault("operation_config", {}).update(deepcopy(desired.get("operation_config", {})))
    validate_graph(nodes)
    return spec


def apply_rule_flow(context, strategy, spec):
    """声明完整图；已有运行图先停止，后续由观测任务继续更新。"""
    validate_graph(spec["nodes"])
    _save_operation_binding(context, strategy, {"requested_action": "start"})
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    ref = binding.get("flow")
    if not ref:
        if (strategy.backend_data or {}).get("flow_id"):
            raise BKBaseResourceMappingError(message="Existing V3 Flow requires explicit migration binding")
        ref = {
            "kind": "Flow",
            "tenant": context["tenant"],
            "namespace": context["namespace"],
            "name": stable_name("flow", strategy.strategy_id),
        }
        _save_operation_binding(context, strategy, {"flow": ref, "pending_spec": spec, "operation": "create"})
    params = resource_params(context, ref, kind="Flow")
    with resource_lock(context, ref):
        current = get_resource_or_none(api.bk_base_v4.flow_get, **params)
        if current is None:
            result = api.bk_base_v4.flow_create(
                tenant=params["tenant"],
                namespace=params["namespace"],
                metadata={**params, "annotations": {"task_stopped": "false"}},
                spec=spec,
                status=None,
            )
            _save_operation_binding(
                context,
                strategy,
                {"managed_nodes": [n["name"] for n in spec["nodes"]], "operation": "wait_running"},
                remove=["pending_spec"],
            )
            return operation_result(result, ref, "create")
    observed = get_rule_flow_status(context, strategy)
    merged = _merged_spec(current["spec"], spec, binding.get("managed_nodes", []))
    if merged == current["spec"] and current["metadata"].get("annotations", {}).get("task_stopped") != "true":
        _save_operation_binding(context, strategy, {"operation": "wait_running"}, remove=["pending_spec"])
        return observed
    if observed["task_state"] != TaskState.STOPPED:
        _save_operation_binding(context, strategy, {"pending_spec": spec, "operation": "wait_stopped"})
        if current["metadata"].get("annotations", {}).get("task_stopped") != "true":
            return operate_rule_flow(context, strategy, action="stop")
        return observed
    with resource_lock(context, ref):
        current = api.bk_base_v4.flow_get(**params)
        merged = _merged_spec(current["spec"], spec, binding.get("managed_nodes", []))
        metadata = deepcopy(current["metadata"])
        metadata.setdefault("annotations", {})["task_stopped"] = "false"
        result = api.bk_base_v4.flow_update(**params, metadata=metadata, spec=merged, status=None)
        _save_operation_binding(
            context,
            strategy,
            {"managed_nodes": [n["name"] for n in spec["nodes"]], "operation": "wait_running"},
            remove=["pending_spec"],
        )
    return operation_result(result, ref, "update")


def advance_rule_flow(context, strategy):
    """现有任务每次仅推进一步，避免在Web请求中阻塞等待。"""
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    if binding.get("pending_spec") and binding.get("requested_action") != "stop":
        result = apply_rule_flow(context, strategy, binding["pending_spec"])
        if result["task_state"] == TaskState.FAILED:
            return result
    return get_rule_flow_status(context, strategy)


def dataflow_batch_status_list(request_data=None, **params):
    """V4关键契约待B09，V3调用保持。"""
    return pending_call("dataflow_batch_status_list", "B09", request_data, **params)


def get_alert_configs(request_data=None, **params):
    """V4关键契约待B13，V3调用保持。"""
    return pending_call("get_alert_configs", "B13", request_data, **params)


def edit_alert_configs(request_data=None, **params):
    """V4关键契约待B13，V3调用保持。"""
    return pending_call("edit_alert_configs", "B13", request_data, **params)


def create_flow(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("create_flow", request_data, **params)


def create_flow_node(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("create_flow_node", request_data, **params)


def update_flow_node(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("update_flow_node", request_data, **params)


def delete_flow_node(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("delete_flow_node", request_data, **params)


def delete_flow_node_bulk(requests, ignore_exceptions=False):
    """V3批量原语，V4禁止逐节点或缺引用操作。"""
    return legacy_bulk("delete_flow_node", requests, ignore_exceptions=ignore_exceptions)


def get_flow_graph(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("get_flow_graph", request_data, **params)


def start_flow(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("start_flow", request_data, **params)


def stop_flow(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("stop_flow", request_data, **params)


def restart_flow(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("restart_flow", request_data, **params)


def get_flow_deploy_data(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("get_flow_deploy_data", request_data, **params)


def _expires(value):
    text = str(value)
    return text if text.endswith("d") or text == "-1" else text + "d"


def _storage_node(context, strategy, config, profile):
    """将审计存储节点转换为已注册的V4集群引用。"""
    kinds = {
        "elastic_storage": ("es", "EsStorageNode"),
        "doris": ("doris", "DorisStorageNode"),
        "hdfs_storage": ("hdfs", "HdfsStorageNode"),
        "queue_storage": ("kafka", "QueueStorageNode"),
    }
    if config["node_type"] not in kinds:
        raise BKBaseResourceMappingError(message="Unsupported audit storage node type")
    storage_type, kind = kinds[config["node_type"]]
    ref = storage_service.resolve_storage_cluster(
        context, audit_namespace=strategy.namespace, storage_type=storage_type, legacy_cluster_id=config["cluster"]
    )
    result = {"kind": kind, "name": stable_name("store", strategy.strategy_id, storage_type), "storage": ref}
    if storage_type == "es":
        table = config.get("physical_table_name")
        alias = None
        if table:
            alias = (
                {"TimeBased": {"format": table.replace("{yyyyMMdd}", "%Y%m%d"), "timezone": 8}}
                if "{yyyyMMdd}" in table
                else {"Fixed": table}
            )
        result.update(
            write_alias=alias,
            expires=_expires(config["expires"]),
            replicas=config.get("replicas"),
            unique_field_list=config.get("storage_keys", []),
            analyzed_fields=config.get("analyzed_fields", []),
            doc_value_fields=config.get("doc_values_fields", []),
            json_field_list=config.get("json_fields", []),
            flattened_fields=config.get("flattened_fields", []),
        )
    elif storage_type == "doris":
        database = profile.get("doris_databases", {}).get(ref["name"])
        if not database:
            raise BKBaseResourceMappingError(message="V4 Doris database must be explicitly configured")
        table = config.get("physical_table_name")
        if table and "{" in table:
            raise BKBaseResourceMappingError(message="V4 Doris table template requires an explicit verified mapping")
        result["storage_config"] = {
            "db": database,
            "table": table,
            "table_type": "duplicate_table",
            "storage_keys": config.get("storage_keys", []),
            "json_fields": config.get("json_fields", []),
            "original_json_fields": config.get("original_json_fields", []),
            "expires": _expires(config["expires"]),
        }
    elif storage_type == "hdfs":
        result.update(
            expires=_expires(config["expires"]),
            storage_config=deepcopy(profile.get("hdfs_storage_config", {"other": {"data_type": "parquet"}})),
        )
    else:
        result["expires"] = _expires(config["expires"])
    return result


def _batch_node(controller, old, profile):
    """保留确定字段；调度锚点和新窗口边界要求明确登记，不能猜测。"""
    schedule = deepcopy(old["dedicated_config"]["schedule_config"])
    period = schedule["schedule_period"]
    key = f"{period}:{schedule['count_freq']}"
    policy = profile.get("batch_schedules", {}).get(key)
    if not isinstance(policy, dict) or not isinstance(policy.get("start_time"), int):
        raise BKBaseResourceMappingError(message=f"V4 batch schedule policy requires validation: {key}")
    schedule["start_time"] = policy["start_time"]
    dedicated = deepcopy(old["dedicated_config"])
    dedicated["schedule_config"] = schedule
    dedicated["self_dependence"]["self_dependency_config"]["dependency_rule"] = "self_no_failed"
    dedicated.setdefault("recovery_config", {"recovery_enable": False, "recovery_times": 0, "recovery_interval": 1})
    output = dedicated["output_config"]
    if output["output_baseline_type"] == "schedule_time" and not output.get("output_baseline"):
        output["output_baseline"] = "schedule_time"
    elif output["output_baseline_type"] == "upstream_result_table":
        output["output_baseline_type"] = "upstream"
    windows = []
    for window in old["window_info"]:
        item = {k: deepcopy(v) for k, v in window.items() if k != "color"}
        item["accumulate_start_time"] = "" if item["window_type"] != "accumulate" else item["accumulate_start_time"]
        item["dependency_rule"] = controller.strategy.configs.get("schedule_config", {}).get(
            "dependency_rule", "no_failed"
        )
        wkey = ":".join(
            str(item[k])
            for k in ("window_type", "window_size", "window_size_unit", "window_offset", "window_offset_unit")
        )
        offsets = profile.get("batch_window_offsets", {}).get(wkey)
        required = {"window_start_offset", "window_start_offset_unit", "window_end_offset", "window_end_offset_unit"}
        if not isinstance(offsets, dict) or not required.issubset(offsets):
            raise BKBaseResourceMappingError(message=f"V4 batch window boundaries require validation: {wkey}")
        item.update({k: offsets[k] for k in required})
        windows.append(item)
    return {
        "kind": "BatchSqlNode",
        "windows_info": windows,
        "dedicated_config": dedicated,
        "processing_info": controller.strategy.sql,
    }


def build_controller_spec(controller, *, context=None):
    """复用业务节点构造和SQL，仅在Service转换V4协议。"""
    strategy = controller.strategy
    context = context or get_bkbase_context()
    profile = GlobalMetaConfig.get(
        config_key=BKBASE_V4_FLOW_CONFIG,
        config_level=ConfigLevelChoices.NAMESPACE.value,
        instance_key=strategy.namespace,
        default={},
    )
    if not isinstance(profile, dict):
        raise BKBaseResourceMappingError(message="Invalid V4 Flow deployment configuration")
    rt_ids = list(controller.rt_ids)
    metadata = metadata_service.get_result_tables(rt_ids, related=["fields", "storages"], context=context)
    sources = {}
    kinds = {
        FlowDataSourceNodeType.REALTIME: "StreamSourceNode",
        FlowDataSourceNodeType.REDIS_KV_SOURCE: "StreamStaticSource",
        FlowDataSourceNodeType.BATCH: "BatchStaticSource",
        FlowDataSourceNodeType.BATCH_REAL: "BatchSourceNode",
    }
    for rt_id in rt_ids:
        namespace = context.get("rt_namespaces", {}).get(rt_id)
        if not namespace:
            raise BKBaseResourceMappingError(message=f"Missing verified namespace for input RT {rt_id}")
        sources[rt_id] = {
            "kind": kinds[controller.check_source_type(rt_id)],
            "data": {"kind": "ResultTable", "tenant": context["tenant"], "namespace": namespace, "name": rt_id},
        }
    controller.rt_node_map = {rt_id: stable_name("src", rt_id) for rt_id in rt_ids}
    biz_id = metadata[0].get("bk_biz_id")
    if not isinstance(biz_id, int):
        raise BKBaseResourceMappingError(message="Missing input RT business ID")
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    output_name = binding.get("output_name") or stable_name("audit", strategy.namespace, strategy.strategy_id)
    output = f"{biz_id}_{output_name}"
    old_sql = controller._build_sql_node_config(biz_id)
    if old_sql["node_type"] == "realtime":
        sql_node = {
            "kind": "StreamNode",
            "config": {
                "sql": strategy.sql,
                "window_config": {
                    "type": None,
                    "count_freq": 0,
                    "length": 0,
                    "waiting_time": 0,
                    "session_gap": 0,
                    "expired_time": 0,
                    "allowed_lateness": False,
                    "lateness_time": 0,
                    "lateness_count_freq": 0,
                },
            },
        }
    else:
        sql_node = _batch_node(controller, old_sql, profile)
    storages = []
    for cls in controller.storage_nodes:
        config = cls(namespace=strategy.namespace).build_node_config(
            bk_biz_id=biz_id, raw_table_name=output_name, from_result_table_ids=[output]
        )
        if config:
            storages.append(_storage_node(context, strategy, config, profile))
    if not isinstance(profile.get("operation_config"), dict):
        raise BKBaseResourceMappingError(message="V4 Flow deployment resources must be explicitly configured")
    operation = deepcopy(profile["operation_config"])
    operation.setdefault("start_position", "continue")
    _save_operation_binding(context, strategy, {"output_name": output_name, "output_rt_id": output})
    return build_rule_flow(
        strategy,
        rt_metadata=metadata,
        binding_map={
            "sources": sources,
            "sql_node": sql_node,
            "output": output,
            "biz_id": biz_id,
            "storages": storages,
            "operation_config": operation,
        },
    )


def configure_rule_controller(controller):
    """集中选择旧逐节点流程或V4整图流程。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return controller._update_or_create_bkbase_flow_v3()
    context = get_bkbase_context()
    context["operation_id"] = (controller.strategy.backend_data or {}).get("bkbase_v4", {}).get("operation_id")
    return apply_rule_flow(context, controller.strategy, build_controller_spec(controller, context=context))


def update_or_create_controller(controller, status):
    """V4只受理一次整图动作，现有check_flow_status任务继续推进。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return controller._update_or_create_v3(status)
    operation_id = uuid4().hex
    try:
        _save_binding(controller.strategy, {"poll_count": 0, "operation_id": operation_id})
        controller._update_or_create_bkbase_flow()
        controller.check_flow_status(
            strategy_id=controller.strategy.strategy_id,
            success_status=StrategyStatusChoices.RUNNING,
            failed_status=StrategyStatusChoices.UPDATE_FAILED
            if status == StrategyStatusChoices.UPDATING
            else StrategyStatusChoices.START_FAILED,
            other_status=status,
            operation_id=operation_id,
        )
    except Exception as error:
        failed_status = (
            StrategyStatusChoices.UPDATE_FAILED
            if status == StrategyStatusChoices.UPDATING
            else StrategyStatusChoices.START_FAILED
        )
        persist_operation_status(controller.strategy, operation_id, failed_status, str(error))
        raise


def toggle_controller(controller, status, force=False):
    """版本路由集中在Service，V4启停不使用旧数字Flow ID。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return controller._toggle_strategy_v3(status, force=force)
    if not force and (
        not has_flow(controller.strategy)
        or controller.strategy.status
        in (
            StrategyStatusChoices.STARTING,
            StrategyStatusChoices.STOPPING,
            StrategyStatusChoices.UPDATING,
            StrategyStatusChoices.FAILED,
        )
    ):
        return
    actions = {
        "start": (
            "start",
            StrategyStatusChoices.STARTING,
            StrategyStatusChoices.RUNNING,
            StrategyStatusChoices.START_FAILED,
        ),
        "stop": (
            "stop",
            StrategyStatusChoices.STOPPING,
            StrategyStatusChoices.DISABLED,
            StrategyStatusChoices.STOP_FAILED,
        ),
        "restart": (
            "restart",
            StrategyStatusChoices.UPDATING,
            StrategyStatusChoices.RUNNING,
            StrategyStatusChoices.UPDATE_FAILED,
        ),
    }
    if status not in actions:
        raise BKBaseResourceMappingError(message="Invalid strategy toggle")
    action, pending, success, failed = actions[status]
    operation_id = uuid4().hex
    binding = _save_binding(
        controller.strategy,
        {
            "requested_action": action,
            "poll_count": 0,
            "operation_id": operation_id,
            "operation": "wait_stopped" if action == "stop" else "wait_running",
        },
        remove=["restart_waiting", "restart_baseline"],
    )
    context = get_bkbase_context()
    context["operation_id"] = operation_id
    if action != "stop" and binding.get("pending_spec"):
        # 停止保留尚未发布的配置，下次启动先应用新图，不能直接重启旧图。
        apply_rule_flow(context, controller.strategy, binding["pending_spec"])
    else:
        operate_rule_flow(context, controller.strategy, action=action)
    if not persist_operation_status(controller.strategy, operation_id, pending):
        return
    controller.check_flow_status(
        strategy_id=controller.strategy.strategy_id,
        success_status=success,
        failed_status=failed,
        other_status=pending,
        operation_id=operation_id,
    )


def describe_controller(controller):
    if get_bkbase_version() == BKBaseVersion.V3:
        return controller._describe_flow_status_v3()
    if not (controller.strategy.backend_data or {}).get("bkbase_v4", {}).get("flow"):
        return "no-start"
    state = get_rule_flow_status(get_bkbase_context(), controller.strategy)["task_state"]
    return {TaskState.RUNNING: "running", TaskState.STOPPED: "no-start", TaskState.FAILED: "failure"}.get(
        state, "pending"
    )


def enqueue_status_check(task, strategy, strategy_id, success_status, failed_status, other_status, operation_id=None):
    """轮询绑定发起它的V4操作；V3保留原队列参数。"""
    args = (strategy_id, success_status, failed_status, other_status)
    if get_bkbase_version() == BKBaseVersion.V3:
        return task.delay(*args)
    operation_id = operation_id or (strategy.backend_data or {}).get("bkbase_v4", {}).get("operation_id")
    if not operation_id:
        raise BKBaseResourceMappingError(message="Missing Flow operation identity")
    return task.delay(*args, operation_id=operation_id)


def is_current_operation(strategy, operation_id):
    """拒绝没有操作身份或已被新启停/更新操作替代的V4回调。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return True
    return bool(operation_id) and (strategy.backend_data or {}).get("bkbase_v4", {}).get("operation_id") == operation_id


def persist_operation_status(strategy, operation_id, status, message=None):
    """短事务内再次检查操作身份，过期回调不得写状态或错误信息。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        strategy.status = status
        if message is not None:
            strategy.status_msg = message
            strategy.save(update_record=False, update_fields=["status_msg"])
        strategy.save(update_record=False, update_fields=["status"])
        return True
    with transaction.atomic():
        current = Strategy.objects.select_for_update().get(pk=strategy.pk)
        if not is_current_operation(current, operation_id):
            return False
        current.status = status
        fields = ["status"]
        if message is not None:
            current.status_msg = message
            fields.append("status_msg")
        current.save(update_record=False, update_fields=fields)
    strategy.status = current.status
    strategy.status_msg = current.status_msg
    return True


def strategy_deploy_data(strategy):
    """按实际观测生成现有策略任务的状态契约，不复制未知字段。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return get_flow_deploy_data(flow_id=strategy.backend_data["flow_id"])
    count = (strategy.backend_data or {}).get("bkbase_v4", {}).get("poll_count", 0) + 1
    operation_id = (strategy.backend_data or {}).get("bkbase_v4", {}).get("operation_id")
    context = get_bkbase_context()
    context["operation_id"] = operation_id
    try:
        observed = advance_rule_flow(context, strategy)
    except BKBaseOperationSuperseded:
        return {"status": "superseded", "flow_status": None, "logs": []}
    except (APIRequestError, LockError) as error:
        observed = {"task_state": None, "message": str(error)}
    except BKBaseResourceMappingError as error:
        observed = {"task_state": TaskState.FAILED, "message": str(error)}
    try:
        _save_operation_binding(context, strategy, {"poll_count": count, "message": observed.get("message", "")})
    except BKBaseOperationSuperseded:
        return {"status": "superseded", "flow_status": None, "logs": []}
    state = observed["task_state"]
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    operation = binding.get("requested_action")
    if binding.get("restart_waiting"):
        if not observed.get("deployment") or observed["deployment"] == binding.get("restart_baseline"):
            if state != TaskState.FAILED:
                state = None
        else:
            try:
                _save_operation_binding(context, strategy, {}, remove=["restart_waiting", "restart_baseline"])
            except BKBaseOperationSuperseded:
                return {"status": "superseded", "flow_status": None, "logs": []}
    if operation != "stop" and (binding.get("pending_spec") or binding.get("operation") == "wait_stopped"):
        if state != TaskState.FAILED:
            state = None
    target = TaskState.STOPPED if operation == "stop" else TaskState.RUNNING
    if count >= BKBASE_V4_MAX_POLLS and state not in (target, TaskState.FAILED):
        state = TaskState.FAILED
        observed["message"] = "Flow operation timed out: " + observed.get("message", "")
    if state == TaskState.FAILED:
        return {
            "status": "failure",
            "flow_status": "failure",
            "logs": [{"level": "ERROR", "message": observed.get("message", "")}],
        }
    complete = state == (TaskState.STOPPED if operation == "stop" else TaskState.RUNNING)
    return {"status": "success" if complete else "other", "flow_status": state, "logs": []}


def require_batch_history():
    """离线执行记录的数据时间契约仍由B09约束。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        raise BKBaseCapabilityNotReady("B09", "offline execution history")


def has_flow(strategy):
    """只判断当前版本自己的绑定，旧数字ID不能替代V4引用。"""
    backend = strategy.backend_data or {}
    if get_bkbase_version() == BKBaseVersion.V4:
        return bool(backend.get("bkbase_v4", {}).get("flow"))
    return bool(backend.get("flow_id"))


def observe_strategy_status(strategy):
    """后台巡检使用实际状态，不驱动更新，也不依赖旧Flow ID。"""
    if not has_flow(strategy):
        return {"flow_status": "no-start"}
    if get_bkbase_version() == BKBaseVersion.V3:
        return get_flow_deploy_data(flow_id=strategy.backend_data["flow_id"])
    result = get_rule_flow_status(get_bkbase_context(), strategy)
    state = {TaskState.RUNNING: "running", TaskState.STOPPED: "no-start", TaskState.FAILED: "failure"}.get(
        result["task_state"], "pending"
    )
    return {"flow_status": state}
