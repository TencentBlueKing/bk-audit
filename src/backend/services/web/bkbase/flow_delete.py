"""协调停止声明与策略本地删除的持久预约。

预约和受理回执独立提交，HTTP位于事务外；本地级联用同一预约校验后提交。
明确受理只证明停止期望态保存，不证明引擎停止或平台资源清理。
"""
from contextlib import contextmanager
from copy import deepcopy
from uuid import uuid4

from bk_resource import api

from api.bk_base_v4.default import flow_spec_for_write
from services.web.bkbase import flow
from services.web.bkbase import flow_operation as operations
from services.web.bkbase.common import get_bkbase_context, resource_params
from services.web.bkbase.exceptions import (
    BKBaseFlowOperationPending,
    BKBaseResourceMappingError,
)
from services.web.strategy_v2.constants import StrategyStatusChoices


def _signature(strategy):
    """配置及本地归属身份变化后，旧删除不得完成。"""
    backend = strategy.backend_data or {}
    return operations._digest(
        {
            "configuration": operations._configuration(strategy),
            "namespace": strategy.namespace,
            "legacy_flow": backend.get("flow_id"),
            "legacy_id": backend.get("id"),
        }
    )


def _scope():
    context = get_bkbase_context()
    return [context["version"], context["tenant"], context["namespace"]]


def _known_stop(strategy):
    pure = operations.binding(strategy).get("pure_operation") or {}
    return bool(
        operations.is_pure(strategy)
        and pure.get("target") == "stop"
        and pure.get("configuration") == operations._configuration(strategy)
        and not pure.get("writer")
        and not pure.get("outcome_unknown")
        and pure.get("attempted")
        and pure.get("accepted") is True
    )


def _conflicts(current, rows):
    """仅允许本策略可证明已结束发送的stop，不绕过其他写保护。"""
    for row in rows:
        if row.pk != current.pk:
            operations.assert_writable([row])
            continue
        saved = operations.binding(row)
        if (
            saved.get("flow_write")
            or (saved.get("pure_operation") or {}).get("writer")
            or (saved.get("delete_operation") or {}).get("writer")
            or (
                (saved.get("pure_operation") or {}).get("write_fence")
                and not _known_stop(row)
                and not operations.can_replace_with_stop(row)
            )
        ):
            raise BKBaseFlowOperationPending()


def _no_flow(strategy, *, operation_id=None):
    saved, backend = operations.binding(strategy), strategy.backend_data or {}
    return not (
        saved.get("flow")
        or backend.get("flow_id")
        or backend.get("id")
        or saved.get("pending_spec")
        or saved.get("flow_write")
        or saved.get("pure_operation")
        or saved.get("restart_waiting")
        or saved.get("managed_nodes")
        or saved.get("output_rt_id")
        or saved.get("engine_flow_id")
        or (saved.get("operation_id") and saved.get("operation_id") != operation_id)
        or strategy.status
        in (StrategyStatusChoices.STARTING, StrategyStatusChoices.UPDATING, StrategyStatusChoices.STOPPING)
    )


def _current(current, operation_id):
    saved = operations.binding(current)
    operation = saved.get("delete_operation") or {}
    if not (
        operation.get("id") == operation_id == saved.get("operation_id")
        and not operation.get("superseded_by")
        and operation.get("target") == "stop"
        and operation.get("pending")
        and operation.get("configuration") == _signature(current)
        and operation.get("scope") == _scope()
        and operation.get("flow") == saved.get("flow")
    ):
        raise BKBaseFlowOperationPending(message="删除预约已变化，不能沿用旧停止声明删除策略")
    return operation


