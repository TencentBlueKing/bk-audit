"""管理结果表共享入库与显式集群引用。

入库资源按RT/目标集群/用途复用；数字旧集群ID不当作V4名字。
完整PUT在资源锁内保留未修改配置，单来源删除不清理共享存储。
"""

import hashlib
import json
from copy import deepcopy

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.db import IntegrityError, connection, transaction

from api.bk_base_v4.serializers import RedisAssetCreateRequestSerializer
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, System
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
    BKBASE_V4_REDIS_BINDING,
    BKBASE_V4_STORAGE_CLUSTER_KINDS,
    BKBASE_V4_STORAGE_CLUSTER_MAP,
    BKBaseVersion,
    DorisDataModel,
    RedisRegistrationState,
    TaskState,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import PluginSceneChoices
from services.web.databus.models import CollectorPlugin, RedisConfig


def resolve_storage_cluster(context, *, audit_namespace, storage_type, legacy_cluster_id):
    """从登记映射取得同租户集群，主副用途不能猜测。"""
    mapping = GlobalMetaConfig.get(
        config_key=BKBASE_V4_STORAGE_CLUSTER_MAP,
        config_level=ConfigLevelChoices.NAMESPACE.value,
        instance_key=audit_namespace,
        default={},
    )
    clusters = mapping.get(storage_type) if isinstance(mapping, dict) else None
    ref = clusters.get(str(legacy_cluster_id)) if isinstance(clusters, dict) else None
    kind = BKBASE_V4_STORAGE_CLUSTER_KINDS.get(storage_type)
    if storage_type == "redis":
        local = RedisConfig.objects.filter(
            namespace=audit_namespace, redis_name_en=str(legacy_cluster_id), is_deleted=False
        ).first()
        if local is not None and BKBASE_V4_REDIS_BINDING in (local.extra or {}):
            saved = (local.extra or {}).get(BKBASE_V4_REDIS_BINDING) or {}
            if saved.get("registration_state") != RedisRegistrationState.BOUND:
                raise BKBaseResourceMappingError(message="Redis registration has no verified resource binding")
            registered_ref = saved.get("resource_ref")
            if ref is not None and ref != registered_ref:
                raise BKBaseResourceMappingError(message="Redis registration conflicts with configured cluster mapping")
            ref = deepcopy(registered_ref)
    if kind is None or not isinstance(ref, dict):
        raise BKBaseResourceMappingError(message=f"Missing V4 {storage_type} cluster mapping for {legacy_cluster_id}")
    resource_params(context, ref, kind=kind)
    return deepcopy(ref)


def _merge_spec(old, config):
    """保留未调整的配置；Doris主键模型不沿用历史普通索引。"""
    spec = deepcopy(old)
    for key, value in config.items():
        if key in ("tableInfo", "taskFieldSetting"):
            spec.setdefault(key, {}).update(deepcopy(value))
        else:
            spec[key] = deepcopy(value)
    if spec.get("tableInfo", {}).get("data_model") in (DorisDataModel.PRIMARY, DorisDataModel.PRIMARY_PARTITION):
        fields = spec.get("taskFieldSetting", {})
        if fields.get("index_fields") is not None:
            fields.pop("index_fields", None)
    return spec


def storage_ref(context, owner, *, rt_ref, cluster_ref, purpose):
    """按同一 RT、集群和用途取得稳定入库引用，声明前后使用相同身份。"""
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
    return deepcopy(ref)


def normalize_physical_table_name(storage_type, value):
    """统一 ES 日期模板；Doris 显式目标必须同时声明库和表。"""
    if not isinstance(value, str) or not value or any(char.isspace() or char in "/\\" for char in value):
        raise BKBaseResourceMappingError(message="Invalid physical storage destination")
    if storage_type == "es":
        return value.replace("{yyyyMMdd}", "%Y%m%d")
    if storage_type == "doris":
        parts = value.split(".")
        if len(parts) != 2 or not all(parts) or any(char in value for char in "{}%"):
            raise BKBaseResourceMappingError(message="V4 Doris destination must be an explicit database.table")
    return value


