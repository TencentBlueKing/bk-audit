"""持久化已有 Flow 的纯启停意图与只读观察。

短事务登记后才发送，HTTP不持有数据库行锁；相同目标未决仅观察。
发送者在途时保留写保护；发送结束或观察结束后按操作代次允许用户重试。
"""
import hashlib
import json
from contextlib import contextmanager
from copy import deepcopy
from uuid import uuid4

from bk_resource import api
from blueapps.utils.logger import logger
from django.db import connection, transaction
from django.db.models import Q

from api.bk_base_v4.default import flow_spec_for_write
from services.web.analyze.constants import (
    BKBASE_FLOW_CONSUMING_MODE,
    CHECK_FLOW_STATUS_SLEEP_SECONDS,
)
from services.web.bkbase import flow
from services.web.bkbase.common import (
    get_bkbase_context,
    get_resource_or_none,
    resource_params,
)
from services.web.bkbase.constants import BKBASE_V4_MAX_POLLS, TaskState
from services.web.bkbase.exceptions import (
    BKBaseFlowOperationPending,
    BKBaseOperationSuperseded,
    BKBaseResourceMappingError,
)
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


def binding(strategy):
    """取得当前实例的V4绑定，不修改原对象。"""
    return (strategy.backend_data or {}).get("bkbase_v4", {})


def is_pure(strategy, operation_id=None):
    """只有当前操作身份一致的纯启停才进入独立观察分支。"""
    saved = binding(strategy)
    pure = saved.get("pure_operation") or {}
    return (
        bool(pure.get("id"))
        and pure["id"] == saved.get("operation_id")
        and not pure.get("superseded_by")
        and (operation_id is None or operation_id == pure["id"])
    )


def unsent_cancelled(strategy):
    """已取消且确定未尝试发送的旧登记不妨碍显式新请求。"""
    pure = binding(strategy).get("pure_operation") or {}
    return (
        is_pure(strategy)
        and not any(pure.get(key) for key in ("attempted", "observing", "write_fence"))
        and (strategy.status == _statuses(pure["target"])[0])
    )