def reserve(strategy):
    """短事务预约；重复请求复用同一未决或明确受理意图。"""
    operations.assert_detached()
    ref = operations.binding(strategy).get("flow")
    if ref:
        resource_params(get_bkbase_context(), ref, kind="Flow")
    with operations.locked_rows(strategy) as (current, rows):
        operations.assert_active(current)
        saved = deepcopy(operations.binding(current))
        previous = saved.get("delete_operation") or {}
        if previous.get("pending"):
            _current(current, previous.get("id"))
            if previous.get("no_send_proof") == "observed_stopped":
                # 旧MCP派生凭证不证明目标身份；只有确知未发送才能沿同一预约声明。
                if (
                    previous.get("attempted") is not False
                    or previous.get("writer")
                    or previous.get("outcome_unknown") is not False
                ):
                    raise BKBaseFlowOperationPending(message="旧观察预约发送情况无法确认，保留C18写保护")
                if previous.get("stage") != "ready" or previous.get("accepted") is not None:
                    raise BKBaseFlowOperationPending(message="C19：旧观察凭证不能替代停止受理")
                previous.pop("no_send_proof")
                previous["stage"] = "registered"
                operations._save(current, strategy, saved, message="旧观察无发送，待正式停止声明受理")
            strategy.backend_data = deepcopy(current.backend_data)
            return previous["id"]
        _conflicts(current, rows)
        for row in rows:
            if row.pk != current.pk and (operations.binding(row).get("delete_operation") or {}).get("pending"):
                raise BKBaseFlowOperationPending()
        local_only = not ref
        if local_only and not _no_flow(current):
            raise BKBaseResourceMappingError(message="缺少正式Flow绑定或仍有创建意图，不能按无Flow删除")
        adopt = bool(ref) and _known_stop(current)
        pure = saved.get("pure_operation") or {}
        operation_id = pure["id"] if adopt else uuid4().hex
        if not adopt:
            operations.supersede_finished(rows, operation_id)
            saved = deepcopy(operations.binding(current))
        operation = {
            "id": operation_id,
            "target": "stop",
            "pending": True,
            "flow": deepcopy(ref),
            "configuration": _signature(current),
            "scope": _scope(),
            "local_only": local_only,
            "stage": "ready" if local_only or adopt else "registered",
            "attempted": bool(adopt and pure.get("attempted")),
            "accepted": True if adopt and pure.get("accepted") is True else None,
            "outcome_unknown": False,
        }
        if local_only:
            operation["no_send_proof"] = "no_flow"
        if not adopt and operations.can_replace_with_stop(current):
            saved["pure_operation"].update(write_fence=False, observing=False, superseded_by=operation_id)
        saved.update(operation_id=operation_id, requested_action="stop", delete_operation=operation)
        operations._save(
            current,
            strategy,
            saved,
            status=None if local_only else StrategyStatusChoices.STOPPING,
            message="已预约删除；停止期望态明确保存后才执行本地级联",
        )
        return operation_id


def _validate(resource, ref):
    operations._validate_resource(resource, ref)
    if not isinstance(resource["spec"].get("nodes"), list):
        raise BKBaseResourceMappingError(message="完整Flow节点配置不可用，停止声明未确认")


def _receipt(strategy, operation_id, *, outcome, writer_token=None):
    """保存本次发送结果；迟到的未发送失败不能覆盖其他线程的受理。"""
    with operations.locked_rows(strategy) as (current, rows):
        saved = deepcopy(operations.binding(current))
        try:
            operation = _current(current, operation_id)
        except BKBaseFlowOperationPending:
            return
        if outcome == "not_sent" and (operation.get("attempted") or operation.get("stage") != "registered"):
            return
        if outcome in ("accepted", "unknown") and operation.get("stage") != "sending":
            return
        if outcome in ("accepted", "unknown") and (not writer_token or operation.get("writer") != writer_token):
            return
        operation = saved["delete_operation"]
        operation.pop("writer", None)
        if outcome == "accepted":
            operation.update(stage="ready", accepted=True, outcome_unknown=False)
            message = "停止期望态已保存，待本地删除；不代表引擎已停止"
        elif outcome == "unknown":
            operation.update(stage="unknown", accepted=None, outcome_unknown=True, pending=False)
            message = "停止声明发送已结束，受理未知；策略未删除，用户可重试"
        else:
            operation.update(stage=outcome, accepted=False, outcome_unknown=False, pending=False)
            message = "停止声明未发送，策略未删除"
        operations._save(
            current,
            strategy,
            saved,
            message=message,
            status=StrategyStatusChoices.DELETE_FAILED if outcome in ("not_sent", "unknown") else None,
        )
        if outcome in ("accepted", "unknown", "not_sent"):
            for row in rows:
                if row.pk == current.pk:
                    continue
                alias_saved = deepcopy(operations.binding(row))
                alias = alias_saved.get("delete_operation") or {}
                if alias.get("id") != operation_id:
                    continue
                if outcome == "not_sent" and (
                    alias.get("attempted") or alias.get("writer") or alias.get("stage") != "registered"
                ):
                    continue
                if outcome != "not_sent" and alias.get("writer") != writer_token:
                    continue
                alias.pop("writer", None)
                if outcome in ("unknown", "not_sent"):
                    alias.update(
                        stage=outcome,
                        accepted=None if outcome == "unknown" else False,
                        outcome_unknown=outcome == "unknown",
                        pending=False,
                    )
                    operations._save(row, row, alias_saved, status=StrategyStatusChoices.DELETE_FAILED, message=message)
                else:
                    alias.update(
                        stage="superseded",
                        accepted=True,
                        outcome_unknown=False,
                        pending=False,
                        superseded_by=operation_id,
                    )
                    operations._save(row, row, alias_saved, message="同 Flow 的删除预约已由原请求处理")


