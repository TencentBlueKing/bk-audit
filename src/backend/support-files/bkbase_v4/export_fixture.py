"""Export configuration using the target's already deployed Django model schema.

Run via runpy from the target manage.py shell, not with candidate Django models
against an old database. SQL writes are rejected by the read-only transaction.
No BKBase, Redis, schema migration or service-control operation is performed.
"""

import io
import json
import os
import re
import runpy
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HELPERS = runpy.run_path(str(Path(__file__).with_name("release_checks.py")))
APPS = ("meta", "databus", "strategy_v2")
REQUIRED = {
    "meta.globalmetaconfig",
    "databus.collectorplugin",
    "databus.collectorconfig",
    "databus.snapshot",
    "strategy_v2.strategy",
    "strategy_v2.linktable",
}
EXCLUDE = {
    "databus.storageoperatelog",
    "databus.snapshotcheckstatistic",
    "strategy_v2.strategyauditinstance",
    "strategy_v2.linktableauditinstance",
    "strategy_v2.strategytagsynctrash",
}


def database_identity(value):
    """Compare actual endpoint/database without passwords or driver options."""
    port = value["port"]
    # Django's MySQL backend omits an empty PORT; the driver then uses 3306.
    if port is None or port == "":
        port = 3306
    elif isinstance(port, str) and re.fullmatch(r"[0-9]+", port):
        port = int(port)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid database port")
    return {"host": str(value["host"]), "port": str(port), "name": str(value["name"])}


def capture(connection, context, root, counters, dump, *, version, stage="before", tables=(), deployment_evidence=None):
    """Capture one read-only consistent transaction and seal a fresh private bundle.

    counters and dump use the same default connection supplied by the deployed
    application's model registry. Missing/inconsistent data never gets a manifest.
    """
    configured = connection.settings_dict
    target = {"host": configured.get("HOST"), "port": configured.get("PORT"), "name": configured.get("NAME")}
    expected_version = context["source_version"] if stage == "before" else context["release_version"]
    if (
        stage not in {"before", "after"}
        or connection.vendor != "mysql"
        or database_identity(target) != database_identity(context["database"])
        or version != expected_version
        or connection.in_atomic_block
        or not connection.get_autocommit()
    ):
        raise ValueError("target, deployed version or transaction mismatch")
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE(), VERSION()")
        actual_database, server_version = cursor.fetchone()
        if str(actual_database) != str(context["database"]["name"]):
            raise ValueError("actual database mismatch")
        if tables:
            cursor.execute("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()")
            engines = dict(cursor.fetchall())
            if any(engines.get(table) != "InnoDB" for table in tables):
                raise ValueError("configuration tables must use InnoDB")
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        try:
            counts = {label: count() for label, count in counters.items()}
            rows = dump()
            observed = Counter(row["model"] for row in rows)
            if set(observed) - set(counts) or {label: observed[label] for label in counts} != counts:
                raise ValueError("snapshot counts mismatch")
            identities = {(row["model"], HELPERS["digest"](row["pk"])) for row in rows}
            if len(identities) != len(rows):
                raise ValueError("duplicate snapshot rows")
        finally:
            cursor.execute("ROLLBACK")
    root = Path(root)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(root, 0o700)
    HELPERS["write_private"](root / "business.json", rows)
    data = (root / "business.json").read_bytes()
    manifest = {
        "schema_version": 1,
        "complete": True,
        "fixture": "business.json",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "stage": stage,
        "version_evidence": "provided_deployment_readback" if deployment_evidence is not None else "caller_asserted",
        "deployed_version_authenticity": "NOT_CHECKED",
        "deployment_receipt_sha256": HELPERS["digest"](deployment_evidence),
        "context_sha256": HELPERS["digest"](context),
        "source": context["source"],
        "database": {**context["database"], "version": str(server_version)},
        "apps": APPS,
        "excluded": sorted(EXCLUDE),
        "soft_deleted_included": True,
        "model_counts": counts,
        "consistency": "single read-only REPEATABLE READ transaction; selected deployed configuration models only",
        "size_bytes": len(data),
        "sha256": HELPERS["hash_bytes"](data),
    }
    HELPERS["write_private"](root / "manifest.json", manifest)
    HELPERS["read_bundle"](root)
    return {"status": "EXPORTED", "object_count": len(rows), "model_count": len(counts)}


