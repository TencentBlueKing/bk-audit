"""Verify explicitly mapped IAM system snapshot resources and publish their Join identity.

The existing GlobalMetaConfig row keeps V3 configuration and independently scoped V4 bindings.
Remote observations happen outside the transaction that publishes a binding or its readiness.
"""
import re

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from django.conf import settings
from django.db import transaction

from apps.meta.constants import GLOBAL_CONFIG_LEVEL_INSTANCE, ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.bkbase import metadata as bkbase_metadata
from services.web.bkbase import source as bkbase_source
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    get_resource_or_none,
    operation_result,
)
from services.web.bkbase.constants import (
    BKBaseVersion,
    CleanRole,
    TableBindingKind,
    TaskState,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import (
    ACTION_DATA_CONFIG_KEY,
    ACTION_DATA_RT_KEY,
    RESOURCE_TYPE_DATA_CONFIG_KEY,
    RESOURCE_TYPE_DATA_RT_KEY,
    USER_INFO_DATA_CONFIG_KEY,
    USER_INFO_DATA_RT_KEY,
)

SYSTEM_SNAPSHOT_KEYS = {
    "action": (ACTION_DATA_CONFIG_KEY, ACTION_DATA_RT_KEY),
    "resource_type": (RESOURCE_TYPE_DATA_CONFIG_KEY, RESOURCE_TYPE_DATA_RT_KEY),
    "user": (USER_INFO_DATA_CONFIG_KEY, USER_INFO_DATA_RT_KEY),
}
V4_CONFIG_KEY = "bkbase_v4"


def _system_context():
    context = get_bkbase_context()
    if not all(isinstance(context[key], str) and context[key].strip() for key in ("tenant", "namespace")):
        raise BKBaseResourceMappingError(message="IAM V4 snapshot requires a configured tenant and project")
    return context


def _mapping(value):
    if not isinstance(value, dict):
        raise BKBaseResourceMappingError(message="Invalid IAM snapshot configuration")
    return value


def _scoped_binding(config, context):
    version = _mapping(config.get(V4_CONFIG_KEY, {}))
    tenant = _mapping(version.get(context["tenant"], {}))
    return tenant.get(context["namespace"])


def _read_config(config_key):
    value = GlobalMetaConfig.get(config_key, default={})
    return _mapping({} if value is None else value)


def _locked_config(config_key, *, create=True):
    queryset = GlobalMetaConfig.objects.select_for_update()
    keys = {
        "config_key": config_key,
        "config_level": ConfigLevelChoices.GLOBAL.value,
        "instance_key": GLOBAL_CONFIG_LEVEL_INSTANCE,
    }
    if not create:
        return queryset.filter(**keys).first()
    config, _ = queryset.get_or_create(**keys)
    return config


def _store_binding(config, root, context, binding):
    versions = root.setdefault(V4_CONFIG_KEY, {})
    versions.setdefault(context["tenant"], {})[context["namespace"]] = binding
    config.config_value = root
    config.save()


def save_v3_config(config_key, value):
    """Save the original V3 snapshot fields while keeping any V4 scopes on the same row."""
    with transaction.atomic():
        config = _locked_config(config_key)
        old = config.config_value
        if isinstance(old, dict) and V4_CONFIG_KEY in old:
            value = {**value, V4_CONFIG_KEY: old[V4_CONFIG_KEY]}
        config.config_value = value
        config.save()


def _explicit_ref(context, value, kind, *, in_project=True):
    if not isinstance(value, dict) or any(
        not isinstance(value.get(key), str) or not value[key].strip() for key in ("tenant", "namespace", "name")
    ):
        raise BKBaseResourceMappingError(message=f"IAM V4 snapshot requires an explicit {kind} reference")
    ref = bkbase_source._replay_ref(context, value, kind)
    if in_project and ref["namespace"] != context["namespace"]:
        raise BKBaseResourceMappingError(message=f"IAM V4 snapshot {kind} is outside the configured project")
    return ref


def _logical_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+_[A-Za-z0-9_]+", value):
        raise BKBaseResourceMappingError(message="Invalid IAM V4 snapshot logical result table ID")
    return value


def _normalize_binding(resource_type, context, value):
    binding = _mapping(value)
    if binding.get("snapshot_type") != resource_type:
        raise BKBaseResourceMappingError(message=f"IAM V4 migration binding must declare snapshot_type={resource_type}")
    return {
        "snapshot_type": resource_type,
        "data_source": _explicit_ref(context, binding.get("data_source"), "DataSource"),
        "data_id": _explicit_ref(context, binding.get("data_id"), "DataId"),
        "source_raw_data_id": bkbase_source._replay_raw_id(binding.get("source_raw_data_id")),
        "clean": _explicit_ref(context, binding.get("clean"), "Clean"),
        "result_table_id": _logical_id(binding.get("result_table_id")),
        "result_table": _explicit_ref(context, binding.get("result_table"), "ResultTable"),
        "storages": {"redis": _explicit_ref(context, _mapping(binding.get("storages")).get("redis"), "DataStorage")},
        "redis": _explicit_ref(context, binding.get("redis"), "Redis", in_project=False),
    }


def _running_resource(context, getter, ref):
    kind = ref["kind"]
    resource = get_resource_or_none(getter, tenant=ref["tenant"], namespace=ref["namespace"], name=ref["name"])
    if resource is None:
        return None
    if bkbase_source._binding_resource_ref(context, resource, kind) != ref:
        raise BKBaseResourceMappingError(message=f"IAM V4 snapshot {kind} identity mismatch")
    if resource.get("status") is not None:
        _mapping(resource["status"])
    state = operation_result(resource, ref, "get")["task_state"]
    if state in (TaskState.FAILED, TaskState.STOPPED):
        raise BKBaseResourceMappingError(message=f"IAM V4 snapshot {kind} is {state}")
    return resource if state == TaskState.RUNNING else None


def _matches_nested_ref(value, ref):
    # The containing resource is tenant-scoped. Nested refs may omit tenant in the V4 protocol.
    return (
        isinstance(value, dict)
        and all(value.get(key) == ref[key] for key in ("kind", "namespace", "name"))
        and ("tenant" not in value or value["tenant"] == ref["tenant"])
    )


def _redis_keys(resource_type, keys):
    expected = {"id"} if resource_type == "user" else {"id", "system_id"}
    if (
        not isinstance(keys, list)
        or len(keys) != len(expected)
        or not all(isinstance(key, str) and key in expected for key in keys)
        or len(set(keys)) != len(expected)
    ):
        raise BKBaseResourceMappingError(message="IAM V4 snapshot Redis Join key fields mismatch")
    return keys


def _verified_redis_binding(resource, table, redis):
    """Return the exact ready RedisBinding reference from ResultTableInfo."""
    status = resource.get("status")
    related = status.get("related") if isinstance(status, dict) and status.get("phase") == "Ok" else None
    if not isinstance(related, list):
        return None
    matches = []
    for item in related:
        if not isinstance(item, dict) or item.get("kind") != TableBindingKind.REDIS:
            continue
        spec = item.get("spec")
        if (
            isinstance(spec, dict)
            and _matches_nested_ref(spec.get("data"), table)
            and _matches_nested_ref(spec.get("storage"), redis)
        ):
            matches.append(item)
    if len(matches) != 1:
        return None
    metadata, state = matches[0].get("metadata"), matches[0].get("status")
    if (
        not isinstance(metadata, dict)
        or metadata.get("tenant") != table["tenant"]
        or any(not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in ("namespace", "name"))
        or not isinstance(state, dict)
        or state.get("phase") != "Ok"
    ):
        return None
    ref = {"kind": TableBindingKind.REDIS, **{key: metadata[key] for key in ("tenant", "namespace", "name")}}
    targets = state.get("related")
    if not isinstance(targets, list) or len(targets) != 1 or not isinstance(targets[0], dict):
        return None
    target = targets[0]
    metadata, state = target.get("metadata"), target.get("status")
    if (
        target.get("kind") != redis["kind"]
        or not isinstance(metadata, dict)
        or any(metadata.get(key) != redis[key] for key in ("tenant", "namespace", "name"))
        or not isinstance(state, dict)
        or state.get("phase") != "Ok"
    ):
        return None
    return ref


def _result_table_info(sdk, context, logical_id):
    try:
        return get_resource_or_none(sdk.result_table_info, tenant=context["tenant"], result_table_id=logical_id)
    except APIRequestError as error:
        if str(error.data.get("code")) == "1558025":
            # This code also covers an unrelated binding target; it does not establish that this Join is gone.
            error.message = "IAM V4 ResultTableInfo 1558025: result table or a binding target is missing"
        raise


def _observe_binding(resource_type, context, binding):
    sdk = api.bk_base_v4
    source = _running_resource(context, sdk.data_source_get, binding["data_source"])
    if source is None:
        return {"ready": False, "waiting_for": "DataSource"}
    report = _mapping(source["spec"].get("report_config"))
    raw_id = binding["source_raw_data_id"]
    source_binding = bkbase_source._source_binding(context, source, raw_id)
    if (
        report.get("type") != "rest_api"
        or report.get("http_mode") != "PULL"
        or source_binding["data_id"] != binding["data_id"]
    ):
        raise BKBaseResourceMappingError(message="IAM V4 snapshot DataSource does not match the mapped PULL and DataId")

    clean = _running_resource(context, sdk.clean_get, binding["clean"])
    if clean is None:
        return {"ready": False, "waiting_for": "Clean"}
    spec = clean["spec"]
    source_role = spec.get("result_table_source", "new")
    roles = {"new": CleanRole.OWNER, "existing": CleanRole.EXISTING}
    role = roles.get(source_role) if isinstance(source_role, str) else None
    if (
        role is None
        or not _matches_nested_ref(spec.get("data_id"), binding["data_id"])
        or bkbase_source._replay_raw_id(spec.get("raw_data_id")) != raw_id
        or spec.get("result_table_id") != binding["result_table_id"]
    ):
        raise BKBaseResourceMappingError(message="IAM V4 snapshot Clean input or output does not match the mapping")
    result_table = _result_table_info(sdk, context, binding["result_table_id"])
    if result_table is None:
        return {"ready": False, "waiting_for": "ResultTable"}
    table, logical_id = bkbase_metadata.result_table_identity(context, result_table)
    if table != binding["result_table"] or logical_id != binding["result_table_id"]:
        raise BKBaseResourceMappingError(message="IAM V4 snapshot logical result table resolves to another resource")

    storage = _running_resource(context, sdk.data_storage_get, binding["storages"]["redis"])
    if storage is None:
        return {"ready": False, "waiting_for": "DataStorage"}
    target = _mapping(storage["spec"].get("tableInfo"))
    if (
        not _matches_nested_ref(target.get("source"), table)
        or not _matches_nested_ref(target.get("storage"), binding["redis"])
        or target.get("storage_type") not in (None, "join")
    ):
        raise BKBaseResourceMappingError(message="IAM V4 snapshot Redis storage does not match the mapped Join")
    keys = _redis_keys(resource_type, _mapping(storage["spec"].get("taskFieldSetting")).get("key_fields"))
    redis_binding = _verified_redis_binding(result_table, table, binding["redis"])
    if redis_binding is None:
        return {"ready": False, "waiting_for": "RedisBinding"}
    return {"ready": True, "clean_role": role, "redis_binding": redis_binding, "redis_key_fields": list(keys)}


def _start_verification(config_key, context, binding, *, only_if_bound=False):
    with transaction.atomic():
        config = _locked_config(config_key, create=False)
        root = _mapping(config.config_value) if config is not None and config.config_value is not None else {}
        current = _scoped_binding(root, context)
        if current is None and only_if_bound:
            return None
        if current is None or _normalize_binding(binding["snapshot_type"], context, current) != binding:
            raise BKBaseResourceMappingError(message="IAM V4 snapshot already has a different migration binding")
        sequence = current.get("verification_started", 0) + 1
        _store_binding(config, root, context, {**current, "verification_started": sequence})
        return sequence


def _apply_observation(config_key, context, binding, observation, sequence):
    """Apply a definitive observation. False signals a competing first import."""
    with transaction.atomic():
        config = _locked_config(config_key)
        root = _mapping({} if config.config_value is None else config.config_value)
        current = _scoped_binding(root, context)
        saved = {**binding, **observation}
        if isinstance(current, dict) and current.get("creation"):
            saved["creation"] = current["creation"]
        if sequence is None:
            if current is not None:
                return False
        else:
            if current is None or _normalize_binding(binding["snapshot_type"], context, current) != binding:
                raise BKBaseResourceMappingError(message="IAM V4 snapshot binding changed while verifying; retry")
            started = current.get("verification_started", 0)
            if not current.get("verification_applied", 0) < sequence <= started:
                raise BKBaseResourceMappingError(message="IAM V4 snapshot observation was superseded; retry")
            saved.update(verification_started=started, verification_applied=sequence)
        _store_binding(config, root, context, saved)
        return True


def _verify_bound_snapshot(resource_type, config_key, context, binding, sequence):
    try:
        observation = _observe_binding(resource_type, context, binding)
    except BKBaseResourceMappingError:
        _apply_observation(
            config_key, context, binding, {"ready": False, "waiting_for": "verification failed"}, sequence
        )
        raise
    _apply_observation(config_key, context, binding, observation, sequence)
    return observation.get("waiting_for")


def ensure_system_snapshot(resource_type, migration_binding=None):
    """Recheck the mapped resources and return the outstanding phase, if any."""
    config_key, _ = SYSTEM_SNAPSHOT_KEYS[resource_type]
    context = _system_context()
    current = _scoped_binding(_read_config(config_key), context)
    if current is None and migration_binding is None:
        return "migration binding"
    binding = _normalize_binding(resource_type, context, current if migration_binding is None else migration_binding)
    if current is not None:
        sequence = _start_verification(config_key, context, binding)
        return _verify_bound_snapshot(resource_type, config_key, context, binding, sequence)

    try:
        observation = _observe_binding(resource_type, context, binding)
    except BKBaseResourceMappingError:
        sequence = _start_verification(config_key, context, binding, only_if_bound=True)
        if sequence is None:
            raise
    else:
        if _apply_observation(config_key, context, binding, observation, sequence=None):
            return observation.get("waiting_for")
        sequence = _start_verification(config_key, context, binding)
    # Another import won the empty-state CAS. Use fresh GETs for the newly reserved sequence.
    return _verify_bound_snapshot(resource_type, config_key, context, binding, sequence)


def system_snapshot_table(resource_type):
    """Read the logical Join table and V4 Redis key order for the current version and scope."""
    config_key, rt_key = SYSTEM_SNAPSHOT_KEYS[resource_type]
    if get_bkbase_version() == BKBaseVersion.V3:
        legacy = GlobalMetaConfig.get(rt_key, default=None)
        return (legacy, None) if legacy else None
    if resource_type == "user" and not settings.SNAPSHOT_USERINFO_RESOURCE_URL:
        return None
    context = _system_context()
    binding = _scoped_binding(_read_config(config_key), context)
    if (
        not isinstance(binding, dict)
        or binding.get("snapshot_type") != resource_type
        or binding.get("ready") is not True
        or not binding.get("redis_binding")
    ):
        raise BKBaseResourceMappingError(message=f"IAM V4 {resource_type} snapshot is not ready for ETL Join")
    _explicit_ref(context, binding["redis_binding"], TableBindingKind.REDIS, in_project=False)
    return _logical_id(binding.get("result_table_id")), _redis_keys(resource_type, binding.get("redis_key_fields"))
