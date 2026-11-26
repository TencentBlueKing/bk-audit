"""管理普通规则完整计算图及声明式运行流程。

后台任务按可信资源Ref推进停止、图更新及配置应用观察。
状态表示正式资源的应用结果；引擎内部状态与非空数据链另行验证。
"""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction

from api.bk_base_v4.tenant import get_bkbase_v4_platform_username
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.notice.constants import WEIXIN_UNAVAILABLE_MESSAGE, MsgType
from core.exceptions import LockError
from services.web.analyze.constants import (
    AUDIT_EVENT_TABLE_PREFIX,
    BKBASE_FLOW_CONSUMING_MODE,
    ControlTypeChoices,
    FlowDataSourceNodeType,
    ObjectType,
)
from services.web.analyze.models import Control
from services.web.bkbase import flow_delete, flow_operation
from services.web.bkbase import metadata as metadata_service
from services.web.bkbase import source as source_service
from services.web.bkbase import storage as storage_service
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    get_resource_or_none,
    legacy_bulk,
    legacy_call,
    operation_result,
    resource_lock,
    resource_params,
    stable_name,
)
from services.web.bkbase.constants import (
    BKBASE_V4_ES_ROLLOVER_TIMEZONE,
    BKBASE_V4_FLOW_CONFIG,
    BKBASE_V4_FLOW_NODE_NAME_MAX_LENGTH,
    BKBASE_V4_MAX_POLLS,
    BKBASE_V4_NOTIFY_CHANNELS,
    BKBaseVersion,
    TaskState,
)
from services.web.bkbase.exceptions import (
    BKBaseCapabilityNotReady,
    BKBaseFlowOperationPending,
    BKBaseFlowWriteFailed,
    BKBaseOperationSuperseded,
    BKBaseResourceMappingError,
)
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot
from services.web.strategy_v2.constants import StrategyStatusChoices, StrategyType
from services.web.strategy_v2.models import Strategy


def node_name(prefix, *parts):
    """仅缩短超出Flow上限的可读部分，保留既有短名及原稳定摘要。"""
    return stable_name(prefix, *parts, max_length=BKBASE_V4_FLOW_NODE_NAME_MAX_LENGTH)


def validate_graph(nodes):
    """整图节点名必须唯一且不超过50字符，所有连边都必须存在。"""
    names = [n.get("name") for n in nodes]
    if (
        not names
        or any(not isinstance(n, str) or not n or len(n) > BKBASE_V4_FLOW_NODE_NAME_MAX_LENGTH for n in names)
        or len(set(names)) != len(names)
    ):
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
        node["name"] = node_name("src", rt_id)
        nodes.append(node)
    sql = deepcopy(binding_map["sql_node"])
    sql.update(
        name=node_name("sql", strategy.strategy_id),
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
        "maintainers": [get_bkbase_v4_platform_username()],
        "operation_config": deepcopy(binding_map.get("operation_config", {"start_position": "continue"})),
        "nodes": nodes,
    }


def _save_binding(strategy, patch, *, remove=(), expected_operation_id=None):
    """短事务合并V4绑定并校验原操作身份，保留旧ID和其他backend_data。"""
    with flow_operation.locked_rows(strategy) as (current, rows):
        flow_operation.assert_active(current)
        flow_operation.assert_writable(rows)
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


def get_rule_flow_status(context, strategy, *, resource=None):
    """从正式 Flow 读取配置应用状态，供启停、巡检和改图观察复用。"""
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    ref = binding.get("flow") or {}
    params = resource_params(context, ref, kind="Flow")
    if resource is None:
        resource = api.bk_base_v4.flow_get(**params)
    flow_operation._validate_resource(resource, ref)
    result = operation_result(resource, ref, "observe")
    result["resource"] = resource
    if result["resource_phase"] == "Ok":
        declared = (resource["metadata"].get("annotations") or {}).get("task_stopped")
        result["task_state"] = TaskState.STOPPED if declared == "true" else TaskState.RUNNING
    elif result["resource_phase"] == "Failed" and not result["message"]:
        result["message"] = "Flow configuration failed to apply."
    return result


def operate_rule_flow(context, strategy, *, action, start_position=None):
    """启停由正式资源控制，原配置重启分两个可关联的声明。"""
    flow_operation.assert_detached()
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
                spec = _aligned_graph(current["spec"], spec)
                _validate_flow_inputs(context, spec)
                _save_operation_binding(context, strategy, {"pending_spec": spec, "operation": "wait_stopped"})
                return operate_rule_flow(context, strategy, action="stop")
        return flow_operation.request_restart(strategy, context=context)
    if action not in ("start", "stop"):
        raise BKBaseResourceMappingError(message="Unsupported Flow action")
    if start_position is not None and start_position not in ("continue", "from_head", "from_tail"):
        raise BKBaseResourceMappingError(message="Invalid Flow consumption position")
    with resource_lock(context, ref):
        current = api.bk_base_v4.flow_get(**params)
        binding = (strategy.backend_data or {}).get("bkbase_v4", {})
        if action == "stop" and binding.get("pending_spec") and binding.get("requested_action") != "stop":
            _validate_flow_inputs(context, binding["pending_spec"])
        metadata, spec = deepcopy(current["metadata"]), deepcopy(current["spec"])
        metadata.setdefault("annotations", {})["task_stopped"] = "true" if action == "stop" else "false"
        if action == "start":
            spec.setdefault("operation_config", {})["start_position"] = BKBASE_FLOW_CONSUMING_MODE
        elif start_position is not None:
            spec.setdefault("operation_config", {})["start_position"] = start_position
        result = _write_flow_request(
            context, strategy, api.bk_base_v4.flow_update, **params, metadata=metadata, spec=spec, status=None
        )
    return operation_result(result, ref, action)


def _node_identity(node, nodes):
    """从原生节点的业务目标识别身份，名称只用于重建图中的连边。"""
    kind = node.get("kind")
    if kind in ("StreamSourceNode", "StreamStaticSource", "BatchStaticSource", "BatchSourceNode"):
        ref = node.get("data")
        family = kind
    elif kind in ("StreamNode", "BatchSqlNode"):
        return ("sql", node["output"]) if node.get("output") else None
    elif kind in ("DorisStorageNode", "HdfsStorageNode", "EsStorageNode", "QueueStorageNode"):
        ref = node.get("storage")
        parent = nodes.get(node.get("input"), {})
        family = (kind, parent.get("output"))
    else:
        return None
    if not isinstance(ref, dict) or any(not ref.get(key) for key in ("kind", "tenant", "namespace", "name")):
        return None
    return (family, *(ref[key] for key in ("kind", "tenant", "namespace", "name")))


