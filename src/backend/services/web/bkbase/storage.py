"""管理结果表共享入库与显式集群引用。

入库资源按RT/目标集群/用途复用；数字旧集群ID不当作V4名字。
完整PUT在资源锁内保留未修改配置，单来源删除不清理共享存储。
"""

from copy import deepcopy

from bk_resource import api

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, System
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
    BKBASE_V4_STORAGE_CLUSTER_MAP,
    BKBaseVersion,
    DorisDataModel,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError


def resolve_storage_cluster(context, *, audit_namespace, storage_type, legacy_cluster_id):
    """从登记映射取得同租户集群，主副用途不能猜测。"""
    mapping = GlobalMetaConfig.get(
        config_key=BKBASE_V4_STORAGE_CLUSTER_MAP,
        config_level=ConfigLevelChoices.NAMESPACE.value,
        instance_key=audit_namespace,
    )
    ref = mapping.get(storage_type, {}).get(str(legacy_cluster_id)) if isinstance(mapping, dict) else None
    if not isinstance(ref, dict) or not ref.get("kind"):
        raise BKBaseResourceMappingError(message=f"Missing V4 {storage_type} cluster mapping for {legacy_cluster_id}")
    resource_params(context, ref)
    return deepcopy(ref)


def _merge_spec(old, config):
    spec = deepcopy(old)
    for key, value in config.items():
        if key in ("tableInfo", "taskFieldSetting"):
            spec.setdefault(key, {}).update(deepcopy(value))
        else:
            spec[key] = deepcopy(value)
    return spec


def ensure_storage(context, owner, *, rt_ref, cluster_ref, purpose, config):
    """复用共享RT入库；不能接管引用不同源表或集群的同名资源。"""
    resource_params(context, rt_ref, kind="ResultTable")
    resource_params(context, cluster_ref)
    binding = deepcopy(owner.bkbase_v4_resources or {})
    ref = binding.get("storages", {}).get(purpose)
    if ref is None:
        ref = {
            "kind": "DataStorage",
            "tenant": context["tenant"],
            "namespace": rt_ref["namespace"],
            "name": stable_name(
                "s", rt_ref["name"], cluster_ref["kind"], cluster_ref["namespace"], cluster_ref["name"], purpose
            ),
        }
    params = resource_params(context, ref, kind="DataStorage")
    with resource_lock(context, ref):
        old = get_resource_or_none(api.bk_base_v4.data_storage_get, **params)
        desired = deepcopy(config)
        desired.setdefault("tableInfo", {}).update(source=rt_ref, storage=cluster_ref)
        if old is not None:
            table = old["spec"].get("tableInfo", {})
            if table.get("source") != rt_ref or table.get("storage") != cluster_ref:
                raise BKBaseResourceMappingError(message="DataStorage ownership mismatch")
            merged = _merge_spec(old["spec"], desired)
            result = (
                old
                if merged == old["spec"]
                else api.bk_base_v4.data_storage_update(
                    **params, metadata=deepcopy(old["metadata"]), spec=merged, status=None
                )
            )
        else:
            result = api.bk_base_v4.data_storage_create(
                tenant=params["tenant"],
                namespace=params["namespace"],
                metadata={k: ref[k] for k in ("tenant", "namespace", "name")},
                spec=desired,
                status=None,
            )
        update_owner_binding(owner, {"storages": {purpose: ref}})
    return operation_result(result, ref, "configure")


def set_storage_state(context, storage_ref, *, running):
    """仅写字符串task_stopped，不删除共享资源。"""
    params = resource_params(context, storage_ref, kind="DataStorage")
    with resource_lock(context, storage_ref):
        old = api.bk_base_v4.data_storage_get(**params)
        metadata = deepcopy(old["metadata"])
        metadata.setdefault("annotations", {})["task_stopped"] = "false" if running else "true"
        result = api.bk_base_v4.data_storage_update(
            **params, metadata=metadata, spec=deepcopy(old["spec"]), status=None
        )
    return operation_result(result, storage_ref, "start" if running else "stop")


def convert_storage_config(params):
    """转换已有审计存储语义，只使用V4文档明确的字段。"""
    info = deepcopy(params.get("config", {}))
    models = {
        DorisDataModel.DUPLICATE: DorisDataModel.DUPLICATE.value,
        "aggregate_table": "AggregateTable",
        "primary_table": "UniqueTable",
        "unique_table": "UniqueTable",
    }
    if info.get("data_model") in models:
        info["data_model"] = models[info["data_model"]]
    expires = params.get("expires")
    if expires is not None:
        value = str(expires)
        info["expire"] = int(value[:-1] if value.endswith("d") else value)
    allowed = {
        "data_model",
        "dimension_table",
        "has_unique_key",
        "is_profiling",
        "replicas",
        "setnx",
        "storage_separator",
        "storage_type",
        "unique_partition_table",
        "expire",
    }
    table = {k: v for k, v in info.items() if k in allowed}
    fields = params.get("fields", [])
    field_settings = {
        key: deepcopy(params[key])
        for key in (
            "key_fields",
            "value_fields",
            "index_fields",
            "analyzed_fields",
            "json_fields",
            "doc_value_fields",
            "original_json_fields",
            "flattened_fields",
            "zh_analyzed_fields",
            "tokenizers",
        )
        if key in params
    }
    for key in ("key_fields", "value_fields"):
        if key in field_settings:
            field_settings[key] = [f["field_name"] if isinstance(f, dict) else f for f in field_settings[key]]
    for option, target in (
        ("is_key", "key_fields"),
        ("is_zh_analyzed", "zh_analyzed_fields"),
        ("is_index", "index_fields"),
        ("is_analyzed", "analyzed_fields"),
        ("is_json", "json_fields"),
        ("is_original_json", "original_json_fields"),
        ("is_doc_values", "doc_value_fields"),
    ):
        if any(option in f for f in fields):
            field_settings[target] = [f["field_name"] for f in fields if f.get(option)]
    return {
        "tableInfo": table,
        "taskFieldSetting": field_settings,
        "autoOffsetReset": params.get("auto_offset_reset", "earliest"),
    }


def configure_storage(owner, params, *, purpose="main", update=False):
    """按业务所有者配置入库，V4只保存独立引用。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        method = api.bk_base.databus_storages_put if update else api.bk_base.databus_storages_post
        return method(**params)
    context = get_bkbase_context()
    ref = (owner.bkbase_v4_resources or {}).get("result_table")
    if not ref:
        raise BKBaseResourceMappingError(message="V4 result table binding is not ready")
    cluster = resolve_storage_cluster(
        context,
        audit_namespace=getattr(owner, "namespace", None) or System.objects.get(system_id=owner.system_id).namespace,
        storage_type=params["storage_type"],
        legacy_cluster_id=params["storage_cluster"],
    )
    return ensure_storage(
        context, owner, rt_ref=ref, cluster_ref=cluster, purpose=purpose, config=convert_storage_config(params)
    )


def create_resource_set(request_data=None, **params):
    """V4关键契约待B05，V3调用保持。"""
    return pending_call("create_resource_set", "B05", request_data, **params)


def update_resource_set(request_data=None, **params):
    """V4关键契约待B05，V3调用保持。"""
    return pending_call("update_resource_set", "B05", request_data, **params)


def databus_storages_post(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("databus_storages_post", request_data, **params)


def databus_storages_put(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("databus_storages_put", request_data, **params)