def ensure_storage(
    context,
    owner,
    *,
    rt_ref,
    cluster_ref,
    purpose,
    config,
    preserve_existing_retention=False,
    _before_write=None,
    _bind_owner=True,
    _retry_failed=False,
    _retry_existing=None,
):
    """复用共享入库；初始编排可先认领写意图，再独立确认绑定。"""
    ref = storage_ref(context, owner, rt_ref=rt_ref, cluster_ref=cluster_ref, purpose=purpose)
    params = resource_params(context, ref, kind="DataStorage")
    wrote = False
    retried_plugin = False
    with resource_lock(context, ref):
        old = get_resource_or_none(api.bk_base_v4.data_storage_get, **params)
        bound = (owner.bkbase_v4_resources or {}).get("storages", {}).get(purpose)
        if old is None and bound is not None:
            raise BKBaseResourceMappingError(message="The established V4 DataStorage is missing; cannot recreate it")
        desired = deepcopy(config)
        desired.setdefault("tableInfo", {}).update(source=rt_ref, storage=cluster_ref)
        physical = None
        storage_type = {"Doris": "doris", "ElasticSearch": "es"}.get(cluster_ref["kind"])
        if storage_type:
            saved = (owner.bkbase_v4_resources or {}).get("physical_targets", {}).get(purpose)
            existing = (old or {}).get("spec", {}).get("tableInfo", {}).get("physical_table_name")
            requested = desired["tableInfo"].get("physical_table_name")
            targets = [
                normalize_physical_table_name(storage_type, value)
                for value in (saved, existing, requested)
                if value is not None
            ]
            if targets:
                physical = targets[0]
                if any(value != physical for value in targets):
                    raise BKBaseResourceMappingError(message="V4 storage destination conflicts with its saved target")
                desired["tableInfo"]["physical_table_name"] = physical
        if _before_write is not None:
            _before_write(ref, desired, old)
        if old is not None:
            table = old["spec"].get("tableInfo", {})
            if table.get("source") != rt_ref or table.get("storage") != cluster_ref:
                raise BKBaseResourceMappingError(message="DataStorage ownership mismatch")
            if preserve_existing_retention:
                desired["tableInfo"].pop("expire", None)
            merged = _merge_spec(old["spec"], desired)
            phase = (old.get("status") or {}).get("phase")
            changed = merged != old["spec"]
            if _retry_existing is not None:
                if old.get("kind") != "DataStorage" or any(
                    old.get("metadata", {}).get(k) != v for k, v in params.items()
                ):
                    raise BKBaseResourceMappingError(message="Existing DataStorage resource identity mismatch")
                _retry_failed = _retry_existing(old)
                if not _retry_failed and phase == "Ok" and changed:
                    raise BKBaseResourceMappingError(
                        message="Existing DataStorage configuration differs during plugin retry"
                    )
            retrying_failed = _retry_failed and phase == "Failed"
            if not (retrying_failed or (_retry_existing is None and changed)):
                result = old
            else:
                wrote = True
                retried_plugin = _retry_existing is not None and retrying_failed
                result = api.bk_base_v4.data_storage_update(
                    **params, metadata=deepcopy(old["metadata"]), spec=merged, status=None
                )
        else:
            # 普通插件副Doris不声明新建周期，由存储侧维护；其他来源仍需有效周期。
            storage_managed_retention = (
                isinstance(owner, CollectorPlugin)
                and owner.plugin_scene == PluginSceneChoices.COLLECTOR
                and purpose == "replica"
                and cluster_ref["kind"] == "Doris"
                and "expire" not in desired["tableInfo"]
            )
            if preserve_existing_retention and not storage_managed_retention:
                expire = desired["tableInfo"].get("expire")
                if not isinstance(expire, int) or isinstance(expire, bool) or (expire <= 0 and expire != -1):
                    raise BKBaseResourceMappingError(
                        message="V4 plugin storage creation requires an explicit valid retention"
                    )
            if _retry_existing is not None and not _retry_existing(None):
                raise BKBaseResourceMappingError(message="Previous DataStorage creation is still unconfirmed")
            wrote = True
            result = api.bk_base_v4.data_storage_create(
                tenant=params["tenant"],
                namespace=params["namespace"],
                metadata={k: ref[k] for k in ("tenant", "namespace", "name")},
                spec=desired,
                status=None,
            )
        if _bind_owner:
            binding = {"storages": {purpose: ref}}
            if physical is not None:
                binding["physical_targets"] = {purpose: physical}
            update_owner_binding(owner, binding)
    observed = operation_result(result, ref, "configure")
    if physical is not None:
        observed["physical_table_name"] = physical
    # 插件显式重试以之后的正式 GET 为准，PUT 回执可能仍携带旧失败。
    if retried_plugin or (wrote and observed["task_state"] != TaskState.FAILED):
        observed["task_state"] = None
    return observed


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
    observed = operation_result(result, storage_ref, "start" if running else "stop")
    if observed["task_state"] != TaskState.FAILED:
        observed["task_state"] = None
    return observed


