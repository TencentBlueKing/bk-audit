"""Plan the collector Clean updates for recovery of an existing Basic snapshot.

Use only bound resources and the actual Redis key order. The restore runner
owns remote writes and commits local links with the corresponding operation.
"""
from copy import deepcopy

from bk_resource import api
from django.db.models import Q

from services.web.bkbase import metadata, source
from services.web.bkbase.constants import CleanRole, CleanState
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.snapshot.join.base import JoinConfig
from services.web.databus.constants import JoinDataType
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot


def _identity(collector):
    fields = (
        "system_id",
        "collector_config_id",
        "collector_plugin_id",
        "bk_data_id",
        "bkbase_table_id",
        "processing_id",
        "etl_config",
        "etl_params",
        "fields",
        "custom_type",
        "source_platform",
        "is_deleted",
    )
    binding = collector.bkbase_v4_resources or {}
    if not isinstance(binding, dict):
        raise BKBaseResourceMappingError(message="Invalid Basic collector bindings")
    return source._replay_digest(
        {
            "inputs": {name: getattr(collector, name) for name in fields},
            "bindings": {
                name: binding.get(name)
                for name in (
                    "clean",
                    "clean_role",
                    "data_id",
                    "source_raw_data_id",
                    "result_table",
                    "result_table_id",
                    "pending_action",
                    "clean_pending_create",
                    "clean_delete_requested",
                )
            },
        }
    )


def _check_input(collector, step, logical_id, linked):
    expected = logical_id if linked else step["original_link"]
    if collector.join_data_rt != expected or _identity(collector) != step["input_digest"]:
        raise BKBaseResourceMappingError(message="Basic collector inputs or link changed")


def writer_digest(collector):
    """Identify the same collector writer independently of editable ETL rules."""
    binding = collector.bkbase_v4_resources or {}
    refs = {}
    for key in ("clean", "data_id", "result_table"):
        ref = binding.get(key) or {}
        if not isinstance(ref, dict):
            raise BKBaseResourceMappingError(message="Invalid Basic collector writer reference")
        refs[key] = {part: ref.get(part) for part in ("kind", "tenant", "namespace", "name")}
    return source._replay_digest(
        {
            "system_id": collector.system_id,
            "collector_config_id": collector.collector_config_id,
            "collector_plugin_id": collector.collector_plugin_id,
            "bk_data_id": collector.bk_data_id,
            "source_raw_data_id": source._replay_raw_id(binding.get("source_raw_data_id", collector.bk_data_id)),
            "bkbase_table_id": collector.bkbase_table_id,
            "processing_id": collector.processing_id,
            "role": binding.get("clean_role"),
            "refs": refs,
        }
    )


def check_completed(snapshot, plan, writes):
    """Validate persisted links without freezing ETL on completed collectors."""
    completed = {plan[key]["collector"]["id"]: plan[key] for key, write in writes.items() if write.get("linked")}
    for collector in CollectorConfig.objects.filter(pk__in=completed):
        step = completed[collector.pk]
        binding = collector.bkbase_v4_resources or {}
        if (
            collector.join_data_rt != snapshot.bkbase_table_id
            or writer_digest(collector) != step["writer_digest"]
            or binding.get("result_table_id", step["logical_output"]) != step["logical_output"]
        ):
            raise BKBaseResourceMappingError(message="Completed Basic collector identity or link changed")


def _configured(snapshot):
    return CollectorConfig.objects.filter(system_id=snapshot.system_id).filter(
        Q(bkbase_table_id__isnull=False) | Q(bkbase_v4_resources__clean__isnull=False)
    )


def _unlinked(snapshot):
    return _configured(snapshot).filter(Q(join_data_rt__isnull=True) | Q(join_data_rt=""))


def has_unlinked(snapshot, *, excluding=None):
    """Check the current collector set before committing Snapshot RUNNING."""
    if snapshot.join_data_type != JoinDataType.BASIC:
        return False
    query = _unlinked(snapshot)
    if excluding is not None:
        query = query.exclude(pk=excluding)
    return query.exists()