def _aligned_graph(current, desired):
    """复用同一Ref/输出的正式节点名；整图归本策略，未再需要的节点不保留。"""
    old_nodes = current.get("nodes")
    if not isinstance(old_nodes, list) or any(not isinstance(node, dict) or not node.get("name") for node in old_nodes):
        raise BKBaseResourceMappingError(message="Existing Flow node structure is incomplete")
    if len({node["name"] for node in old_nodes}) != len(old_nodes):
        raise BKBaseResourceMappingError(message="Duplicate existing Flow node identity")
    validate_graph(desired["nodes"])
    old = {node["name"]: node for node in old_nodes}
    target = {node["name"]: node for node in desired["nodes"]}
    names = {}
    for node in desired["nodes"]:
        identity = _node_identity(node, target)
        matches = [item["name"] for item in old_nodes if identity is not None and _node_identity(item, old) == identity]
        if len(matches) > 1:
            raise BKBaseResourceMappingError(message="Ambiguous Flow nodes for the same business target")
        names[node["name"]] = matches[0] if matches else node["name"]
    result = deepcopy(desired)
    for node in result["nodes"]:
        node["name"] = names[node["name"]]
        if "inputs" in node:
            node["inputs"] = [names[name] for name in node["inputs"]]
        if node.get("input"):
            node["input"] = names[node["input"]]
    validate_graph(result["nodes"])
    return result


def _assert_storage_target(previous, desired):
    """普通改图不得切换已有物理目标，缺省字段交由锁内合并保留。"""
    if desired.get("kind") == "DorisStorageNode":
        before, after = previous.get("storage_config") or {}, desired.get("storage_config") or {}
        if any(
            before.get(key) is not None and after.get(key) is not None and before[key] != after[key]
            for key in ("db", "table")
        ):
            raise BKBaseResourceMappingError(message="V4 Flow Doris destination conflicts with its saved target")
    elif desired.get("kind") == "EsStorageNode":
        before, after = deepcopy(previous.get("write_alias")), deepcopy(desired.get("write_alias"))
        for alias in (before, after):
            if isinstance(alias, dict) and isinstance(alias.get("TimeBased"), dict):
                template = alias["TimeBased"].get("format")
                if isinstance(template, str):
                    alias["TimeBased"]["format"] = template.replace("{yyyyMMdd}", "%Y%m%d")
                # 普通编辑只核物理目标；切日时区由最新正式图原样保留。
                alias["TimeBased"].pop("timezone", None)
        if before is not None and after is not None and before != after:
            raise BKBaseResourceMappingError(message="V4 Flow ES destination conflicts with its saved target")


def _merged_spec(old, desired, *, preserve_storage_targets=False):
    """更新策略独占整图，保留同目标存储未声明的配置及远端顶层字段。"""
    desired = _aligned_graph(old, desired)
    spec = deepcopy(old)
    existing = {node["name"]: node for node in old.get("nodes", [])}
    target = {node["name"]: node for node in desired["nodes"]}
    nodes = []
    for node in desired["nodes"]:
        previous = existing.get(node["name"], {})
        old_identity, new_identity = _node_identity(previous, existing), _node_identity(node, target)
        same_target = previous.get("kind") == node.get("kind") and (
            old_identity is None or new_identity is None or old_identity == new_identity
        )
        if same_target and preserve_storage_targets:
            _assert_storage_target(previous, node)
        merged = {**deepcopy(previous), **deepcopy(node)} if same_target else deepcopy(node)
        if same_target and node.get("kind") == "BatchSqlNode":
            dedicated = merged["dedicated_config"]
            saved = previous.get("dedicated_config", {})
            dedicated["schedule_config"]["start_time"] = _batch_start_time(
                dedicated["schedule_config"], saved.get("schedule_config", {})
            )
            merged["windows_info"] = _preserve_batch_windows(previous, merged["windows_info"])
            if isinstance(saved.get("output_config"), dict):
                dedicated["output_config"] = deepcopy(saved["output_config"])
        if (
            same_target
            and preserve_storage_targets
            and node.get("kind") == "EsStorageNode"
            and "write_alias" in previous
        ):
            merged["write_alias"] = deepcopy(previous["write_alias"])
        if same_target and node.get("kind") == "DorisStorageNode":
            old_config, config = previous.get("storage_config"), node.get("storage_config")
            if isinstance(old_config, dict) and isinstance(config, dict):
                merged["storage_config"] = deepcopy({**old_config, **config})
            if isinstance(merged.get("storage_config"), dict):
                # 开关只用于新节点；锁内最新正式值（包括缺省/null）不能被新建默认覆盖。
                if isinstance(old_config, dict) and "use_lowercase_field" in old_config:
                    merged["storage_config"]["use_lowercase_field"] = deepcopy(old_config["use_lowercase_field"])
                else:
                    merged["storage_config"].pop("use_lowercase_field", None)
        nodes.append(merged)
    spec.update({key: deepcopy(value) for key, value in desired.items() if key not in ("nodes", "operation_config")})
    spec["nodes"] = nodes
    spec.setdefault("operation_config", {}).update(deepcopy(desired.get("operation_config", {})))
    validate_graph(nodes)
    return spec


def _same_flow_spec(before, after):
    """仅将空离线节点覆盖的缺省/null/{}视为等价，不改正式回读及其他字段。"""
    compared = [deepcopy(before), deepcopy(after)]
    for spec in compared:
        operation = spec.get("operation_config")
        config = operation.get("batch_sql_deploy_config") if isinstance(operation, dict) else None
        if isinstance(config, dict) and config.get("node_deploy_configs") is None:
            config["node_deploy_configs"] = {}
    return compared[0] == compared[1]


