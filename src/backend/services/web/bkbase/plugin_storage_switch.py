"""Advance an explicit default-cluster switch for a bound log plugin.

The namespace default records the requested target. Each affected plugin keeps
its own write claim and remains marked until DataStorage and BKLog converge.
"""

import uuid
from copy import deepcopy

from bk_resource import api, resource
from bk_resource.exceptions import APIRequestError
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.exceptions import StorageChanging
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.bkbase import source, storage
from services.web.bkbase.common import (
    get_bkbase_context,
    operation_result,
    resource_lock,
    resource_params,
)
from services.web.bkbase.constants import (
    BKBASE_V4_STORAGE_CLUSTER_KINDS,
    CleanRole,
    TaskState,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector_plugin.serializers import (
    UpdatePluginRequestSerializer,
)
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    ClusterMode,
    SnapShotStorageChoices,
)
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot

SWITCH_KEY = "storage_cluster_switch"
UPDATE_KEY = "storage_cluster_update"
_CONFIG_KEYS = {
    ClusterMode.MAIN: DEFAULT_STORAGE_CONFIG_KEY,
    ClusterMode.REPLICA: DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
}
_STORAGE_TYPES = {ClusterMode.MAIN: "es", ClusterMode.REPLICA: "doris"}
_UNSET_ETL_CONFIG = object()


def _valid_bklog_etl_config(value):
    """认领前复用真实请求字段校验，不把空值替换成默认清洗类型。"""
    try:
        UpdatePluginRequestSerializer().fields["etl_config"].run_validation(value)
    except ValidationError:
        return False
    return True


def _default(namespace, purpose):
    return GlobalMetaConfig.get(
        _CONFIG_KEYS[purpose], config_level=ConfigLevelChoices.NAMESPACE, instance_key=namespace, default=None
    )


def _identifier(purpose, config):
    if purpose == ClusterMode.REPLICA:
        return config.get("bkbase_cluster_id") if isinstance(config, dict) else None
    return str(config) if config is not None else None


def reserve(plugins, *, namespace, purpose, target):
    """Record affected plugin intents while the caller commits the namespace default."""
    operation_id = uuid.uuid4().hex
    old = _identifier(purpose, _default(namespace, purpose))
    new = _identifier(purpose, target)
    for plugin in plugins.select_for_update().order_by("pk"):
        binding = plugin.bkbase_v4_resources or {}
        previous = binding.get(SWITCH_KEY)
        if previous and not previous.get("failed"):
            raise StorageChanging()
        bound = (binding.get("storages") or {}).get(purpose)
        configured = plugin.has_storage if purpose == ClusterMode.MAIN else plugin.has_replica_storage
        if bound or configured:
            previous_old = previous["old"] if previous and previous["purpose"] == purpose and old == new else old
            binding[SWITCH_KEY] = {
                "operation_id": operation_id,
                "purpose": purpose,
                "old": previous_old,
                "target": new,
            }
        else:
            # A plugin without an existing task still uses its normal first-time setup.
            binding.pop(SWITCH_KEY, None)
            binding[UPDATE_KEY] = {"operation_id": operation_id}
        plugin.bkbase_v4_resources = binding
        plugin.storage_changed = True
        plugin.save(update_fields=["bkbase_v4_resources", "storage_changed"])


@transaction.atomic
def mark_config_update(plugins):
    """Record a successful storage edit separately from a pending cluster move."""
    operation_id = uuid.uuid4().hex
    for plugin in plugins.select_for_update().order_by("pk"):
        binding = plugin.bkbase_v4_resources or {}
        binding[UPDATE_KEY] = {"operation_id": operation_id}
        plugin.bkbase_v4_resources = binding
        plugin.storage_changed = True
        plugin.save(update_fields=["bkbase_v4_resources", "storage_changed"])