def project_id(value):
    """Normalize the existing string setting strictly; bool is never an ID."""
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value):
        return int(value)
    raise ValueError("invalid legacy project setting")


def export_target(connection, settings, context, root, counters, dump, deployed, *, stage, tables=()):
    """Check installed application scope and externally collected deployment evidence.

    This tool cannot authenticate the deployment readback or prove which image is
    running. Its origin remains explicitly NOT_CHECKED in the sealed manifest.
    """
    if stage not in {"before", "after"} or getattr(settings, "APP_CODE", None) != context["application"]:
        raise ValueError("application or stage mismatch")
    if (
        stage == "before"
        and project_id(getattr(settings, "BKBASE_PROJECT_ID", None)) != context["source"]["project_id"]
    ):
        raise ValueError("legacy project does not match deployed settings")
    expected = context["source_version"] if stage == "before" else context["release_version"]
    age = (datetime.now(timezone.utc) - HELPERS["timestamp"](deployed["collected_at"])).total_seconds()
    if (
        deployed.get("environment") != context["environment"]
        or deployed.get("application") != context["application"]
        or deployed.get("stage") != stage
        or deployed.get("version") != expected
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", deployed.get("image_digest", ""))
        or not isinstance(deployed.get("source"), str)
        or not deployed["source"].strip()
        or not 0 <= age <= context.get("max_evidence_age_seconds", 14400)
    ):
        raise ValueError("deployment evidence mismatch or stale")
    # A receipt digest identifies the reviewed version input; it is not a signature.
    return capture(
        connection,
        context,
        root,
        counters,
        dump,
        version=expected,
        stage=stage,
        tables=tables,
        deployment_evidence=deployed,
    )


def main():
    """Use only installed target models, selected via explicit private context."""
    from django.apps import apps
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connections, router

    context = HELPERS["read_json"](os.environ["AUDIT_RELEASE_CONTEXT"])
    stage = os.environ["AUDIT_EXPORT_STAGE"]
    deployed = HELPERS["read_json"](os.environ["AUDIT_DEPLOYMENT_EVIDENCE"])
    connection = connections["default"]
    models = [
        model
        for label in APPS
        for model in apps.get_app_config(label).get_models()
        if model._meta.managed
        and not model._meta.proxy
        and model._meta.label_lower not in EXCLUDE
        and router.allow_migrate_model("default", model)
    ]
    labels = [model._meta.label_lower for model in models]
    if not REQUIRED.issubset(labels):
        raise ValueError("required configuration model missing")
    # default database is explicit; no manager hides soft-deleted records.
    counters = {
        model._meta.label_lower: (lambda model=model: model._base_manager.using("default").count()) for model in models
    }
    tables = {model._meta.db_table for model in models}
    tables.update(
        field.remote_field.through._meta.db_table
        for model in models
        for field in model._meta.local_many_to_many
        if field.remote_field.through._meta.auto_created
    )

    def dump():
        output = io.StringIO()
        call_command(
            "dumpdata", *labels, use_base_manager=True, database="default", format="json", stdout=output, verbosity=0
        )
        return json.loads(output.getvalue())

    try:
        result = export_target(
            connection,
            settings,
            context,
            os.environ["AUDIT_RELEASE_EXPORT_DIR"],
            counters,
            dump,
            deployed,
            stage=stage,
            tables=tables,
        )
        print(json.dumps(result))
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Driver exceptions can include connection details; never echo their text.
        raise SystemExit("FAIL: read-only export refused or failed; no release success implied") from None
