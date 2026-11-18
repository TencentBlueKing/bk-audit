"""Offline, read-only BKBase V4 release evidence checks; never imports Django.

PASS refers only to the supplied configuration snapshots and GET receipts. It is
not an online platform check, a database backup, or product acceptance.
"""

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

MAX_BYTES = 512 * 1024 * 1024
REF_KEYS = {"kind", "tenant", "namespace", "name"}
KINDS = {"data_source": "DataSource", "data_id": "DataId", "clean": "Clean", "result_table": "ResultTable"}
ROUTES = {
    "Flow": "/v4/tenants/{tenant}/namespaces/{namespace}/flows/{name}/",
    "Clean": "/v4/tenants/{tenant}/namespaces/{namespace}/cleans/{name}/",
    "DataSource": "/v4/tenants/{tenant}/namespaces/{namespace}/datasources/{name}/",
    "DataStorage": "/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/{name}/",
    "DataId": "/v4/namespaces/{namespace}/dataids/{name}/",
    "ResultTable": "/v4/namespaces/{namespace}/resulttables/{name}/",
}
OWNER_MODELS = {
    "flow": "strategy_v2.strategy",
    "plugin": "databus.collectorplugin",
    "event_plugin": "databus.collectorplugin",
    "collector": "databus.collectorconfig",
    "snapshot": "databus.snapshot",
    "iam": "meta.globalmetaconfig",
}
REQUIRED_MODELS = {
    "meta.globalmetaconfig",
    "databus.collectorplugin",
    "databus.collectorconfig",
    "databus.snapshot",
    "strategy_v2.strategy",
    "strategy_v2.linktable",
}


def hash_bytes(value):
    """Return a SHA256 without retaining or reporting source contents."""
    return hashlib.sha256(value).hexdigest()


def digest(value):
    """Canonical JSON SHA used for receipt bodies and redacted identifiers."""
    return hash_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def read_json(path):
    """Read bounded regular JSON; reject links and duplicate object keys."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("invalid input file")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    return json.loads(path.read_bytes(), object_pairs_hook=pairs)


def identity(row):
    """Stable fixture model and primary-key identity, independent of row order."""
    return row["model"], digest(row["pk"])


def read_bundle(root):
    """Verify the existing native fixture bundle format and all declared counts."""
    root = Path(root)
    manifest = read_json(root / "manifest.json")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("complete") is not True
        or manifest.get("fixture") != "business.json"
    ):
        raise ValueError("invalid bundle manifest")
    rows = read_json(root / "business.json")
    data = (root / "business.json").read_bytes()
    if len(data) != manifest.get("size_bytes") or hash_bytes(data) != manifest.get("sha256"):
        raise ValueError("fixture integrity mismatch")
    counts = manifest.get("model_counts")
    if (
        not isinstance(counts, dict)
        or not counts
        or not isinstance(rows, list)
        or any(type(n) is not int or n < 0 for n in counts.values())
    ):
        raise ValueError("invalid fixture counts")
    seen, actual = set(), Counter()
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("model") not in counts
            or row.get("pk") is None
            or not isinstance(row.get("fields"), dict)
        ):
            raise ValueError("invalid fixture row")
        key = identity(row)
        if key in seen:
            raise ValueError("duplicate fixture identity")
        seen.add(key)
        actual[row["model"]] += 1
    if {model: actual[model] for model in counts} != counts:
        raise ValueError("fixture count mismatch")
    return {"manifest": manifest, "rows": rows}


def write_private(path, value):
    """Create a new 0600 evidence file; never truncate existing evidence."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def timestamp(value):
    """Require an explicit timezone; local naive timestamps are ambiguous."""
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result


def pointer(value, path):
    """Resolve an exact JSON pointer; missing values never become wildcards."""
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("JSON pointer required")
    for segment in path[1:].split("/"):
        segment = segment.replace("~1", "/").replace("~0", "~")
        value = value[int(segment)] if isinstance(value, list) else value[segment]
    return value


def prune(value, allowed):
    """Remove only explicitly permitted binding leaves for preservation checks."""
    if not isinstance(value, dict) or not isinstance(allowed, dict):
        return None
    result = deepcopy(value)
    for key, child in allowed.items():
        if key not in result:
            continue
        if isinstance(child, dict) and isinstance(result[key], dict):
            remaining = prune(result[key], child)
            if remaining:
                result[key] = remaining
            else:
                del result[key]
        else:
            del result[key]
    return result