def _clusters(context, plugin, purpose, *keys):
    if purpose == ClusterMode.MAIN:
        rows = resource.databus.storage.storage_list(namespace=plugin.namespace)
        ids = {}
        for row in rows:
            cluster = row["cluster_config"]
            number = str(cluster["cluster_id"])
            if number in keys:
                if number in ids:
                    raise BKBaseResourceMappingError(message="Ambiguous BKLog storage cluster mapping")
                ids[number] = cluster.get("custom_option", {}).get("bkbase_cluster_id")
        keys = tuple(ids.get(key) for key in keys)
    if not all(keys):
        raise BKBaseResourceMappingError(message="Explicit plugin storage cluster mappings are required")
    return tuple(
        storage.resolve_storage_cluster(
            context, audit_namespace=plugin.namespace, storage_type=_STORAGE_TYPES[purpose], legacy_cluster_id=key
        )
        for key in keys
    )


def _owner_inputs(plugin, purpose):
    binding = plugin.bkbase_v4_resources or {}
    return {
        "namespace": plugin.namespace,
        "collector_plugin_id": plugin.collector_plugin_id,
        "role": binding.get("clean_role"),
        "result_table": binding.get("result_table"),
        "logical_id": binding.get("result_table_id"),
        "storage": (binding.get("storages") or {}).get(purpose),
    }


def _save(plugin, operation, inputs, patch=None, *, done=False, expected_etl_config=_UNSET_ETL_CONFIG):
    """Compare the activation generation and owner bindings before writing back."""
    with transaction.atomic():
        latest = CollectorPlugin.objects.select_for_update().get(pk=plugin.pk)
        binding = latest.bkbase_v4_resources or {}
        purpose = operation["purpose"]
        if (
            not latest.storage_changed
            or binding.get(SWITCH_KEY) != operation
            or _owner_inputs(latest, purpose) != inputs
            or _identifier(purpose, _default(latest.namespace, purpose)) != operation["target"]
            or (expected_etl_config is not _UNSET_ETL_CONFIG and latest.etl_config != expected_etl_config)
        ):
            return None
        updated = {**operation, **(patch or {})}
        if done:
            binding.pop(SWITCH_KEY)
            if binding.get(UPDATE_KEY) == operation.get("covered_update"):
                binding.pop(UPDATE_KEY, None)
            latest.storage_changed = bool(binding.get(UPDATE_KEY))
        else:
            binding[SWITCH_KEY] = updated
        latest.bkbase_v4_resources = binding
        latest.save(update_fields=["bkbase_v4_resources", "storage_changed"])
        return updated


def _digest(value):
    metadata = value["metadata"]
    annotations = {k: v for k, v in metadata.get("annotations", {}).items() if k != "bk_username"}
    return source._replay_digest([value["spec"], metadata.get("labels", {}), annotations])


def _read(context, plugin, inputs, purpose):
    ref = source._replay_ref(context, inputs["storage"], "DataStorage")
    table = source._replay_ref(context, inputs["result_table"], "ResultTable")
    if inputs["role"] != CleanRole.OWNER or not inputs["logical_id"]:
        raise BKBaseResourceMappingError(message="Plugin ResultTable ownership is missing (C08)")
    targets = Q()
    for key in (ClusterMode.MAIN, ClusterMode.REPLICA, *SnapShotStorageChoices.values):
        targets |= Q(**{f"bkbase_v4_resources__storages__{key}__{part}": value for part, value in ref.items()})
    if (
        CollectorPlugin.objects.filter(targets).exclude(pk=plugin.pk).exists()
        or CollectorConfig.objects.filter(targets).exists()
        or Snapshot.objects.filter(targets).exists()
        or sum(
            all(isinstance(candidate, dict) and candidate.get(k) == v for k, v in ref.items())
            for candidate in (plugin.bkbase_v4_resources.get("storages") or {}).values()
        )
        != 1
    ):
        raise BKBaseResourceMappingError(message="Plugin storage target has another local writer or role")
    actual_table = api.bk_base_v4.result_table_resource_get(namespace=table["namespace"], name=table["name"])
    if (
        source._binding_resource_ref(context, actual_table, "ResultTable") != table
        or actual_table["metadata"].get("labels", {}).get("result_table_id") != inputs["logical_id"]
    ):
        raise BKBaseResourceMappingError(message="Plugin ResultTable identity changed")
    current = api.bk_base_v4.data_storage_get(**resource_params(context, ref))
    if (
        source._binding_resource_ref(context, current, "DataStorage") != ref
        or not isinstance(current.get("status"), dict)
        or (current["spec"].get("tableInfo") or {}).get("source") != table
        or any(
            current["metadata"].get(key, {}).get("result_table_id") not in (None, inputs["logical_id"])
            for key in ("labels", "annotations")
        )
    ):
        raise BKBaseResourceMappingError(message="Plugin DataStorage identity or source changed")
    cluster = source._replay_ref(
        context, current["spec"]["tableInfo"].get("storage"), BKBASE_V4_STORAGE_CLUSTER_KINDS[_STORAGE_TYPES[purpose]]
    )
    return current, cluster


