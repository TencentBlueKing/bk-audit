"""显式规划并切换已停用V4 Flow的ES切日时区。

普通改图继续保护完整物理目标；本入口只允许同模板同存储的整数8到0。
执行前备份并复核唯一归属，未确认写保留既有flow_write保护，不自动重试。
"""

from copy import deepcopy

from bk_resource import api

from api.bk_base_v4.default import flow_spec_for_write
from services.web.bkbase import flow, flow_operation
from services.web.bkbase.common import resource_lock, resource_params
from services.web.bkbase.constants import (
    BKBASE_V4_ES_ROLLOVER_TIMEZONE,
    BKBASE_V4_LEGACY_ES_ROLLOVER_TIMEZONE,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.constants import StrategyStatusChoices, StrategyType
from services.web.strategy_v2.models import Strategy

SCHEMA_VERSION = 1
REF_FIELDS = ("kind", "tenant", "namespace", "name")


class _UnconfirmedWrite(BaseException):
    """让既有write_guard保留未知写凭据，退出保护后再转为业务异常。"""


def convert_spec(spec):
    """深拷贝整图，仅将有日模板且显式整数8的ES节点切换到0。"""
    if not isinstance(spec, dict) or not isinstance(spec.get("nodes"), list):
        raise BKBaseResourceMappingError(message="Invalid Flow graph for ES timezone migration")
    result = deepcopy(spec)
    flow.validate_graph(result["nodes"])
    changes = []
    for node in result["nodes"]:
        if node.get("kind") != "EsStorageNode":
            continue
        storage = node.get("storage")
        if (
            not isinstance(storage, dict)
            or storage.get("kind") != "ElasticSearch"
            or any(not isinstance(storage.get(key), str) or not storage[key] for key in REF_FIELDS)
        ):
            raise BKBaseResourceMappingError(message="ES node requires an explicit storage reference")
        alias = node.get("write_alias")
        if not isinstance(alias, dict) or ("Fixed" in alias) == ("TimeBased" in alias):
            raise BKBaseResourceMappingError(message="ES write_alias is missing or ambiguous; do not guess")
        if "Fixed" in alias:
            if not isinstance(alias["Fixed"], str) or not alias["Fixed"]:
                raise BKBaseResourceMappingError(message="Invalid Fixed ES destination")
            continue
        timed = alias["TimeBased"]
        if not isinstance(timed, dict):
            raise BKBaseResourceMappingError(message="Invalid TimeBased ES destination")
        template, zone = timed.get("format"), timed.get("timezone")
        if (
            not isinstance(template, str)
            or not any(marker in template for marker in ("{yyyyMMdd}", "%Y%m%d"))
            or type(zone) is not int
            or zone not in (BKBASE_V4_LEGACY_ES_ROLLOVER_TIMEZONE, BKBASE_V4_ES_ROLLOVER_TIMEZONE)
        ):
            raise BKBaseResourceMappingError(message="ES daily template or timezone is not an explicit 8/0 value")
        if zone == BKBASE_V4_LEGACY_ES_ROLLOVER_TIMEZONE:
            timed["timezone"] = BKBASE_V4_ES_ROLLOVER_TIMEZONE
            changes.append({"node": node["name"], "from": zone, "to": BKBASE_V4_ES_ROLLOVER_TIMEZONE})
    return result, changes


def _local_snapshot(strategy):
    """计划固定归属和业务配置，避免预览后覆盖新一代配置。"""
    return deepcopy(
        {
            "namespace": strategy.namespace,
            "strategy_type": strategy.strategy_type,
            "status": strategy.status,
            "is_deleted": strategy.is_deleted,
            "configs": strategy.configs,
            "backend_data": strategy.backend_data,
        }
    )


def _check_local(strategy, rows, audit_namespace, flow_ref):
    """仅接受已停用且唯一绑定的规则策略，包含软删别名和未决操作。"""
    flow_operation.assert_active(strategy)
    saved = flow_operation.binding(strategy)
    pure = saved.get("pure_operation") or {}
    if (
        len(rows) != 1
        or strategy.namespace != audit_namespace
        or strategy.strategy_type != StrategyType.RULE
        or strategy.status != StrategyStatusChoices.DISABLED
        or saved.get("flow") != flow_ref
        or not saved.get("output_rt_id")
        or saved.get("pending_spec") is not None
        or not isinstance(pure, dict)
        or any(pure.get(key) for key in ("observing", "outcome_unknown"))
    ):
        raise BKBaseResourceMappingError(
            message="Timezone switch requires a unique, disabled rule strategy without pending work"
        )
    flow_operation.assert_writable(rows)


def _check_resource(context, flow_ref, value, output_rt_id):
    """核对正式Ref、已生效的停止配置及ES节点的原业务输出。"""
    params = resource_params(context, flow_ref, kind="Flow")
    if (
        not isinstance(value, dict)
        or value.get("kind") != "Flow"
        or not isinstance(value.get("metadata"), dict)
        or any(value["metadata"].get(key) != params[key] for key in ("tenant", "namespace", "name"))
        or (value.get("status") or {}).get("phase") != "Ok"
        or value["metadata"].get("annotations", {}).get("task_stopped") != "true"
    ):
        raise BKBaseResourceMappingError(message="Formal Flow must match its reference and be applied/stopped")
    after, changes = convert_spec(value.get("spec"))
    nodes = {node["name"]: node for node in after["nodes"]}
    outputs = [node for node in nodes.values() if node.get("output") == output_rt_id]
    if len(outputs) != 1 or outputs[0].get("kind") not in ("StreamNode", "BatchSqlNode"):
        raise BKBaseResourceMappingError(message="Flow output does not uniquely match the strategy binding")
    for node in nodes.values():
        if node.get("kind") == "EsStorageNode" and (
            node.get("input") != outputs[0]["name"] or node["storage"]["tenant"] != context["tenant"]
        ):
            raise BKBaseResourceMappingError(message="ES storage does not belong to the bound strategy output/tenant")
    return after, changes


def preview(context, strategy_id, audit_namespace, flow_ref):
    """只读生成完整备份和最小变化计划，不修改平台或本地绑定。"""
    if (
        type(strategy_id) is not int
        or strategy_id <= 0
        or not isinstance(audit_namespace, str)
        or not audit_namespace
        or not isinstance(flow_ref, dict)
        or set(flow_ref) != set(REF_FIELDS)
        or any(not isinstance(flow_ref.get(key), str) or not flow_ref[key] for key in REF_FIELDS)
    ):
        raise BKBaseResourceMappingError(message="Explicit strategy identity and full Flow reference are required")
    params = resource_params(context, flow_ref, kind="Flow")
    strategy = Strategy.objects.get(pk=strategy_id)
    with flow_operation.locked_rows(strategy) as (current, rows):
        _check_local(current, rows, audit_namespace, flow_ref)
        local = _local_snapshot(current)
    resource = api.bk_base_v4.flow_get(**params)
    after, changes = _check_resource(context, flow_ref, resource, local["backend_data"]["bkbase_v4"]["output_rt_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "strategy_id": strategy_id,
        "audit_namespace": audit_namespace,
        "flow_ref": deepcopy(flow_ref),
        "before_local": local,
        "before_resource": deepcopy(resource),
        "after_spec": after,
        "changes": changes,
        "action": "update" if changes else "unchanged",
    }


def apply_plan(context, plan, *, before_write):
    """锁内重新生成同一计划，持久备份后只发一次保持停止的PUT。

    仅表示精确配置回执已受理；配置应用及后续正常启动需另行观察。
    未确认回执保留flow_write未知标记，不能通过重跑命令自动解锁。
    """
    flow_operation.assert_detached()
    if (
        not isinstance(plan, dict)
        or type(plan.get("schema_version")) is not int
        or plan["schema_version"] != SCHEMA_VERSION
    ):
        raise BKBaseResourceMappingError(message="Invalid timezone migration plan")
    flow_ref = plan.get("flow_ref")
    params = resource_params(context, flow_ref, kind="Flow")
    with resource_lock(context, flow_ref):
        fresh = preview(context, plan.get("strategy_id"), plan.get("audit_namespace"), flow_ref)
        if fresh != plan:
            raise BKBaseResourceMappingError(
                message="Local configuration, formal Flow or plan changed; generate a new preview"
            )
        if fresh["action"] == "unchanged":
            return "unchanged"
        strategy = Strategy.objects.get(pk=plan["strategy_id"])
        write_context = {
            **context,
            "operation_id": fresh["before_local"]["backend_data"]["bkbase_v4"].get("operation_id"),
        }
        try:
            with flow_operation.write_guard(write_context, strategy):
                with flow_operation.locked_rows(strategy) as (current, rows):
                    local = _local_snapshot(current)
                    local["backend_data"]["bkbase_v4"].pop("flow_write", None)
                    if len(rows) != 1 or local != fresh["before_local"]:
                        raise BKBaseResourceMappingError(message="Strategy changed before timezone migration send")
                before_write()
                try:
                    result = api.bk_base_v4.flow_update(
                        **params,
                        metadata=deepcopy(fresh["before_resource"]["metadata"]),
                        spec=deepcopy(fresh["after_spec"]),
                        status=None
                    )
                    if (
                        not isinstance(result, dict)
                        or result.get("kind") != "Flow"
                        or any(
                            (result.get("metadata") or {}).get(key) != params[key]
                            for key in ("tenant", "namespace", "name")
                        )
                        or flow_spec_for_write(result.get("spec")) != flow_spec_for_write(fresh["after_spec"])
                        or (result.get("metadata") or {}).get("annotations", {}).get("task_stopped") != "true"
                    ):
                        raise ValueError("Timezone migration response is not the exact stopped target")
                except BaseException as error:
                    raise _UnconfirmedWrite() from error
        except _UnconfirmedWrite as error:
            raise BKBaseResourceMappingError(
                message="Timezone PUT outcome unconfirmed; retain flow_write and inspect the exact Flow before recovery"
            ) from error
    return "accepted"
