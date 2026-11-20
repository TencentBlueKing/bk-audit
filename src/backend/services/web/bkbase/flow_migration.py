"""核对旧策略Flow的权威迁移映射，仅导入本地资源绑定。

默认预览不写；显式应用复用资源锁并在短事务内复查本地旧值。
策略/输出从既有审计记录取得，节点由正式图动态识别；迁移命令不写平台。
"""

from copy import deepcopy

from django.db import transaction
from django.db.models import Q

from services.web.bkbase import flow, flow_operation
from services.web.bkbase.common import resource_lock, resource_params
from services.web.strategy_v2.constants import (
    RuleAuditConfigType,
    StrategyStatusChoices,
    StrategyType,
)
from services.web.strategy_v2.models import LinkTable, Strategy

MAX_BATCH_SIZE = 20
SCHEMA_VERSION = 1
MIGRATION_SUCCEEDED = "succeeded"
SQL_NODE_KINDS = {"StreamNode", "BatchSqlNode"}


def _positive_int(value):
    return type(value) is int and value > 0


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def validate_manifest(payload, *, context, legacy_tenant=None, legacy_project_id=None, limit=MAX_BATCH_SIZE):
    """先核对操作者声明的旧来源和整批唯一性，不用当前项目配置猜历史身份。"""
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH_SIZE:
        raise ValueError(f"limit必须在1–{MAX_BATCH_SIZE}之间")
    if isinstance(payload, dict) and "schema_version" not in payload:
        if not 1 <= len(payload) <= limit:
            raise ValueError(f"每份映射必须包含1–{limit}条，不自动截断")
        rows, targets = [], set()
        for legacy_id, name in payload.items():
            if (
                not isinstance(legacy_id, str)
                or not legacy_id.isdecimal()
                or int(legacy_id) <= 0
                or str(int(legacy_id)) != legacy_id
                or not _text(name)
                or name in targets
            ):
                raise ValueError("映射应为唯一的正整数flow_id到非空flow_name，不接受重复目标")
            resource_params(
                context,
                {
                    "kind": "Flow",
                    "tenant": context.get("tenant"),
                    "namespace": context.get("namespace"),
                    "name": name,
                },
                kind="Flow",
            )
            targets.add(name)
            rows.append({"legacy_flow_id": int(legacy_id), "flow_name": name})
        return rows
    if not _text(legacy_tenant) or not _positive_int(legacy_project_id):
        raise ValueError("旧版详细清单必须明确预期旧租户标识和旧项目ID")
    if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int:
        raise ValueError("迁移清单必须为带schema_version的JSON对象")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("不支持的迁移清单版本")
    source = payload.get("source")
    if (
        not isinstance(source, dict)
        or source.get("tenant") != legacy_tenant
        or not _positive_int(source.get("project_id"))
        or source["project_id"] != legacy_project_id
    ):
        raise ValueError("迁移清单与显式声明的旧租户/项目不一致")
    rows = payload.get("mappings")
    if not isinstance(rows, list) or not 1 <= len(rows) <= limit:
        raise ValueError(f"每份清单必须包含1–{limit}条映射；不自动截断")
    strategies, legacy_flows, targets = set(), set(), set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or not _positive_int(row.get("strategy_id"))
            or not _positive_int(row.get("legacy_flow_id"))
            or not _text(row.get("audit_namespace"))
            or not _text(row.get("output_rt_id"))
            or row.get("migration_status") != MIGRATION_SUCCEEDED
        ):
            raise ValueError("映射缺少明确的审计身份、旧Flow、原输出RT或成功迁移结果")
        ref = row.get("flow")
        if (
            not isinstance(ref, dict)
            or set(ref) != {"kind", "tenant", "namespace", "name"}
            or ref["kind"] != "Flow"
            or ref["tenant"] != context.get("tenant")
            or not all(_text(ref[key]) for key in ("tenant", "namespace", "name"))
        ):
            raise ValueError("新Flow必须为当前租户的完整资源引用")
        target = tuple(ref[key] for key in ("tenant", "namespace", "name"))
        if row["strategy_id"] in strategies or row["legacy_flow_id"] in legacy_flows or target in targets:
            raise ValueError("同批策略、旧Flow或新Flow引用重复")
        strategies.add(row["strategy_id"])
        legacy_flows.add(row["legacy_flow_id"])
        targets.add(target)
    return deepcopy(rows)