@contextmanager
def locked_rows(strategy):
    """按固定顺序锁定当前业务中正式Flow的已知稳定关联行。"""
    ref = binding(strategy).get("flow")
    query = Q(pk=strategy.pk)
    if ref:
        query |= Q(
            **{f"backend_data__bkbase_v4__flow__{key}": ref[key] for key in ("kind", "tenant", "namespace", "name")}
        )
    with transaction.atomic():
        # 普通读取定位别名，再按主键加锁；不对JSON扫描结果执行FOR UPDATE。
        # 此QuerySet保留软删绑定，删除本地策略不能撤销尚未结束的远端写。
        ids = set(Strategy.objects.get_queryset().filter(query).values_list("pk", flat=True)) | {strategy.pk}
        rows = list(Strategy.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
        current = next(row for row in rows if row.pk == strategy.pk)
        if binding(current).get("flow") != ref:
            raise BKBaseOperationSuperseded()
        yield current, rows


def assert_writable(rows):
    """未决纯启停或一次尚未结束的实际写入不能被其他写穿过。"""
    for row in rows:
        saved = binding(row)
        pure = saved.get("pure_operation") or {}
        delete = saved.get("delete_operation") or {}
        if (
            pure.get("writer")
            or pure.get("write_fence")
            or saved.get("flow_write")
            or delete.get("pending")
            or delete.get("writer")
        ):
            raise BKBaseFlowOperationPending()


def check_writable(strategy):
    """提前拒绝未决资源，实际发送前仍须再次校验并登记。"""
    with locked_rows(strategy) as (current, rows):
        assert_active(current)
        assert_writable(rows)


def assert_active(strategy):
    """等待行锁期间完成的软删除，同样必须阻止后续写入。"""
    if strategy.is_deleted:
        raise BKBaseFlowOperationPending(message="策略已删除，不能继续发送Flow操作")


def assert_detached():
    """外层事务会推迟持久登记提交，必须在任何Flow发送前拒绝。"""
    if connection.in_atomic_block:
        raise BKBaseFlowOperationPending(message="Flow操作必须在外层事务提交后独立执行，当前请求未发送")


def _save(current, strategy, saved, *, status=None, message=None):
    """只合并本阶段状态；调用方必须已经持有当前行锁。"""
    backend = deepcopy(current.backend_data or {})
    backend["bkbase_v4"] = saved
    current.backend_data = backend
    fields = ["backend_data"]
    if status is not None:
        current.status = status
        fields.append("status")
    if message is not None:
        pure = saved.get("pure_operation") or {}
        baseline = pure.get("failure_baseline") or {}
        previous_message = baseline.get("message")
        if previous_message and not pure.get("goal_observed"):
            label = "恢复前失败" if baseline.get("phase") == "Failed" else "此前状态"
            message += f"；{label}：{previous_message}"
        elif pure.get("goal_observed") and saved.get("pending_spec"):
            message += "；仍有未发布配置，未应用待改图"
        current.status_msg = message
        fields.append("status_msg")
    current.save(update_record=False, update_fields=fields)
    strategy.backend_data, strategy.status, strategy.status_msg = backend, current.status, current.status_msg


def supersede_finished(rows, operation_id):
    """同一 Flow 的已结束意图标记被新代替，不触碰在途写。"""
    for row in rows:
        saved = deepcopy(binding(row))
        pure = saved.get("pure_operation") or {}
        deleted = saved.get("delete_operation") or {}
        changed = False
        if pure and not any(pure.get(key) for key in ("writer", "observing", "write_fence")):
            pure["superseded_by"] = operation_id
            changed = True
        if deleted and not deleted.get("pending") and not deleted.get("writer"):
            deleted["superseded_by"] = operation_id
            changed = True
        if changed:
            _save(row, row, saved)


@contextmanager
def write_guard(context, strategy):
    """给既有改图/重启的一次实际发送登记持久互斥，不延伸其恢复协议。"""
    assert_detached()
    token = uuid4().hex
    with locked_rows(strategy) as (current, rows):
        assert_active(current)
        assert_writable(rows)
        saved = deepcopy(binding(current))
        if saved.get("operation_id") != context.get("operation_id"):
            raise BKBaseOperationSuperseded()
        expected_create = context.get("missing_create_expected")
        if expected_create is not None:
            check_create_rebuild(current, rows, expected_create)
        saved["flow_write"] = {"token": token, "operation_id": context.get("operation_id")}
        _save(current, strategy, saved)
    finished = False
    try:
        yield
        finished = True
    except Exception:
        finished = True
        raise
    finally:
        with locked_rows(strategy) as (current, _):
            saved = deepcopy(binding(current))
            marker = saved.get("flow_write") or {}
            if (
                marker.get("token") == token
                and marker.get("operation_id") == context.get("operation_id")
                and saved.get("operation_id") == context.get("operation_id")
            ):
                if finished:
                    saved.pop("flow_write")
                else:
                    # BaseException/进程中断不能作为发送已结束的证明。
                    marker["outcome_unknown"] = True
                _save(current, strategy, saved)


def _digest(value):
    """配置摘要不保存额外业务数据，也不把状态和处理人当作图变更。"""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _matches_flow_spec_digest(spec, expected):
    """兼容原摘要以及新发送时补全、GET 时省略未启用侧的表示。"""
    return expected == _digest(spec) or expected == _digest(flow_spec_for_write(spec))


def _configuration(strategy):
    return _digest(
        {
            "configs": strategy.configs,
            "sql": strategy.sql,
            "control_id": strategy.control_id,
            "control_version": strategy.control_version,
            "link_table_uid": strategy.link_table_uid,
            "link_table_version": strategy.link_table_version,
            "strategy_type": strategy.strategy_type,
            "flow": binding(strategy).get("flow"),
            "pending_spec": binding(strategy).get("pending_spec"),
        }
    )


def pending_create(strategy):
    """识别仍保存原目标的创建阶段，不把发送结束等同创建成功。"""
    saved = binding(strategy)
    return (
        bool(saved.get("flow"))
        and saved.get("operation") == "create"
        and isinstance(saved.get("pending_spec"), dict)
        and bool(saved["pending_spec"])
        and saved.get("requested_action") != "stop"
    )


def check_create_rebuild(current, rows, expected):
    """只允许同代次、独占且无活动保护的创建重构，不封禁已结束发送提示。"""
    assert_active(current)
    assert_writable(rows)
    if (binding(current).get("operation_id"), _configuration(current)) != expected:
        raise BKBaseOperationSuperseded()
    pure = binding(current).get("pure_operation") or {}
    if (
        not pending_create(current)
        or len(rows) != 1
        or binding(current).get("flow_write") is not None
        or pure.get("observing")
        or (pure.get("restart") and not pure.get("goal_observed"))
    ):
        raise BKBaseFlowOperationPending(message="创建重试存在共享归属或未结束操作，不能重构Flow")


def read_controller_flow(context, strategy):
    """构图仅为受保护的创建候选接受明确不存在，共享该次正式观察。"""
    ref = binding(strategy)["flow"]
    params = resource_params(context, ref, kind="Flow")
    if not pending_create(strategy):
        return api.bk_base_v4.flow_get(**params)
    expected = (binding(strategy).get("operation_id"), _configuration(strategy))
    with locked_rows(strategy) as (current, rows):
        check_create_rebuild(current, rows, expected)
    resource = get_resource_or_none(api.bk_base_v4.flow_get, **params)
    with locked_rows(strategy) as (current, rows):
        check_create_rebuild(current, rows, expected)
    if resource is None:
        # 仅本次构图到实际发送的内存票据；原持久状态和发送恢复协议不变。
        context["missing_create_expected"] = expected
    return resource


def _statuses(target):
    if target == "stop":
        return StrategyStatusChoices.STOPPING, StrategyStatusChoices.DISABLED, StrategyStatusChoices.STOP_FAILED
    return StrategyStatusChoices.STARTING, StrategyStatusChoices.RUNNING, StrategyStatusChoices.START_FAILED


def can_replace_with_stop(strategy):
    """明确受理且发送者已结束的失败启动，可由新停止意图取代。"""
    pure = binding(strategy).get("pure_operation") or {}
    return bool(
        strategy.status == StrategyStatusChoices.START_FAILED
        and is_pure(strategy)
        and pure.get("target") == "start"
        and pure.get("attempted")
        and pure.get("accepted") is True
        and not pure.get("writer")
        and not pure.get("outcome_unknown")
        and pure.get("configuration") == _configuration(strategy)
    )


def route(strategy, target):
    """已有未决目标优先拦截，避免控制器把重复启动选择成重启。"""
    current = Strategy.objects.get(pk=strategy.pk)
    saved = binding(current)
    pure = saved.get("pure_operation") or {}
    if pure.get("writer") or pure.get("write_fence") or (is_pure(current) and pure.get("observing")):
        if pure.get("writer"):
            raise BKBaseFlowOperationPending()
        if pure.get("restart") and not pure.get("observing"):
            raise BKBaseFlowOperationPending(message="Flow 重启结果待核实，不能再次发送")
        if target == "stop" and can_replace_with_stop(current):
            request(current, target)
            return True
        expected = "start" if pure.get("restart") else pure.get("target")
        if not is_pure(current) or expected != target:
            raise BKBaseFlowOperationPending()
        enqueue(current)
        return True
    if (
        target == "start"
        and is_pure(current)
        and pure.get("restart")
        and current.status in (StrategyStatusChoices.UPDATE_FAILED, StrategyStatusChoices.UPDATING)
    ):
        if can_retry_restart(current):
            retry_restart(current)
            return True
        raise BKBaseFlowOperationPending(message="Flow 重启未完成，请先核实本次停止或启动结果")
    if (
        saved.get("flow")
        and not saved.get("pending_spec")
        and (
            target == "stop"
            or current.status == StrategyStatusChoices.DISABLED
            or (
                target == "start"
                and pure.get("id") == saved.get("operation_id")
                and pure.get("target") == "start"
                and current.status == StrategyStatusChoices.START_FAILED
            )
        )
    ):
        request(current, target)
        return True
    check_writable(current)
    return False


def _can_recover_failed_flow(strategy):
    """只允许稳定本地状态的原图启动，不取代正在发送或观察的动作。"""
    if strategy.status not in (
        StrategyStatusChoices.DISABLED,
        StrategyStatusChoices.RUNNING,
        StrategyStatusChoices.FAILED,
        StrategyStatusChoices.START_FAILED,
        StrategyStatusChoices.UPDATE_FAILED,
    ):
        return False
    pure = binding(strategy).get("pure_operation") or {}
    return not is_pure(strategy) or (
        pure.get("target") == "start"
        and not pure.get("restart")
        and not pure.get("observing")
        and pure.get("configuration") == _configuration(strategy)
    )


def _check_failed_flow_retry(current, expected):
    """正式预检与登记之间再次核同一代配置，避免改图或新意图被覆盖。"""
    if expected is None:
        return
    if binding(current).get("operation_id") != expected[0] or _configuration(current) != expected[1]:
        raise BKBaseOperationSuperseded()
    if not _can_recover_failed_flow(current):
        raise BKBaseFlowOperationPending()


def retry_failed_flow(strategy):
    """显式操作先判正式Failed；失败纯启动也可在Ok后按原目标重试。"""
    if not binding(strategy).get("flow") or not _can_recover_failed_flow(strategy):
        return False
    assert_detached()
    with locked_rows(strategy) as (current, rows):
        assert_active(current)
        assert_writable(rows)
        expected = (binding(current).get("operation_id"), _configuration(current))
        _check_failed_flow_retry(current, expected)
        ref = deepcopy(binding(current)["flow"])
        creating = pending_create(current)
        retrying_start = (
            current.status == StrategyStatusChoices.START_FAILED
            and is_pure(current)
            and binding(current)["pure_operation"].get("target") == "start"
        )
    context = get_bkbase_context()
    params = resource_params(context, ref, kind="Flow")
    remote = get_resource_or_none(api.bk_base_v4.flow_get, **params) if creating else api.bk_base_v4.flow_get(**params)
    if remote is None:
        with locked_rows(strategy) as (current, rows):
            _check_failed_flow_retry(current, expected)
            check_create_rebuild(current, rows, expected)
        strategy._bkbase_missing_create_expected = expected
        return False
    _validate_resource(remote, ref)
    phase = remote["status"].get("phase")
    if phase != "Failed" and not (retrying_start and phase == "Ok"):
        return False
    request(
        strategy,
        "start",
        expected_recovery=expected,
        failure_baseline=remote["status"] if phase == "Failed" else None,
    )
    return True


def request(strategy, target, *, expected_restart=None, expected_recovery=None, failure_baseline=None):
    """登记待发送意图；一次声明PUT后仅观察，不重发未知结果。"""
    assert_detached()
    context = get_bkbase_context()
    ref = binding(strategy).get("flow") or {}
    params = resource_params(context, ref, kind="Flow")
    monitor_accepted = False
    with flow.resource_lock(context, ref):
        with locked_rows(strategy) as (current, rows):
            assert_active(current)
            _check_restart_retry(current, expected_restart)
            _check_failed_flow_retry(current, expected_recovery)
            saved = deepcopy(binding(current))
            previous = saved.get("pure_operation") or {}
            replacing = target == "stop" and can_replace_with_stop(current)
            reused = not replacing and is_pure(current) and (previous.get("write_fence") or previous.get("observing"))
            if reused:
                if previous.get("restart") or previous.get("target") != target:
                    raise BKBaseFlowOperationPending()
                strategy.backend_data = deepcopy(current.backend_data)
            else:
                for row in rows:
                    if row.pk == current.pk and replacing:
                        if saved.get("flow_write") or (saved.get("delete_operation") or {}).get("pending"):
                            raise BKBaseFlowOperationPending()
                    else:
                        assert_writable([row])
                if (saved.get("pending_spec") and expected_recovery is None) or (
                    current.status
                    in (
                        StrategyStatusChoices.STARTING,
                        StrategyStatusChoices.STOPPING,
                        StrategyStatusChoices.UPDATING,
                    )
                    and not unsent_cancelled(current)
                ):
                    raise BKBaseFlowOperationPending()
                operation_id = uuid4().hex
                supersede_finished(rows, operation_id)
                saved = deepcopy(binding(current))
                saved.update(operation_id=operation_id, requested_action=target, poll_count=0)
                saved["pure_operation"] = {
                    "id": operation_id,
                    "target": target,
                    "configuration": _configuration(current),
                    "attempted": False,
                    "accepted": None,
                    "outcome_unknown": False,
                    "write_fence": True,
                    "observing": True,
                    "goal_observed": False,
                }
                if target == "start":
                    known_failure = failure_baseline or (
                        previous.get("failure_baseline") if not previous.get("goal_observed") else None
                    )
                    if known_failure:
                        saved["pure_operation"]["failure_baseline"] = deepcopy(known_failure)
                    elif current.status_msg:
                        saved["pure_operation"]["failure_baseline"] = {"message": current.status_msg}
                _save(current, strategy, saved, status=_statuses(target)[0], message="已登记启停意图，尚未发送")
        if not reused:
            operation_id = binding(strategy)["operation_id"]
            try:
                remote = api.bk_base_v4.flow_get(**params)
                _validate_resource(remote, ref)
                if target == "stop" and not isinstance(remote["spec"].get("nodes"), list):
                    raise BKBaseResourceMappingError(message="完整Flow节点不可用，未发送停止声明")
                if target == "start":
                    phase = (remote.get("status") or {}).get("phase")
                    if phase not in ("Ok", "Failed"):
                        raise BKBaseResourceMappingError(message="Flow 配置尚未生效，未发送启动")
                metadata, spec = deepcopy(remote["metadata"]), deepcopy(remote["spec"])
                metadata.setdefault("annotations", {})["task_stopped"] = "true" if target == "stop" else "false"
                if target == "start":
                    spec.setdefault("operation_config", {})["start_position"] = BKBASE_FLOW_CONSUMING_MODE
            except Exception as error:
                _receipt(
                    strategy,
                    operation_id,
                    attempted=False,
                    reason=str(error) if isinstance(error, BKBaseResourceMappingError) else "",
                )
            else:
                with locked_rows(strategy) as (current, _):
                    saved = deepcopy(binding(current))
                    pure = saved.get("pure_operation") or {}
                    if not is_pure(current, operation_id) or pure.get("attempted") or not pure.get("observing"):
                        return
                    if _configuration(current) != pure["configuration"]:
                        pure.update(write_fence=False, observing=False)
                        pure["message"] = "本地配置已变化，旧启停未发送"
                        _save(current, strategy, saved)
                        return
                    writer_token = uuid4().hex
                    if (
                        target == "start"
                        and phase == "Failed"
                        and (pure.get("failure_baseline") or {}).get("phase") != "Failed"
                    ):
                        # 首次正式读取才确认失败时，保留诊断但不据其字段推断远端代次。
                        pure["failure_baseline"] = deepcopy(remote["status"])
                    pure.update(
                        attempted=True,
                        outcome_unknown=True,
                        writer=writer_token,
                        spec_digest=_digest(flow_spec_for_write(spec)),
                    )
                    _save(current, strategy, saved, message="启停声明正在发送，远端结果待核实")
                try:
                    result = api.bk_base_v4.flow_update(**params, metadata=metadata, spec=spec, status=None)
                    _validate_resource(result, ref)
                    if (
                        (result["metadata"].get("annotations") or {}).get("task_stopped")
                        != ("true" if target == "stop" else "false")
                        or flow_spec_for_write(result["spec"]) != flow_spec_for_write(spec)
                        or (result.get("status") or {}).get("phase") != "Pending"
                    ):
                        raise BKBaseResourceMappingError(message="启停声明响应与本次完整请求不一致")
                except Exception:
                    _receipt(strategy, operation_id, attempted=True, writer_token=writer_token)
                else:
                    monitor_accepted = _receipt(
                        strategy, operation_id, attempted=True, accepted=True, writer_token=writer_token
                    )
    if monitor_accepted:
        # 回执已提交且Redis锁已释放；broker网络不能占用业务事务或资源锁。
        enqueue_monitor_after_commit(strategy, operation_id, is_active=target == "start")
    enqueue(strategy)


def _receipt(strategy, operation_id, *, attempted, accepted=False, reason="", writer_token=None):
    """保存本地回执，返回可在资源锁外排通知的信号；未知写判断不变。"""
    with locked_rows(strategy) as (current, rows):
        if not is_pure(current, operation_id):
            return
        saved = deepcopy(binding(current))
        pure = saved["pure_operation"]
        if attempted and (not writer_token or pure.get("writer") != writer_token):
            return False
        already_accepted = pure.get("accepted") is True
        if not attempted and (pure.get("attempted") or not pure.get("observing")):
            return
        # 发送结果之后必须重新开始观察；此前在途的快照不得用于解除写保护。
        pure.pop("observation", None)
        pure.pop("writer", None)
        pure.update(
            accepted=True if accepted else (None if attempted else False), outcome_unknown=attempted and not accepted
        )
        config_matches = _configuration(current) == pure["configuration"]
        if not attempted:
            pure.update(observing=False, write_fence=False)
            _save(
                current,
                strategy,
                saved,
                status=_statuses(pure["target"])[2] if config_matches else None,
                message=("读取Flow失败，启停未发送；可重新发起" + (f"：{reason}" if reason else "")) if config_matches else None,
            )
            for row in rows:
                if row.pk == current.pk or not is_pure(row, operation_id):
                    continue
                alias_saved = deepcopy(binding(row))
                alias = alias_saved["pure_operation"]
                if alias.get("attempted") or alias.get("writer"):
                    continue
                alias.pop("observation", None)
                alias.update(observing=False, write_fence=False)
                matches = _configuration(row) == alias.get("configuration")
                _save(
                    row,
                    row,
                    alias_saved,
                    status=_statuses(alias["target"])[2] if matches else None,
                    message="读取Flow失败，启停未发送；可重新发起" if matches else None,
                )
        elif not accepted:
            pure.update(observing=False, write_fence=False, goal_observed=False)
            _save(
                current,
                strategy,
                saved,
                status=_statuses(pure["target"])[2] if config_matches else None,
                message="启停发送已结束，受理未知；用户可重试" if config_matches else None,
            )
            for row in rows:
                if row.pk == current.pk or not is_pure(row, operation_id):
                    continue
                alias_saved = deepcopy(binding(row))
                alias = alias_saved["pure_operation"]
                if alias.get("writer") != writer_token:
                    continue
                alias.pop("writer", None)
                alias.pop("observation", None)
                alias.update(
                    accepted=None, outcome_unknown=True, observing=False, write_fence=False, goal_observed=False
                )
                matches = _configuration(row) == alias.get("configuration")
                _save(
                    row,
                    row,
                    alias_saved,
                    status=_statuses(alias["target"])[2] if matches else None,
                    message="启停发送已结束，受理未知；用户可重试" if matches else None,
                )
        else:
            if accepted and pure.get("goal_observed"):
                # 发送完成前的快照不解除保护，2xx持久成功后再只读观察一次。
                pure.update(goal_observed=False, observing=True)
            _save(
                current,
                strategy,
                saved,
                message="声明已受理，等待实际目标" if config_matches else None,
            )
            for row in rows:
                if row.pk == current.pk or not is_pure(row, operation_id):
                    continue
                alias_saved = deepcopy(binding(row))
                alias = alias_saved["pure_operation"]
                if alias.get("writer") != writer_token:
                    continue
                alias.pop("writer", None)
                alias.pop("observation", None)
                alias.update(accepted=True, outcome_unknown=False, goal_observed=False, observing=True)
                _save(row, row, alias_saved)
    return attempted and accepted and config_matches and not already_accepted


def enqueue_monitor_after_commit(
    strategy, operation_id, *, is_active, expected_configuration=None, expected_status=None
):
    """在事务与资源锁外发布通知任务，提交后重新核对现有操作身份和Ref。

    可传配置摘要及预期终态，受理后与提交回调前均核对。
    排队失败不改变已受理Flow结果，也不新增消息幂等状态。
    """
    expected_ref = deepcopy(binding(strategy).get("flow") or {})
    resource_params(get_bkbase_context(), expected_ref, kind="Flow")
    strategy_id = strategy.pk
    if expected_configuration is not None:
        try:
            current = Strategy.objects.filter(pk=strategy_id, is_deleted=False).first()
            if current is None or _configuration(current) != expected_configuration:
                return
        except Exception:
            logger.exception("BKBase restart monitor configuration check failed: strategy=%s", strategy_id)
            return

    def enqueue_current():
        try:
            current = Strategy.objects.filter(pk=strategy_id, is_deleted=False).first()
            if (
                current is None
                or not flow.is_current_operation(current, operation_id)
                or binding(current).get("flow") != expected_ref
            ):
                return
            if expected_configuration is not None and _configuration(current) != expected_configuration:
                return
            if expected_status is not None and current.status != expected_status:
                return
            if is_pure(current, operation_id):
                pure = binding(current)["pure_operation"]
                if pure.get("accepted") is not True or _configuration(current) != pure["configuration"]:
                    return
            # tasks同样依赖本模块；仅为打破该导入环延迟导入。
            from services.web.analyze.tasks import toggle_monitor

            toggle_monitor.delay(strategy_id=strategy_id, is_active=is_active, operation_id=operation_id)
        except Exception:
            logger.exception("BKBase monitor task enqueue failed: strategy=%s", strategy_id)

    transaction.on_commit(enqueue_current)


def _validate_resource(resource, ref):
    if (
        resource.get("kind", "Flow") != "Flow"
        or any(resource.get("metadata", {}).get(key) != ref[key] for key in ("tenant", "namespace", "name"))
        or not isinstance(resource.get("spec"), dict)
    ):
        raise BKBaseResourceMappingError(message="Flow response identity or spec does not match binding")


def enqueue(strategy, countdown=None):
    """排队失败保留未决登记，由已有周期任务补排只读观察。"""
    saved = binding(strategy)
    pure = saved.get("pure_operation") or {}
    if not is_pure(strategy) or not pure.get("observing"):
        return
    pending, success, failed = (
        (StrategyStatusChoices.UPDATING, StrategyStatusChoices.RUNNING, StrategyStatusChoices.UPDATE_FAILED)
        if pure.get("restart")
        else _statuses(pure["target"])
    )
    try:
        # 控制器模块同样依赖该任务；延迟导入只为打破其导入环。
        from services.web.analyze.tasks import check_flow_status

        if countdown is None:
            check_flow_status.delay(strategy.pk, success, failed, pending, operation_id=pure["id"])
        else:
            check_flow_status.apply_async(
                args=[strategy.pk],
                kwargs={
                    "success_status": success,
                    "failed_status": failed,
                    "other_status": pending,
                    "operation_id": pure["id"],
                },
                countdown=CHECK_FLOW_STATUS_SLEEP_SECONDS,
            )
    except Exception:
        with locked_rows(strategy) as (current, _):
            if (
                is_pure(current, pure["id"])
                and binding(current)["pure_operation"].get("observing")
                and _configuration(current) == pure["configuration"]
            ):
                _save(current, strategy, deepcopy(binding(current)), message="Flow观察任务未入队，等待现有周期任务补排；不补发启停")


def _restart_receipt(resource):
    """保存可选的远端证据；仅注解更新可能无历史 ID 且版本不变。"""
    status = resource.get("status") or {}
    return {key: status.get(key) for key in ("history_id", "version", "start_time")}


def _restart_matches(resource, target, spec_digest):
    return (resource["metadata"].get("annotations") or {}).get("task_stopped") == (
        "true" if target == "stop" else "false"
    ) and _matches_flow_spec_digest(resource["spec"], spec_digest)


def can_retry_unsent_restart(strategy):
    """仅首步确定未发送且原配置未变，允许用户重新发起。"""
    pure = binding(strategy).get("pure_operation") or {}
    return (
        strategy.status == StrategyStatusChoices.UPDATE_FAILED
        and is_pure(strategy)
        and pure.get("restart")
        and pure.get("target") == "stop"
        and pure.get("attempted") is False
        and not any(pure.get(key) for key in ("writer", "observing", "write_fence", "outcome_unknown"))
        and _configuration(strategy) == pure.get("configuration")
    )


def can_retry_restart(strategy):
    """发送者已退出且观察已结束的同配置失败重启可由用户重试。"""
    pure = binding(strategy).get("pure_operation") or {}
    return (
        strategy.status == StrategyStatusChoices.UPDATE_FAILED
        and is_pure(strategy)
        and pure.get("restart")
        and pure.get("target") in ("stop", "start")
        and type(pure.get("attempted")) is bool
        and not any(pure.get(key) for key in ("writer", "observing", "write_fence"))
        and _configuration(strategy) == pure.get("configuration")
    )


def _check_restart_retry(current, expected):
    """重试读取期间出现新操作或配置时，不得替换新版本。"""
    if expected is None:
        return
    if binding(current).get("operation_id") != expected[0] or _configuration(current) != expected[1]:
        raise BKBaseOperationSuperseded()
    if not can_retry_restart(current):
        raise BKBaseFlowOperationPending()


def retry_restart(strategy):
    """显式重试按当前正式状态选择普通启动或新的 stop/start。"""
    with locked_rows(strategy) as (current, rows):
        assert_active(current)
        assert_writable(rows)
        if not can_retry_restart(current):
            raise BKBaseFlowOperationPending()
        expected = (binding(current)["operation_id"], _configuration(current))
        ref = deepcopy(binding(current)["flow"])
    context = get_bkbase_context()
    remote = api.bk_base_v4.flow_get(**resource_params(context, ref, kind="Flow"))
    _validate_resource(remote, ref)
    phase = remote["status"].get("phase")
    if phase == "Failed":
        return request(strategy, "start", expected_restart=expected, failure_baseline=remote["status"])
    if phase != "Ok":
        raise BKBaseResourceMappingError(message="Flow配置尚未生效，未发送重试")
    if (remote["metadata"].get("annotations") or {}).get("task_stopped") == "true":
        return request(strategy, "start", expected_restart=expected)
    return request_restart(strategy, expected_restart=expected)


def request_restart(strategy, *, context=None, expected_restart=None):
    """在原图上登记一个跨 stop/start 的操作代次。"""
    assert_detached()
    context = context or get_bkbase_context()
    resource_params(context, binding(strategy).get("flow") or {}, kind="Flow")
    with locked_rows(strategy) as (current, rows):
        assert_active(current)
        assert_writable(rows)
        saved = deepcopy(binding(current))
        if context.get("operation_id") and saved.get("operation_id") != context["operation_id"]:
            raise BKBaseOperationSuperseded()
        _check_restart_retry(current, expected_restart)
        if saved.get("pending_spec") or (
            current.status != StrategyStatusChoices.RUNNING and not can_retry_restart(current)
        ):
            raise BKBaseFlowOperationPending(message="仅可重启已运行且没有待发布配置的 Flow")
        operation_id = uuid4().hex
        supersede_finished(rows, operation_id)
        saved = deepcopy(binding(current))
        saved.update(operation_id=operation_id, requested_action="restart", poll_count=0)
        saved["pure_operation"] = dict(
            id=operation_id,
            restart=True,
            target="stop",
            configuration=_configuration(current),
            observing=True,
            write_fence=True,
            attempted=False,
        )
        _save(current, strategy, saved, status=StrategyStatusChoices.UPDATING, message="重启：准备停止原 Flow")
    _send_restart_step(context, strategy, operation_id)
    enqueue(strategy)


def _restart_step(strategy, operation_id, target):
    pure = binding(strategy).get("pure_operation") or {}
    return is_pure(strategy, operation_id) and pure.get("restart") and pure.get("target") == target


def _end_restart(current, strategy, saved, message, *, unknown=False, success=False):
    pure = saved["pure_operation"]
    pure.update(observing=False, write_fence=bool(pure.get("writer")), outcome_unknown=unknown, goal_observed=success)
    matches = _configuration(current) == pure["configuration"]
    status = StrategyStatusChoices.RUNNING if success else StrategyStatusChoices.UPDATE_FAILED
    _save(current, strategy, saved, status=status if matches else None, message=message if matches else None)


def _send_restart_step(context, strategy, operation_id):
    """发送前重读完整资源、核对停止凭证，短事务声明后只发送一次。"""
    assert_detached()
    ref = binding(strategy)["flow"]
    target = binding(strategy)["pure_operation"]["target"]
    params = resource_params(context, ref, kind="Flow")
    with flow.resource_lock(context, ref):
        with locked_rows(strategy) as (current, _):
            pure = binding(current).get("pure_operation") or {}
            if (
                not _restart_step(current, operation_id, target)
                or pure.get("attempted") is not False
                or not pure.get("observing")
            ):
                return
        reason = ""
        try:
            remote = api.bk_base_v4.flow_get(**params)
            _validate_resource(remote, ref)
            metadata, spec = deepcopy(remote["metadata"]), deepcopy(remote["spec"])
            spec_digest = _digest(flow_spec_for_write(spec))
            if (remote.get("status") or {}).get("phase") != "Ok" or not isinstance(spec.get("nodes"), list):
                raise BKBaseResourceMappingError(message="Flow 未处于已生效状态或完整节点不可用")
            if target == "stop" and (metadata.get("annotations") or {}).get("task_stopped") == "true":
                raise BKBaseResourceMappingError(message="Flow 已声明停止，不能发起新的重启")
            if target == "start" and (
                not pure.get("stop_receipt") or not _restart_matches(remote, "stop", pure.get("spec_digest"))
            ):
                raise BKBaseResourceMappingError(message="重启停止凭证或 Flow 配置已变化")
            if target == "start":
                # 先核对原停止凭证，再按本次启用配置生成摘要，避免沿用旧消费位置。
                spec.setdefault("operation_config", {})["start_position"] = BKBASE_FLOW_CONSUMING_MODE
                spec_digest = _digest(flow_spec_for_write(spec))
            metadata["annotations"] = {
                **(metadata.get("annotations") or {}),
                "task_stopped": "true" if target == "stop" else "false",
            }
        except Exception as error:
            reason = str(error) if isinstance(error, BKBaseResourceMappingError) else "读取 Flow 失败"
        with locked_rows(strategy) as (current, _):
            saved = deepcopy(binding(current))
            pure = saved.get("pure_operation") or {}
            if (
                not _restart_step(current, operation_id, target)
                or pure.get("attempted") is not False
                or not pure.get("observing")
            ):
                return
            if current.is_deleted or _configuration(current) != pure["configuration"] or reason:
                _end_restart(current, strategy, saved, f"重启：未发送{target}。{reason}")
                return
            writer = uuid4().hex
            pure.update(attempted=True, writer=writer, spec_digest=spec_digest)
            _save(current, strategy, saved, message="重启：正在发送停止" if target == "stop" else "重启：正在发送启动")
        receipt = None
        try:
            result = api.bk_base_v4.flow_update(**params, metadata=metadata, spec=spec, status=None)
            _validate_resource(result, ref)
            if (result.get("status") or {}).get("phase") == "Pending" and _restart_matches(result, target, spec_digest):
                receipt = _restart_receipt(result)
        except Exception:
            pass  # 已发起的 PUT 可能成功；没有可关联回执时绝不补发。
        with locked_rows(strategy) as (current, _):
            saved = deepcopy(binding(current))
            pure = saved.get("pure_operation") or {}
            if not _restart_step(current, operation_id, target) or pure.get("writer") != writer:
                return
            pure.pop("writer")
            if receipt is None or not pure.get("observing"):
                _end_restart(current, strategy, saved, "重启：发送结果缺少本次凭证，后续操作待核实", unknown=True)
            else:
                pure["receipt"] = receipt
                if target == "start":
                    # 停止是重启的中间步骤，不能作为普通停用或删除的受理凭证。
                    pure["accepted"] = True
                message = "重启：声明已受理，等待本次生效" if _configuration(current) == pure["configuration"] else None
                _save(current, strategy, saved, message=message)


def observe_restart(strategy):
    """仅本次停止已生效才推进启动；正式 phase 仅用于当前操作回读。"""
    operation_id = binding(strategy).get("operation_id")
    target = binding(strategy)["pure_operation"]["target"]
    context = get_bkbase_context()
    ref = binding(strategy)["flow"]
    ticket = uuid4().hex
    with locked_rows(strategy) as (current, _):
        if not _restart_step(current, operation_id, target):
            return {"retry": False}
        saved = deepcopy(binding(current))
        pure = saved["pure_operation"]
        if not pure.get("observing"):
            return {"retry": False}
        if pure.get("attempted") is not False:
            pure["observation"] = ticket
            _save(current, strategy, saved)
    if pure.get("attempted") is False:
        # 已登记但未声明发送的步骤可恢复。已声明的写永不由轮询补发。
        _send_restart_step(context, strategy, operation_id)
        return {"retry": bool(binding(strategy)["pure_operation"].get("observing"))}
    observed_phase = None
    if pure.get("receipt"):
        try:
            remote = api.bk_base_v4.flow_get(**resource_params(context, ref, kind="Flow"))
            _validate_resource(remote, ref)
            if _restart_matches(remote, target, pure["spec_digest"]):
                observed_phase = remote["status"].get("phase")
        except Exception:
            pass  # GET 失败只消耗本地观察预算。
    with locked_rows(strategy) as (current, _):
        saved = deepcopy(binding(current))
        latest = saved.get("pure_operation") or {}
        if not _restart_step(current, operation_id, target) or not latest.get("observing"):
            return {"retry": False}
        if latest.get("observation") != ticket:
            return {"retry": False}
        if current.is_deleted or _configuration(current) != latest["configuration"]:
            _end_restart(current, strategy, saved, "重启：本地配置已变化", unknown=observed_phase not in ("Ok", "Failed"))
            return {"retry": False}
        if latest.get("receipt") != pure.get("receipt"):
            return {"retry": True}  # 回执在本次读取期间才提交，不能沿用更早的观察。
        if observed_phase == "Failed":
            message = "重启：本次停止生效失败" if target == "stop" else "重启：本次启动生效失败"
            if remote["status"].get("message"):
                message += f"：{remote['status']['message']}"
            _end_restart(current, strategy, saved, message)
            return {"retry": False}
        if observed_phase == "Ok" and target == "start":
            _end_restart(current, strategy, saved, "重启：本次启动配置已生效", success=True)
        elif observed_phase == "Ok":
            latest.update(target="start", attempted=False, accepted=None, stop_receipt=latest.pop("receipt"))
            saved["poll_count"] = 0
            _save(current, strategy, saved, message="重启：本次停止配置已生效，准备启动")
        else:
            saved["poll_count"] += 1
            if saved["poll_count"] >= BKBASE_V4_MAX_POLLS:
                _end_restart(current, strategy, saved, "重启：未观察到本次配置生效，后续操作待核实", unknown=True)
                return {"retry": False}
            _save(current, strategy, saved)
            return {"retry": True}
    if target == "stop":
        _send_restart_step(context, strategy, operation_id)
        return {"retry": bool(binding(strategy)["pure_operation"].get("observing"))}
    enqueue_monitor_after_commit(strategy, operation_id, is_active=True, expected_configuration=pure["configuration"])
    return {"retry": False}


def observe(strategy):
    """只读正式Flow配置；预算、异常或pending_spec都不推进任何写。"""
    operation_id = binding(strategy).get("operation_id")
    ticket = uuid4().hex
    with locked_rows(strategy) as (current, _):
        if not is_pure(current, operation_id):
            return {"status": "superseded", "retry": False}
        saved = deepcopy(binding(current))
        pure = saved["pure_operation"]
        if not pure.get("observing"):
            return {"status": "success" if pure.get("goal_observed") else "other", "retry": False}
        pure["observation"] = ticket
        _save(current, strategy, saved)
    observed, error = {}, False
    try:
        observed = flow.get_rule_flow_status(get_bkbase_context(), strategy)
        _validate_resource(observed["resource"], binding(strategy)["flow"])
    except Exception:
        error = True
    with locked_rows(strategy) as (current, rows):
        if not is_pure(current, operation_id) or binding(current)["pure_operation"].get("observation") != ticket:
            return {"status": "superseded", "retry": False}
        saved = deepcopy(binding(current))
        pure = saved["pure_operation"]
        saved["poll_count"] = saved.get("poll_count", 0) + 1
        config_matches = _configuration(current) == pure["configuration"]
        resource = observed.get("resource", {})
        declared = resource.get("metadata", {}).get("annotations", {}).get("task_stopped")
        target_matches = declared == ("true" if pure["target"] == "stop" else "false") and (
            not pure.get("spec_digest") or _matches_flow_spec_digest(resource.get("spec"), pure["spec_digest"])
        )
        goal = (
            not error
            and config_matches
            and pure.get("accepted") is True
            and not pure.get("writer")
            and (resource.get("status", {}).get("phase") == "Ok" and target_matches)
        )
        pending, success, failed = _statuses(pure["target"])
        message = "等待本次Flow启停配置应用；仅进行只读观察"
        if goal:
            pure.update(goal_observed=True, observing=False)
            if not pure.get("writer") and (pure.get("accepted") is True or not pure.get("attempted")):
                pure["write_fence"] = False
            message = "已观测到本次启停配置应用"
        elif saved["poll_count"] >= BKBASE_V4_MAX_POLLS:
            message = "观察预算已用尽，目标仍未证实；发送仍在途，继续保持互斥"
            # 尚未发送的登记可以安全取消，旧发送者随后会在claim检查中退出。
            if not pure.get("attempted"):
                pure.update(observing=False, write_fence=False)
                message = "登记后未发送，已取消旧意图；可重新发起"
            elif pure.get("accepted") is True and not pure.get("writer"):
                pure.update(observing=False, write_fence=False)
                message = "观察预算已用尽，实际结果未确认；可由用户重试"
        elif not config_matches:
            message = "本地配置已变化，旧启停不回写新业务状态；保留未决写保护"
        elif error:
            message = "实际状态读取失败，启停结果仍未决；不补发请求"
        recovering_failed = (pure.get("failure_baseline") or {}).get("phase") == "Failed"
        if recovering_failed and not error and observed.get("task_state") == TaskState.FAILED:
            # Failed字段变化不证明是本次恢复的完成；仍按原预算只读等待。
            if observed.get("message"):
                message += f"；当前失败反馈：{observed['message']}"
        actual_failure = (
            not error and target_matches and observed.get("task_state") == TaskState.FAILED and not recovering_failed
        )
        if actual_failure:
            pure["observed_failure"] = True
            message = "本次Flow启停配置应用失败"
            if observed.get("message"):
                message += f"：{observed['message']}"
        pure["message"] = message
        status = success if goal else (failed if not pure.get("observing") else pending)
        if actual_failure and pure.get("accepted") is True:
            status = failed
            if not pure.get("writer"):
                pure.update(observing=False, write_fence=False)
        _save(
            current,
            strategy,
            saved,
            status=status if config_matches else None,
            message=message if config_matches else None,
        )
        if not pure.get("observing") and not pure.get("write_fence"):
            for row in rows:
                if row.pk == current.pk or not is_pure(row, operation_id):
                    continue
                alias_saved = deepcopy(binding(row))
                alias = alias_saved["pure_operation"]
                if alias.get("writer") or alias.get("accepted") is not True:
                    continue
                alias.pop("observation", None)
                alias.update(observing=False, write_fence=False, goal_observed=goal)
                matches = _configuration(row) == alias.get("configuration")
                _save(row, row, alias_saved, status=status if matches else None, message=message if matches else None)
        return {
            "status": "success" if goal else "other",
            "flow_status": observed.get("task_state"),
            "logs": [],
            "retry": bool(pure.get("observing") and saved["poll_count"] < BKBASE_V4_MAX_POLLS),
        }