def collectors(snapshot, plan=None, writes=None, *, locked=False):
    """Select newly unlinked collectors, or recheck only the persisted plan."""
    if snapshot.join_data_type != JoinDataType.BASIC:
        return {}
    logical_id = snapshot.bkbase_table_id
    planned = {key: step["collector"] for key, step in (plan or {}).items() if "collector" in step}
    query = (
        _unlinked(snapshot)
        if plan is None
        else _configured(snapshot).filter(pk__in=[s["id"] for s in planned.values()])
    )
    query = query.order_by("pk")
    if locked:
        query = query.select_for_update()
    result = {}
    for collector in query:
        if len(logical_id) > CollectorConfig._meta.get_field("join_data_rt").max_length:
            raise BKBaseResourceMappingError(message="Basic ResultTable ID exceeds the collector link field")
        key = f"collector:{collector.pk}"
        if key in planned:
            step = planned[key]
            _check_input(collector, step, logical_id, (writes or {}).get(key, {}).get("linked"))
        else:
            step = {"id": collector.pk, "input_digest": _identity(collector), "original_link": collector.join_data_rt}
        result[key] = (collector, step)
    if plan is not None and result.keys() != planned.keys():
        raise BKBaseResourceMappingError(message="Basic restore collector set changed")
    return result


def join_config(logical_id, redis):
    """Use the Redis storage's join key order without changing the storage."""
    config = JoinConfig(logical_id).config
    join_fields = {item["target_field"]: item for item in config["join_on"]}
    spec = (redis or {}).get("spec", {})
    table = spec.get("tableInfo")
    fields = spec.get("taskFieldSetting")
    keys = fields.get("key_fields") if isinstance(fields, dict) else None
    if (
        not isinstance(keys, list)
        or len(keys) != len(join_fields)
        or not all(isinstance(key, str) and key in join_fields for key in keys)
        or len(set(keys)) != len(join_fields)
        or not isinstance(table, dict)
        or table.get("storage_type") not in (None, "join")
    ):
        raise BKBaseResourceMappingError(message="Basic restore requires the bound Redis join and its three keys")
    config["join_on"] = [join_fields[key] for key in keys]
    return config


def _reference_match(binding_key, ref):
    return Q(**{f"bkbase_v4_resources__{binding_key}__{key}": value for key, value in ref.items()})


def read(context, collector, get_resource):
    """Verify Clean identity, input ownership and the existing logical output."""
    binding = collector.bkbase_v4_resources or {}
    ref = source._replay_ref(context, binding.get("clean"), "Clean")
    data_id = source._replay_ref(context, binding.get("data_id"), "DataId")
    table_ref = source._replay_ref(context, binding.get("result_table"), "ResultTable")
    raw_id = source._replay_raw_id(collector.bk_data_id)
    role = binding.get("clean_role")
    if (
        role not in CleanRole.values
        or source._replay_raw_id(binding.get("source_raw_data_id", raw_id)) != raw_id
        or binding.get("pending_action") == "delete"
        or binding.get("clean_pending_create")
        or binding.get("clean_delete_requested")
    ):
        raise BKBaseResourceMappingError(message="Basic collector Clean ownership is incomplete")
    conflicts = _reference_match("clean", ref)
    if role == CleanRole.OWNER:
        conflicts |= _reference_match("result_table", table_ref) & Q(bkbase_v4_resources__clean_role=role)
    if (
        CollectorConfig.objects.filter(conflicts).exclude(pk=collector.pk).exists()
        or CollectorPlugin.objects.filter(conflicts).exists()
        or Snapshot.objects.filter(conflicts).exists()
    ):
        raise BKBaseResourceMappingError(message="Basic collector Clean has another local writer")
    clean = get_resource(context, ref, api.bk_base_v4.clean_get)
    table = get_resource(context, table_ref, api.bk_base_v4.result_table_resource_get)
    spec = clean["spec"]
    actual_ref, logical_id = metadata.result_table_identity(context, table)
    if actual_ref != table_ref:
        raise BKBaseResourceMappingError(message="Basic collector ResultTable reference changed")
    if (
        not isinstance(logical_id, str)
        or not logical_id
        or logical_id != spec.get("result_table_id")
        or logical_id != binding.get("result_table_id", logical_id)
        or collector.bkbase_table_id not in (None, "", logical_id)
        or spec.get("data_id") != data_id
        or source._replay_raw_id(spec.get("raw_data_id")) != raw_id
        or spec.get("result_table_source", "new") != {CleanRole.OWNER: "new", CleanRole.EXISTING: "existing"}[role]
        or (
            collector.processing_id
            and clean["metadata"].get("labels", {}).get("processing_id") != collector.processing_id
        )
    ):
        raise BKBaseResourceMappingError(message="Basic collector Clean input or output changed")
    if role == CleanRole.EXISTING:
        fields = table["spec"].get("fields")
        output_names = {field["field_name"] for field in JoinConfig.fields()}
        if not isinstance(fields, list) or not output_names.issubset(
            field.get("field_name") for field in fields if isinstance(field, dict)
        ):
            raise BKBaseResourceMappingError(message="Basic collector ResultTable is missing snapshot output fields")
    return clean


