import json
from io import StringIO
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from .test_iam_v4_model_client import BASE, GATEWAY, page, reply

SYSTEM = {
    "id": "bk-audit",
    "name": "Audit",
    "description": "",
    "callback_url": "https://audit.example.test/api/v1/iam/resources/",
    "clients": ["audit"],
    "managers": ["maintainer"],
}
RESOURCE = {"id": "scene", "name": "Scene", "ancestors": []}
OPERATION = {"id": "list_scene", "name": "List scenes", "resource_type_id": "scene"}
DESTINATION = {
    "system": {"id": "bk-audit", "name": "Audit"},
    "resource_types": [RESOURCE],
    "actions": [OPERATION],
    "roles": [],
}
MISSING = reply(404, {"error": {"code": "NOT_FOUND"}, "request_id": "lookup"})
MANAGERS = ("--managers", "maintainer")


def existing(*, resources=(), actions=(), roles=(), system=SYSTEM):
    return [
        reply(200, {"data": system}),
        page(len(resources), list(resources)),
        page(len(actions), list(actions)),
        page(len(roles), list(roles)),
    ]


@pytest.fixture
def invoke(monkeypatch, tmp_path):
    monkeypatch.delenv("BKAPP_IAM_V4_MODEL_CLIENTS", raising=False)
    monkeypatch.delenv("BKAPP_IAM_V4_MODEL_MANAGERS", raising=False)
    session = Mock()
    monkeypatch.setattr("requests.Session", lambda: session)
    model = tmp_path / "model.json"
    model.write_text(json.dumps(DESTINATION))

    def run(*args):
        output = StringIO()
        call_command("iam_v4_migrate", "--model", str(model), *args, stdout=output)
        return output.getvalue()

    with override_settings(
        APP_CODE="audit",
        SECRET_KEY="placeholder-app-secret",
        BK_IAM_SYSTEM_ID="bk-audit",
        BK_IAM_SYSTEM_NAME="Audit",
        BK_IAM_RESOURCE_API_HOST="https://audit.example.test/",
        BK_IAM_V4_API_URL=GATEWAY,
        BKPAAS_MULTI_TENANT_MODE=False,
    ):
        yield run, session


def methods(session):
    return [call.args[0] for call in session.request.call_args_list]


def digest(output):
    return next(line.split("=", 1)[1] for line in output.splitlines() if line.startswith("plan_digest="))


def test_omitted_lists_keep_existing_access(invoke):
    run, session = invoke
    current = {**SYSTEM, "clients": ["audit", "automation"], "managers": ["iam_owner"]}
    session.request.side_effect = existing(system=current, resources=(RESOURCE,), actions=(OPERATION,))
    assert "changes=0" in run()
    assert methods(session) == ["GET"] * 4


def test_explicit_client_replacement_is_visible_in_preview(invoke, monkeypatch):
    run, session = invoke
    monkeypatch.setenv("BKAPP_IAM_V4_MODEL_CLIENTS", "env_client")
    current = {**SYSTEM, "clients": ["audit", "automation"]}
    session.request.side_effect = existing(system=current, resources=(RESOURCE,), actions=(OPERATION,))
    output = run("--clients", "new_client")
    assert 'clients: ["audit", "automation"] -> ["audit", "new_client"]' in output
    assert methods(session) == ["GET"] * 4


def test_environment_clients_replace_only_the_client_list(invoke, monkeypatch, tmp_path):
    run, session = invoke
    monkeypatch.setenv("BKAPP_IAM_V4_MODEL_CLIENTS", "reporting, automation, reporting")
    monkeypatch.setenv("BKAPP_IAM_V4_MODEL_MANAGERS", "bootstrap_owner")
    current = {**SYSTEM, "clients": ["audit", "retired"], "managers": ["iam_owner"]}
    updated = {**current, "clients": ["audit", "automation", "reporting"]}
    session.request.side_effect = [
        *existing(system=current, resources=(RESOURCE,), actions=(OPERATION,)),
        reply(204),
        *existing(system=updated, resources=(RESOURCE,), actions=(OPERATION,)),
    ]
    assert "verified: system=bk-audit changes=1" in run("--apply", "--snapshot-dir", str(tmp_path))
    assert session.request.call_args_list[4].kwargs["json"] == {"clients": ["audit", "automation", "reporting"]}