def apply_rule_flow(context, strategy, spec):
    """按正式Ref维护策略独占整图，依次停止、发布和观察应用结果。"""
    flow_operation.assert_detached()
    spec = deepcopy(spec)
    spec.setdefault("operation_config", {})["start_position"] = BKBASE_FLOW_CONSUMING_MODE
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    ref = binding.get("flow")
    if not ref and (strategy.backend_data or {}).get("flow_id"):
        raise BKBaseResourceMappingError(message="Existing V3 Flow requires explicit migration binding")
    # 沿用原入口的短事务代次校验，旧任务不能先落入新一代的归属校验。
    _save_operation_binding(context, strategy, {"requested_action": "start"})
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    ref = binding.get("flow")
    if not ref:
        validate_graph(spec["nodes"])
        _validate_flow_inputs(context, spec)
        ref = {
            "kind": "Flow",
            "tenant": context["tenant"],
            "namespace": context["namespace"],
            "name": stable_name("flow", strategy.strategy_id),
        }
        _save_operation_binding(
            context,
            strategy,
            {"flow": ref, "pending_spec": spec, "operation": "create", "requested_action": "start"},
        )
        binding = (strategy.backend_data or {})["bkbase_v4"]
    params = resource_params(context, ref, kind="Flow")
    with resource_lock(context, ref):
        current = get_resource_or_none(api.bk_base_v4.flow_get, **params)
        if current is None:
            if binding.get("operation") != "create":
                raise BKBaseResourceMappingError(
                    message="Bound Flow is missing; recreation requires an explicit new flow"
                )
            validate_graph(spec["nodes"])
            _validate_batch_deployment(context, spec)
            _validate_flow_inputs(context, spec)
            _save_operation_binding(context, strategy, {"requested_action": "start"})
            result = _write_flow_request(
                context,
                strategy,
                api.bk_base_v4.flow_create,
                tenant=params["tenant"],
                namespace=params["namespace"],
                metadata={**params, "annotations": {"task_stopped": "false"}},
                spec=spec,
                status=None,
            )
            _save_operation_binding(
                context,
                strategy,
                {"operation": "wait_running"},
                remove=["pending_spec"],
            )
            return operation_result(result, ref, "create")
    if binding.get("operation") == "create" and binding.get("pending_spec"):
        raise BKBaseResourceMappingError(message="Flow creation result requires explicit verification before recovery")
    observed = get_rule_flow_status(context, strategy, resource=current)
    phase = (current.get("status") or {}).get("phase")
    if phase == "Failed":
        raise BKBaseResourceMappingError(message="Flow配置失败，请按原配置启动恢复后再发布改图")
    desired = _aligned_graph(current["spec"], spec)
    _validate_flow_inputs(context, desired)
    merged = _merged_spec(current["spec"], desired, preserve_storage_targets=True)
    _validate_batch_deployment(context, merged)
    _validate_flow_inputs(context, merged)
    if phase != "Ok":
        # 未收敛的正式配置只观察，保留待发布整图供后续Ok后推进。
        _save_operation_binding(context, strategy, {"pending_spec": desired, "operation": "wait_stopped"})
        return observed
    if (
        _same_flow_spec(merged, current["spec"])
        and current["metadata"].get("annotations", {}).get("task_stopped") != "true"
    ):
        _save_operation_binding(
            context,
            strategy,
            {"operation": "wait_running"},
            remove=["pending_spec"],
        )
        return observed
    if observed["task_state"] != TaskState.STOPPED:
        _save_operation_binding(context, strategy, {"pending_spec": desired, "operation": "wait_stopped"})
        if current["metadata"].get("annotations", {}).get("task_stopped") != "true":
            return operate_rule_flow(context, strategy, action="stop")
        return observed
    with resource_lock(context, ref):
        current = api.bk_base_v4.flow_get(**params)
        phase = (current.get("status") or {}).get("phase")
        if phase == "Failed":
            raise BKBaseResourceMappingError(message="Flow配置失败，请按原配置启动恢复后再发布改图")
        if phase != "Ok":
            _save_operation_binding(context, strategy, {"pending_spec": desired, "operation": "wait_stopped"})
            return get_rule_flow_status(context, strategy, resource=current)
        latest = get_rule_flow_status(context, strategy, resource=current)
        if latest["task_state"] != TaskState.STOPPED:
            # 释放锁后由下一轮正常启停流程重新停止，不能在此重入同一资源锁。
            _save_operation_binding(context, strategy, {"pending_spec": desired, "operation": "wait_stopped"})
            return latest
        desired = _aligned_graph(current["spec"], desired)
        _validate_flow_inputs(context, desired)
        merged = _merged_spec(current["spec"], desired, preserve_storage_targets=True)
        _validate_batch_deployment(context, merged)
        _validate_flow_inputs(context, merged)
        metadata = deepcopy(current["metadata"])
        metadata.setdefault("annotations", {})["task_stopped"] = "false"
        result = _write_flow_request(
            context, strategy, api.bk_base_v4.flow_update, **params, metadata=metadata, spec=merged, status=None
        )
        _save_operation_binding(
            context,
            strategy,
            {"operation": "wait_running"},
            remove=["pending_spec"],
        )
    return operation_result(result, ref, "update")


def advance_rule_flow(context, strategy):
    """现有任务每次仅推进一步，避免在Web请求中阻塞等待。"""
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    if flow_operation.is_pure(strategy):
        return get_rule_flow_status(context, strategy)
    if binding.get("pending_spec") and binding.get("requested_action") != "stop":
        result = apply_rule_flow(context, strategy, binding["pending_spec"])
        if result["task_state"] == TaskState.FAILED:
            return result
    return get_rule_flow_status(context, strategy)


def dataflow_batch_status_list(request_data=None, **params):
    """按已确认的 processing_id 读取离线执行记录。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return legacy_call("dataflow_batch_status_list", request_data, **params)
    data = {**(request_data or {}), **params}
    job_id, offset, limit = data.get("processing_id"), data.get("offset", 0), data.get("limit", 10)
    if (
        not isinstance(job_id, str)
        or not job_id.strip()
        or any(c.isspace() or c in "/\\?#%" for c in job_id)
        or type(offset) is not int
        or offset < 0
        or type(limit) is not int
        or limit <= 0
    ):
        raise BKBaseResourceMappingError(message="Invalid batch job identity or pagination")
    try:
        if any(type(data[key]) is not int or data[key] % 1000 for key in ("data_start", "data_end")):
            raise ValueError("time must use whole-second milliseconds")
        start = datetime.fromtimestamp(data["data_start"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        end = datetime.fromtimestamp(data["data_end"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if data["data_start"] > data["data_end"]:
            raise ValueError("inverted window")
    except (KeyError, TypeError, ValueError, OverflowError, OSError) as error:
        raise BKBaseResourceMappingError(message="Invalid batch time window") from error
    page, skip = offset // limit + 1, offset % limit
    rows = []
    while len(rows) < skip + limit:
        response = api.bk_base_v4.batch_status_list(
            job_id=job_id, start_time=start, end_time=end, page_num=page, page_size=limit, is_data_time=True
        )
        history = response.get("history") if isinstance(response, dict) else None
        if not isinstance(history, list) or not all(isinstance(row, dict) for row in history):
            raise BKBaseResourceMappingError(message="Invalid batch history response")
        rows.extend(history)
        if len(history) < limit:
            break
        page += 1
    return rows[skip : skip + limit]


def get_alert_configs(request_data=None, *, flow_ref=None, **params):
    """读取已有Flow的完整通知配置；V4首次GET可能生成默认配置。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return legacy_call("get_alert_configs", request_data, **params)
    context = get_bkbase_context()
    target = resource_params(context, flow_ref or {}, kind="Flow")
    return api.bk_base_v4.data_source_notifies(**target, kind="Flow")


