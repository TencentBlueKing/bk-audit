"""转换审计清洗规则并管理Clean生命周期。

创建者角色独立于采集项删除；保存和发布分别推进配置版本。
单次API受理不能当成运行完成，绑定保留供异步任务重试。
"""

import json
import re
import time
from copy import deepcopy

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.db.models import Q

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
    pending_call,
    resource_lock,
    resource_params,
    stable_name,
    update_owner_binding,
)
from services.web.bkbase.constants import (
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
from services.web.databus.models import CollectorConfig, CollectorPlugin


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


def convert_rules(config, *, fields=()):
    """展开V3树式规则，保留扇出行为及业务字段的别名、维度定义。"""
    config = json.loads(config) if isinstance(config, str) else config
    rules = []
    conf = config.get("conf", {})
    field_map = {field["field_name"]: field for field in fields}

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
            rules.append({"input_id": input_id, "output_id": output_id, "operator": operator})
        elif kind == "access":
            positional = node.get("subtype") == "access_pos"
            key = node.get("index") if positional else node.get("key")
            if positional:
                if isinstance(key, str) and key.isascii() and key.isdigit():
                    key = int(key)
                if type(key) is not int or key < 0:
                    raise BKBaseResourceMappingError(message="Invalid clean array index")
            operator = {"type": "get", "key_index": [{"type": "index" if positional else "key", "value": key}]}
            if "default_type" in node:
                operator.update(
                    missing_strategy="default",
                    default=None if node["default_type"] == "null" else node.get("default_value"),
                )
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
                operator = {"type": "assign", "key_index": str(key), "output_type": assignment["type"]}
                field = field_map.get(target, {})
                if field.get("field_alias") is not None:
                    operator["alias"] = field["field_alias"]
                if "is_dimension" in field:
                    operator["is_dimension"] = field["is_dimension"]
                if target == conf.get("time_field_name"):
                    operator["is_time_field"] = True
                    operator["time_format"] = {"format": conf["time_format"], "zone": conf.get("timezone", 8)}
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


def ensure_clean(context, owner, *, rules, rt_ref, publish=True):
    """稳定引用下声明/更新Clean，首次失败后的重试先核实远端。"""
    binding = deepcopy(owner.bkbase_v4_resources or {})
    ref = binding.get("clean") or {
        "kind": "Clean",
        "tenant": context["tenant"],
        "namespace": context["namespace"],
        "name": stable_name("c", owner.__class__.__name__, owner.pk),
    }
    params = resource_params(context, ref, kind="Clean")
    spec = deepcopy(rules)
    role = CleanRole.OWNER if spec.get("result_table_source", "new") == "new" else CleanRole.EXISTING
    if binding.get("clean_role") not in (None, role):
        raise BKBaseResourceMappingError(message="Clean ownership cannot be changed")
    update_owner_binding(
        owner, {"clean": ref, "clean_role": role, "result_table": rt_ref, "clean_pending_create": True}
    )
    with resource_lock(context, ref):
        old = get_resource_or_none(api.bk_base_v4.clean_get, **params)
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
            if (
                old["spec"].get("raw_data_id") != spec["raw_data_id"]
                or old["spec"].get("result_table_id") != spec["result_table_id"]
            ):
                raise BKBaseResourceMappingError(message="Existing Clean ownership mismatch")
            desired = deepcopy(old["spec"])
            desired.update(spec)
            changed = any(old["spec"].get(k) != v for k, v in spec.items())
            must_publish = publish and (
                old["spec"].get("deploy_revision") != old["spec"].get("config_revision")
                or old["spec"].get("desired_status") != CleanState.RUNNING
            )
            if changed or must_publish:
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
    patch = {"clean_ready": observed["task_state"] == TaskState.RUNNING}
    if role == CleanRole.EXISTING:
        patch.update(
            poll_count=0,
            blocked=observed["task_state"] == TaskState.FAILED,
            clean_message=observed.get("message", ""),
        )
    update_owner_binding(owner, patch, remove=["clean_pending_create"])
    return observed


def configure_clean(owner, params, *, rt_owner=False, publish=True):
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
    if not (owner.bkbase_v4_resources or {}).get("data_id"):
        source.resolve_synced_source(context, owner, raw_data_id=params["raw_data_id"])
    if rt_owner:
        rt_id = params.get("result_table_id") or f"{params['bk_biz_id']}_{params['result_table_name']}"
        rt_ref = {"kind": "ResultTable", "tenant": context["tenant"], "namespace": context["namespace"], "name": rt_id}
    else:
        plugin = CollectorPlugin.objects.get(collector_plugin_id=owner.collector_plugin_id)
        rt_ref = (plugin.bkbase_v4_resources or {}).get("result_table")
        if not rt_ref:
            raise BKBaseResourceMappingError(message="Shared V4 result table is not ready")
        resource_params(context, rt_ref, kind="ResultTable")
    spec = {
        "alias": params.get("clean_config_name", params.get("result_table_name_alias")),
        "description": params.get("description", ""),
        "data_id": owner.bkbase_v4_resources["data_id"],
        "raw_data_id": int(params["raw_data_id"]),
        "result_table_source": "new" if rt_owner else "existing",
        "result_table_id": rt_ref["name"],
        "result_table_alias": params.get("result_table_name_alias", ""),
        "rules": convert_rules(params["json_config"], fields=params.get("fields", ())),
    }
    raw_config = json.loads(params["json_config"]) if isinstance(params["json_config"], str) else params["json_config"]
    if "join" in raw_config:
        spec["join"] = deepcopy(raw_config["join"])
    return ensure_clean(context, owner, rules=spec, rt_ref=rt_ref, publish=publish)


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
    """适配已验证的单节点正则预览，其他V4配置继续保留B06门禁。

    消费者读取label节点而非最终入库字段；HTTP成功也必须检查算子状态。
    """
    if get_bkbase_version() == BKBaseVersion.V3:
        return pending_call("clean_preview", "B06", request_data, **params)
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
        return pending_call("clean_preview", "B06", request)
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


def _configure_plugin(handler):
    """插件级共享RT及主副入库按顺序推进，后续周期任务负责等待。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        handler.create_or_update_clean()
        handler.create_or_update_storage()
        return None
    plugin = handler.plugin
    update_owner_binding(plugin, {"ready": False})
    result = configure_clean(plugin, handler.build_clean_config(), rt_owner=True)
    if result["task_state"] != TaskState.RUNNING:
        return result
    if plugin.plugin_scene == PluginSceneChoices.EVENT:
        main, replica = handler.build_event_storage_config(), None
    else:
        main, replica = handler.build_storage_config()
    main_result = storage_service.configure_storage(plugin, main, purpose="main")
    if main_result["task_state"] == TaskState.FAILED:
        return main_result
    results = [main_result]
    if replica:
        results.append(storage_service.configure_storage(plugin, replica, purpose="replica"))
    failed = next((result for result in results if result["task_state"] == TaskState.FAILED), None)
    if failed:
        return failed
    running = all(r["task_state"] == TaskState.RUNNING for r in results)
    if running:
        plugin.has_storage = True
        plugin.has_replica_storage = bool(replica)
        plugin.save(update_fields=["has_storage", "has_replica_storage"])
        if plugin.plugin_scene == PluginSceneChoices.EVENT:
            rt_id = plugin.bkbase_v4_resources["result_table"]["name"]
            meta = metadata_service.get_result_table(rt_id, related=["storages"])
            physical = meta.get("storages", {}).get("doris", {}).get("physical_table_name")
            if not physical:
                raise BKBaseResourceMappingError(message="V4 event physical table mapping is not ready")
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


def reset_plugin_operation(plugin):
    """显式重试允许修正配置后重新推进，后台轮询不自动清除终止状态。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        update_owner_binding(plugin, {"poll_count": 0, "blocked": False, "message": ""})


def configure_plugin(handler):
    """插件初始化逐次推进，有界重试并隔离单插件错误。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return _configure_plugin(handler)
    plugin = handler.plugin
    count = (plugin.bkbase_v4_resources or {}).get("poll_count", 0) + 1
    message, failed = "", False
    try:
        result = _configure_plugin(handler)
        failed = result and result["task_state"] == TaskState.FAILED
        message = result.get("message", "") if result else ""
    except (APIRequestError, BKBaseException, LockError) as error:
        result, message = None, str(error)
        logger.exception("BKBase V4 plugin operation failed: %s", plugin.pk)
    ready = (plugin.bkbase_v4_resources or {}).get("ready", False)
    blocked = not ready and (failed or count >= BKBASE_V4_MAX_POLLS)
    if blocked and not failed:
        message = "Clean/storage initialization timed out: " + message
    update_owner_binding(plugin, {"poll_count": count, "blocked": blocked, "message": message})
    return result


def poll_clean_operations():
    """逐条推进删源或清洗，错误隔离且超时停止重试，保留引用供人工重试。"""
    if get_bkbase_version() != BKBaseVersion.V4:
        return
    context = get_bkbase_context()
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
            else:
                ref = binding["clean"]
                current = api.bk_base_v4.clean_get(**resource_params(context, ref, kind="Clean"))
                result = operation_result(current, ref, "observe")
            message = result.get("message", "")
        except (APIRequestError, BKBaseException, LockError) as error:
            message = str(error)
            logger.exception("BKBase V4 Clean observation failed: %s", collector.pk)
        ready = result.get("task_state") == TaskState.RUNNING and binding.get("pending_action") != "delete"
        blocked = result.get("task_state") == TaskState.FAILED or (not ready and count >= BKBASE_V4_MAX_POLLS)
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
    ref = binding.get("result_table")
    if not ref:
        return None
    resource_params(get_bkbase_context(), ref, kind="ResultTable")
    return ref["name"]