def resolve_mappings(context, rows):
    """最小映射沿原Flow唯一定位审计策略，环境提供当前租户和BKBase项目。"""
    resolved = []
    for row in rows:
        if "flow_name" not in row:
            resolved.append(deepcopy(row))
            continue
        candidates = list(Strategy.objects.get_queryset().filter(backend_data__flow_id=row["legacy_flow_id"]))
        if len(candidates) != 1:
            raise ValueError("旧Flow不能唯一定位审计策略，拒绝导入共享或未知身份")
        strategy = candidates[0]
        ref = {
            "kind": "Flow",
            "tenant": context["tenant"],
            "namespace": context["namespace"],
            "name": row["flow_name"],
        }
        outputs = _legacy_output_candidates(strategy)
        nodes = flow.read_flow_nodes(context, ref) if len(outputs) > 1 else None
        resolved.append(
            {
                "strategy_id": strategy.pk,
                "audit_namespace": strategy.namespace,
                "legacy_flow_id": row["legacy_flow_id"],
                "flow": ref,
                "output_rt_id": _legacy_output_rt(strategy, flow_nodes=nodes),
            }
        )
    return resolved


def _legacy_output_candidates(strategy):
    """原输入业务号只限定可能输出；跨业务联表不据输入顺序猜归属。"""
    backend = strategy.backend_data or {}
    raw_name = backend.get("raw_table_name")
    configs = strategy.configs or {}
    if not _text(raw_name) or configs.get("config_type") not in RuleAuditConfigType.values:
        raise ValueError("缺少原raw_table_name或有效数据源配置，不能猜原输出RT")
    source = configs.get("data_source") or {}
    if configs["config_type"] == RuleAuditConfigType.LINK_TABLE:
        linked = source.get("link_table") or {}
        table = LinkTable.objects.get(uid=linked.get("uid"), version=linked.get("version"))
        rt_ids = list(table.rt_ids)
    else:
        rt_ids = [source.get("rt_id")]
    biz_ids = set()
    for rt_id in rt_ids:
        if not _text(rt_id) or "_" not in rt_id:
            raise ValueError("原输入RT缺少明确业务身份")
        biz_id = rt_id.split("_", 1)[0]
        if not biz_id.isdecimal() or int(biz_id) <= 0:
            raise ValueError("原输入RT缺少有效业务ID")
        biz_ids.add(int(biz_id))
    return {f"{biz_id}_{raw_name}" for biz_id in biz_ids}


def _legacy_output_rt(strategy, *, output_rt_id=None, flow_nodes=None):
    """详细清单显式核输出；最小清单用正式SQL节点消除跨业务歧义。"""
    candidates = _legacy_output_candidates(strategy)
    if output_rt_id is not None:
        if output_rt_id not in candidates:
            raise ValueError("迁移输出RT与原V3业务输出不一致")
        return output_rt_id
    if flow_nodes is not None:
        outputs = [
            node.get("output")
            for node in flow_nodes
            if node.get("kind") in SQL_NODE_KINDS and node.get("output") in candidates
        ]
        if len(outputs) != 1:
            raise ValueError("正式Flow不能唯一识别原输出RT")
        return outputs[0]
    if len(candidates) != 1:
        raise ValueError("原输出RT的业务身份存在歧义，需核对原环境清单或正式图")
    return candidates.pop()