def convert_storage_config(params):
    """转换已有审计存储语义，只使用V4文档明确的字段。"""
    info = deepcopy(params.get("config", {}))
    model = info.get("data_model")
    if model is not None and model not in DorisDataModel.values:
        raise BKBaseResourceMappingError(message="Unsupported V4 Doris data model")
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
    if params.get("storage_type") in ("es", "doris") and "physical_table_name" in params:
        table["physical_table_name"] = normalize_physical_table_name(
            params["storage_type"], params["physical_table_name"]
        )
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
        if target == "key_fields" and target in field_settings:
            continue
        if any(option in f for f in fields):
            field_settings[target] = [f["field_name"] for f in fields if f.get(option)]
    if model in (DorisDataModel.PRIMARY, DorisDataModel.PRIMARY_PARTITION):
        field_settings.pop("index_fields", None)
    return {
        "tableInfo": table,
        "taskFieldSetting": field_settings,
        "autoOffsetReset": params.get("auto_offset_reset", "earliest"),
    }


def configure_storage(
    owner,
    params,
    *,
    purpose="main",
    update=False,
    preserve_existing_retention=False,
    _before_write=None,
    _bind_owner=True,
    _retry_failed=False,
    _retry_existing=None,
):
    """按业务所有者配置入库，V4只保存独立引用。

    普通插件维护保留锁内读到的当前周期；副Doris新建不声明周期，其他来源仍校验。
    默认仍消费显式 expires，供业务发起实际周期变更。
    未声明消费起点时保留已有值，新建由平台采用默认值。
    """
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
    config = convert_storage_config(params)
    if (
        preserve_existing_retention
        and "expires" in params
        and params["expires"] is None
        and "expire" not in config["tableInfo"]
    ):
        # 保留显式空值供新建校验；已有存储仍由锁内合并保留当前周期。
        config["tableInfo"]["expire"] = None
    if "auto_offset_reset" not in params:
        config.pop("autoOffsetReset", None)
    intent = {}
    if _before_write is not None:
        intent.update(_before_write=_before_write, _bind_owner=_bind_owner, _retry_failed=_retry_failed)
    if _retry_existing is not None:
        intent["_retry_existing"] = _retry_existing
    return ensure_storage(
        context,
        owner,
        rt_ref=ref,
        cluster_ref=cluster,
        purpose=purpose,
        config=config,
        preserve_existing_retention=preserve_existing_retention,
        **intent,
    )