def test_existing_managers_are_preserved_even_with_explicit_override(invoke, monkeypatch):
    run, session = invoke
    monkeypatch.setenv("BKAPP_IAM_V4_MODEL_MANAGERS", "bootstrap_owner")
    session.request.side_effect = existing(resources=(RESOURCE,), actions=(OPERATION,))
    assert "changes=0" in run("--managers", "somebody_else")
    assert methods(session) == ["GET"] * 4


@pytest.mark.parametrize(
    ("clients_env", "managers_env", "expected_clients", "expected_managers"),
    [
        ("", "", ["audit"], []),
        (" reporting, automation ", " owner_b, owner_a ", ["audit", "automation", "reporting"], ["owner_a", "owner_b"]),
    ],
)
def test_bootstrap_uses_environment_or_defaults(
    invoke, monkeypatch, tmp_path, clients_env, managers_env, expected_clients, expected_managers
):
    run, session = invoke
    monkeypatch.setenv("BKAPP_IAM_V4_MODEL_CLIENTS", clients_env)
    monkeypatch.setenv("BKAPP_IAM_V4_MODEL_MANAGERS", managers_env)
    target = {**SYSTEM, "clients": expected_clients, "managers": expected_managers}
    session.request.side_effect = [
        MISSING,
        *([reply(201, {"data": []})] * 3),
        *existing(system=target, resources=(RESOURCE,), actions=(OPERATION,)),
    ]
    assert "verified: system=bk-audit changes=3" in run("--apply", "--snapshot-dir", str(tmp_path))
    assert session.request.call_args_list[1].kwargs["json"] == target


@override_settings(BK_IAM_SYSTEM_NAME="Configured Audit")
def test_name_and_callback_use_existing_settings(invoke, tmp_path):
    run, session = invoke
    session.request.side_effect = [MISSING, MISSING, reply(403, {"error": {"code": "DENIED"}})]
    expected = digest(run(*MANAGERS))
    with pytest.raises(CommandError, match="HTTP 403"):
        run(*MANAGERS, "--apply", "--expect-plan", expected, "--snapshot-dir", str(tmp_path))
    assert session.request.call_args.kwargs["json"] == {**SYSTEM, "name": "Configured Audit"}


def test_callback_and_single_tenant_header_can_be_explicitly_overridden(invoke):
    run, session = invoke
    url = "https://shared.example.test/api/v1/iam/resources/"
    session.request.side_effect = existing(
        system={**SYSTEM, "callback_url": url}, resources=(RESOURCE,), actions=(OPERATION,)
    )
    assert "changes=0" in run("--callback-url", url, "--tenant-id", "default")
    assert session.request.call_args.kwargs["headers"]["X-Bk-Tenant-Id"] == "default"


@override_settings(BKPAAS_MULTI_TENANT_MODE=True, BK_TENANT_ID="tencent")
def test_multi_tenant_rejects_foreign_model_scope_before_request(invoke):
    run, session = invoke
    with pytest.raises(CommandError, match="tenant=system"):
        run("--tenant-id", "tencent")
    session.request.assert_not_called()


def test_default_dry_run_is_get_only_even_when_target_missing(invoke):
    run, session = invoke
    session.request.side_effect = [MISSING]
    output = run(*MANAGERS)
    assert methods(session) == ["GET"]
    assert "X-Bk-Tenant-Id" not in session.request.call_args.kwargs["headers"]
    assert all(
        label in output
        for label in ("create system bk-audit", "create resource_type scene", "create action list_scene")
    )
    assert "placeholder-app-secret" not in output
    assert len(digest(output)) == 64


@override_settings(BKPAAS_MULTI_TENANT_MODE=True, BK_TENANT_ID="tencent")
def test_multi_tenant_migrates_using_system_not_instance_tenant(invoke):
    run, session = invoke
    session.request.side_effect = [MISSING]
    assert "tenant=system" in run("--dry-run", *MANAGERS)
    assert session.request.call_args.kwargs["headers"]["X-Bk-Tenant-Id"] == "system"


def test_apply_rejects_stale_preview_before_writing(invoke, tmp_path):
    run, session = invoke
    session.request.side_effect = [MISSING, *existing(resources=(RESOURCE,))]
    old_digest = digest(run(*MANAGERS))
    with pytest.raises(CommandError, match="preview"):
        run(*MANAGERS, "--apply", "--expect-plan", old_digest, "--snapshot-dir", str(tmp_path))
    assert methods(session) == ["GET"] * 5