def _publish(context, plugin, operation, inputs, ref, current, target):
    desired = deepcopy(current)
    desired["spec"]["tableInfo"]["storage"] = target
    write = {"inputs": inputs, "baseline": _digest(current), "target": _digest(desired)}
    claimed = _save(plugin, operation, inputs, {"write": write})
    if not claimed:
        return
    try:
        result = api.bk_base_v4.data_storage_update(
            **resource_params(context, ref), metadata=desired["metadata"], spec=desired["spec"], status=None
        )
    except APIRequestError:
        return
    if (
        isinstance(result, dict)
        and isinstance(result.get("status"), dict)
        and isinstance(result.get("metadata"), dict)
        and result["status"].get("phase") == "Pending"
        and all(result["metadata"].get(k) == ref[k] for k in ("tenant", "namespace", "name"))
    ):
        _save(plugin, claimed, inputs, {"write": {**write, "history_id": result["status"].get("history_id")}})


def _sync(plugin, operation, inputs, update_plugin):
    if operation.get("bklog_started"):
        return
    checked_config = plugin.etl_config
    if not _valid_bklog_etl_config(checked_config):
        _save(
            plugin,
            operation,
            inputs,
            {"message": "Invalid local Plugin etl_config"},
            expected_etl_config=checked_config,
        )
        return
    claimed = _save(
        plugin,
        operation,
        inputs,
        {"bklog_started": True, "covered_update": (plugin.bkbase_v4_resources or {}).get(UPDATE_KEY)},
        expected_etl_config=checked_config,
    )
    if not claimed:
        return
    try:
        update_plugin(plugin)
    except APIRequestError:
        _save(plugin, claimed, inputs, {"message": "BKLog synchronization outcome unknown"})
        return
    _save(plugin, claimed, inputs, done=True)


def _config_inputs(plugin):
    binding = plugin.bkbase_v4_resources or {}
    storages = binding.get("storages") or {}
    return {
        purpose: (
            _owner_inputs(plugin, purpose),
            _identifier(purpose, _default(plugin.namespace, purpose)),
        )
        for purpose, configured in (
            (ClusterMode.MAIN, plugin.has_storage),
            (ClusterMode.REPLICA, plugin.has_replica_storage),
        )
        if configured or storages.get(purpose)
    }


def _save_config_update(plugin, operation, inputs, updated, *, expected_etl_config=_UNSET_ETL_CONFIG):
    with transaction.atomic():
        latest = CollectorPlugin.objects.select_for_update().get(pk=plugin.pk)
        binding = latest.bkbase_v4_resources or {}
        if (
            not latest.storage_changed
            or binding.get(SWITCH_KEY)
            or binding.get(UPDATE_KEY) != operation
            or (inputs is not None and _config_inputs(latest) != inputs)
            or (expected_etl_config is not _UNSET_ETL_CONFIG and latest.etl_config != expected_etl_config)
        ):
            return False
        if updated is None:
            binding.pop(UPDATE_KEY)
            latest.storage_changed = False
        else:
            binding[UPDATE_KEY] = updated
        latest.bkbase_v4_resources = binding
        latest.save(update_fields=["bkbase_v4_resources", "storage_changed"])
        return True