def _redis_registration_params(params):
    """仅映射已明确的直连Redis；项目、租户和IAM管理员来自可信平台上下文。"""
    context = get_bkbase_context()
    resource_params(context)
    actor = bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
    if not bk_resource_settings.PLATFORM_AUTH_ENABLED or not isinstance(actor, str) or not actor:
        raise BKBaseResourceMappingError(message="Redis registration requires the configured platform user identity")
    info = params.get("connection_info")
    if not isinstance(info, dict):
        raise BKBaseResourceMappingError(message="Missing Redis connection configuration")
    if info.get("enable_sentinel") is not False and (
        info.get("enable_sentinel") or any(info.get(key) for key in ("name_sentinel", "host_sentinel", "port_sentinel"))
    ):
        raise BKBaseResourceMappingError(message="Sentinel registration requires its explicit V4 connection contract")
    if set(info) - {
        "enable_sentinel",
        "name_sentinel",
        "host_sentinel",
        "port_sentinel",
        "host",
        "port",
        "password",
        "db",
    }:
        raise BKBaseResourceMappingError(message="Unsupported Redis connection options")
    if info.get("password") == "*******":
        raise BKBaseResourceMappingError(message="Masked Redis password cannot be used for registration")
    if params.get("share"):
        raise BKBaseResourceMappingError(message="Redis sharing requires explicit target projects")
    payload = {
        "tenant": context["tenant"],
        "project_name": context["namespace"],
        "asset_name": params.get("resource_set_id"),
        "asset_alias": params.get("resource_set_name"),
        "sub_type": "Redis",
        "belong_type": "project_private",
        "connection": {
            "kind": "Redis",
            "config": {key: info[key] for key in ("host", "port", "password", "db") if key in info},
        },
        "tags": params.get("tag", []),
        "encrypt_password": True,
        "sync_to_iam": True,
    }
    serializer = RedisAssetCreateRequestSerializer(data=payload)
    if not serializer.is_valid():
        # 校验异常可能回显口令原文，不将其完整details带入业务异常或登记记录。
        raise BKBaseResourceMappingError(message="Incomplete or invalid Redis registration parameters")
    return context, actor, dict(serializer.validated_data)


def create_resource_set(request_data=None, **params):
    """V3保持原语；V4只登记直连Redis，成功返回asset_name受理回执。"""
    if get_bkbase_version() == BKBaseVersion.V3:
        return legacy_call("create_resource_set", request_data, **params)
    _, _, payload = _redis_registration_params({**(request_data or {}), **params})
    return api.bk_base_v4.storage_asset_create(**payload)


def list_registered_redis_assets(*, page=1, page_size=100, asset_name=None):
    """按可信BKBase项目读取一页Redis资产；列表状态不表示连接或任务就绪。"""
    context = get_bkbase_context()
    resource_params(context)
    params = {
        "tenant": context["tenant"],
        "project_name": context["namespace"],
        "sub_types": ["Redis"],
        "page": page,
        "page_size": page_size,
    }
    if asset_name is not None:
        params["asset_name"] = asset_name
    return api.bk_base_v4.storage_asset_list(**params)


def _redis_asset_ref(context, asset_name):
    """只读取正式详情的resource_ns；不读取、回写或连接遮罩密码。"""
    detail = api.bk_base_v4.storage_asset_get(
        tenant=context["tenant"], project_name=context["namespace"], sub_type="Redis", asset_name=asset_name
    )
    ns = detail.get("resource_ns")
    if not isinstance(ns, dict) or ns.get("kind") != "Redis":
        raise BKBaseResourceMappingError(message="Redis asset detail has no authoritative resource_ns")
    ref = {
        "kind": "Redis",
        "tenant": ns.get("tenant", context["tenant"]),
        "namespace": ns.get("namespace"),
        "name": ns.get("name"),
    }
    resource_params(context, ref, kind="Redis")
    if ref["namespace"] != context["namespace"] or ref["name"] != asset_name:
        raise BKBaseResourceMappingError(
            message="Registered Redis resource does not match the trusted project and asset"
        )
    if detail.get("belong_type", "project_private") != "project_private":
        raise BKBaseResourceMappingError(message="New Redis registration cannot adopt a shared or public asset")
    return ref


def _save_redis_registration(config, patch):
    """短事务仅合并登记字段，保留既有extra的使用计数、系统和其它数据。"""
    with transaction.atomic():
        current = RedisConfig.objects.select_for_update().get(pk=config.pk)
        extra = deepcopy(current.extra or {})
        saved = extra.setdefault(BKBASE_V4_REDIS_BINDING, {})
        saved.update(deepcopy(patch))
        current.extra = extra
        current.save(update_fields=["extra"])
    config.extra = extra


