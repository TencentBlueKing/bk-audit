"""转换审计清洗规则并管理Clean生命周期。

创建者角色独立于采集项删除；保存和发布分别推进配置版本。
单次API受理不能当成运行完成，绑定保留供异步任务重试。
"""

import json
import re
import time
from contextlib import nullcontext
from copy import deepcopy

from bk_resource import api
from bk_resource.exceptions import APIRequestError, ValidateException
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.exceptions import LockError
from services.web.bkbase import metadata as metadata_service
from services.web.bkbase import source
from services.web.bkbase import storage as storage_service
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    get_resource_or_none,
    legacy_call,
    operation_result,
    resource_lock,
    resource_params,
    stable_name,
    update_owner_binding,
)
from services.web.bkbase.constants import (
    BKBASE_V4_CLEAN_TIME_FORMAT_ALIASES,
    BKBASE_V4_MAX_POLLS,
    BKBaseVersion,
    CleanRole,
    CleanState,
    TaskState,
)
from services.web.bkbase.exceptions import (
    BKBaseException,
    BKBaseResourceMappingError,
    BKBaseSharedResourceProtected,
)
from services.web.databus.constants import (
    DORIS_EVENT_BKBASE_RT_ID_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
    DORIS_EVENT_STORAGE_CONFIG_KEY,
    PluginSceneChoices,
    SourcePlatformChoices,
)
from services.web.databus.exceptions import DatabusException
from services.web.databus.models import CollectorConfig, CollectorPlugin

PLUGIN_OPERATION_EXCEPTIONS = (APIRequestError, BKBaseException, LockError, DatabusException)
PLUGIN_RETRY_STEPS = "plugin_retry_steps"


def _convert_named_regex_groups(pattern):
    """转换Java命名组为V4已验证写法，保留转义、字符类和零宽断言。"""
    converted = []
    class_starts = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            converted.append(pattern[index : index + 2])
            index += 2
            continue
        if char == "[":
            # 字符类首位（或^之后）的]是字面量；嵌套字符类单独跟踪。
            class_starts.append(index + 1 + (pattern[index + 1 : index + 2] == "^"))
        elif char == "]" and class_starts and index > class_starts[-1]:
            class_starts.pop()
        elif not class_starts and pattern.startswith("(?<", index):
            group = re.match(r"\(\?<([a-zA-Z][a-zA-Z0-9_]*)>", pattern[index:])
            if group:
                converted.append(f"(?P<{group[1]}>")
                index += group.end()
                continue
        converted.append(char)
        index += 1
    return "".join(converted)


