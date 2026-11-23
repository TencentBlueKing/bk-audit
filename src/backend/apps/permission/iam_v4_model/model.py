import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
MODEL_KEYS = {"system", "resource_types", "actions", "roles"}


@dataclass(frozen=True)
class ModelSnapshot:
    system: dict
    resource_types: dict[str, dict]
    actions: dict[str, dict]
    roles: dict[str, dict]

    def document(self) -> dict:
        data = asdict(self)
        for key in ("resource_types", "actions", "roles"):
            data[key] = list(data[key].values())
        return data


def valid_id(value) -> bool:
    return isinstance(value, str) and ID_RE.fullmatch(value) is not None


def _unique_keys(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate JSON key")
        data[key] = value
    return data


def _fields(item, required, optional, *, strict):
    if not isinstance(item, dict) or not required <= item.keys():
        raise ValueError(f"incomplete model item: expected {', '.join(sorted(required))}")
    if strict and (unknown := item.keys() - required - optional):
        raise ValueError(f"unsupported model fields: {', '.join(sorted(unknown))}")
    if item.get("tenant_id"):
        raise ValueError("tenant-specific model items are not supported by the global migration")


def _string(value, field, optional=False):
    if not isinstance(value, str) or (not optional and not value.strip()) or "${" in value or "{{" in value:
        raise ValueError(f"invalid or unresolved {field}")
    return value


def _list(value, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _index(items, transform, label):
    result = {}
    names = set()
    for item in _list(items, label):
        entry = transform(item)
        item_id = entry["id"]
        if not valid_id(item_id) or item_id in result:
            raise ValueError(f"invalid or duplicate {label} ID")
        if "name" in entry:
            name = entry["name"].casefold()
            if name in names:
                raise ValueError(f"duplicate {label} name")
            names.add(name)
        result[item_id] = entry
    return dict(sorted(result.items()))


def _names(values, field):
    return sorted({_string(value, field).strip() for value in _list(values, field)})


def normalize_model(data: dict, *, strict: bool) -> ModelSnapshot:
    """Normalize managed fields without interpreting absent collections as empty."""
    _fields(data, MODEL_KEYS, set(), strict=strict)
    system = data["system"]
    system_keys = {"id", "name", "clients", "managers", "callback_url"}
    _fields(system, system_keys if strict else system_keys | {"description"}, {"description"}, strict=strict)
    if not valid_id(system["id"]):
        raise ValueError("invalid IAM system ID")
    system = {
        "id": system["id"],
        "name": _string(system["name"], "system.name"),
        "description": _string(system.get("description", ""), "system.description", optional=True),
        "clients": _names(system["clients"], "clients"),
        "managers": _names(system["managers"], "managers"),
        "callback_url": _string(system["callback_url"], "callback_url", optional=not strict),
    }

    def resource(item):
        required = {"id", "name"} if strict else {"id", "name", "ancestors"}
        _fields(item, required, {"ancestors"}, strict=strict)
        ancestors = _list(item.get("ancestors", []), "ancestors")
        if not all(valid_id(i) for i in ancestors) or len(set(ancestors)) != len(ancestors):
            raise ValueError("invalid resource ancestors")
        return {"id": item["id"], "name": _string(item["name"], "resource name"), "ancestors": ancestors}

    resources = _index(data["resource_types"], resource, "resource type")
    for resource_id, item in resources.items():
        ancestors = item["ancestors"]
        if resource_id in ancestors or any(
            ancestor not in resources or resources[ancestor]["ancestors"] != ancestors[:i]
            for i, ancestor in enumerate(ancestors)
        ):
            raise ValueError(f"invalid ancestor chain for {resource_id}")

    def action(item, *, role_action=False):
        required = {"id"} if role_action else {"id", "name"}
        if not strict:
            required.add("resource_type_id")
        _fields(item, required, {"resource_type_id"}, strict=strict)
        scope = item.get("resource_type_id", "")
        if not isinstance(scope, str) or (scope and (not valid_id(scope) or scope not in resources)):
            raise ValueError("invalid or unknown action resource type")
        entry = {"id": item["id"], "resource_type_id": scope}
        if not role_action:
            entry["name"] = _string(item["name"], "action name")
        return entry

    actions = _index(data["actions"], action, "action")

    def role(item):
        required = {"id", "name", "actions"} if strict else {"id", "name", "actions", "description"}
        _fields(item, required, {"description"}, strict=strict)
        role_actions = list(_index(item["actions"], lambda row: action(row, role_action=True), "role action").values())
        scopes = {}
        for entry in role_actions:
            declared = actions.get(entry["id"])
            if declared is None:
                raise ValueError(f"unknown action in role {item['id']}")
            bound = declared["resource_type_id"]
            scope = entry["resource_type_id"]
            valid_scopes = [bound, *resources[bound]["ancestors"]] if bound else [""]
            if scope not in valid_scopes or scopes.setdefault(bound, scope) != scope:
                raise ValueError(f"invalid or inconsistent resource scope in role {item['id']}")
        return {
            "id": item["id"],
            "name": _string(item["name"], "role name"),
            "description": _string(item.get("description", ""), "role description", optional=True),
            "actions": role_actions,
        }

    return ModelSnapshot(system, resources, actions, _index(data["roles"], role, "role"))


def load_model(
    path: Path,
    *,
    system_id: str,
    app_code: str,
    callback_url: str,
    clients: list[str],
    managers: list[str],
    system_name: str | None = None,
) -> ModelSnapshot:
    """Render only the deployment-specific system fields, keeping roles and actions as authored."""
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    _fields(data, MODEL_KEYS, set(), strict=True)
    system = data["system"]
    _fields(system, {"id", "name"}, {"description", "clients", "managers", "callback_url"}, strict=True)
    if system["id"] not in (system_id, "${SYSTEM_ID}") or not valid_id(system_id):
        raise ValueError("model system ID does not match BKAPP_IAM_SYSTEM_ID")
    url = urlsplit(callback_url)
    if (
        url.scheme != "https"
        or not url.hostname
        or not url.path
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
    ):
        raise ValueError("callback_url must be a complete HTTPS endpoint without credentials or query")
    system.update(
        id=system_id,
        name=system["name"] if system_name is None else system_name,
        callback_url=callback_url,
        clients=[_string(app_code, "app_code"), *clients],
        managers=managers,
    )
    return normalize_model(data, strict=True)
