from dataclasses import replace

import pytest

from apps.permission.iam_v4_model.model import normalize_model
from apps.permission.iam_v4_model.reconcile import build_plan

GATEWAY = "https://gateway.example.test/api/bkiam/prod"
GATEWAY_ALT = "https://gateway.example.test/api/bkiam/stage"
BASE = "/api/v1/open/rbac/model/systems/bk-audit/"
SYSTEM = {
    "id": "bk-audit",
    "name": "Audit",
    "callback_url": "https://audit.example.test/api/v1/iam/resources/",
    "clients": ["audit"],
    "managers": [],
}
PARENT = {"id": "parent", "name": "Parent", "ancestors": []}
CHILD = {"id": "child", "name": "Child", "ancestors": ["parent"]}
EDIT = {"id": "edit_child", "name": "Edit child", "resource_type_id": "child"}
VIEW = {"id": "view_child", "name": "View child", "resource_type_id": "child"}
R_EDIT = {"id": "edit_child", "resource_type_id": "parent"}
R_VIEW = {"id": "view_child", "resource_type_id": "parent"}


def snapshot(*, system=SYSTEM, resources=(), actions=(), roles=()):
    return normalize_model(
        {"system": system, "resource_types": list(resources), "actions": list(actions), "roles": list(roles)},
        strict=True,
    )


def plan(target, current):
    return build_plan(target, current, gateway_url=GATEWAY, tenant_id="system")


def test_bootstrap_orders_ancestors_and_references():
    model = snapshot(
        resources=(CHILD, PARENT), actions=(EDIT,), roles=({"id": "admin", "name": "Admin", "actions": [R_EDIT]},)
    )
    creation = plan(model, None)
    assert [(step.kind, step.ids) for step in creation.steps] == [
        ("system", ("bk-audit",)),
        ("resource_type", ("parent",)),
        ("resource_type", ("child",)),
        ("action", ("edit_child",)),
        ("role", ("admin",)),
    ]
    assert not creation.blocked


def test_full_sync_updates_metadata_and_deletes_in_reverse_dependency_order():
    current = snapshot(
        resources=(CHILD, PARENT),
        actions=(EDIT, VIEW, {"id": "plain", "name": "Plain"}),
        roles=(
            {"id": "used", "name": "Used", "actions": [R_EDIT, R_VIEW]},
            {"id": "legacy", "name": "Legacy", "actions": [{"id": "plain"}]},
        ),
    )
    target = snapshot(
        system={**SYSTEM, "name": "New Audit"},
        resources=(PARENT, CHILD),
        actions=(EDIT,),
        roles=({"id": "used", "name": "Renamed", "actions": [R_EDIT]},),
    )
    changes = plan(target, current)
    assert not changes.blocked
    deletes = [step for step in changes.steps if step.method == "DELETE"]
    assert [(step.kind, step.ids) for step in deletes] == [
        ("role_action", ("used/view_child",)),
        ("role", ("legacy",)),
        ("action", ("plain",)),
        ("action", ("view_child",)),
    ]
    assert deletes[0].params == {"ids": "view_child"}
    updates = {step.path: step.body for step in changes.steps if step.method == "PUT"}
    assert updates == {BASE: {"name": "New Audit"}, BASE + "roles/used/": {"name": "Renamed"}}

    removal = plan(snapshot(), current)
    assert [(step.kind, step.ids) for step in removal.steps][-2:] == [
        ("resource_type", ("child",)),
        ("resource_type", ("parent",)),
    ]


@pytest.mark.parametrize("referenced", [True, False])
def test_action_binding_change_requires_recreate_and_refuses_to_drop_existing_bindings(referenced):
    roles = ({"id": "admin", "name": "Admin", "actions": [R_EDIT]},) if referenced else ()
    old = snapshot(resources=(PARENT, CHILD), actions=(EDIT,), roles=roles)
    new = snapshot(resources=(PARENT, CHILD), actions=({**EDIT, "resource_type_id": "parent"},), roles=roles)
    change = plan(new, old)
    if referenced:
        assert "edit_child" in " ".join(change.blocked)
        assert change.steps == ()
    else:
        assert not change.blocked
        assert [(item.method, item.operation) for item in change.steps] == [
            ("DELETE", "recreate-remove"),
            ("POST", "recreate-create"),
        ]


def test_existing_role_may_not_remove_last_action_in_a_resource_scope():
    role = {"id": "admin", "name": "Admin"}
    current = snapshot(resources=(PARENT, CHILD), actions=(EDIT,), roles=({**role, "actions": [R_EDIT]},))
    target = snapshot(resources=(PARENT, CHILD), actions=(EDIT,), roles=({**role, "actions": []},))
    assert "admin" in " ".join(plan(target, current).blocked)


def test_no_change_and_stable_digest():
    target = snapshot(resources=(PARENT, CHILD), actions=(EDIT, VIEW))
    current = replace(target, actions=dict(reversed(list(target.actions.items()))))
    actual = plan(target, current)
    assert actual.steps == ()
    assert actual.digest == plan(target, target).digest
    assert actual.digest != build_plan(target, target, gateway_url=GATEWAY_ALT, tenant_id="system").digest
    assert actual.digest != plan(target, snapshot(resources=(PARENT, CHILD), actions=(EDIT,))).digest


def test_replacing_all_actions_cannot_change_an_existing_roles_scope():
    role = {"id": "admin", "name": "Admin"}
    current = snapshot(resources=(CHILD, PARENT), actions=(EDIT,), roles=({**role, "actions": [R_EDIT]},))
    target = snapshot(
        resources=(CHILD, PARENT),
        actions=(VIEW,),
        roles=({**role, "actions": [{"id": "view_child", "resource_type_id": "child"}]},),
    )
    assert any("admin" in issue and "scope" in issue for issue in plan(target, current).blocked)


@pytest.mark.parametrize("kind", ["resource_type", "action", "role"])
def test_replacing_an_id_cannot_create_a_conflicting_name(kind):
    if kind == "resource_type":
        old = snapshot(resources=(PARENT,))
        new = snapshot(resources=({**PARENT, "id": "replacement"},))
    elif kind == "action":
        old = snapshot(actions=({"id": "old_action", "name": "Same"},))
        new = snapshot(actions=({"id": "new_action", "name": "Same"},))
    else:
        old = snapshot(roles=({"id": "old_role", "name": "Same", "actions": []},))
        new = snapshot(roles=({"id": "new_role", "name": "Same", "actions": []},))
    assert any(kind in issue and "name" in issue for issue in plan(new, old).blocked)