def _validate_local(strategy, row):
    """拒绝已删除、身份冲突和未决操作，不清空旧字段或操作凭据。"""
    if (
        strategy.is_deleted
        or strategy.namespace != row["audit_namespace"]
        or strategy.strategy_type != StrategyType.RULE
    ):
        raise ValueError("策略不存在、已删除或审计命名空间/策略类型不一致")
    backend = strategy.backend_data or {}
    if not isinstance(backend, dict) or backend.get("flow_id") != row["legacy_flow_id"]:
        raise ValueError("策略原flow_id与迁移清单不一致")
    saved = backend.get("bkbase_v4", {})
    if not isinstance(saved, dict):
        raise ValueError("既有V4绑定结构无效")
    pure = saved.get("pure_operation") or {}
    if not isinstance(pure, dict):
        raise ValueError("既有操作凭据结构无效")
    flow_operation.assert_writable([strategy])
    if (
        strategy.status
        in (
            StrategyStatusChoices.STARTING,
            StrategyStatusChoices.STOPPING,
            StrategyStatusChoices.UPDATING,
            StrategyStatusChoices.FAILED,
        )
        or saved.get("pending_spec") is not None
        or saved.get("flow_write") is not None
        or any(pure.get(key) for key in ("writer", "write_fence", "observing", "outcome_unknown"))
    ):
        raise ValueError("策略存在在途、未发布配置或结果未知的操作，不能导入绑定")
    if saved.get("flow") is not None and saved["flow"] != row["flow"]:
        raise ValueError("策略已绑定不同的新Flow")
    output = _legacy_output_rt(strategy, output_rt_id=row["output_rt_id"])
    if output != row["output_rt_id"]:
        raise ValueError("迁移输出RT与原V3业务输出不一致")
    for field, expected in [("output_rt_id", output), ("output_name", backend["raw_table_name"])]:
        if saved.get(field) is not None and saved[field] != expected:
            raise ValueError("既有V4输出身份冲突")


def _reject_aliases(strategy, row):
    """软删记录仍可能有未结束写入；旧Flow或新Ref均不能已有其他归属。"""
    query = Q(backend_data__flow_id=row["legacy_flow_id"]) | Q(
        **{f"backend_data__bkbase_v4__flow__{key}": value for key, value in row["flow"].items()}
    )
    if Strategy.objects.get_queryset().filter(query).exclude(pk=strategy.pk).exists():
        raise ValueError("旧Flow或新Flow引用已被其他策略记录使用，不能导入共享绑定")


def _verify_remote(context, row):
    """正式GET按kind和原输出RT唯一核对SQL节点，不猜或重命名远端节点。"""
    nodes = flow.read_flow_nodes(context, row["flow"])
    flow.validate_graph(nodes)
    candidates = [node for node in nodes if node.get("output") == row["output_rt_id"]]
    if len(candidates) != 1 or candidates[0]["kind"] not in SQL_NODE_KINDS:
        raise ValueError("正式Flow无法按原输出RT唯一识别SQL计算节点")


def preview_mapping(context, row):
    """只读核对本地策略及迁移后的正式Flow，产生精确的绑定合并预览。"""
    strategy = Strategy.objects.get(pk=row["strategy_id"])
    _validate_local(strategy, row)
    _reject_aliases(strategy, row)
    _verify_remote(context, row)
    before = deepcopy(strategy.backend_data)
    after = deepcopy(before)
    after.setdefault("bkbase_v4", {}).update(
        flow=deepcopy(row["flow"]), output_name=before["raw_table_name"], output_rt_id=row["output_rt_id"]
    )
    return {
        "before_backend_data": before,
        "after_backend_data": after,
        "status": strategy.status,
        "configs": deepcopy(strategy.configs),
        "action": "unchanged" if before == after else "bind",
    }


def apply_mapping(context, row, plan, *, before_save):
    """资源锁内复核正式Flow；短事务比较旧值后仅写绑定，先持久化回退证据。"""
    with resource_lock(context, row["flow"]):
        _verify_remote(context, row)
        with transaction.atomic():
            current = Strategy.objects.select_for_update().get(pk=row["strategy_id"])
            if (
                current.backend_data != plan["before_backend_data"]
                or current.status != plan["status"]
                or current.configs != plan["configs"]
            ):
                raise ValueError("预览后本地策略已改变，拒绝覆盖；请重新生成预览")
            _validate_local(current, row)
            _reject_aliases(current, row)
            if plan["action"] == "unchanged":
                return "unchanged"
            before_save()
            current.backend_data = deepcopy(plan["after_backend_data"])
            current.save(update_record=False, update_fields=["backend_data"])
    return "updated"
