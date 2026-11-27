import json
from dataclasses import replace
from pathlib import Path

import pytest

from apps.permission.iam_v4_model.model import load_model
from apps.permission.iam_v4_model.reconcile import build_plan

MODEL = Path(__file__).resolve().parents[2] / "support-files/iam_v4/model.json"
CONFIG = {
    "system_id": "bk-audit",
    "app_code": "audit_site",
    "callback_url": "https://audit.example.test/api/v1/iam/resources/",
    "clients": ["audit_extra"],
    "managers": ["model_owner"],
}


def test_reference_model_preserves_ancestor_role_actions():
    snapshot = load_model(MODEL, **CONFIG)
    assert [len(snapshot.resource_types), len(snapshot.actions), len(snapshot.roles)] == [11, 38, 6]
    assert snapshot.actions["edit_strategy"]["resource_type_id"] == "strategy"
    assert {"id": "edit_strategy", "resource_type_id": "scene"} in snapshot.roles["scene_admin"]["actions"]
    assert snapshot.system["clients"] == ["audit_extra", "audit_site"]
    assert snapshot.system["managers"] == ["model_owner"]
    assert snapshot.system["callback_url"] == CONFIG["callback_url"]


def test_builtin_assets_extend_only_four_root_resources():
    """从原七类模型升级时，计划只注册四类，无 Action/角色/授权变化。"""
    target = load_model(MODEL, **CONFIG)
    original_ids = {"system", "scene", "strategy", "link_table", "risk", "notice_group", "tag"}
    current = replace(
        target, resource_types={key: val for key, val in target.resource_types.items() if key in original_ids}
    )
    plan = build_plan(target, current, gateway_url="https://iam.example.test", tenant_id="system")
    assert not plan.blocked
    assert [(step.operation, step.kind, step.ids) for step in plan.steps] == [
        ("create", "resource_type", ("manual_event",)),
        ("create", "resource_type", ("strategy_tag",)),
        ("create", "resource_type", ("ticket_node",)),
        ("create", "resource_type", ("ticket_permission",)),
    ]
    for step in plan.steps:
        assert step.body[0]["ancestors"] == []


@pytest.mark.parametrize("scope", ["tag", "strategy"])
def test_role_scope_rejects_unrelated_or_inconsistent_resources(tmp_path, scope):
    content = json.loads(MODEL.read_text())
    scene_role = next(role for role in content["roles"] if role["id"] == "scene_admin")
    next(action for action in scene_role["actions"] if action["id"] == "edit_strategy")["resource_type_id"] = scope
    path = tmp_path / "model.json"
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="scene_admin"):
        load_model(path, **CONFIG)


@pytest.mark.parametrize("broken", ["no_roles", "cycle", "dangling", "duplicate", "wrong_system", "empty_callback"])
def test_invalid_or_partial_model_is_rejected(tmp_path, broken):
    content = json.loads(MODEL.read_text())
    config = CONFIG.copy()
    if broken == "no_roles":
        content.pop("roles")
    elif broken == "cycle":
        content["resource_types"][0]["ancestors"] = [content["resource_types"][0]["id"]]
    elif broken == "dangling":
        content["actions"][0]["resource_type_id"] = "not_registered"
    elif broken == "wrong_system":
        content["system"]["id"] = "another_system"
    elif broken == "empty_callback":
        config["callback_url"] = ""
    path = tmp_path / "model.json"
    encoded = json.dumps(content)
    path.write_text(('{"roles": [], ' + encoded[1:]) if broken == "duplicate" else encoded)
    with pytest.raises(ValueError):
        load_model(path, **config)


def test_unknown_fields_do_not_silently_change_full_model_scope(tmp_path):
    content = json.loads(MODEL.read_text())
    content["instance_views"] = []
    path = tmp_path / "model.json"
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="instance_views"):
        load_model(path, **CONFIG)


@pytest.mark.parametrize("scope", [False, 0, [], {}, None])
def test_non_string_action_scope_is_not_an_unbound_action(tmp_path, scope):
    content = json.loads(MODEL.read_text())
    action = next(row for row in content["actions"] if row["resource_type_id"] == "")
    action["resource_type_id"] = scope
    path = tmp_path / "model.json"
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="resource type"):
        load_model(path, **CONFIG)


def test_target_rejects_duplicate_names(tmp_path):
    content = json.loads(MODEL.read_text())
    content["actions"][0]["name"] = content["actions"][1]["name"]
    path = tmp_path / "model.json"
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="duplicate action name"):
        load_model(path, **CONFIG)