def test_bare_apply_deletes_obsolete_action_and_saves_default_snapshot(invoke, monkeypatch, tmp_path):
    run, session = invoke
    monkeypatch.setenv("HOME", str(tmp_path))
    obsolete = {"id": "obsolete", "name": "Obsolete", "resource_type_id": ""}
    session.request.side_effect = [
        *existing(resources=(RESOURCE,), actions=(OPERATION, obsolete)),
        reply(204),
        *existing(resources=(RESOURCE,), actions=(OPERATION,)),
    ]

    assert "verified: system=bk-audit changes=1" in run("--apply")
    assert methods(session) == ["GET"] * 4 + ["DELETE"] + ["GET"] * 4
    assert session.request.call_args_list[4].args[1].endswith("/actions/obsolete/")
    snapshot = next((tmp_path / ".local/state/bk-audit/iam-v4-snapshots").glob("iam-v4-*.json"))
    assert snapshot.stat().st_mode & 0o777 == 0o600
    saved = json.loads(snapshot.read_text())
    assert {action["id"] for action in saved["before"]["actions"]} == {"obsolete", "list_scene"}
    assert {action["id"] for action in saved["target"]["actions"]} == {"list_scene"}


def test_apply_checks_snapshot_location_before_writing(invoke, tmp_path):
    run, session = invoke
    session.request.side_effect = [MISSING, MISSING]
    expected = digest(run(*MANAGERS))
    with pytest.raises(CommandError, match="snapshot"):
        run(*MANAGERS, "--apply", "--expect-plan", expected, "--snapshot-dir", str(tmp_path / "absent"))
    assert methods(session) == ["GET", "GET"]


def test_apply_refuses_to_recreate_an_action_in_use(invoke, tmp_path):
    run, session = invoke
    old_op = {**OPERATION, "resource_type_id": ""}
    old_role = {
        "id": "legacy",
        "name": "Legacy",
        "description": "",
        "actions": [{"id": "list_scene", "resource_type_id": ""}],
    }
    live = existing(resources=(RESOURCE,), actions=(old_op,), roles=(old_role,))
    session.request.side_effect = live * 2
    output = run()
    assert "recreation required" in output
    with pytest.raises(CommandError, match="blocked"):
        run("--apply", "--expect-plan", digest(output), "--snapshot-dir", str(tmp_path))
    assert methods(session) == ["GET"] * 8


def test_apply_reports_partial_error_and_does_not_attempt_rollback(invoke, tmp_path):
    run, session = invoke
    session.request.side_effect = [
        MISSING,
        MISSING,
        reply(201, {"data": {"id": "bk-audit"}}),
        reply(403, {"error": {"code": "DENIED"}, "request_id": "test-request"}),
    ]
    with pytest.raises(CommandError, match="test-request") as err:
        run(*MANAGERS, "--apply", "--expect-plan", digest(run(*MANAGERS)), "--snapshot-dir", str(tmp_path))
    assert "completed=1" in str(err.value) and "remaining=1" in str(err.value)
    assert methods(session) == ["GET", "GET", "POST", "POST"]
    assert len(list(tmp_path.glob("iam-v4-*.json"))) == 1


def test_apply_reads_back_and_next_preview_is_noop(invoke, tmp_path):
    run, session = invoke
    live = existing(resources=(RESOURCE,), actions=(OPERATION,))
    session.request.side_effect = [MISSING, MISSING, *([reply(201, {"data": []})] * 3), *live, *live]
    output = run(*MANAGERS, "--apply", "--expect-plan", digest(run(*MANAGERS)), "--snapshot-dir", str(tmp_path))
    assert "verified" in output
    assert "changes=0" in run("--dry-run")
    assert methods(session) == ["GET"] * 2 + ["POST"] * 3 + ["GET"] * 8
    assert session.request.call_args_list[2].args[1] == GATEWAY + BASE
    snapshot = next(tmp_path.glob("iam-v4-*.json"))
    assert snapshot.stat().st_mode & 0o777 == 0o600
    assert "placeholder-app-secret" not in snapshot.read_text()


def test_apply_readback_mismatch_is_not_success(invoke, tmp_path):
    run, session = invoke
    session.request.side_effect = [MISSING, MISSING, *([reply(201, {"data": []})] * 3), *existing()]
    with pytest.raises(CommandError, match="readback"):
        run(*MANAGERS, "--apply", "--expect-plan", digest(run(*MANAGERS)), "--snapshot-dir", str(tmp_path))