def edit_alert_configs(request_data=None, *, flow_ref=None, **params):
    """写回完整通知配置；检测与收敛参数由调用方保留，不猜旧Flow映射。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return legacy_call("edit_alert_configs", request_data, **params)
    context = get_bkbase_context()
    target = resource_params(context, flow_ref or {}, kind="Flow")
    tenant = target.pop("tenant")
    data = {**(request_data or {}), **params}
    return api.bk_base_v4.data_source_notifies_update(
        tenant=tenant, target={"kind": "Flow", **target}, active=data["active"], alert_config=data["alert_config"]
    )


def configure_monitor(strategy, *, active, receivers, notify_config, operation_id=None):
    """切换策略通知并适配接收人与渠道；完整保留已有检测项及收敛配置。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        config = get_alert_configs(object_type=ObjectType.DATAFLOW, object_id=strategy.backend_data["flow_id"])
        config.update(active=active, alert_config_id=config["id"], receivers=receivers, notify_config=notify_config)
        return edit_alert_configs(**config)
    context = get_bkbase_context()
    ref = (strategy.backend_data or {}).get("bkbase_v4", {}).get("flow")
    if not ref:
        raise BKBaseResourceMappingError(message="C19: notification update requires the persisted V4 Flow reference")
    resource_params(context, ref, kind="Flow")

    def current_generation():
        current = Strategy.objects.filter(strategy_id=strategy.strategy_id).first()
        return bool(
            current
            and is_current_operation(current, operation_id)
            and (current.backend_data or {}).get("bkbase_v4", {}).get("flow") == ref
        )

    if active:
        if MsgType.WEIXIN in notify_config:
            logger.warning("[NoticeChannelRetired] strategy=%s channel=weixin", strategy.strategy_id)
            if not any(value != MsgType.WEIXIN for value in notify_config):
                raise BKBaseResourceMappingError(message=str(WEIXIN_UNAVAILABLE_MESSAGE))
        try:
            channels = sorted({BKBASE_V4_NOTIFY_CHANNELS[value] for value in notify_config if value != MsgType.WEIXIN})
            names = [receiver["username"] for receiver in receivers if receiver["receiver_type"] == "user"]
            if len(names) != len(receivers) or any(not isinstance(name, str) or not name for name in names):
                raise ValueError("Invalid notification receiver")
        except (KeyError, TypeError, ValueError) as error:
            raise BKBaseResourceMappingError(message="Unsupported notification receiver or channel") from error
    if not current_generation():
        return None
    config = deepcopy(get_alert_configs(flow_ref=ref))
    try:
        alert = config["alert_config"]
        groups = alert["notify_group_configs"]
        if not isinstance(groups, list) or not isinstance(alert["converge_rules"], list):
            raise ValueError("Incomplete notification groups or convergence rules")
        for group in groups:
            if (
                not isinstance(group["active"], bool)
                or not isinstance(group["group"], str)
                or not isinstance(group["notify_configs"], list)
                or not all(isinstance(item, dict) for item in group["notify_configs"])
                or not isinstance(group["receiver_config"], dict)
            ):
                raise ValueError("Invalid notification group")
            if active:
                group["receiver_config"].update(receivers=names, notify_channels=channels)
    except (KeyError, TypeError, ValueError) as error:
        raise BKBaseResourceMappingError(
            message="Incomplete V4 notification configuration; refusing partial update"
        ) from error
    if not current_generation():
        return None
    return edit_alert_configs(flow_ref=ref, active=active, alert_config=alert)


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


def _storage_node(context, strategy, config, profile, *, existing_nodes=(), output_rt_id=None):
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
    outputs = {node["name"] for node in existing_nodes if node.get("output") == output_rt_id} if output_rt_id else None
    existing = [
        node
        for node in existing_nodes
        if node.get("kind") == kind and (outputs is None or node.get("input") in outputs)
    ]
    ref = storage_service.resolve_storage_cluster(
        context, audit_namespace=strategy.namespace, storage_type=storage_type, legacy_cluster_id=config["cluster"]
    )
    matches = [node for node in existing if node.get("storage") == ref]
    if len(matches) > 1:
        raise BKBaseResourceMappingError(message="Ambiguous existing Flow storage destination")
    current = matches[0] if matches else {}
    result = {"kind": kind, "name": node_name("store", strategy.strategy_id, storage_type), "storage": ref}
    if storage_type == "es":
        table = config.get("physical_table_name")
        if table:
            result["write_alias"] = (
                {
                    "TimeBased": {
                        "format": table.replace("{yyyyMMdd}", "%Y%m%d"),
                        "timezone": BKBASE_V4_ES_ROLLOVER_TIMEZONE,
                    }
                }
                if "{yyyyMMdd}" in table or "%Y%m%d" in table
                else {"Fixed": table}
            )
        elif not current:
            result["write_alias"] = None
        result.update(
            expires=_expires(config["expires"]),
            replicas=config.get("replicas"),
            unique_field_list=config.get("storage_keys", []),
            analyzed_fields=config.get("analyzed_fields", []),
            doc_value_fields=config.get("doc_values_fields", []),
            json_field_list=config.get("json_fields", []),
            flattened_fields=config.get("flattened_fields", []),
        )
    elif storage_type == "doris":
        previous = current.get("storage_config") or {}
        table = config.get("physical_table_name")
        database = None
        if table and "." in table:
            database, table = storage_service.normalize_physical_table_name("doris", table).split(".")
        elif table or not previous.get("db"):
            database = previous.get("db") or profile.get("doris_databases", {}).get(ref["name"])
        if not (database or previous.get("db")):
            raise BKBaseResourceMappingError(message="V4 Doris database must be explicitly configured")
        if table and "{" in table:
            raise BKBaseResourceMappingError(message="V4 Doris table template requires an explicit verified mapping")
        result["storage_config"] = {
            "table_type": "duplicate_table",
            "storage_keys": config.get("storage_keys", []),
            "json_fields": config.get("json_fields", []),
            "original_json_fields": config.get("original_json_fields", []),
            "field_config_group": {},
            "expires": _expires(config["expires"]),
        }
        # 已有目标缺省字段由写入锁内的最新GET保留，不将早期GET当成显式改值。
        if database:
            result["storage_config"]["db"] = database
        if config.get("physical_table_name") or not current:
            result["storage_config"]["table"] = table
        if not current:
            result["storage_config"]["use_lowercase_field"] = settings.BKBASE_V4_DORIS_USE_LOWERCASE_FIELD
    elif storage_type == "hdfs":
        configured = profile.get("hdfs_storage_config")
        result["expires"] = _expires(config["expires"])
        if configured is None and current:
            return result
        storage_config = deepcopy(configured if configured is not None else {"other": {"dataType": "parquet"}})
        other = storage_config.get("other", {})
        if "data_type" in other:
            legacy_format = other.pop("data_type")
            if "dataType" in other and other["dataType"] != legacy_format:
                raise BKBaseResourceMappingError(message="Conflicting HDFS data format configuration")
            other["dataType"] = legacy_format
        result["storage_config"] = storage_config
    else:
        result["expires"] = _expires(config["expires"])
    _assert_storage_target(current, result)
    return result