def _default_output(rule, fields):
    """Identify the standard same-name log extraction generated before a join exists."""
    name = rule["output_id"]
    operator = rule.get("operator")
    return (
        rule.keys() == {"input_id", "output_id", "operator"}
        and rule["input_id"] == "json_data"
        and isinstance(operator, dict)
        and operator.keys() <= {"type", "key_index", "output_type", "alias", "is_dimension"}
        and operator.get("type") == "assign"
        and operator.get("key_index") == name
        and operator.get("output_type") == fields[name]
    )


def desired(current, config):
    """Append the Basic association or align its order with the bound Redis keys."""
    result = deepcopy(current)
    spec = result["spec"]
    revision, deploy = spec.get("config_revision", 0), spec.get("deploy_revision", 0)
    if (
        type(revision) is not int
        or type(deploy) is not int
        or not 0 <= revision <= deploy
        or spec.get("desired_status") != CleanState.RUNNING
    ):
        raise BKBaseResourceMappingError(message="Basic collector Clean is stopped or has unpublished rules")
    joins = spec.get("join")
    if joins is None:
        joins = []
    rules = spec.get("rules")
    if (
        not isinstance(joins, list)
        or any(not isinstance(join, dict) or not isinstance(join.get("select"), list) for join in joins)
        or not isinstance(rules, list)
        or any(not isinstance(rule, dict) for rule in rules)
    ):
        raise BKBaseResourceMappingError(message="Invalid Basic collector Clean rules or joins")
    fields = {field["field_name"]: field["field_type"] for field in JoinConfig.fields()}
    existing = None
    for join in joins:
        if any(not isinstance(field, dict) for field in join["select"]):
            raise BKBaseResourceMappingError(message="Invalid Basic collector Clean output")
        if join.get("result_table_id") == config["result_table_id"]:
            on = join.get("join_on")
            if (
                existing is not None
                or not isinstance(on, list)
                or len(on) != len(config["join_on"])
                or not all(pair in on for pair in config["join_on"])
                or join["select"] != config["select"]
            ):
                raise BKBaseResourceMappingError(message="Basic collector has a conflicting join for the ResultTable")
            existing = join
        elif any(field.get("as") in fields for field in join["select"]):
            raise BKBaseResourceMappingError(message="Basic collector has a join to another snapshot")
    rules_to_keep = []
    for rule in rules:
        if rule.get("output_id") not in fields:
            rules_to_keep.append(rule)
        elif not _default_output(rule, fields):
            raise BKBaseResourceMappingError(message="Basic collector has a conflicting snapshot output rule")
    if existing is None:
        spec.update(rules=rules_to_keep, join=[*joins, config])
    elif existing["join_on"] == config["join_on"] and len(rules_to_keep) == len(rules):
        return result
    else:
        existing["join_on"] = config["join_on"]
        spec["rules"] = rules_to_keep
    spec.update(config_revision=deploy + 1, deploy_revision=deploy + 1)
    return result


def lock_input(snapshot, step, *, confirm):
    """Recheck the collector under a row lock and optionally commit its association."""
    collector = CollectorConfig.objects.filter(pk=step["id"]).select_for_update().first()
    if collector is None:
        raise BKBaseResourceMappingError(message="Basic collector disappeared during restore")
    _check_input(collector, step, snapshot.bkbase_table_id, linked=False)
    if confirm:
        collector.join_data_rt = snapshot.bkbase_table_id
        collector.save(update_fields=["join_data_rt"])