def _intermediate_name_mapper(extract):
    """转换不合法的中间名，避免与现有中间名或结果字段冲突。"""
    reserved = {"__raw_data"}
    renamed = {}

    def collect_names(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("result", "assign_to") and isinstance(value, str):
                    reserved.add(value)
                collect_names(value)
        elif isinstance(node, list):
            for value in node:
                collect_names(value)

    def intermediate_name(value):
        if not isinstance(value, str):
            raise BKBaseResourceMappingError(message="Invalid clean intermediate name")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            return value
        if value not in renamed:
            counter = 0
            while True:
                # 中间字段不是 BKBase 资源名，保留已有清洗规则的字段命名。
                candidate = stable_name("tmp", value, counter, max_length=58).replace("-", "_")
                if candidate not in reserved:
                    break
                counter += 1
            reserved.add(candidate)
            renamed[value] = candidate
        return renamed[value]

    collect_names(extract)
    return intermediate_name


def _v4_get_default(node):
    """Encode legacy integer defaults for the nullable string field of V4 get."""
    if node.get("default_type", "null") == "null":
        return None
    value = node.get("default_value")
    return str(value) if type(value) is int else value


def convert_rules(config, *, fields=()):
    """展开V3树式规则，保留扇出行为及业务字段的别名、维度定义。"""
    config = json.loads(config) if isinstance(config, str) else config
    rules = []
    conf = config.get("conf", {})
    field_map = {field["field_name"]: field for field in fields}
    intermediate_name = _intermediate_name_mapper(config.get("extract"))

    def walk(node, input_id):
        if not node:
            return
        if isinstance(node, list):
            for child in node:
                walk(child, input_id)
            return
        kind = node.get("type")
        output_id = node.get("result") or input_id
        if kind == "branch":
            if node.get("name"):
                raise BKBaseResourceMappingError(message="Conditional V3 branch requires explicit conversion")
            walk(node.get("next"), input_id)
            return
        if kind == "fun":
            method = node.get("method")
            args = node.get("args", [])
            if method == "from_json":
                operator = {"type": "json_de"}
            elif method == "iterate":
                operator = {
                    "type": "iter",
                    "iteration_index_field": args[0] if args else "_iteration_idx",
                    "reserve_index": bool(args[1]) if len(args) > 1 else False,
                }
            elif method == "split":
                operator = {"type": "split_str", "delimiter": args[0]}
            elif method == "regex_extract":
                argument = args[0]
                if isinstance(argument, dict):
                    output_id = argument["result"]
                    pattern = argument["regexp"]
                else:
                    pattern = argument
                operator = {"type": "regex", "regex": _convert_named_regex_groups(pattern)}
            else:
                raise BKBaseResourceMappingError(message=f"Unsupported legacy clean function: {method}")
            output_id = intermediate_name(output_id)
            rules.append({"input_id": input_id, "output_id": output_id, "operator": operator})
        elif kind == "access":
            positional = node.get("subtype") == "access_pos"
            key = node.get("index") if positional else node.get("key")
            if positional:
                if isinstance(key, str) and key.isascii() and key.isdigit():
                    key = int(key)
                if type(key) is not int or key < 0:
                    raise BKBaseResourceMappingError(message="Invalid clean array index")
            operator = {
                "type": "get",
                "key_index": [{"type": "index" if positional else "key", "value": key}],
                "default": _v4_get_default(node),
            }
            if "default_type" in node:
                operator["missing_strategy"] = "default"
            output_id = intermediate_name(output_id)
            rules.append({"input_id": input_id, "output_id": output_id, "operator": operator})
        elif kind == "assign":
            assigns = node.get("assign", [])
            if isinstance(assigns, dict):
                assigns = [assigns]
            for assignment in assigns:
                target = assignment["assign_to"]
                key = assignment.get("index", assignment.get("key", ""))
                if node.get("subtype") == "assign_json" and key == "__all_keys__":
                    key = ""
                whole_input = (
                    node.get("subtype") == "assign_value" and "key" not in assignment and "index" not in assignment
                ) or (
                    node.get("subtype") == "assign_json"
                    and "index" not in assignment
                    and assignment.get("key") == "__all_keys__"
                )
                operator = {
                    "type": "assign",
                    "key_index": None if whole_input else str(key),
                    "output_type": assignment["type"],
                }
                field = field_map.get(target, {})
                if field.get("field_alias") is not None:
                    operator["alias"] = field["field_alias"]
                if "is_dimension" in field:
                    operator["is_dimension"] = field["is_dimension"]
                if target == conf.get("time_field_name"):
                    time_format = conf["time_format"]
                    if isinstance(time_format, str):
                        time_format = BKBASE_V4_CLEAN_TIME_FORMAT_ALIASES.get(time_format, time_format)
                    operator["is_time_field"] = True
                    operator["time_format"] = {"format": time_format, "zone": conf.get("timezone", 8)}
                rules.append({"input_id": input_id, "output_id": target, "operator": operator})
            output_id = input_id
        else:
            raise BKBaseResourceMappingError(message=f"Unsupported legacy clean node: {kind}")
        walk(node.get("next"), output_id)

    walk(config.get("extract"), "__raw_data")
    return rules


def update_clean(context, clean_ref, *, patch, publish):
    """完整保留当前资源，只在发布时追平deploy_revision。"""
    params = resource_params(context, clean_ref, kind="Clean")
    with resource_lock(context, clean_ref):
        old = api.bk_base_v4.clean_get(**params)
        spec = deepcopy(old["spec"])
        spec.update(deepcopy(patch))
        spec["config_revision"] = max(int(old["spec"].get("config_revision", 0)) + 1, int(time.time() * 1000))
        if publish:
            spec.update(deploy_revision=spec["config_revision"], desired_status=CleanState.RUNNING)
        else:
            spec["deploy_revision"] = old["spec"].get("deploy_revision", 0)
        result = api.bk_base_v4.clean_update(**params, metadata=deepcopy(old["metadata"]), spec=spec, status=None)
    return operation_result(result, clean_ref, "publish" if publish else "save")


def set_clean_state(context, clean_ref, *, running):
    """修改期望启停不隐式发布尚未发布的规则。"""
    params = resource_params(context, clean_ref, kind="Clean")
    with resource_lock(context, clean_ref):
        old = api.bk_base_v4.clean_get(**params)
        spec = deepcopy(old["spec"])
        spec["desired_status"] = CleanState.RUNNING if running else CleanState.STOPPED
        result = api.bk_base_v4.clean_update(**params, metadata=deepcopy(old["metadata"]), spec=spec, status=None)
    return operation_result(result, clean_ref, "start" if running else "stop")


def delete_source_clean(context, collector):
    """普通删源保护owner，已受理删除由后台任务继续确认。"""
    if _collector_has_no_clean(collector):
        return {"accepted": True, "deleted": True, "task_state": TaskState.STOPPED}
    binding = collector.bkbase_v4_resources or {}
    if binding.get("clean_role") != CleanRole.EXISTING:
        raise BKBaseSharedResourceProtected()
    ref = binding.get("clean") or {}
    params = resource_params(context, ref, kind="Clean")
    patch = {"pending_action": "delete"}
    if binding.get("pending_action") != "delete" or binding.get("blocked"):
        # 显式发起或重试删除需解除旧失败；已在轮询的删除保留预算。
        patch.update(blocked=False, poll_count=0, clean_message="")
    update_owner_binding(collector, patch)
    with resource_lock(context, ref):
        current = get_resource_or_none(api.bk_base_v4.clean_get, **params)
        if current is None:
            update_owner_binding(
                collector, {}, remove=["clean", "clean_role", "clean_delete_requested", "pending_action", "clean_ready"]
            )
            return {"ref": ref, "accepted": True, "deleted": True, "task_state": TaskState.STOPPED}
        if binding.get("clean_delete_requested"):
            return operation_result(current, ref, "delete")
        observed = operation_result(current, ref, "stop")
        if observed["task_state"] != TaskState.STOPPED or current["spec"].get("desired_status") != CleanState.STOPPED:
            # 已提交的停止交给controller推进，重复PUT会重新触发调和。
            if current["spec"].get("desired_status") == CleanState.STOPPED:
                return observed
            spec = deepcopy(current["spec"])
            spec["desired_status"] = CleanState.STOPPED
            result = api.bk_base_v4.clean_update(
                **params, metadata=deepcopy(current["metadata"]), spec=spec, status=None
            )
            return operation_result(result, ref, "stop")
        api.bk_base_v4.clean_delete(**params)
        update_owner_binding(collector, {"clean_delete_requested": True})
        return {**operation_result(current, ref, "delete"), "task_state": None}


def owner_clean_ref(context, owner):
    """使用已声明的 Clean 引用，首次创建使用稳定的归属名称。"""
    binding = owner.bkbase_v4_resources or {}
    ref = binding.get("clean")
    if not ref:
        operation = binding.get("source_provision") or {}
        if not isinstance(operation, dict):
            raise BKBaseResourceMappingError(message="Invalid Snapshot provision operation")
        if operation.get("stage") == "ready" and not operation.get("completed"):
            # POST 已经认领但尚未确认时继续按原引用回读；坏记录仅使当前快照失败。
            step = operation.get("clean_step")
            if step is not None:
                if not isinstance(step, dict):
                    raise BKBaseResourceMappingError(message="Invalid Snapshot Clean claim")
                ref = step.get("ref")
    return ref or {
        "kind": "Clean",
        "tenant": context["tenant"],
        "namespace": context["namespace"],
        "name": stable_name("c", owner.__class__.__name__, owner.pk),
    }


def _preserve_collector_join(owner, current, desired):
    """普通 ETL 更新保留已部署 Basic 关联的 Redis 复合键顺序。"""
    logical_id = getattr(owner, "join_data_rt", None)
    if not logical_id or not desired.get("join"):
        return
    current_joins = current.get("join") or []
    if not isinstance(current_joins, list) or any(
        not isinstance(join, dict)
        or not isinstance(join.get("select"), list)
        or any(not isinstance(field, dict) for field in join["select"])
        for join in current_joins
    ):
        raise BKBaseResourceMappingError(message="Collector Clean has invalid snapshot joins")
    for index, join in enumerate(desired["join"]):
        if join["result_table_id"] != logical_id:
            continue
        fields = {field["as"] for field in join["select"]}
        matches = []
        for existing in current_joins:
            if existing.get("result_table_id") == logical_id:
                matches.append(existing)
            elif any(field.get("as") in fields for field in existing["select"]):
                raise BKBaseResourceMappingError(message="Collector Clean already joins a different snapshot")
        if not matches:
            continue
        previous = matches[0]
        on = previous.get("join_on") or []
        if (
            len(matches) != 1
            or previous.get("select") != join["select"]
            or len(on) != len(join["join_on"])
            or not all(pair in on for pair in join["join_on"])
        ):
            raise BKBaseResourceMappingError(message="Collector Clean has a conflicting snapshot join")
        desired["join"][index] = deepcopy(previous)


def _logical_table_id(value):
    """逻辑表名是 Clean 的业务字段，不能从资源引用推导。"""
    if not isinstance(value, str) or not value or any(char.isspace() or char in ",=" for char in value):
        raise BKBaseResourceMappingError(message="Missing or invalid logical result table ID")
    return value


def _existing_clean_table_id(context, ref, resource, *, raw_id, data_ref, source_role):
    """只从身份、输入及角色均吻合的已有 Clean 读取逻辑表名。"""
    if source._binding_resource_ref(context, resource, "Clean") != ref:
        raise BKBaseResourceMappingError(message="Existing Clean resource identity mismatch")
    spec = resource["spec"]
    if (
        source._replay_raw_id(spec.get("raw_data_id")) != raw_id
        or source._replay_ref(context, spec.get("data_id"), "DataId") != data_ref
        or spec.get("result_table_source", "new") != source_role
    ):
        raise BKBaseResourceMappingError(message="Existing Clean ownership mismatch")
    return _logical_table_id(spec.get("result_table_id"))


def adapt_pull_clean_config(config, *, report_config=None):
    """按实际Source封装选择业务抽取路径；V4算子语法仍由convert_rules独立转换。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return config
    if source.pull_report_data_path(report_config) is None:
        return config
    # 已证列表来源不能再次from_json或取data.results，保留其原配套规则。
    response = next(node for node in config["extract"]["next"]["next"] if node.get("key") == "data")
    rows = response["next"]["next"]["next"]
    response["result"] = rows["result"]
    response["next"] = rows["next"]
    return config


def validate_pull_clean_input(report_config, rules):
    """已保存Clean计划必须仍匹配Source封装；只识别审计模板入口，不猜自定义图。"""
    path = source.pull_report_data_path(report_config)
    roots = {
        rule.get("output_id")
        for rule in rules
        if rule.get("input_id") == "__raw_data" and rule.get("operator", {}).get("type") == "json_de"
    }
    responses = {
        rule.get("output_id")
        for rule in rules
        if rule.get("input_id") in roots
        and rule.get("operator", {}).get("type") == "get"
        and rule["operator"].get("key_index") == [{"type": "key", "value": "data"}]
    }
    expected = "json_de" if path is None else "iter"
    if not any(
        rule.get("input_id") in responses and rule.get("operator", {}).get("type") == expected for rule in rules
    ):
        raise BKBaseResourceMappingError(
            message="PULL Source input shape no longer matches saved Clean plan; inspect its original configuration"
        )


def _verified_result_table_ref(context, binding, logical_id):
    """核对已有引用；缺失时以已确认的 Clean 逻辑输出查询正式引用。"""
    candidate = binding.get("result_table")
    if not candidate:
        return metadata_service.get_result_table_ref(context, logical_id)
    ref = source._replay_ref(context, candidate, "ResultTable")
    actual_ref = metadata_service.get_result_table_ref(context, logical_id)
    if actual_ref != ref:
        raise BKBaseResourceMappingError(message="V4 ResultTable identity conflicts with Clean logical output")
    return ref


def _bound_raw_data_id(context, owner, binding, data_ref):
    """旧绑定缺少数字键时，从同一正式来源确认数字标签和 DataId。"""
    raw_id = binding.get("source_raw_data_id")
    if "migration_import" in binding and "data_source" not in binding:
        raw_id = source.bound_plugin_raw_id(context, binding)
    if raw_id is None:
        ref = source._replay_ref(context, binding.get("data_source"), "DataSource")
        resource = api.bk_base_v4.data_source_get(**resource_params(context, ref, kind="DataSource"))
        if source._binding_resource_ref(context, resource, "DataSource") != ref:
            raise BKBaseResourceMappingError(message="Bound Clean DataSource identity mismatch")
        raw_id = source._replay_raw_id(resource["metadata"].get("labels", {}).get("raw_data_id"))
        if source._source_binding(context, resource, raw_id)["data_id"] != data_ref:
            raise BKBaseResourceMappingError(message="Bound Clean DataSource has a different DataId")
    raw_id = source._replay_raw_id(raw_id)
    collector_raw = getattr(owner, "bk_data_id", None)
    if collector_raw is not None and source._replay_raw_id(collector_raw) != raw_id:
        raise BKBaseResourceMappingError(message="Bound Clean does not match the collector raw DataID")
    return raw_id


def _verified_running_clean_identity(context, owner, ref):
    """读取已绑定且实际运行的 Clean，核对本地身份及声明。"""
    binding = owner.bkbase_v4_resources or {}
    role = binding.get("clean_role")
    source_role = {CleanRole.OWNER: "new", CleanRole.EXISTING: "existing"}.get(role) if isinstance(role, str) else None
    if (
        binding.get("clean") != ref
        or source_role is None
        or binding.get("clean_pending_create")
        or binding.get("pending_action")
    ):
        raise BKBaseResourceMappingError(message="Bound Clean has an unresolved operation or role")
    data_ref = source._replay_ref(context, binding.get("data_id"), "DataId")
    raw_id = _bound_raw_data_id(context, owner, binding, data_ref)
    resource = api.bk_base_v4.clean_get(**resource_params(context, ref, kind="Clean"))
    logical_id = _existing_clean_table_id(
        context, ref, resource, raw_id=raw_id, data_ref=data_ref, source_role=source_role
    )
    if binding.get("result_table_id") not in (None, logical_id):
        raise BKBaseResourceMappingError(message="Bound Clean logical result table ID mismatch")
    spec = resource["spec"]
    if (
        not isinstance(resource.get("status"), dict)
        or operation_result(resource, ref, "observe")["task_state"] != TaskState.RUNNING
        or spec.get("desired_status") != CleanState.RUNNING
        or spec.get("config_revision", 0) != spec.get("deploy_revision", 0)
    ):
        raise BKBaseResourceMappingError(message="Bound Clean is not ready")
    return {"result_table_id": logical_id, "source_raw_data_id": raw_id}


def _shared_plugin_table(context, plugin):
    """即便本地有逻辑声明，合流也只能使用已确认就绪的 owner。"""
    ref = source._replay_ref(context, (plugin.bkbase_v4_resources or {}).get("clean"), "Clean")
    with resource_lock(context, ref):
        latest = CollectorPlugin.objects.get(pk=plugin.pk)
        binding = latest.bkbase_v4_resources or {}
        if binding.get("clean_role") != CleanRole.OWNER:
            raise BKBaseResourceMappingError(message="Shared Clean owner binding is missing")
        identity = _verified_running_clean_identity(context, latest, ref)
        logical_id = identity["result_table_id"]
        rt_ref = _verified_result_table_ref(context, binding, logical_id)
        identity["result_table"] = rt_ref
        if any(binding.get(key) is None for key in identity):
            update_owner_binding(latest, identity)
    return logical_id, rt_ref


def _same_clean_rules(declared, actual, *, strict_types=False):
    """归一已证默认回显；新快照显式开启类型严格比较，既有调用保持原行为。"""
    if not isinstance(declared, list) or not isinstance(actual, list) or len(declared) != len(actual):
        return source._replay_digest(declared) == source._replay_digest(actual) if strict_types else declared == actual
    normalized = deepcopy(actual)
    for wanted, observed in zip(declared, normalized):
        if not isinstance(wanted, dict) or not isinstance(observed, dict):
            return (
                source._replay_digest(declared) == source._replay_digest(actual) if strict_types else declared == actual
            )
        wanted_operator, observed_operator = wanted.get("operator"), observed.get("operator")
        if not isinstance(wanted_operator, dict) or not isinstance(observed_operator, dict):
            continue
        if wanted_operator.get("type") != observed_operator.get("type"):
            continue
        if wanted_operator.get("type") == "assign":
            for key in (
                "time_fallback",
                "fixed_value",
                "time_format",
                "desc",
                "in_place_time_parsing",
                "input_type",
                "is_time_field",
            ):
                if key not in wanted_operator and key in observed_operator and observed_operator[key] is None:
                    observed_operator.pop(key)
        elif wanted_operator.get("type") == "json_de":
            if "error_strategy" not in wanted_operator and observed_operator.get("error_strategy") == "drop":
                observed_operator.pop("error_strategy")
        elif wanted_operator.get("type") == "iter":
            if wanted_operator.get("reserve_index") is False and "reserve_index" not in observed_operator:
                observed_operator["reserve_index"] = False
            if "reserve_index" in wanted_operator and "reserve_index" in observed_operator:
                # Python 的 False/0、True/1 等值不代表协议值相同。
                if type(wanted_operator["reserve_index"]) is not type(observed_operator["reserve_index"]):
                    return False
    return (
        source._replay_digest(declared) == source._replay_digest(normalized) if strict_types else declared == normalized
    )


def _same_json_decode_path(old_rules, new_rules, output_id, legacy_json_decoders):
    """从解码输出回溯到原始输入，逐节点核对唯一生产者、取值和分支语义。"""

    def unique_output(rules, name):
        matches = [rule for rule in rules if isinstance(rule, dict) and rule.get("output_id") == name]
        return matches[0] if len(matches) == 1 else None

    seen = set()
    while output_id != "__raw_data":
        if not isinstance(output_id, str) or not output_id or output_id in seen:
            return False
        seen.add(output_id)
        old = unique_output(old_rules, output_id)
        new = unique_output(new_rules, output_id)
        if old is None or new is None:
            return False
        before, after = old.get("operator"), new.get("operator")
        if not isinstance(before, dict) or not isinstance(after, dict):
            return False
        comparable = deepcopy(old)
        if (
            (new.get("input_id"), output_id) in legacy_json_decoders
            and before.get("type") == after.get("type") == "json_de"
            and before.get("error_strategy") == "null"
            and "error_strategy" not in after
        ):
            # 仅将本次可保留的解码策略视为相同；显式修改仍使下游路径不同。
            comparable["operator"].pop("error_strategy")
        if not _same_clean_rules([new], [comparable], strict_types=True):
            return False
        output_id = new.get("input_id")
    # 原始输入不能被规则同名覆盖，否则不具备可信根。
    return not any(rule.get("output_id") == "__raw_data" for rule in old_rules + new_rules if isinstance(rule, dict))


def _preserve_bound_json_decoders(current, desired, legacy_json_decoders):
    """同可信绑定、完整同解码路径的旧 null 不退为默认 drop；不改赋值类型。"""
    old_rules, new_rules = current.get("rules"), desired.get("rules")
    if not isinstance(old_rules, list) or not isinstance(new_rules, list):
        return
    preserved = []
    for rule in new_rules:
        input_id, output_id = rule.get("input_id"), rule.get("output_id")
        operator = rule.get("operator", {})
        if (
            (input_id, output_id) in legacy_json_decoders
            and operator.get("type") == "json_de"
            and "error_strategy" not in operator
            and _same_json_decode_path(old_rules, new_rules, output_id, legacy_json_decoders)
        ):
            old = next(r for r in old_rules if r.get("output_id") == output_id)
            if old["operator"].get("error_strategy") == "null":
                preserved.append(rule)
    # 完成全部路径核验后再补策略，避免上游补值影响其他节点的比较顺序。
    for rule in preserved:
        rule["operator"]["error_strategy"] = "null"


def ensure_clean(
    context,
    owner,
    *,
    rules,
    rt_ref,
    publish=True,
    _locked_clean_ref=None,
    _require_existing=False,
    _legacy_json_decoders=(),
    _retry_existing=None,
):
    """稳定引用下声明/更新Clean，首次失败后的重试先核实远端。"""
    binding = deepcopy(owner.bkbase_v4_resources or {})
    ref = owner_clean_ref(context, owner)
    params = resource_params(context, ref, kind="Clean")
    if _locked_clean_ref is not None and _locked_clean_ref != ref:
        raise BKBaseResourceMappingError(message="Collector Clean binding changed under lock")
    spec = deepcopy(rules)
    data_ref = source._replay_ref(context, spec.get("data_id"), "DataId")
    raw_id = source._replay_raw_id(spec.get("raw_data_id"))
    logical_id = _logical_table_id(spec.get("result_table_id"))
    source_role = spec.get("result_table_source", "new")
    role = CleanRole.OWNER if source_role == "new" else CleanRole.EXISTING
    if binding.get("clean_role") not in (None, role):
        raise BKBaseResourceMappingError(message="Clean ownership cannot be changed")
    if binding.get("result_table_id") not in (None, logical_id):
        raise BKBaseResourceMappingError(message="Clean logical result table ID cannot be changed")
    pending = {
        "clean": ref,
        "clean_role": role,
        "result_table_id": logical_id,
    }
    if rt_ref is not None:
        resource_params(context, rt_ref, kind="ResultTable")
        if binding.get("result_table") not in (None, rt_ref):
            raise BKBaseResourceMappingError(message="Clean ResultTable binding cannot be changed")
        pending["result_table"] = rt_ref
    retried = False
    with resource_lock(context, ref) if _locked_clean_ref is None else nullcontext():
        old = get_resource_or_none(api.bk_base_v4.clean_get, **params)
        if old is None and _require_existing:
            raise BKBaseResourceMappingError(message="The established V4 Clean is missing; cannot recreate it")
        if old is None and _retry_existing is not None and not _retry_existing(None):
            raise BKBaseResourceMappingError(message="Previous Clean creation is still unconfirmed")
        if old is not None:
            actual = _existing_clean_table_id(
                context, ref, old, raw_id=raw_id, data_ref=data_ref, source_role=source_role
            )
            if actual != logical_id:
                raise BKBaseResourceMappingError(message="Existing Clean logical result table ID mismatch")
            if _locked_clean_ref is not None:
                _preserve_collector_join(owner, old["spec"], spec)
            if (
                _require_existing
                and binding.get("clean") == ref
                and binding.get("data_id") == data_ref
                and binding.get("clean_role") == role
                and binding.get("result_table_id") == logical_id
                and rt_ref is not None
                and binding.get("result_table") == rt_ref
            ):
                _preserve_bound_json_decoders(old["spec"], spec, _legacy_json_decoders)
        if old is None:
            pending["clean_pending_create"] = True
        # 仅真正创建才标记结果待确认；已建立资源的更新失败不能降为创建重试。
        update_owner_binding(owner, pending)
        if old is None:
            revision = int(time.time() * 1000)
            spec.update(
                config_revision=revision,
                deploy_revision=revision if publish else 0,
                desired_status=CleanState.RUNNING if publish else CleanState.STOPPED,
            )
            result = api.bk_base_v4.clean_create(
                tenant=params["tenant"],
                namespace=params["namespace"],
                metadata={k: ref[k] for k in ("tenant", "namespace", "name")},
                spec=spec,
                status=None,
            )
        else:
            desired = deepcopy(old["spec"])
            desired.update(spec)
            changed = any(
                not _same_clean_rules(v, old["spec"].get(k)) if k == "rules" else old["spec"].get(k) != v
                for k, v in spec.items()
            )
            must_publish = publish and (
                old["spec"].get("deploy_revision") != old["spec"].get("config_revision")
                or old["spec"].get("desired_status") != CleanState.RUNNING
            )
            if _retry_existing is not None:
                retried = _retry_existing(old)
                if not retried and (old.get("status") or {}).get("phase") == "Ok" and (changed or must_publish):
                    raise BKBaseResourceMappingError(message="Existing Clean configuration differs during plugin retry")
            if retried or (_retry_existing is None and (changed or must_publish)):
                desired["config_revision"] = max(
                    int(old["spec"].get("config_revision", 0)) + 1, int(time.time() * 1000)
                )
                desired["deploy_revision"] = (
                    desired["config_revision"] if publish else old["spec"].get("deploy_revision", 0)
                )
                if publish:
                    desired["desired_status"] = CleanState.RUNNING
                result = api.bk_base_v4.clean_update(
                    **params, metadata=deepcopy(old["metadata"]), spec=desired, status=None
                )
            else:
                result = old
    observed = operation_result(result, ref, "configure")
    if retried:
        # 重试 PUT 回执可能仍是旧状态，下一轮正式 GET 才确认发布结果。
        observed["task_state"] = None
    patch = {"clean_ready": observed["task_state"] == TaskState.RUNNING}
    if role == CleanRole.EXISTING:
        patch.update(
            poll_count=0,
            blocked=observed["task_state"] == TaskState.FAILED,
            clean_message=observed.get("message", ""),
        )
    update_owner_binding(owner, patch, remove=["clean_pending_create"])
    return observed


def declared_result_table_id(params):
    """按 Clean 请求生成逻辑输出，不生成 ResultTable Ref。"""
    if "result_table_id" in params:
        return _logical_table_id(params["result_table_id"])
    table_name = _logical_table_id(params.get("result_table_name"))
    business = source._replay_raw_id(params.get("bk_biz_id"))
    return f"{business}_{table_name}"


def build_clean_spec(params, *, data_ref, logical_id, rt_owner, _legacy_json_decoders=None):
    """转换业务规则为正式 Clean 声明，发布版本由调用方补充。"""
    raw_config = json.loads(params["json_config"]) if isinstance(params["json_config"], str) else params["json_config"]
    spec = {
        "alias": params.get("clean_config_name", params.get("result_table_name_alias")),
        "description": params.get("description", ""),
        "data_id": data_ref,
        "raw_data_id": source._replay_raw_id(params.get("raw_data_id")),
        "result_table_source": "new" if rt_owner else "existing",
        "result_table_id": _logical_table_id(logical_id),
        "result_table_alias": params.get("result_table_name_alias", ""),
        "rules": convert_rules(raw_config, fields=params.get("fields", ())),
    }
    if _legacy_json_decoders is not None:
        _legacy_json_decoders.update(
            (rule["input_id"], rule["output_id"]) for rule in spec["rules"] if rule["operator"]["type"] == "json_de"
        )
    if "join" in raw_config:
        spec["join"] = deepcopy(raw_config["join"])
    return spec


def configure_clean(owner, params, *, rt_owner=False, publish=True, _locked_clean_ref=None, _retry_existing=None):
    """统一现有插件/采集项清洗入口，V4不覆盖旧版资源ID。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        field = "processing_id" if hasattr(owner, "processing_id") else "bkbase_processing_id"
        processing_id = getattr(owner, field)
        request = deepcopy(params)
        if processing_id:
            request["processing_id"] = processing_id
            api.bk_base.databus_cleans_put(**request)
            stop_bkbase_clean(owner.bkbase_table_id, processing_id)
            result = {"result_table_id": owner.bkbase_table_id, "processing_id": processing_id}
        else:
            result = api.bk_base.databus_cleans_post(**request)
            setattr(owner, field, result["processing_id"])
            owner.bkbase_table_id = result["result_table_id"]
            owner.save(update_fields=[field, "bkbase_table_id"])
        start_bkbase_clean(result["result_table_id"], result["processing_id"])
        return result
    context = get_bkbase_context()
    field = "processing_id" if hasattr(owner, "processing_id") else "bkbase_processing_id"
    if getattr(owner, field, None) and not (owner.bkbase_v4_resources or {}).get("clean"):
        raise BKBaseResourceMappingError(message="Existing V3 clean requires an explicit V4 migration binding")
    raw_id = source._positive_raw_data_id(str(params.get("raw_data_id")))
    bound_raw_id = (owner.bkbase_v4_resources or {}).get("source_raw_data_id")
    if raw_id is None or (bound_raw_id is not None and bound_raw_id != raw_id):
        raise BKBaseResourceMappingError(message="Clean raw_data_id does not match its source binding")
    if not (owner.bkbase_v4_resources or {}).get("data_id"):
        source.resolve_synced_source(context, owner, raw_data_id=params["raw_data_id"])
    binding = owner.bkbase_v4_resources or {}
    if "migration_import" in binding and "data_source" not in binding:
        if source.bound_plugin_raw_id(context, binding) != raw_id:
            raise BKBaseResourceMappingError(message="Imported Native DataId does not match Clean input")
    if rt_owner:
        binding = owner.bkbase_v4_resources or {}
        if binding.get("clean"):
            rt_id = _logical_table_id(binding.get("result_table_id"))
            rt_ref = (
                _verified_result_table_ref(context, binding, rt_id)
                if binding.get("result_table") or (_retry_existing is None and not binding.get("clean_pending_create"))
                else None
            )
        else:
            rt_ref, rt_id = None, declared_result_table_id(params)
    else:
        plugin = CollectorPlugin.objects.get(collector_plugin_id=owner.collector_plugin_id)
        rt_id, rt_ref = _shared_plugin_table(context, plugin)
    legacy_json_decoders = set()
    spec = build_clean_spec(
        params,
        data_ref=owner.bkbase_v4_resources["data_id"],
        logical_id=rt_id,
        rt_owner=rt_owner,
        _legacy_json_decoders=legacy_json_decoders,
    )
    require_existing = (owner.bkbase_v4_resources or {}).get("clean") and not (owner.bkbase_v4_resources or {}).get(
        "clean_pending_create"
    )
    intent = {"_require_existing": True} if require_existing else {}
    if require_existing and legacy_json_decoders:
        intent["_legacy_json_decoders"] = legacy_json_decoders
    if _retry_existing is not None:
        intent["_retry_existing"] = _retry_existing
    return ensure_clean(
        context, owner, rules=spec, rt_ref=rt_ref, publish=publish, _locked_clean_ref=_locked_clean_ref, **intent
    )


def start_bkbase_clean(bkbase_result_table_id, processing_id, username=None):
    """原V3启停委托保留，仅供V3流程使用。"""
    if get_bkbase_version() != BKBaseVersion.V3:
        raise BKBaseResourceMappingError(message="V4 clean operations require an explicit resource reference")
    return api.bk_base.databus_tasks_post(
        result_table_id=bkbase_result_table_id,
        processing_id=processing_id,
        storages=["kafka"],
        bk_username=username or bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
    )


def stop_bkbase_clean(bkbase_result_table_id, processing_id, username=None):
    """原V3停任务不能作为V4资源操作的隐式回退。"""
    if get_bkbase_version() != BKBaseVersion.V3:
        raise BKBaseResourceMappingError(message="V4 clean operations require an explicit resource reference")
    return api.bk_base.databus_tasks_delete(
        result_table_id=bkbase_result_table_id,
        processing_id=processing_id,
        storages=["clean"],
        bk_username=username or bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME,
    )


def clean_preview(request_data=None, **params):
    """适配审计当前使用的单节点正则预览，其他配置在本地拒绝。

    消费者读取label节点而非最终入库字段；HTTP成功也必须检查算子状态。
    """
    if get_bkbase_version() == BKBaseVersion.V3:
        return legacy_call("clean_preview", request_data, **params)
    request = dict(request_data or params)
    conf = request.get("conf")
    try:
        conf = json.loads(conf) if isinstance(conf, str) else conf
    except (TypeError, ValueError):
        conf = None
    supported = (
        isinstance(conf, dict)
        and conf.get("type") == "fun"
        and conf.get("method") == "regex_extract"
        and conf.get("next") is None
        and isinstance(conf.get("label"), str)
        and bool(conf["label"])
        and isinstance(conf.get("args"), list)
        and len(conf["args"]) == 1
        and isinstance(conf["args"][0], dict)
        and isinstance(conf["args"][0].get("regexp"), str)
        and isinstance(conf["args"][0].get("result"), str)
        and bool(conf["args"][0]["result"])
        and request.get("debug_by_step") is True
    )
    if not supported:
        raise ValidationError({"conf": "V4 preview only accepts a single regex_extract node with debug_by_step=true"})
    result = api.bk_base_v4.clean_debug(input=request["msg"], rules=convert_rules({"extract": conf}), filter_rules=[])
    outputs = result.get("rules_output")
    if (
        result.get("status") != "succeed"
        or not isinstance(outputs, list)
        or len(outputs) != 1
        or not isinstance(outputs[0], dict)
        or outputs[0].get("status") != "succeed"
        or outputs[0].get("output_id") != conf["args"][0]["result"]
        or not isinstance(outputs[0].get("value"), dict)
    ):
        raise APIRequestError(
            module_name="bkbase_v4",
            url="/v4/databus/clean/debug/",
            result={"message": "Clean preview failed or returned an unsupported result"},
        )
    label = conf["label"]
    return {"nodes": {label: outputs[0]["value"]}, "errors": {label: ""}, "error_message": ""}


def databus_cleans_post(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("databus_cleans_post", request_data, **params)


def databus_cleans_put(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("databus_cleans_put", request_data, **params)


def databus_cleans_delete(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("databus_cleans_delete", request_data, **params)


def databus_tasks_post(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("databus_tasks_post", request_data, **params)


def databus_tasks_delete(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("databus_tasks_delete", request_data, **params)


def _collector_has_no_clean(collector):
    """仅无旧清洗ID且无V4清洗痕迹时，允许直接删除未配置的来源。"""
    binding = collector.bkbase_v4_resources or {}
    return not (
        getattr(collector, "processing_id", None)
        or getattr(collector, "bkbase_table_id", None)
        or any(
            binding.get(key)
            for key in ("clean", "clean_role", "clean_pending_create", "clean_delete_requested", "result_table")
        )
    )


def validate_collector_delete(collector):
    """普通删源先保护共享RT创建者，早于日志停采、清洗停止和本地删除。"""
    if get_bkbase_version() == BKBaseVersion.V3 or _collector_has_no_clean(collector):
        return
    binding = collector.bkbase_v4_resources or {}
    if binding.get("clean_role") != CleanRole.EXISTING:
        raise BKBaseSharedResourceProtected()
    # 部分创建或迁移未就绪时，必须在日志停采之前拒绝缺失或越界引用。
    resource_params(get_bkbase_context(), binding.get("clean") or {}, kind="Clean")


def stop_log_collector_clean(collector):
    """日志采集删除入口等待V4清洗真正删除，V3只停止原清洗。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        if collector.processing_id:
            stop_bkbase_clean(collector.bkbase_table_id, collector.processing_id)
        return True
    return delete_source_clean(get_bkbase_context(), collector).get("deleted", False)


def bound_collectors(queryset):
    """已绑定的清洗包含处理中资源，避免同DataID被重复接入。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return queryset.filter(bkbase_table_id__isnull=False)
    return queryset.filter(bkbase_v4_resources__clean__isnull=False)


def delete_collector(collector):
    """同一删源业务入口，V4不在异步删除完成前删除本地记录。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        if collector.processing_id:
            stop_bkbase_clean(collector.bkbase_table_id, collector.processing_id)
            api.bk_base.databus_cleans_delete(processing_id=collector.processing_id)
        type(collector)._objects.filter(pk=collector.pk).delete()
        return None
    result = delete_source_clean(get_bkbase_context(), collector)
    if result.get("deleted"):
        if collector.source_platform == SourcePlatformChoices.BKLOG:
            collector.delete()
        else:
            type(collector)._objects.filter(pk=collector.pk).delete()
    return result


def configured_collectors(queryset):
    """结果表选择只暴露清洗已实际运行的V4来源。"""
    return (
        queryset.filter(bkbase_v4_resources__clean_ready=True)
        if get_bkbase_version() == BKBaseVersion.V4
        else queryset.filter(bkbase_table_id__isnull=False)
    )


def pending_plugins(queryset):
    """周期任务只推进尚未完成的V4插件，不反复重发已运行规则。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return queryset.filter(bkbase_table_id__isnull=True)
    return queryset.filter(Q(bkbase_v4_resources__ready__isnull=True) | Q(bkbase_v4_resources__ready=False)).filter(
        Q(bkbase_v4_resources__blocked__isnull=True) | Q(bkbase_v4_resources__blocked=False)
    )


def _retry_plugin_resource(plugin, step):
    """把单次显式资格交给资源锁内的读回；先记录已检查再允许发请求。"""
    if PLUGIN_RETRY_STEPS not in (plugin.bkbase_v4_resources or {}):
        return {}

    def claim(resource):
        remaining = plugin.bkbase_v4_resources[PLUGIN_RETRY_STEPS]
        if step not in remaining:
            return False
        update_owner_binding(plugin, {PLUGIN_RETRY_STEPS: [name for name in remaining if name != step]})
        return resource is None or (resource.get("status") or {}).get("phase") == "Failed"

    return {"_retry_existing": claim}


def _configure_plugin(handler):
    """插件级共享RT及主副入库按顺序推进，后续周期任务负责等待。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        handler.create_or_update_clean()
        handler.create_or_update_storage()
        return None
    plugin = handler.plugin
    # 导入器依赖本模块的Clean核验；运行时导入避免循环依赖。
    from services.web.bkbase.resource_migration import (
        MIGRATION_BINDING_KEY,
        MIGRATION_MAINTENANCE_KEY,
        observe_imported_resource,
    )

    binding = plugin.bkbase_v4_resources or {}
    if MIGRATION_BINDING_KEY in binding and not binding.get(MIGRATION_MAINTENANCE_KEY):
        update_owner_binding(plugin, {"ready": False, "clean_ready": False})
        return observe_imported_resource(get_bkbase_context(), plugin)
    update_owner_binding(plugin, {"ready": False})
    result = configure_clean(
        plugin, handler.build_clean_config(), rt_owner=True, **_retry_plugin_resource(plugin, "clean")
    )
    if result["task_state"] != TaskState.RUNNING:
        return result
    binding = plugin.bkbase_v4_resources
    rt_id = _logical_table_id(binding.get("result_table_id"))
    rt_ref = _verified_result_table_ref(get_bkbase_context(), binding, rt_id)
    if not binding.get("result_table"):
        update_owner_binding(plugin, {"result_table": rt_ref})
    if plugin.plugin_scene == PluginSceneChoices.EVENT:
        main, replica = handler.build_event_storage_config(), None
    else:
        main, replica = handler.build_storage_config()
    preserve_retention = plugin.plugin_scene == PluginSceneChoices.COLLECTOR
    main_result = storage_service.configure_storage(
        plugin,
        main,
        purpose="main",
        preserve_existing_retention=preserve_retention and "expires" not in main,
        **_retry_plugin_resource(plugin, "main"),
    )
    if main_result["task_state"] == TaskState.FAILED:
        return main_result
    results = [main_result]
    if replica:
        results.append(
            storage_service.configure_storage(
                plugin,
                replica,
                purpose="replica",
                preserve_existing_retention=preserve_retention,
                **_retry_plugin_resource(plugin, "replica"),
            )
        )
    failed = next((result for result in results if result["task_state"] == TaskState.FAILED), None)
    if failed:
        return failed
    running = all(r["task_state"] == TaskState.RUNNING for r in results)
    if running:
        plugin.has_storage = True
        plugin.has_replica_storage = bool(replica)
        plugin.save(update_fields=["has_storage", "has_replica_storage"])
        if plugin.plugin_scene == PluginSceneChoices.EVENT:
            physical = main_result.get("physical_table_name") or main.get("physical_table_name")
            if not physical:
                raise BKBaseResourceMappingError(message="V4 event storage requires a saved physical destination")
            main["physical_table_name"] = physical
            for key, value in (
                (DORIS_EVENT_STORAGE_CONFIG_KEY, main),
                (DORIS_EVENT_BKBASE_RT_ID_KEY, rt_id),
                (DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY, physical),
            ):
                GlobalMetaConfig.set(
                    key, value, config_level=ConfigLevelChoices.NAMESPACE.value, instance_key=plugin.namespace
                )
        update_owner_binding(plugin, {"ready": True})
        return main_result
    return next(r for r in results if r["task_state"] != TaskState.RUNNING)


def reset_plugin_operation(plugin, *, retry_failed=None):
    """按 ID 区分原配置恢复和提交新配置。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        from services.web.bkbase.resource_migration import (
            MIGRATION_BINDING_KEY,
            MIGRATION_MAINTENANCE_KEY,
        )

        binding = plugin.bkbase_v4_resources or {}
        patch = {"poll_count": 0, "blocked": False}
        remove = []
        if retry_failed is False:
            patch["ready"] = False
            remove.append(PLUGIN_RETRY_STEPS)
        elif binding.get("blocked") is True or (retry_failed is True and PLUGIN_RETRY_STEPS not in binding):
            patch.update({"ready": False, PLUGIN_RETRY_STEPS: ["clean", "main", "replica"]})
        if MIGRATION_BINDING_KEY in binding:
            # 仅现有显式task id入口调用reset；后续Beat可继续这次已授权的异步维护。
            patch[MIGRATION_MAINTENANCE_KEY] = True
        update_owner_binding(plugin, patch, remove=remove)


def record_plugin_failure(plugin, error, *, poll_count=None):
    """记录预期业务失败，保留未决写证据并使旧就绪状态失效。"""
    count = poll_count if poll_count is not None else (plugin.bkbase_v4_resources or {}).get("poll_count", 0) + 1
    blocked = count >= BKBASE_V4_MAX_POLLS
    message = str(error)
    if blocked:
        message = "Clean/storage initialization timed out: " + message
    update_owner_binding(
        plugin,
        {"ready": False, "clean_ready": False, "poll_count": count, "blocked": blocked, "message": message},
    )


def configure_plugin(handler):
    """插件初始化逐次推进，有界重试并隔离单插件错误。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return _configure_plugin(handler)
    from services.web.bkbase.resource_migration import (
        MIGRATION_BINDING_KEY,
        MIGRATION_MAINTENANCE_KEY,
    )

    plugin = handler.plugin
    count = (plugin.bkbase_v4_resources or {}).get("poll_count", 0) + 1
    message, failed = "", False
    try:
        result = _configure_plugin(handler)
        failed = result and result["task_state"] == TaskState.FAILED
        message = result.get("message", "") if result else ""
    except PLUGIN_OPERATION_EXCEPTIONS as error:
        logger.exception("BKBase V4 plugin operation failed: %s", plugin.pk)
        record_plugin_failure(plugin, error, poll_count=count)
        return None
    ready = (plugin.bkbase_v4_resources or {}).get("ready", False)
    binding = plugin.bkbase_v4_resources or {}
    imported_stopped = (
        MIGRATION_BINDING_KEY in binding
        and not binding.get(MIGRATION_MAINTENANCE_KEY)
        and result
        and result.get("task_state") == TaskState.STOPPED
    )
    if imported_stopped:
        count = 0
    blocked = not ready and (failed or (not imported_stopped and count >= BKBASE_V4_MAX_POLLS))
    if blocked and not failed:
        message = "Clean/storage initialization timed out: " + message
    update_owner_binding(
        plugin,
        {"poll_count": count, "blocked": blocked, "message": message},
        remove=[MIGRATION_MAINTENANCE_KEY, PLUGIN_RETRY_STEPS] if ready else [],
    )
    return result


def backfill_ready_logical_table_ids(context, model, *, after_pk, limit):
    """只读平台并按主键限批补录已验证的旧 Clean 输出，返回下一批游标。"""
    ready_key = "ready" if model is CollectorPlugin else "clean_ready"
    ids = list(model.objects.filter(pk__gt=after_pk).order_by("pk").values_list("pk", flat=True)[: limit + 1])
    next_after_pk = ids[limit - 1] if len(ids) > limit else None
    ids = ids[:limit]
    candidates = (
        model.objects.filter(
            pk__in=ids, bkbase_v4_resources__clean__isnull=False, **{f"bkbase_v4_resources__{ready_key}": True}
        )
        .filter(Q(bkbase_v4_resources__result_table_id__isnull=True) | Q(bkbase_v4_resources__result_table_id=None))
        .order_by("pk")
    )
    updated, failures = 0, []
    for owner in candidates:
        try:
            ref = source._replay_ref(context, owner.bkbase_v4_resources.get("clean"), "Clean")
            with resource_lock(context, ref):
                latest = model.objects.get(pk=owner.pk)
                binding = latest.bkbase_v4_resources
                if (
                    not isinstance(binding, dict)
                    or not binding.get(ready_key)
                    or binding.get("result_table_id") is not None
                ):
                    continue
                identity = _verified_running_clean_identity(context, latest, ref)
                # 正式 GET 在行锁之外；保留读取期间修改过的本地身份。
                expected = {"pk": owner.pk, "bkbase_v4_resources": binding}
                if model is CollectorConfig:
                    expected["bk_data_id"] = latest.bk_data_id
                saved = model.objects.filter(**expected).update(bkbase_v4_resources={**binding, **identity})
                if saved:
                    updated += 1
                else:
                    failures.append((owner.pk, "binding changed"))
        except (APIRequestError, BKBaseException, ValidateException, LockError, ObjectDoesNotExist) as error:
            failures.append((owner.pk, type(error).__name__))
    return len(ids), updated, len(ids) - updated - len(failures), failures, next_after_pk


def poll_clean_operations():
    """逐条推进删源或清洗，错误隔离且超时停止重试，保留引用供人工重试。"""
    if get_bkbase_version() != BKBaseVersion.V4:
        return
    context = get_bkbase_context()
    from services.web.bkbase.resource_migration import (
        MIGRATION_BINDING_KEY,
        observe_imported_resource,
    )

    queryset = CollectorConfig.objects.filter(bkbase_v4_resources__clean__isnull=False).filter(
        Q(bkbase_v4_resources__blocked__isnull=True) | Q(bkbase_v4_resources__blocked=False)
    )
    for collector in queryset:
        binding = collector.bkbase_v4_resources
        if binding.get("clean_ready") and binding.get("pending_action") != "delete":
            continue
        count = binding.get("poll_count", 0) + 1
        result, message = {}, ""
        try:
            if binding.get("pending_action") == "delete":
                result = delete_collector(collector)
                if result.get("deleted"):
                    continue
            elif MIGRATION_BINDING_KEY in binding:
                result = observe_imported_resource(context, collector)
            else:
                ref = binding["clean"]
                current = api.bk_base_v4.clean_get(**resource_params(context, ref, kind="Clean"))
                result = operation_result(current, ref, "observe")
            message = result.get("message", "")
        except (APIRequestError, BKBaseException, LockError) as error:
            message = str(error)
            logger.exception("BKBase V4 Clean observation failed: %s", collector.pk)
        ready = result.get("task_state") == TaskState.RUNNING and binding.get("pending_action") != "delete"
        imported_stopped = (
            MIGRATION_BINDING_KEY in binding
            and binding.get("pending_action") != "delete"
            and result.get("task_state") == TaskState.STOPPED
        )
        if imported_stopped:
            count = 0
        blocked = result.get("task_state") == TaskState.FAILED or (
            not ready and not imported_stopped and count >= BKBASE_V4_MAX_POLLS
        )
        if blocked and result.get("task_state") != TaskState.FAILED:
            message = "Clean operation timed out: " + message
        update_owner_binding(
            collector, {"clean_ready": ready, "clean_message": message, "poll_count": count, "blocked": blocked}
        )


def result_table_id(owner, *, require_ready=True):
    """向既有消费者投影当前版本RT，不改写历史V3字段。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return owner.bkbase_table_id
    binding = owner.bkbase_v4_resources or {}
    if require_ready and not binding.get("ready", binding.get("clean_ready", False)):
        return None
    logical_id = binding.get("result_table_id")
    return _logical_table_id(logical_id) if logical_id is not None else None