def contains(actual, expected):
    """Compare binding subsets while preserving unmentioned existing keys."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    return type(actual) is type(expected) and actual == expected


class Invalid(Exception):
    """A safe report code; source data is never embedded in exceptions."""


class Inspector:
    """Check a frozen release declaration against supplied snapshots and receipts."""

    def __init__(self, context, now):
        self.context, self.now = context, now
        self.checks, self.receipts = [], {}

    def add(self, code, scope="release", status="FAIL"):
        self.checks.append({"status": status, "code": code, "object": scope})

    def require(self, condition, code):
        if not condition:
            raise Invalid(code)

    def ref(self, value, kind=None):
        self.require(
            isinstance(value, dict)
            and set(value) == REF_KEYS
            and all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_.:-]+", v) for v in value.values())
            and value["tenant"] == self.context["tenant"]
            and value["namespace"] in self.context["namespaces"]
            and (kind is None or value["kind"] == kind),
            "INVALID_REF",
        )
        return digest(value)

    def receipt_key(self, item):
        return self.ref(item["ref"]), item.get("operation", "resource_get")

    def load_receipts(self, payload):
        self.require(payload["schema_version"] == 1 and payload["context"] == self.context, "RECEIPT_CONTEXT")
        seen = set()
        for item in payload["items"]:
            try:
                key = self.receipt_key(item)
                self.require(key not in seen, "RECEIPT_DUPLICATE")
                seen.add(key)
                self.require(item.get("method") == "GET", "RECEIPT_METHOD")
                self.require(type(item.get("http_status")) is int and item["http_status"] == 200, "RECEIPT_HTTP")
                ref = item["ref"]
                if key[1] == "result_table_info":
                    self.require(
                        ref["kind"] == "ResultTable"
                        and bool(re.fullmatch(r"[0-9]+_[A-Za-z0-9_]+", item["logical_id"])),
                        "RECEIPT_URL",
                    )
                    path = "/v4/result_tables/{}/".format(quote(item["logical_id"], safe=""))
                else:
                    self.require(key[1] == "resource_get" and ref["kind"] in ROUTES, "RECEIPT_OPERATION")
                    path = ROUTES[ref["kind"]].format(**{k: quote(v, safe="") for k, v in ref.items()})
                self.require(item.get("url") == self.context["api_origin"].rstrip("/") + path, "RECEIPT_URL")
                age = (self.now - timestamp(item["collected_at"])).total_seconds()
                self.require(0 <= age <= self.context.get("max_evidence_age_seconds", 14400), "RECEIPT_TIME")
                self.require(item.get("body_sha256") == digest(item["body"]), "RECEIPT_DIGEST")
                body = item["body"]
                if isinstance(body, dict) and ("result" in body or "code" in body):
                    self.require(
                        body.get("result") is True and body.get("code") == "00" and "data" in body, "RECEIPT_API"
                    )
                    body = body["data"]
                self.require(
                    isinstance(body, dict)
                    and body.get("kind", "ResultTable" if key[1] == "result_table_info" else None) == ref["kind"]
                    and isinstance(body.get("metadata"), dict)
                    and all(body["metadata"].get(k) == ref[k] for k in ("tenant", "namespace", "name")),
                    "RECEIPT_IDENTITY",
                )
                self.receipts[key] = body
            except Invalid as error:
                self.add(str(error))
            except (KeyError, TypeError, ValueError, AttributeError):
                self.add("RECEIPT_STRUCTURE")

    def resource(self, ref, scope, operation="resource_get"):
        key = self.ref(ref), operation
        body = self.receipts.get(key)
        if body is None:
            self.add("RECEIPT_MISSING", scope, "NOT_CHECKED")
        return body

    def state(self, body, ref, expected, scope):
        if body is None:
            return
        phase = body.get("status", {}).get("phase")
        if phase is None:
            self.add("STATE_MISSING", scope, "NOT_CHECKED")
        elif phase != "Ok":
            self.add("RESOURCE_PHASE", scope)
        if ref["kind"] in ("Flow", "Clean", "DataSource"):
            state = body.get("spec", {}).get("current_status")
            if ref["kind"] == "Flow":
                stopped = body.get("metadata", {}).get("annotations", {}).get("task_stopped")
                if stopped in {"true", "false"}:
                    declared = "stopped" if stopped == "true" else "running"
                    if isinstance(state, str) and state.lower() != declared:
                        self.add("TASK_STATE_CONFLICT", scope)
                    state = declared
            if not isinstance(state, str):
                self.add("STATE_MISSING", scope, "NOT_CHECKED")
            elif state.lower() != expected:
                self.add("TASK_STATE", scope)
            if ref["kind"] in {"Clean", "DataSource"}:
                desired = body.get("spec", {}).get("desired_status")
                if not isinstance(desired, str):
                    self.add("STATE_DESIRED_MISSING", scope, "NOT_CHECKED")
                elif desired.lower() != expected:
                    self.add("TASK_DESIRED_STATE", scope)
        # DataStorage Ok is configuration evidence only, never running/nonempty.

    def contracts(self, item, scope):
        # Identity/task/Storage relations are checked by scenario code, never by
        # caller-selected pointers. These two optional comparisons are literal
        # expectations only; semantic V3->V4 equivalence needs independent review.
        needed = {"fields", "rules"}
        self.add("FIELD_RULE_SEMANTICS_MANUAL", scope, "NOT_CHECKED")
        supplied = set()
        for check in item.get("checks", []):
            mapping = item["mapping"]
            allowed = []
            if item["scenario"] == "flow":
                main = mapping["flow"]
                allowed.append(main)
                if check["topic"] == "fields":
                    flow_body = self.receipts.get((self.ref(main), "resource_get"), {})
                    allowed.extend(
                        n["data"] for n in flow_body.get("spec", {}).get("nodes", []) if isinstance(n.get("data"), dict)
                    )
                    for (_, _), resource in self.receipts.items():
                        logical = resource.get("spec", {}).get("predefiendResultTableId") or resource.get(
                            "metadata", {}
                        ).get("labels", {}).get("result_table_id")
                        if resource.get("kind") == "ResultTable" and logical == mapping["output_rt_id"]:
                            allowed.append(
                                {
                                    "kind": "ResultTable",
                                    **{k: resource["metadata"][k] for k in ("tenant", "namespace", "name")},
                                }
                            )
            else:
                topic_refs = {
                    "fields": [mapping["result_table"]],
                    "rules": [mapping["clean"]],
                }
                allowed = topic_refs.get(check["topic"], [])
            self.require(check["ref"] in allowed, "CONTRACT_UNRELATED_REF")
            self.require(
                check["topic"] in needed and check["pointer"].startswith(("/spec/", "/status/")), "CONTRACT_STRUCTURE"
            )
            if check["topic"] == "fields":
                self.require(
                    bool(re.fullmatch(r"/spec/(fields|nodes/[0-9]+/fields)", check["pointer"])), "CONTRACT_STRUCTURE"
                )
            elif check["topic"] == "rules":
                self.require(
                    bool(re.fullmatch(r"/spec/(rules|nodes/[0-9]+/(config/sql|processing_info))", check["pointer"])),
                    "CONTRACT_STRUCTURE",
                )
            self.require(("equals" in check) != ("sha256" in check), "CONTRACT_STRUCTURE")
            body = self.resource(check["ref"], scope, check.get("operation", "resource_get"))
            if body is None:
                continue
            try:
                actual = pointer(body, check["pointer"])
            except (KeyError, IndexError, TypeError, ValueError):
                self.add("CONTRACT_VALUE_MISSING", scope, "NOT_CHECKED")
                continue
            supplied.add(check["topic"])
            if check["topic"] in {"fields", "rules"}:
                self.require(isinstance(actual, (list, str, dict)) and bool(actual), "CONTRACT_STRUCTURE")
            if "equals" in check:
                matches = digest(actual) == digest(check["equals"])
            else:
                matches = bool(re.fullmatch(r"[0-9a-f]{64}", check["sha256"])) and digest(actual) == check["sha256"]
            if not matches:
                self.add("CONTRACT_DIFFERENCE", scope)
        for topic in sorted(needed - supplied):
            self.add("CONTRACT_MISSING", scope + ":" + topic, "NOT_CHECKED")

    def flow(self, item, row, rows, scope):
        mapping, fields = item["mapping"], row["fields"]
        backend = fields["backend_data"] or {}
        self.require(
            fields.get("status") in {"disabled", "running"}
            and item["expected_state"] == ("stopped" if fields["status"] == "disabled" else "running"),
            "LEGACY_STATE",
        )
        self.require(item["source"] == self.context["source"], "LEGACY_SOURCE")
        self.require(
            mapping["strategy_id"] == row["pk"]
            and mapping["audit_namespace"] == fields["namespace"]
            and mapping["legacy_flow_id"] == backend.get("flow_id")
            and type(mapping["legacy_flow_id"]) is int
            and mapping["legacy_flow_id"] > 0
            and mapping.get("migration_status") == "succeeded",
            "LEGACY_IDENTITY",
        )
        self.ref(mapping["flow"], "Flow")
        source = (fields.get("configs") or {}).get("data_source") or {}
        rt_ids = [source["rt_id"]] if source.get("rt_id") else []
        linked = source.get("link_table")
        if linked:
            matches = [
                r
                for r in rows.values()
                if r["model"] == "strategy_v2.linktable"
                and all(str(r["fields"].get(k)) == str(linked.get(k)) for k in ("uid", "version"))
            ]
            self.require(len(matches) == 1, "FLOW_INPUT")
            config = matches[0]["fields"]["config"]
            rt_ids = [link[side]["rt_id"] for link in config.get("links", []) for side in ("left_table", "right_table")]
        outputs = {
            rt.split("_", 1)[0] + "_" + backend["raw_table_name"]
            for rt in rt_ids
            if isinstance(rt, str) and re.fullmatch(r"[0-9]+_.+", rt)
        }
        if not outputs:
            self.add("FLOW_INPUT_UNRESOLVED", scope, "NOT_CHECKED")
        else:
            self.require(mapping["output_rt_id"] in outputs, "FLOW_OUTPUT")
        body = self.resource(mapping["flow"], scope)
        if body is not None:
            nodes = body.get("spec", {}).get("nodes", [])
            matches = [n for n in nodes if n.get("output") == mapping["output_rt_id"]]
            self.require(len(matches) == 1 and matches[0].get("kind") in {"StreamNode", "BatchSqlNode"}, "FLOW_OUTPUT")
            self.require(
                all(isinstance(n.get("name"), str) and n["name"] for n in nodes)
                and len({n["name"] for n in nodes}) == len(nodes),
                "FLOW_NODES",
            )
            names = {n["name"] for n in nodes}
            self.require(
                all(
                    edge in names
                    for n in nodes
                    for edge in n.get("inputs", []) + ([n["input"]] if n.get("input") else [])
                ),
                "FLOW_NODES",
            )
            actual_sources = set()
            source_nodes = [
                n
                for n in nodes
                if n.get("kind") in {"StreamSourceNode", "StreamStaticSource", "BatchSourceNode", "BatchStaticSource"}
            ]
            if not source_nodes:
                self.add("FLOW_SOURCES_MISSING", scope, "NOT_CHECKED")
            for node in source_nodes:
                source_ref = node.get("data")
                self.ref(source_ref, "ResultTable")
                source_body = self.resource(source_ref, scope)
                if source_body is None:
                    continue
                logical = source_body.get("spec", {}).get("predefiendResultTableId") or source_body.get(
                    "metadata", {}
                ).get("labels", {}).get("result_table_id")
                if logical is None:
                    self.add("FLOW_SOURCE_LOGICAL_ID_MISSING", scope, "NOT_CHECKED")
                else:
                    actual_sources.add(logical)
                # Runtime capability/asset dimension checks remain manual in this
                # finite release helper; do not reproduce the Flow planner here.
            if source_nodes and len(actual_sources) == len(source_nodes):
                self.require(actual_sources == set(rt_ids), "FLOW_SOURCE_IDENTITY")
            self.add("FLOW_CAPABILITY_AND_OUTPUT_STORAGE_MANUAL", scope, "NOT_CHECKED")
        self.state(body, mapping["flow"], item["expected_state"], scope)
        return {
            "backend_data": {
                "bkbase_v4": {
                    "flow": mapping["flow"],
                    "output_name": backend["raw_table_name"],
                    "output_rt_id": mapping["output_rt_id"],
                }
            }
        }

    def table_binding(self, body, table, cluster, purpose, scope):
        """Verify actual ready Redis/HDFS Binding and its RT/storage identity."""
        related = body.get("status", {}).get("related")
        if not isinstance(related, list):
            self.add("TABLE_BINDING_MISSING", scope, "NOT_CHECKED")
            return
        kind = {"redis": "RedisBinding", "hdfs": "HdfsBinding"}[purpose]
        candidates = [b for b in related if b.get("kind") == kind and b.get("spec", {}).get("storage") == cluster]
        self.require(len(candidates) == 1, "TABLE_BINDING_IDENTITY")
        binding = candidates[0]
        self.ref({"kind": kind, **{k: binding["metadata"][k] for k in ("tenant", "namespace", "name")}}, kind)
        self.require(
            binding.get("spec", {}).get("data") == table and binding.get("status", {}).get("phase") == "Ok",
            "TABLE_BINDING_IDENTITY",
        )
        if purpose == "redis":
            targets = binding.get("status", {}).get("related")
            if not isinstance(targets, list):
                self.add("BINDING_CLUSTER_STATE_MISSING", scope, "NOT_CHECKED")
                return
            self.require(
                len(targets) == 1
                and targets[0].get("kind") == cluster["kind"]
                and all(targets[0].get("metadata", {}).get(k) == cluster[k] for k in ("tenant", "namespace", "name"))
                and targets[0].get("status", {}).get("phase") == "Ok",
                "BINDING_CLUSTER_STATE",
            )
        else:
            config = binding.get("spec", {}).get("storageConfig", {})
            dimensions = [
                config[k]["dimensionTable"]
                for k in ("iceberg", "paimon")
                if isinstance(config.get(k), dict) and "dimensionTable" in config[k]
            ]
            if not dimensions:
                self.add("HDFS_DIMENSION_MISSING", scope, "NOT_CHECKED")
            else:
                self.require(all(value is True for value in dimensions), "HDFS_DIMENSION")

    def local_resource_identity(self, item, row, rows, scope):
        """Check old owner, audit namespace and retained V3 identities."""
        scenario, mapping, fields = item["scenario"], item["mapping"], row["fields"]
        if scenario in {"snapshot", "iam"}:
            self.add("SNAPSHOT_IAM_COMPLETE_CONTRACT_MANUAL", scope, "NOT_CHECKED")
        legacy = mapping["legacy"]
        self.require(
            type(legacy["raw_data_id"]) is int
            and legacy["raw_data_id"] > 0
            and all(isinstance(legacy[k], str) and legacy[k] for k in ("processing_id", "result_table_id")),
            "LEGACY_IDENTITY",
        )
        if scenario in {"plugin", "event_plugin", "collector"}:
            self.require(mapping["owner"] == scenario and mapping["owner_pk"] == row["pk"], "LEGACY_IDENTITY")
        if scenario in {"plugin", "event_plugin"}:
            self.require(
                fields.get("plugin_scene") == ("event" if scenario == "event_plugin" else "collector"), "PLUGIN_SCENE"
            )
        namespace = fields.get("namespace")
        if namespace is None:
            systems = [
                r
                for r in rows.values()
                if r["model"] == "meta.system" and r["fields"].get("system_id", r["pk"]) == fields.get("system_id")
            ]
            if len(systems) == 1:
                namespace = systems[0]["fields"].get("namespace")
        if scenario != "iam":
            self.require(namespace == mapping["audit_namespace"] and namespace is not None, "AUDIT_NAMESPACE")
            self.require(
                fields.get("processing_id" if scenario == "collector" else "bkbase_processing_id")
                == legacy["processing_id"]
                and fields.get("bkbase_table_id") == legacy["result_table_id"],
                "LEGACY_IDENTITY",
            )
        if scenario in {"collector", "snapshot"}:
            self.require(
                fields.get("bk_data_id" if scenario == "collector" else "bkbase_data_id") == legacy["raw_data_id"],
                "LEGACY_IDENTITY",
            )
        return namespace

    def remote_resource_identity(self, item, scope):
        """Check exact GET identities and source/Clean/ResultTable relations."""
        scenario, mapping = item["scenario"], item["mapping"]
        legacy = mapping["legacy"]
        for key, kind in KINDS.items():
            if key not in mapping and key == "data_source":
                continue
            self.ref(mapping[key], kind)
            body = self.resource(mapping[key], scope)
            self.state(body, mapping[key], item["expected_state"], scope)
            if body is None:
                continue
            spec = body.get("spec", {})
            labels = body["metadata"].get("labels", {})
            if key == "data_source":
                self.require(
                    str(labels.get("raw_data_id")) == str(legacy["raw_data_id"])
                    and spec.get("data_id") == mapping["data_id"],
                    "SOURCE_IDENTITY",
                )
            elif key == "data_id" and "data_source" not in mapping:
                self.require(spec.get("predefined", {}).get("dataId") == legacy["raw_data_id"], "SOURCE_IDENTITY")
            elif key == "clean":
                role = "existing" if scenario == "collector" else "new"
                self.require(
                    spec.get("raw_data_id") == legacy["raw_data_id"]
                    and spec.get("data_id") == mapping["data_id"]
                    and spec.get("result_table_id") == legacy["result_table_id"]
                    and spec.get("result_table_source") == role,
                    "CLEAN_IDENTITY",
                )
                if "data_source" in mapping or "processing_id" in labels:
                    self.require(labels.get("processing_id") == legacy["processing_id"], "CLEAN_IDENTITY")
                self.require(
                    spec.get("config_revision") is not None
                    and spec.get("config_revision") == spec.get("deploy_revision"),
                    "CLEAN_REVISION",
                )
            elif key == "result_table":
                # Explicit logical identity only: never infer legacy ownership from bizId.
                logical = spec.get("predefiendResultTableId") or labels.get("result_table_id")
                if logical is None:
                    self.add("RT_LOGICAL_ID_MISSING", scope, "NOT_CHECKED")
                else:
                    self.require(
                        logical == legacy["result_table_id"] and labels.get("result_table_id", logical) == logical,
                        "RT_IDENTITY",
                    )

    def storage_purposes(self, item, row, rows, namespace):
        """Enforce original scene, main/replica roles and event physical target."""
        scenario, mapping, fields = item["scenario"], item["mapping"], row["fields"]
        legacy = mapping["legacy"]
        storages = mapping["storages"]
        if scenario in {"plugin", "event_plugin"}:
            expected = {
                p
                for p, enabled in (("main", fields.get("has_storage")), ("replica", fields.get("has_replica_storage")))
                if enabled
            }
            self.require(
                set(storages) == expected and (not fields.get("has_replica_storage") or fields.get("has_storage")),
                "STORAGE_PURPOSE",
            )
            if scenario == "event_plugin":
                self.require(expected == {"main"} and "physical_table_name" in storages["main"], "PHYSICAL_TARGET")
                saved = {}
                for candidate in rows.values():
                    config = candidate["fields"]
                    if (
                        candidate["model"] == "meta.globalmetaconfig"
                        and config.get("config_level") == "namespace"
                        and config.get("instance_key") == namespace
                        and config.get("config_key")
                        in {"doris_event_bkbase_rt_id", "doris_event_physical_table_name", "doris_event_storage_config"}
                    ):
                        self.require(config["config_key"] not in saved, "EVENT_GLOBALMETA_DUPLICATE")
                        saved[config["config_key"]] = config.get("config_value")
                original_rt = saved.get("doris_event_bkbase_rt_id")
                original_target = saved.get("doris_event_physical_table_name")
                if not original_target and isinstance(saved.get("doris_event_storage_config"), dict):
                    original_target = saved["doris_event_storage_config"].get("physical_table_name")
                if original_rt:
                    self.require(original_rt == legacy["result_table_id"], "EVENT_GLOBALMETA_RT")
                if original_target:
                    self.require(original_target == storages["main"]["physical_table_name"], "EVENT_GLOBALMETA_TARGET")
        elif scenario == "collector":
            self.require(not storages, "STORAGE_PURPOSE")
            parents = [
                r
                for r in rows.values()
                if r["model"] == "databus.collectorplugin"
                and r["fields"].get("collector_plugin_id") == fields.get("collector_plugin_id")
            ]
            self.require(
                len(parents) == 1 and parents[0]["fields"].get("bkbase_table_id") == legacy["result_table_id"],
                "COLLECTOR_PARENT",
            )
        elif scenario in {"snapshot", "iam"}:
            self.require(bool(storages) and set(storages) <= {"redis", "hdfs"}, "STORAGE_PURPOSE")
            if scenario == "snapshot":
                self.require(
                    fields.get("status") in {"closed", "running"}
                    and item["expected_state"] == ("stopped" if fields["status"] == "closed" else "running"),
                    "LEGACY_STATE",
                )

    def resource_patch(self, item, scope):
        """Build the existing import patch while checking actual storage targets."""
        scenario, mapping = item["scenario"], item["mapping"]
        legacy, storages = mapping["legacy"], mapping["storages"]
        patch = {k: deepcopy(mapping[k]) for k in KINDS if k in mapping}
        patch.update(
            source_raw_data_id=legacy["raw_data_id"],
            result_table_id=legacy["result_table_id"],
            clean_role="existing" if scenario == "collector" else "owner",
        )
        if scenario in {"plugin", "event_plugin", "collector"}:
            patch["migration_import"] = deepcopy(mapping)
        targets, used_storages = {}, set()
        for purpose, entry in storages.items():
            storage_id = self.ref(entry["resource"], "DataStorage")
            self.require(storage_id not in used_storages, "STORAGE_DUPLICATE")
            used_storages.add(storage_id)
            cluster_kind = {
                "main": "Doris" if scenario == "event_plugin" else "ElasticSearch",
                "replica": "Doris",
                "redis": "Redis",
                "hdfs": "HDFS",
            }[purpose]
            self.ref(entry["cluster"], cluster_kind)
            body = self.resource(entry["resource"], scope)
            self.state(body, entry["resource"], item["expected_state"], scope)
            physical = entry.get("physical_table_name")
            if physical is not None:
                self.require(
                    isinstance(physical, str)
                    and bool(physical)
                    and not any(c.isspace() or c in "/\\" for c in physical),
                    "PHYSICAL_TARGET",
                )
                if cluster_kind == "ElasticSearch":
                    physical = physical.replace("{yyyyMMdd}", "%Y%m%d")
                if cluster_kind == "Doris":
                    self.require(len(physical.split(".")) == 2 and all(physical.split(".")), "PHYSICAL_TARGET")
                targets[purpose] = physical
            if body is not None:
                table = body.get("spec", {}).get("tableInfo", {})
                self.require(
                    table.get("source") == mapping["result_table"] and table.get("storage") == entry["cluster"],
                    "STORAGE_IDENTITY",
                )
                if physical is not None and table.get("physical_table_name") is not None:
                    actual = table["physical_table_name"]
                    if cluster_kind == "ElasticSearch" and isinstance(actual, str):
                        actual = actual.replace("{yyyyMMdd}", "%Y%m%d")
                    self.require(actual == physical, "PHYSICAL_TARGET")
            if scenario in {"snapshot", "iam"}:
                table_info = self.resource(mapping["result_table"], scope, "result_table_info")
                if table_info is not None:
                    self.table_binding(table_info, mapping["result_table"], entry["cluster"], purpose, scope)
            if physical is None and purpose in {"main", "replica"}:
                self.add("PHYSICAL_TARGET_UNDECLARED", scope, "NOT_CHECKED")
        if storages:
            patch["storages"] = {p: e["resource"] for p, e in storages.items()}
        if targets:
            patch["physical_targets"] = targets
        return patch

    def resources(self, item, row, rows, scope):
        """Compose finite resource checks and the actual local binding expectation."""
        scenario, mapping, fields = item["scenario"], item["mapping"], row["fields"]
        legacy, storages = mapping["legacy"], mapping["storages"]
        namespace = self.local_resource_identity(item, row, rows, scope)
        self.remote_resource_identity(item, scope)
        self.storage_purposes(item, row, rows, namespace)
        patch = self.resource_patch(item, scope)
        if scenario in {"snapshot", "iam"}:
            # These imports have separate contracts: require an explicit narrow local binding.
            explicit = item["expected_binding"]
            allowed_keys = {
                *KINDS,
                "source_raw_data_id",
                "result_table_id",
                "storages",
                "clean_role",
                "physical_targets",
                "snapshot_type",
                "redis",
                "redis_binding",
                "redis_key_fields",
            }
            self.require(isinstance(explicit, dict) and not set(explicit) - allowed_keys, "LOCAL_BINDING_PLAN")
            self.require(
                contains(
                    explicit,
                    {k: patch[k] for k in (*KINDS, "source_raw_data_id", "result_table_id", "storages") if k in patch},
                ),
                "LOCAL_BINDING_PLAN",
            )
            patch = explicit
        if scenario == "iam":
            self.require(
                item["config_key"] == fields.get("config_key") and isinstance(fields.get("config_value"), dict),
                "IAM_CONFIG",
            )
            self.require(patch.get("snapshot_type") in {"action", "resource_type", "user"}, "IAM_CONFIG")
            keys = {
                "action": "bkaudit_action_config_data",
                "resource_type": "bkaudit_resource_type_config_data",
                "user": "bkaudit_user_info_config_data",
            }
            self.require(
                fields["config_key"] == keys[patch["snapshot_type"]]
                and item["binding_namespace"] in self.context["namespaces"]
                and set(storages) == {"redis"}
                and patch.get("redis") == storages["redis"]["cluster"],
                "IAM_CONFIG",
            )
            old = fields["config_value"]
            old_clean = old.get("clean_resp")
            if not isinstance(old_clean, dict):
                self.add("IAM_LEGACY_IDENTITY_MISSING", scope, "NOT_CHECKED")
            else:
                self.require(
                    old.get("bkbase_data_id") == legacy["raw_data_id"]
                    and old_clean.get("processing_id") == legacy["processing_id"]
                    and old_clean.get("result_table_id") == legacy["result_table_id"],
                    "LEGACY_IDENTITY",
                )
            redis_keys = {"id"} if patch["snapshot_type"] == "user" else {"id", "system_id"}
            self.require(
                isinstance(patch.get("redis_key_fields"), list)
                and set(patch["redis_key_fields"]) == redis_keys
                and len(patch["redis_key_fields"]) == len(redis_keys),
                "IAM_REDIS_KEYS",
            )
            return {"config_value": {"bkbase_v4": {self.context["tenant"]: {item["binding_namespace"]: patch}}}}
        return {"bkbase_v4_resources": patch}

    def inspect(self, plan, before, after):
        self.require(plan["schema_version"] == 1 and plan["context"] == self.context, "TARGET_CONTEXT")
        self.require(
            all(
                str(before["manifest"]["database"][k]) == str(self.context["database"][k])
                for k in ("host", "port", "name")
            ),
            "DATABASE_TARGET",
        )
        timestamp(before["manifest"]["created_at"])
        for bundle, expected in ((before, self.context["source_version"]), (after, self.context["release_version"])):
            if bundle is None:
                continue
            manifest = bundle["manifest"]
            if not REQUIRED_MODELS <= set(manifest.get("model_counts", {})):
                self.add("EXPORT_SCOPE_NOT_CHECKED", status="NOT_CHECKED")
            if "version" not in manifest:
                self.add("SNAPSHOT_VERSION_NOT_CHECKED", status="NOT_CHECKED")
            else:
                self.require(manifest["version"] == expected, "SNAPSHOT_VERSION")
            if "source" not in manifest:
                self.add("LEGACY_SOURCE_NOT_CHECKED", status="NOT_CHECKED")
            else:
                self.require(manifest["source"] == self.context["source"], "LEGACY_SOURCE")
            if "context_sha256" in manifest:
                self.require(manifest["context_sha256"] == digest(self.context), "SNAPSHOT_CONTEXT")
            age = (self.now - timestamp(manifest["created_at"])).total_seconds()
            self.require(0 <= age <= self.context.get("max_evidence_age_seconds", 14400), "SNAPSHOT_TIME")
        rows = {identity(row): row for row in before["rows"]}
        self.require(len(rows) == len(before["rows"]), "INVENTORY_DUPLICATE")
        if after is not None:
            self.require(
                all(
                    str(after["manifest"]["database"][k]) == str(self.context["database"][k])
                    for k in ("host", "port", "name")
                ),
                "DATABASE_TARGET",
            )
            self.require(
                timestamp(after["manifest"]["created_at"]) >= timestamp(before["manifest"]["created_at"]), "POST_TIME"
            )
            after_rows = {identity(row): row for row in after["rows"]}
            self.require(len(after_rows) == len(after["rows"]) and set(after_rows) == set(rows), "POST_SCOPE")
        seen, writers, old_flows = set(), set(), set()
        patches = {}
        for item in plan["objects"]:
            scope = digest([item.get("model"), item.get("pk")])[:16]
            try:
                key = identity(item)
                self.require(key not in seen, "SCOPE_DUPLICATE")
                seen.add(key)
                self.require(key in rows, "SCOPE_UNKNOWN")
                row = rows[key]
                if item["action"] == "exclude":
                    self.require(
                        isinstance(item.get("reason"), str) and bool(item["reason"].strip()), "EXCLUSION_REASON"
                    )
                    self.add("EXCLUDED_BY_SCOPE", scope, "PASS")
                    continue
                self.require(
                    item["action"] == "migrate"
                    and item["scenario"] in OWNER_MODELS
                    and row["model"] == OWNER_MODELS[item["scenario"]],
                    "MAPPING_SCENARIO",
                )
                self.require(item["expected_state"] in {"running", "stopped"}, "EXPECTED_STATE")
                self.require(not row["fields"].get("is_deleted"), "DELETED_OWNER")
                if item["scenario"] == "flow":
                    old_id = item["mapping"]["legacy_flow_id"]
                    self.require(old_id not in old_flows, "DUPLICATE_LEGACY_FLOW")
                    old_flows.add(old_id)
                    writer = item["mapping"]["flow"]
                    self.require(
                        not any(
                            other_key != key
                            and other["model"] == "strategy_v2.strategy"
                            and (
                                (other["fields"].get("backend_data") or {}).get("flow_id") == old_id
                                or (other["fields"].get("backend_data") or {}).get("bkbase_v4", {}).get("flow")
                                == writer
                            )
                            for other_key, other in rows.items()
                        ),
                        "DUPLICATE_OWNERSHIP",
                    )
                    patch = self.flow(item, row, rows, scope)
                else:
                    writer = item["mapping"]["clean"]
                    patch = self.resources(item, row, rows, scope)
                writer_key = self.ref(writer)
                self.require(writer_key not in writers, "DUPLICATE_OWNERSHIP")
                writers.add(writer_key)
                patches[key] = patch
                self.contracts(item, scope)
                if after is not None:
                    self.require(contains(after_rows[key]["fields"], patch), "LOCAL_BINDING")
                self.add("OBJECT_CHECKED", scope, "PASS")
            except Invalid as error:
                self.add(str(error), scope)
            except (KeyError, IndexError, TypeError, ValueError, AttributeError):
                self.add("MAPPING_STRUCTURE", scope)
        for key in set(rows) - seen:
            self.add("SCOPE_MISSING", digest(key)[:16])
        if after is not None:
            for key, row in rows.items():
                allowed = deepcopy(patches.get(key, {}))
                # Normal import clears these flags; no other unknown V4 keys may change.
                if "bkbase_v4_resources" in allowed:
                    allowed["bkbase_v4_resources"].update(ready=None, clean_ready=None)
                actual_fields = deepcopy(after_rows[key]["fields"])
                if "bkbase_v4_resources" not in row["fields"] and actual_fields.get("bkbase_v4_resources") == {}:
                    actual_fields.pop("bkbase_v4_resources")
                if digest(prune(row["fields"], allowed)) != digest(prune(actual_fields, allowed)):
                    self.add("PRESERVATION", digest(key)[:16])


def verify(context, plan, before, receipts, *, after=None, now=None):
    """Return a redacted check report; invalid or unknown evidence never passes."""
    inspector = Inspector(context, now or datetime.now(timezone.utc))
    try:
        origin = urlsplit(context["api_origin"])
        inspector.require(
            bool(context["environment"])
            and bool(context["release_version"])
            and bool(context["source_version"])
            and isinstance(context["tenant"], str)
            and bool(context["tenant"])
            and type(context["source"]["project_id"]) is int
            and context["source"]["project_id"] > 0
            and bool(context["source"]["tenant"])
            and origin.scheme == "https"
            and origin.hostname is not None
            and not origin.username
            and not origin.password
            and not origin.query
            and not origin.fragment
            and isinstance(context["namespaces"], list)
            and bool(context["namespaces"])
            and len(set(context["namespaces"])) == len(context["namespaces"]),
            "TARGET_CONTEXT",
        )
        inspector.require(isinstance(plan["objects"], list), "INPUT_STRUCTURE")
        inspector.load_receipts(receipts)
        inspector.inspect(plan, before, after)
        if not any(item.get("action") == "migrate" for item in plan["objects"]):
            inspector.add("NO_MIGRATION_OBJECTS", status="NOT_CHECKED")
    except Invalid as error:
        inspector.add(str(error))
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        inspector.add("INPUT_STRUCTURE")
    counts = Counter(c["status"] for c in inspector.checks)
    status = "FAIL" if counts["FAIL"] else "NOT_CHECKED" if counts["NOT_CHECKED"] else "PASS"
    return {
        "schema_version": 1,
        "status": status,
        "verification_mode": "provided_offline_evidence",
        "stage": "postflight" if after is not None else "preflight",
        "context_sha256": digest(context),
        "plan_sha256": digest(plan),
        "created_at": inspector.now.isoformat(),
        "summary": dict(counts),
        "checks": inspector.checks,
        "not_covered": [
            "live_resource_freshness",
            "receipt_source_authenticity",
            "deployed_version_authenticity",
            "field_rule_semantic_equivalence",
            "flow_runtime_capabilities_and_output_physical_storage",
            "complete_snapshot_iam_contract",
            "datastorage_task_running_and_nonempty_business_data",
            "product_acceptance",
            "full_permission_matrix",
            "database_backup_and_restore",
        ],
    }


def main(argv=None):
    """CLI entry: only reads inputs and exclusively creates a private report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("preflight", "postflight"))
    parser.add_argument("--context", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--before", required=True, help="existing native fixture bundle directory")
    parser.add_argument("--receipts", required=True)
    parser.add_argument("--after", help="fresh actual local fixture bundle; required for postflight")
    parser.add_argument("--output", required=True, help="new report file; never overwritten")
    args = parser.parse_args(argv)
    if bool(args.after) != (args.stage == "postflight"):
        parser.error("--after is required only for postflight")
    try:
        result = verify(
            read_json(args.context),
            read_json(args.plan),
            read_bundle(args.before),
            read_json(args.receipts),
            after=read_bundle(args.after) if args.after else None,
        )
    except (OSError, ValueError, TypeError, KeyError):
        result = {"status": "FAIL", "checks": [{"status": "FAIL", "code": "INPUT_INVALID", "object": "release"}]}
    try:
        write_private(args.output, result)
    except OSError:
        print("FAIL: report creation refused (existing or inaccessible path)")
        return 2
    print("{}: {} checks; details in the private report".format(result["status"], len(result["checks"])))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