def _batch_period(unit):
    """原生GET使用H/D，业务构图使用hour/day，比较时统一单位。"""
    return {"H": "hour", "D": "day"}.get(unit, unit)


def _batch_start_time(schedule, previous=None):
    """起点由引擎在启动时解释；同周期编辑保留合法原值，换周期重新选择。"""
    period = _batch_period(schedule.get("schedule_period"))
    if period not in ("hour", "day"):
        raise BKBaseResourceMappingError(message="Unsupported V4 batch schedule period")
    if previous is not None and (
        not isinstance(previous, dict) or _batch_period(previous.get("schedule_period")) not in ("hour", "day")
    ):
        raise BKBaseResourceMappingError(message="V4 existing batch schedule period is invalid")
    if previous is not None and _batch_period(previous.get("schedule_period")) == period:
        start = previous.get("start_time")
        minimum = 1 if period == "hour" else 0
        if type(start) is not int or not minimum <= start <= 23:
            raise BKBaseResourceMappingError(message="V4 existing batch schedule start_time is invalid")
        return start
    return 1 if period == "hour" else 0


def _batch_window_key(window):
    """只复用同一输入、窗口类型及业务时间范围的正式窗口。"""
    return tuple(
        _batch_period(window.get(key)) if key.endswith("_unit") else window.get(key)
        for key in (
            "result_table_id",
            "window_type",
            "window_size",
            "window_size_unit",
            "window_offset",
            "window_offset_unit",
        )
    )


def _batch_offsets_valid(window):
    """偏移必须完整且单位明确，缺项不能被候选值自动补齐。"""
    return all(
        type(window.get(key)) is int and window.get(f"{key}_unit") in ("hour", "day", "H", "D")
        for key in ("window_start_offset", "window_end_offset")
    )


def _preserve_batch_windows(previous, windows):
    """按语义复用存量窗口，禁止用新建候选或profile回填已存在的窗口。"""
    saved = {}
    for window in previous.get("windows_info", []):
        key = _batch_window_key(window)
        if key in saved:
            raise BKBaseResourceMappingError(message="Ambiguous existing batch window")
        saved[key] = window
    result = []
    for window in windows:
        existing = saved.get(_batch_window_key(window))
        if existing is not None and not _batch_offsets_valid(existing):
            raise BKBaseResourceMappingError(message="V4 existing batch window boundaries are invalid")
        result.append(deepcopy(existing if existing is not None else window))
    return result


def _validate_batch_deployment(context, spec):
    """校验离线集群和存储输出，将原生null节点覆盖归一为空对象。"""
    batch_nodes = [node for node in spec["nodes"] if node.get("kind") == "BatchSqlNode"]
    if not batch_nodes:
        return
    config = spec.get("operation_config", {}).get("batch_sql_deploy_config")
    if (
        not isinstance(config, dict)
        or not isinstance(config.get("cluster"), str)
        or not config["cluster"].strip()
        or (config.get("node_deploy_configs") is not None and not isinstance(config["node_deploy_configs"], dict))
    ):
        raise BKBaseResourceMappingError(message="V4 batch deployment requires cluster and node_deploy_configs")
    if config.get("node_deploy_configs") is None:
        config["node_deploy_configs"] = {}
    kinds = {
        "EsStorageNode": "ElasticSearch",
        "DorisStorageNode": "Doris",
        "HdfsStorageNode": "Hdfs",
        "QueueStorageNode": "Kafka",
    }
    for batch in batch_nodes:
        sinks = [node for node in spec["nodes"] if node.get("kind") in kinds and node.get("input") == batch["name"]]
        if not sinks:
            raise BKBaseResourceMappingError(message="V4 batch storage output must be configured")
        for sink in sinks:
            source_service._replay_ref(context, sink.get("storage"), kinds[sink["kind"]])


def _batch_node(controller, old, profile, *, existing=None):
    """沿用业务SQL和选窗；相对起点交给引擎，旧窗口与新建候选分开处理。"""
    existing = existing or {}
    schedule = deepcopy(old["dedicated_config"]["schedule_config"])
    previous_schedule = existing.get("dedicated_config", {}).get("schedule_config", {}) if existing else None
    schedule["start_time"] = _batch_start_time(schedule, previous_schedule)
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
        if any(_batch_window_key(saved) == _batch_window_key(item) for saved in existing.get("windows_info", [])):
            windows.extend(_preserve_batch_windows(existing, [item]))
            continue
        item["accumulate_start_time"] = "" if item["window_type"] != "accumulate" else item["accumulate_start_time"]
        item["dependency_rule"] = controller.strategy.configs.get("schedule_config", {}).get(
            "dependency_rule", "no_failed"
        )
        wkey = ":".join(
            str(item[k])
            for k in ("window_type", "window_size", "window_size_unit", "window_offset", "window_offset_unit")
        )
        configured = profile.get("batch_window_offsets", {})
        if not isinstance(configured, dict):
            raise BKBaseResourceMappingError(message="Invalid V4 batch window boundaries configuration")
        if wkey in configured:
            offsets = configured[wkey]
        elif wkey in ("scroll:1:hour:0:hour", "whole:1:hour:0:hour"):
            # 仅覆盖已确认的一小时零偏移组合；日/多小时不从该样本外推。
            offsets = {
                "window_start_offset": 0,
                "window_start_offset_unit": "hour",
                "window_end_offset": 1,
                "window_end_offset_unit": "hour",
            }
        else:
            offsets = None
        if not isinstance(offsets, dict) or not _batch_offsets_valid(offsets):
            raise BKBaseResourceMappingError(message=f"V4 batch window boundaries require validation: {wkey}")
        item.update(
            {
                key: offsets[key]
                for key in (
                    "window_start_offset",
                    "window_start_offset_unit",
                    "window_end_offset",
                    "window_end_offset_unit",
                )
            }
        )
        windows.append(item)
    return {
        "kind": "BatchSqlNode",
        "windows_info": windows,
        "dedicated_config": dedicated,
        "processing_info": controller.strategy.sql,
    }


def _verified_input_ref(context, candidate):
    """核对显式候选与正式 ResultTable 的完整引用及逻辑身份。"""
    ref = source_service._replay_ref(context, candidate, "ResultTable")
    actual = api.bk_base_v4.result_table_resource_get(namespace=ref["namespace"], name=ref["name"])
    actual_ref, logical_id = metadata_service.result_table_identity(context, actual)
    if actual_ref != ref:
        raise BKBaseResourceMappingError(message="Input ResultTable resource identity mismatch")
    namespace = context.get("rt_namespaces", {}).get(logical_id)
    if namespace and namespace != ref["namespace"]:
        raise BKBaseResourceMappingError(message="Input ResultTable project conflicts with dataset configuration")
    return ref, logical_id