def advance_config_update(plugin, update_plugin):
    """Sync configuration once the bound tasks already match their defaults."""
    inputs = _config_inputs(plugin)
    operation = (plugin.bkbase_v4_resources or {}).get(UPDATE_KEY)
    if operation is None:
        # A pre-upgrade flag provides no authority to change the live target.
        operation = {"operation_id": uuid.uuid4().hex}
        if not _save_config_update(plugin, None, inputs, operation):
            return
    if operation.get("bklog_started") and not operation.get("bklog_confirmed"):
        return
    try:
        for purpose, (owner, key) in inputs.items():
            if not owner["storage"]:
                raise BKBaseResourceMappingError(message="Missing existing plugin storage binding (C08)")
            context = get_bkbase_context()
            current, cluster = _read(context, plugin, owner, purpose)
            (target,) = _clusters(context, plugin, purpose, key)
            if cluster != target:
                raise BKBaseResourceMappingError(
                    message="Plugin storage differs from its default without switch intent"
                )
            if operation_result(current, owner["storage"], "observe")["task_state"] != TaskState.RUNNING:
                return
    except BKBaseResourceMappingError as error:
        message = str(error.message)
        if operation.get("message") != message:
            _save_config_update(plugin, operation, inputs, {**operation, "message": message})
        return
    if operation.get("bklog_confirmed"):
        _save_config_update(plugin, operation, inputs, None)
        return
    checked_config = plugin.etl_config
    if not _valid_bklog_etl_config(checked_config):
        _save_config_update(
            plugin,
            operation,
            inputs,
            {**operation, "message": "Invalid local Plugin etl_config"},
            expected_etl_config=checked_config,
        )
        return
    claimed = {**operation, "bklog_started": True}
    if not _save_config_update(plugin, operation, inputs, claimed, expected_etl_config=checked_config):
        return
    try:
        update_plugin(plugin)
    except APIRequestError:
        _save_config_update(plugin, claimed, inputs, {**claimed, "message": "BKLog synchronization outcome unknown"})
        return
    if not _save_config_update(plugin, claimed, inputs, None):
        # The original request succeeded, but the asynchronously created bindings
        # may already be visible. Check them on the next pass without another write.
        _save_config_update(plugin, claimed, None, {**claimed, "bklog_confirmed": True})


def advance(plugin, update_plugin):
    """Advance a single target or wait for an independently observed result."""
    binding = plugin.bkbase_v4_resources or {}
    operation = binding[SWITCH_KEY]
    if operation.get("failed"):
        return
    purpose = operation["purpose"]
    inputs = _owner_inputs(plugin, purpose)
    write = operation.get("write")
    if write and write["inputs"] != inputs:
        _save(plugin, operation, inputs, {"message": "Plugin storage binding changed after a write was claimed"})
        return
    if not inputs["storage"]:
        _save(plugin, operation, inputs, {"failed": True, "message": "Missing existing plugin storage binding (C08)"})
        return
    context = get_bkbase_context()
    ref = source._replay_ref(context, inputs["storage"], "DataStorage")
    with resource_lock(context, ref):
        plugin.refresh_from_db()
        if (
            not plugin.storage_changed
            or plugin.bkbase_v4_resources.get(SWITCH_KEY) != operation
            or _owner_inputs(plugin, purpose) != inputs
            or _identifier(purpose, _default(plugin.namespace, purpose)) != operation["target"]
        ):
            return
        try:
            current, cluster = _read(context, plugin, inputs, purpose)
            state = operation_result(current, ref, "observe")["task_state"]
            if write:
                digest = _digest(current)
                if digest not in (write["baseline"], write["target"]):
                    raise BKBaseResourceMappingError(message="Plugin storage configuration drifted")
                history = write.get("history_id")
                if digest != write["target"] or (
                    history is not None and current["status"].get("history_id") != history
                ):
                    return
                if state == TaskState.FAILED:
                    _save(plugin, operation, inputs, {"failed": True, "message": "Plugin storage target failed"})
                elif state == TaskState.RUNNING:
                    _sync(plugin, operation, inputs, update_plugin)
                return
            previous, target = _clusters(context, plugin, purpose, operation["old"], operation["target"])
            if cluster == target and state == TaskState.RUNNING:
                _sync(plugin, operation, inputs, update_plugin)
            elif cluster == previous and state == TaskState.RUNNING:
                _publish(context, plugin, operation, inputs, ref, current, target)
            else:
                raise BKBaseResourceMappingError(message="Plugin storage does not match the previous ready cluster")
        except BKBaseResourceMappingError as error:
            if not operation.get("write") and not operation.get("bklog_started"):
                _save(plugin, operation, inputs, {"failed": True, "message": str(error.message)})
            else:
                _save(plugin, operation, inputs, {"message": str(error.message)})
