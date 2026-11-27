import hashlib
import json
from dataclasses import asdict, dataclass

from .client import SYSTEMS_PATH
from .model import ModelSnapshot


@dataclass(frozen=True)
class Step:
    operation: str
    kind: str
    ids: tuple[str, ...]
    method: str
    path: str
    body: dict | list | None = None
    params: dict | None = None

    @property
    def label(self) -> str:
        return f"{self.operation} {self.kind} {','.join(self.ids)}"


@dataclass(frozen=True)
class MigrationPlan:
    steps: tuple[Step, ...]
    blocked: tuple[str, ...]
    digest: str


def _changed_fields(wanted, existing, fields):
    return {key: wanted[key] for key in fields if wanted[key] != existing[key]}


def _by_depth(items, keys):
    return sorted(keys, key=lambda item_id: (len(items[item_id]["ancestors"]), item_id))


def _name_conflicts(kind, desired, existing):
    owners = {item["name"].casefold(): item_id for item_id, item in existing.items()}
    for item_id, item in sorted(desired.items()):
        owner = owners.get(item["name"].casefold())
        if owner is not None and owner != item_id:
            yield f"{kind} {item_id}: name currently belongs to {owner}; rename or retire it in a separate change"


def _role_scopes(entries, actions):
    return {actions[item_id]["resource_type_id"]: entry["resource_type_id"] for item_id, entry in entries.items()}


def build_plan(
    target: ModelSnapshot, current: ModelSnapshot | None, *, gateway_url: str, tenant_id: str | None
) -> MigrationPlan:
    """只对比权限模型并生成执行计划，不调用 IAM。"""
    system_id = target.system["id"]
    if current is not None and system_id != current.system["id"]:
        raise ValueError("cannot reconcile snapshots for different IAM systems")
    root = f"{SYSTEMS_PATH}{system_id}/"
    steps, blocked = [], []
    if current is None:
        steps.append(Step("create", "system", (system_id,), "POST", SYSTEMS_PATH, target.system))
        old_resources, old_actions, old_roles = {}, {}, {}
    else:
        metadata = _changed_fields(
            target.system, current.system, ("name", "description", "clients", "managers", "callback_url")
        )
        if metadata:
            steps.append(Step("update", "system", (system_id,), "PUT", root, metadata))
        old_resources, old_actions, old_roles = current.resource_types, current.actions, current.roles

    resources, actions, roles = target.resource_types, target.actions, target.roles
    for kind, desired, existing in (
        ("resource_type", resources, old_resources),
        ("action", actions, old_actions),
        ("role", roles, old_roles),
    ):
        blocked.extend(_name_conflicts(kind, desired, existing))
    resource_path, action_path, role_path = (root + segment for segment in ("resource-types/", "actions/", "roles/"))
    for item_id in _by_depth(resources, resources.keys() - old_resources.keys()):
        steps.append(Step("create", "resource_type", (item_id,), "POST", resource_path, [resources[item_id]]))
    for item_id in sorted(resources.keys() & old_resources.keys()):
        item, old = resources[item_id], old_resources[item_id]
        if item["ancestors"] != old["ancestors"]:
            blocked.append(f"resource_type {item_id}: changing ancestry requires an authorization impact review")
        elif item["name"] != old["name"]:
            steps.append(
                Step("update", "resource_type", (item_id,), "PUT", f"{resource_path}{item_id}/", {"name": item["name"]})
            )

    for item_id in sorted(actions.keys() - old_actions.keys()):
        steps.append(Step("create", "action", (item_id,), "POST", action_path, [actions[item_id]]))
    old_role_action_ids = {action["id"] for role in old_roles.values() for action in role["actions"]}
    for item_id in sorted(actions.keys() & old_actions.keys()):
        item, old = actions[item_id], old_actions[item_id]
        path = f"{action_path}{item_id}/"
        if item["resource_type_id"] != old["resource_type_id"]:
            # IAM 不支持直接修改操作绑定的资源类型；有角色引用时不能删后重建。
            if item_id in old_role_action_ids:
                blocked.append(f"action {item_id}: recreation required, but an existing role still references it")
            else:
                steps.append(Step("recreate-remove", "action", (item_id,), "DELETE", path))
                steps.append(Step("recreate-create", "action", (item_id,), "POST", action_path, [item]))
        elif item["name"] != old["name"]:
            steps.append(Step("update", "action", (item_id,), "PUT", path, {"name": item["name"]}))

    for item_id in sorted(roles.keys() - old_roles.keys()):
        steps.append(Step("create", "role", (item_id,), "POST", role_path, [roles[item_id]]))
    for role_id in sorted(roles.keys() & old_roles.keys()):
        role, old = roles[role_id], old_roles[role_id]
        path = f"{role_path}{role_id}/"
        metadata = _changed_fields(role, old, ("name", "description"))
        if metadata:
            steps.append(Step("update", "role", (role_id,), "PUT", path, metadata))
        old_entries = {entry["id"]: entry for entry in old["actions"]}
        entries = {entry["id"]: entry for entry in role["actions"]}
        before_scopes = _role_scopes(old_entries, old_actions)
        after_scopes = _role_scopes(entries, actions)
        if any(before_scopes[k] != after_scopes[k] for k in before_scopes.keys() & after_scopes.keys()):
            blocked.append(f"role {role_id}: changing authorization scope requires IAM review")
        for item_id in sorted(entries.keys() & old_entries.keys()):
            if entries[item_id] != old_entries[item_id]:
                blocked.append(f"role_action {role_id}/{item_id}: changing authorization scope requires IAM review")
        add_ids = sorted(entries.keys() - old_entries.keys())
        if add_ids:
            steps.append(
                Step(
                    "create",
                    "role_action",
                    tuple(f"{role_id}/{i}" for i in add_ids),
                    "POST",
                    path + "actions/",
                    [entries[i] for i in add_ids],
                )
            )
        remove_ids = sorted(old_entries.keys() - entries.keys())
        if remove_ids:
            # 模型接口无法判断是否已有授权，因此不移除某种资源类型下的最后一个操作。
            if before_scopes.keys() - after_scopes.keys() or set(before_scopes.values()) - set(after_scopes.values()):
                blocked.append(f"role {role_id}: removing its last action for a resource type requires IAM review")
            else:
                steps.append(
                    Step(
                        "delete",
                        "role_action",
                        tuple(f"{role_id}/{i}" for i in remove_ids),
                        "DELETE",
                        path + "actions/",
                        params={"ids": ",".join(remove_ids)},
                    )
                )

    # 先删依赖方、后删被引用方，不级联；如有线上授权，交由 IAM 拒绝删除。
    for kind, path, ids in (
        ("role", role_path, sorted(old_roles.keys() - roles.keys())),
        ("action", action_path, sorted(old_actions.keys() - actions.keys())),
        ("resource_type", resource_path, reversed(_by_depth(old_resources, old_resources.keys() - resources.keys()))),
    ):
        for item_id in ids:
            steps.append(Step("delete", kind, (item_id,), "DELETE", f"{path}{item_id}/"))

    fingerprint = json.dumps(
        {
            "gateway": gateway_url,
            "tenant": tenant_id,
            "current": asdict(current) if current is not None else None,
            "target": asdict(target),
            "steps": [asdict(step) for step in steps],
            "blocked": blocked,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return MigrationPlan(tuple(steps), tuple(blocked), hashlib.sha256(fingerprint.encode("utf-8")).hexdigest())