def declare(strategy):
    """Controller真实删除入口：同一预约最多发送一次停止声明。"""
    operation_id = reserve(strategy)
    operation = operations.binding(strategy)["delete_operation"]
    if operation.get("stage") != "registered" or operation.get("attempted"):
        return
    context, ref = get_bkbase_context(), operation["flow"]
    params = resource_params(context, ref, kind="Flow")
    with flow.resource_lock(context, ref):
        try:
            resource = api.bk_base_v4.flow_get(**params)
            _validate(resource, ref)
        except Exception:
            _receipt(strategy, operation_id, outcome="not_sent")
            return
        with operations.locked_rows(strategy) as (current, rows):
            operations.assert_active(current)
            operation = _current(current, operation_id)
            _conflicts(current, rows)
            if operation.get("stage") != "registered" or operation.get("attempted"):
                return
            saved = deepcopy(operations.binding(current))
            writer_token = uuid4().hex
            saved["delete_operation"].update(
                stage="sending", attempted=True, accepted=None, outcome_unknown=True, writer=writer_token
            )
            operations._save(current, strategy, saved, message="停止声明正在发送，当前策略尚未删除")
        metadata, spec = deepcopy(resource["metadata"]), deepcopy(resource["spec"])
        metadata.setdefault("annotations", {})["task_stopped"] = "true"
        try:
            result = api.bk_base_v4.flow_update(**params, metadata=metadata, spec=spec, status=None)
            _validate(result, ref)
            task_stopped = result["metadata"].get("annotations", {}).get("task_stopped")
            if task_stopped != "true" or flow_spec_for_write(result["spec"]) != flow_spec_for_write(spec):
                raise BKBaseResourceMappingError(message="停止声明响应与本次完整请求不一致")
        except Exception:
            _receipt(strategy, operation_id, outcome="unknown", writer_token=writer_token)
        else:
            _receipt(strategy, operation_id, outcome="accepted", writer_token=writer_token)


@contextmanager
def ready(strategy, operation_id):
    """同一短事务核定受理并执行调用方本地级联，异常全部回滚。"""
    with operations.locked_rows(strategy) as (current, rows):
        operations.assert_active(current)
        operation = _current(current, operation_id)
        _conflicts(current, rows)
        proof = operation.get("no_send_proof")
        if operation.get("stage") != "ready" or operation.get("outcome_unknown") or operation.get("writer"):
            raise BKBaseFlowOperationPending(message="停止声明尚未明确受理，策略未删除")
        if proof == "no_flow":
            if not _no_flow(current, operation_id=operation_id):
                raise BKBaseFlowOperationPending()
        elif proof:
            raise BKBaseFlowOperationPending(message="C19：观察凭证不能替代明确停止受理")
        elif not (operation.get("attempted") and operation.get("accepted") is True):
            raise BKBaseFlowOperationPending(message="缺少本次明确停止受理记录，策略未删除")
        yield current
        saved = deepcopy(operations.binding(current))
        saved["delete_operation"].update(pending=False, stage="deleted")
        operations._save(current, strategy, saved)