def register_redis_config(data, params):
    """由真实RedisHandler登记并绑定；extra保留最小部分结果，未知写不重POST。

    已受理但未读到Ref时，同一创建请求只重读详情。BOUND仅表示引用已核实，
    不证明Redis连通、集群调和、清洗入库或数据验收。
    """
    context, actor, payload = _redis_registration_params(params)
    if connection.in_atomic_block:
        raise BKBaseResourceMappingError(message="Redis registration must run outside an outer database transaction")
    fingerprint = hashlib.sha256(
        json.dumps(
            {"payload": payload, "audit_namespace": data["namespace"], "actor": actor, "version": params["version"]},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    created = False
    try:
        with transaction.atomic():
            config = RedisConfig.objects.select_for_update().filter(redis_name_en=payload["asset_name"]).first()
            if config is None:
                config = RedisConfig.objects.create(
                    namespace=data["namespace"],
                    redis_name_en=payload["asset_name"],
                    redis_name=payload["asset_alias"],
                    admin=[actor],
                    connection_info=deepcopy(params["connection_info"]),
                    version=params["version"],
                    extra={
                        BKBASE_V4_REDIS_BINDING: {
                            "registration_state": RedisRegistrationState.REGISTERING,
                            "request_digest": fingerprint,
                            "tenant": context["tenant"],
                            "project_name": context["namespace"],
                            "asset_name": payload["asset_name"],
                        }
                    },
                )
                created = True
            else:
                saved = (config.extra or {}).get(BKBASE_V4_REDIS_BINDING, {})
                if saved.get("request_digest") != fingerprint or config.is_deleted:
                    raise BKBaseResourceMappingError(
                        message="Redis name already exists locally; explicit binding or update is required"
                    )
                state = saved.get("registration_state")
                if state == RedisRegistrationState.BOUND:
                    resource_params(context, saved.get("resource_ref") or {}, kind="Redis")
                    return config
                if state != RedisRegistrationState.ACCEPTED:
                    raise BKBaseResourceMappingError(
                        message=f"Redis registration {config.pk} is {state}; automatic creation retry is disabled"
                    )
    except IntegrityError:
        raise BKBaseResourceMappingError(
            message="Concurrent Redis registration exists; do not resend creation"
        ) from None
    if created:
        try:
            receipt = create_resource_set(**params)
            if not isinstance(receipt, dict) or receipt.get("asset_name") != payload["asset_name"]:
                raise BKBaseResourceMappingError(message="Redis registration receipt does not match requested asset")
        except (APIRequestError, BKBaseResourceMappingError) as error:
            code = (
                str(getattr(error, "data", {}).get("code", "")) if isinstance(getattr(error, "data", {}), dict) else ""
            )
            state = RedisRegistrationState.REJECTED if code == "1553003" else RedisRegistrationState.UNKNOWN
            _save_redis_registration(config, {"registration_state": state, "error_code": code})
            raise BKBaseResourceMappingError(
                message=f"Redis registration {config.pk} is {state}; automatic creation retry is disabled"
            ) from None
        _save_redis_registration(config, {"registration_state": RedisRegistrationState.ACCEPTED})
    try:
        ref = _redis_asset_ref(context, payload["asset_name"])
    except (APIRequestError, BKBaseResourceMappingError):
        raise BKBaseResourceMappingError(
            message=(
                f"Redis registration {config.pk} accepted but Ref unverified; "
                "repeat the same create request to read detail only"
            )
        ) from None
    _save_redis_registration(config, {"registration_state": RedisRegistrationState.BOUND, "resource_ref": ref})
    return config


def update_resource_set(request_data=None, **params):
    """V4一期跳过已有Redis更新并保留原注册配置；V3透传原请求。"""
    if get_bkbase_version() == BKBaseVersion.V4:
        logger.warning("[BKBaseV4RedisUpdateSkipped] B05: Redis更新暂不支持，已跳过并保留原注册配置")
        return None
    return legacy_call("update_resource_set", request_data, **params)


def databus_storages_post(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("databus_storages_post", request_data, **params)


def databus_storages_put(request_data=None, **params):
    """V3原语；V4由该能力的完整流程替代。"""
    return legacy_call("databus_storages_put", request_data, **params)