def _validate_flow_inputs(context, spec, *, audit_sources=None):
    """按正式Ref验证整图输入，不以迁移节点名称证明或否定业务身份。"""
    refs = {}
    for node in spec["nodes"]:
        if node.get("kind") not in ("StreamSourceNode", "StreamStaticSource", "BatchStaticSource", "BatchSourceNode"):
            continue
        ref, logical_id = _verified_input_ref(context, node.get("data"))
        if logical_id in refs and refs[logical_id] != ref:
            raise BKBaseResourceMappingError(message="Multiple Flow input references for the same logical ID")
        refs[logical_id] = ref


def _controller_flow_nodes(context, strategy):
    """同一次正式观察用于输入与存量节点；仅创建候选允许已证不存在。"""
    ref = (strategy.backend_data or {}).get("bkbase_v4", {}).get("flow")
    if not ref:
        return []
    resource = flow_operation.read_controller_flow(context, strategy)
    return [] if resource is None else read_flow_nodes(context, ref, resource=resource)


def _input_result_table_refs(strategy, context, rt_ids, *, existing_nodes=None):
    """核对已有输入绑定，缺失引用按逻辑 ID 读取实际租户内项目。"""
    candidates = []
    for model in (CollectorPlugin, CollectorConfig, Snapshot):
        for logical_id, binding in model.objects.filter(bkbase_table_id__in=rt_ids).values_list(
            "bkbase_table_id", "bkbase_v4_resources"
        ):
            binding = binding or {}
            if not isinstance(binding, dict):
                raise BKBaseResourceMappingError(message="Invalid local ResultTable binding")
            if binding.get("result_table"):
                if binding.get("result_table_id") not in (None, logical_id):
                    raise BKBaseResourceMappingError(
                        message="Local input ResultTable binding has a conflicting logical ID"
                    )
                candidates.append((logical_id, binding["result_table"]))
    flow_ref = (strategy.backend_data or {}).get("bkbase_v4", {}).get("flow")
    if flow_ref:
        nodes = _controller_flow_nodes(context, strategy) if existing_nodes is None else existing_nodes
        for node in nodes:
            if node.get("kind") in ("StreamSourceNode", "StreamStaticSource", "BatchStaticSource", "BatchSourceNode"):
                candidates.append((None, node.get("data")))
    verified, resources = {}, {}
    for expected_id, candidate in candidates:
        ref = source_service._replay_ref(context, candidate, "ResultTable")
        key = tuple(ref[field] for field in ("tenant", "namespace", "name"))
        if key not in resources:
            resources[key] = _verified_input_ref(context, ref)
        ref, logical_id = resources[key]
        if expected_id is not None and logical_id != expected_id:
            raise BKBaseResourceMappingError(message="Input ResultTable logical identity mismatch")
        if logical_id not in rt_ids:
            continue
        if logical_id in verified and verified[logical_id] != ref:
            raise BKBaseResourceMappingError(message="Multiple input ResultTable references for the same logical ID")
        verified[logical_id] = ref
    for logical_id in rt_ids:
        if logical_id not in verified:
            verified[logical_id] = metadata_service.get_result_table_ref(context, logical_id)
    return verified


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
    existing_nodes = _controller_flow_nodes(context, strategy)
    input_refs = _input_result_table_refs(strategy, context, rt_ids, existing_nodes=existing_nodes)
    metadata = metadata_service.get_result_tables(rt_ids, related=["fields", "storages"], context=context)
    sources = {}
    kinds = {
        FlowDataSourceNodeType.REALTIME: "StreamSourceNode",
        FlowDataSourceNodeType.REDIS_KV_SOURCE: "StreamStaticSource",
        FlowDataSourceNodeType.BATCH: "BatchStaticSource",
        FlowDataSourceNodeType.BATCH_REAL: "BatchSourceNode",
    }
    for rt_id in rt_ids:
        sources[rt_id] = {
            "kind": kinds[controller.check_source_type(rt_id)],
            "data": input_refs[rt_id],
        }
    controller.rt_node_map = {rt_id: node_name("src", rt_id) for rt_id in rt_ids}
    binding = (strategy.backend_data or {}).get("bkbase_v4", {})
    output_name = binding.get("output_name") or stable_name(
        AUDIT_EVENT_TABLE_PREFIX, strategy.namespace, strategy.strategy_id
    )
    output = binding.get("output_rt_id")
    if output:
        business, separator, raw_name = output.partition("_")
        if not separator or not business.isdecimal() or int(business) <= 0 or raw_name != output_name:
            raise BKBaseResourceMappingError(message="Saved Flow output identity is invalid")
        biz_id = int(business)
    else:
        if binding.get("flow") and (strategy.backend_data or {}).get("flow_id"):
            raise BKBaseResourceMappingError(message="Migrated Flow requires its verified original output RT")
        biz_id = metadata[0].get("bk_biz_id")
        if type(biz_id) is not int or biz_id <= 0:
            raise BKBaseResourceMappingError(message="Missing input RT business ID")
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
        existing_batch = [
            node for node in existing_nodes if node.get("kind") == "BatchSqlNode" and node.get("output") == output
        ]
        if len(existing_batch) > 1:
            raise BKBaseResourceMappingError(message="Ambiguous existing batch output")
        sql_node = _batch_node(controller, old_sql, profile, existing=existing_batch[0] if existing_batch else None)
    storages = []
    for cls in controller.storage_nodes:
        config = cls(namespace=strategy.namespace).build_node_config(
            bk_biz_id=biz_id, raw_table_name=output_name, from_result_table_ids=[output]
        )
        if config:
            storages.append(
                _storage_node(context, strategy, config, profile, existing_nodes=existing_nodes, output_rt_id=output)
            )
    if not isinstance(profile.get("operation_config"), dict):
        raise BKBaseResourceMappingError(message="V4 Flow deployment resources must be explicitly configured")
    operation = deepcopy(profile["operation_config"])
    operation["start_position"] = BKBASE_FLOW_CONSUMING_MODE
    if sql_node["kind"] == "BatchSqlNode":
        operation.setdefault("stream_sql_deploy_config", None)
    spec = build_rule_flow(
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
    if sql_node["kind"] == "BatchSqlNode":
        _validate_batch_deployment(context, spec)
    _save_operation_binding(context, strategy, {"output_name": output_name, "output_rt_id": output})
    return spec


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
    binding = (controller.strategy.backend_data or {}).get("bkbase_v4", {})
    if status in ("start", "stop") and binding.get("flow") and not binding.get("pending_spec"):
        return flow_operation.request(controller.strategy, status)
    if status == "restart" and binding.get("flow") and not binding.get("pending_spec"):
        return flow_operation.request_restart(controller.strategy)
    flow_operation.check_writable(controller.strategy)
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
    if not has_flow(controller.strategy):
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
    """拒绝跨版本、无当前身份或已被新操作替代的回调。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return operation_id is None
    saved = (strategy.backend_data or {}).get("bkbase_v4", {})
    if not operation_id or saved.get("operation_id") != operation_id:
        return False
    return not any(
        op.get("id") == operation_id and op.get("superseded_by")
        for op in (saved.get("pure_operation") or {}, saved.get("delete_operation") or {})
    )


def persist_operation_status(strategy, operation_id, status, message=None):
    """短事务内再次检查操作身份，过期或跨版本回调不得写状态。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        if operation_id is not None:
            return False
        strategy.status = status
        if message is not None:
            strategy.status_msg = message
            strategy.save(update_record=False, update_fields=["status_msg"])
        strategy.save(update_record=False, update_fields=["status"])
        return True
    with transaction.atomic():
        current = Strategy.objects.select_for_update().get(pk=strategy.pk)
        if not is_current_operation(current, operation_id) or flow_operation.is_pure(current):
            return False
        graph_became_running = (
            current.status in (StrategyStatusChoices.STARTING, StrategyStatusChoices.UPDATING)
            and status == StrategyStatusChoices.RUNNING
        )
        current.status = status
        fields = ["status"]
        if message is not None:
            current.status_msg = message
            fields.append("status_msg")
        current.save(update_record=False, update_fields=fields)
        if graph_became_running:
            flow_operation.enqueue_monitor_after_commit(
                strategy,
                operation_id,
                is_active=True,
                expected_configuration=flow_operation._configuration(strategy),
                expected_status=StrategyStatusChoices.RUNNING,
            )
    strategy.status = current.status
    strategy.status_msg = current.status_msg
    return True


def strategy_deploy_data(strategy):
    """按实际观测生成现有策略任务的状态契约，不复制未知字段。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return get_flow_deploy_data(flow_id=strategy.backend_data["flow_id"])
    if flow_operation.is_pure(strategy):
        pure = flow_operation.binding(strategy)["pure_operation"]
        if pure.get("restart"):
            # 详情读取不驱动重启的下一次写入。
            return {"status": "success" if pure.get("goal_observed") else "other", "logs": []}
        return flow_operation.observe(strategy)
    if getattr(strategy, "status", None) in (
        StrategyStatusChoices.FAILED,
        StrategyStatusChoices.START_FAILED,
        StrategyStatusChoices.UPDATE_FAILED,
        StrategyStatusChoices.STOP_FAILED,
    ):
        # 已结束发送的失败只允许用户重新登记，迟到的同代回调不能自动补发。
        return {
            "status": "failure",
            "flow_status": "failure",
            "logs": [
                {"level": "ERROR", "message": strategy.status_msg or "Flow operation failed; explicit retry required."}
            ],
        }
    count = (strategy.backend_data or {}).get("bkbase_v4", {}).get("poll_count", 0) + 1
    operation_id = (strategy.backend_data or {}).get("bkbase_v4", {}).get("operation_id")
    context = get_bkbase_context()
    context["operation_id"] = operation_id
    try:
        observed = advance_rule_flow(context, strategy)
    except BKBaseOperationSuperseded:
        return {"status": "superseded", "flow_status": None, "logs": []}
    except BKBaseFlowWriteFailed as error:
        observed = {"task_state": TaskState.FAILED, "message": str(error)}
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


def read_flow_nodes(context, flow_ref, *, require_applied=False, resource=None):
    """读取正式 Flow 的原生节点，校验资源身份并保留平台节点模型。"""
    params = resource_params(context, flow_ref, kind="Flow")
    value = api.bk_base_v4.flow_get(**params) if resource is None else resource
    if not isinstance(value, dict) or value.get("kind") != "Flow" or not isinstance(value.get("metadata"), dict):
        raise BKBaseResourceMappingError(message="Invalid V4 Flow resource")
    if any(value["metadata"].get(key) != params[key] for key in ("tenant", "namespace", "name")):
        raise BKBaseResourceMappingError(message="V4 Flow resource identity mismatch")
    if require_applied and (value.get("status") or {}).get("phase") != "Ok":
        raise BKBaseResourceMappingError(message="V4 Flow configuration has not been applied")
    spec = value.get("spec")
    nodes = spec.get("nodes") if isinstance(spec, dict) else None
    if not isinstance(nodes, list) or any(
        not isinstance(node, dict)
        or not isinstance(node.get("kind"), str)
        or not node["kind"]
        or not isinstance(node.get("name"), str)
        or not node["name"]
        for node in nodes
    ):
        raise BKBaseResourceMappingError(message="Invalid V4 Flow node structure")
    return deepcopy(nodes)


def batch_processing_id(strategy):
    """从生效的规则 Flow 选出唯一目标 BatchSqlNode 的 output。"""
    binding = (strategy.backend_data or {}).get("bkbase_v4") or {}
    ref = binding.get("flow")
    if not isinstance(ref, dict):
        raise BKBaseResourceMappingError(message="C19: missing V4 Flow reference for batch history")
    nodes = read_flow_nodes(get_bkbase_context(), ref, require_applied=True)
    candidates = [node for node in nodes if node.get("kind") == "BatchSqlNode"]
    target = binding.get("output_rt_id")
    if target:
        candidates = [node for node in candidates if node.get("output") == target]
    if len(candidates) != 1:
        raise BKBaseResourceMappingError(message="Cannot uniquely identify the rule BatchSqlNode")
    output = candidates[0].get("output")
    if not isinstance(output, str) or not output.strip():
        raise BKBaseResourceMappingError(message="BatchSqlNode output is missing")
    return output


def has_flow(strategy):
    """只判断当前版本绑定；已知旧Flow缺引用是C19，不能冒充无资源。"""
    backend = strategy.backend_data or {}
    if get_bkbase_version() == BKBaseVersion.V4:
        ref = (backend.get("bkbase_v4") or {}).get("flow")
        if not ref and backend.get("flow_id"):
            raise BKBaseResourceMappingError(message="C19：已有旧Flow但缺少V4正式绑定，不能判定无Flow或已停止")
        return bool(ref)
    return bool(backend.get("flow_id"))


def observe_strategy_status(strategy):
    """后台巡检读取正式资源的配置应用状态，不驱动更新。"""
    if not has_flow(strategy):
        return {"flow_status": "no-start"}
    if get_bkbase_version() == BKBaseVersion.V3:
        return get_flow_deploy_data(flow_id=strategy.backend_data["flow_id"])
    result = get_rule_flow_status(get_bkbase_context(), strategy)
    state = {TaskState.RUNNING: "running", TaskState.STOPPED: "no-start", TaskState.FAILED: "failure"}.get(
        result["task_state"], "pending"
    )
    return {"flow_status": state}


def _write_flow_request(context, strategy, endpoint, **params):
    """既有改图和重启仅添加持久互斥，不改变其业务协议。"""
    with flow_operation.write_guard(context, strategy):
        try:
            return endpoint(**params)
        except Exception as error:
            raise BKBaseFlowWriteFailed(message=f"Flow发送失败或受理未知，用户可重试：{error}") from error


def route_pure_toggle(controller, target):
    """在控制器选择重启前拦截已有纯启停，以及稳定绑定的停用。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return False
    strategy = controller.strategy
    if flow_operation.route(strategy, target):
        return True
    if target == "start":
        try:
            if flow_operation.retry_failed_flow(strategy):
                return True
        except (APIRequestError, LockError):
            # 额外恢复预检的读取失败仍由原启停入口登记和反馈。
            pass
    saved = flow_operation.binding(strategy)
    if (
        target == "start"
        and strategy.status == StrategyStatusChoices.RUNNING
        and saved.get("flow")
        and not saved.get("pending_spec")
    ):
        flow_operation.request_restart(strategy)
        return True
    return False


def retry_failed_pure(strategy):
    """正式Failed先恢复原图，既有纯操作失败继续按原目标重试。"""
    if get_bkbase_version() != BKBaseVersion.V4 or strategy.strategy_type != StrategyType.RULE:
        return False
    if flow_operation.retry_failed_flow(strategy):
        return True
    if getattr(strategy, "_bkbase_missing_create_expected", None) is not None:
        return False
    pure = flow_operation.binding(strategy).get("pure_operation") or {}
    target = pure.get("target")
    if (
        flow_operation.is_pure(strategy)
        and pure.get("restart")
        and strategy.status == StrategyStatusChoices.UPDATE_FAILED
    ):
        if flow_operation.can_retry_restart(strategy):
            flow_operation.retry_restart(strategy)
            return True
        raise BKBaseFlowOperationPending(message="Flow 重启未完成，请先核实本次停止或启动结果")
    if pure.get("id") != flow_operation.binding(strategy).get("operation_id") or target not in ("start", "stop"):
        return False
    if strategy.status != flow_operation._statuses(target)[2]:
        return False
    if (
        pure.get("writer")
        or pure.get("observing")
        or pure.get("write_fence")
        or pure.get("configuration") != flow_operation._configuration(strategy)
    ):
        raise BKBaseFlowOperationPending()
    flow_operation.request(strategy, target)
    return True


def prepare_controller_update(strategy, status):
    """V4改图排队前原子检查未决写，V3维持旧状态保存路径。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return False
    with flow_operation.locked_rows(strategy) as (current, rows):
        flow_operation.assert_active(current)
        flow_operation.assert_writable(rows)
        expected = getattr(strategy, "_bkbase_missing_create_expected", None)
        if expected is not None or flow_operation.pending_create(current):
            expected = expected or (
                flow_operation.binding(current).get("operation_id"),
                flow_operation._configuration(current),
            )
            flow_operation.check_create_rebuild(current, rows, expected)
        current.status = status
        current.save(update_record=False, update_fields=["status"])
    strategy.status = status
    if hasattr(strategy, "_bkbase_missing_create_expected"):
        del strategy._bkbase_missing_create_expected
    return True


def check_pure_operation(strategy, operation_id):
    """普通启停回调只读观察，重启回调按已登记的停止、启动步骤推进。"""
    if get_bkbase_version() == BKBaseVersion.V3 or not flow_operation.is_pure(strategy, operation_id):
        return False
    pure = flow_operation.binding(strategy)["pure_operation"]
    result = flow_operation.observe_restart(strategy) if pure.get("restart") else flow_operation.observe(strategy)
    if result.get("retry"):
        flow_operation.enqueue(strategy, countdown=True)
    return True


def recover_pure_operation(strategy):
    """复用既有周期任务补排只读观察，登记与队列之间崩溃也不补发PUT。"""
    if get_bkbase_version() == BKBaseVersion.V3 or not flow_operation.is_pure(strategy):
        return False
    if not (strategy.backend_data or {})["bkbase_v4"]["pure_operation"].get("observing"):
        return False
    flow_operation.enqueue(strategy)
    return True


def lock_strategy_configuration(strategy):
    """由既有update_db事务调用，将配置与启停登记置于相同行锁边界。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return False
    with flow_operation.locked_rows(strategy) as (current, rows):
        flow_operation.assert_active(current)
        flow_operation.assert_writable(rows)
        if current.status in (
            StrategyStatusChoices.STARTING,
            StrategyStatusChoices.STOPPING,
            StrategyStatusChoices.UPDATING,
        ) and not flow_operation.unsent_cancelled(current):
            raise BKBaseFlowOperationPending()
        # 用锁定读的当前值，避免REPEATABLE READ下refresh回旧的一致性快照。
        for field in Strategy._meta.concrete_fields:
            setattr(strategy, field.attname, deepcopy(getattr(current, field.attname)))
    return True


def reserve_configuration_update(strategy, need_update_remote, draft_save):
    """配置事务提交时同时标记待改图，避免队列之前插入纯启停。"""
    if get_bkbase_version() == BKBaseVersion.V4 and need_update_remote and not draft_save:
        strategy.status = StrategyStatusChoices.UPDATING
        strategy.save(update_record=False, update_fields=["status"])


def prepare_controller_delete(strategy):
    """V4控制器按删除预约提交停止声明；V3维持原同步调用。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return False
    flow_delete.declare(strategy)
    return True


def uses_v4_delete(strategy=None):
    """删除资源需按版本选择事务边界。"""
    if get_bkbase_version() != BKBaseVersion.V4:
        return False
    if strategy is not None and strategy.strategy_type != StrategyType.RULE and strategy.control_id:
        control_type = Control.objects.filter(pk=strategy.control_id).values_list("control_type_id", flat=True).first()
        if control_type == ControlTypeChoices.BKM:
            if flow_operation.binding(strategy).get("flow") or flow_operation.binding(strategy).get("delete_operation"):
                raise BKBaseResourceMappingError(message="非BKBase控件带有Flow删除绑定，需先核实归属")
            return False
    return True


def reserve_strategy_delete(strategy):
    """Web入口在Flow I/O前持久预约删除。"""
    return flow_delete.reserve(strategy)


def finish_strategy_delete(strategy, operation_id):
    """将本地级联放入同一预约身份校验的短事务。"""
    return flow_delete.ready(strategy, operation_id)
