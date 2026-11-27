import json
import re

import requests

from api.utils import normalize_iam_v4_gateway_url

from .model import ModelSnapshot, normalize_model, valid_id

SYSTEMS_PATH = "/api/v1/open/rbac/model/systems/"
PAGE_SIZE = 100
_ID = r"[a-z][a-z0-9_-]{0,31}"
_COLLECTION = r"(?:resource-types|actions|roles)"
_SYSTEM = rf"{SYSTEMS_PATH}{_ID}/"
_CHILD = rf"{_SYSTEM}{_COLLECTION}/{_ID}/"
_ROLE_ACTIONS = rf"{_SYSTEM}roles/{_ID}/actions/"
_MUTATIONS = {
    "POST": re.compile(rf"(?:{SYSTEMS_PATH}|{_SYSTEM}{_COLLECTION}/|{_ROLE_ACTIONS})"),
    "PUT": re.compile(rf"(?:{_SYSTEM}|{_CHILD})"),
    "DELETE": re.compile(rf"(?:{_CHILD}|{_ROLE_ACTIONS})"),
}
_SAFE_MARKER = re.compile(r"[a-zA-Z0-9_.:-]{1,100}")


class ModelAPIError(Exception):
    """An IAM model operation did not produce a trustworthy result."""


class ModelClient:
    """Use application credentials for model management, independently of runtime IAM clients."""

    def __init__(self, gateway_url: str, app_code: str, app_secret: str, tenant_id: str | None, *, session=None):
        self.gateway_url = normalize_iam_v4_gateway_url(gateway_url)
        if not app_code or not app_secret:
            raise ValueError("IAM model application credentials are missing")
        self._secret = app_secret
        self._headers = {
            "X-Bkapi-Authorization": json.dumps({"bk_app_code": app_code, "bk_app_secret": app_secret}),
        }
        if tenant_id:
            if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", tenant_id):
                raise ValueError("invalid model management tenant ID")
            self._headers["X-Bk-Tenant-Id"] = tenant_id
        self._session = requests.Session() if session is None else session

    def _marker(self, value) -> str:
        return value if isinstance(value, str) and _SAFE_MARKER.fullmatch(value) and self._secret not in value else "-"

    def _request(self, method, path, *, json_body=None, params=None, allow_missing_system=False):
        kwargs = {"headers": self._headers, "timeout": (5, 25), "allow_redirects": False}
        if params:
            kwargs["params"] = params
        if json_body is not None:
            kwargs["json"] = json_body
        try:
            response = self._session.request(method, self.gateway_url + path, **kwargs)
        except requests.RequestException:
            raise ModelAPIError(f"{method} {path}: IAM gateway transport failed; result is unknown") from None
        status = response.status_code
        if status == 204 and method != "GET" and not response.content:
            return None
        try:
            body = response.json()
        except ValueError:
            raise ModelAPIError(f"{method} {path}: HTTP {status}, invalid IAM JSON response") from None
        if not isinstance(body, dict):
            raise ModelAPIError(f"{method} {path}: HTTP {status}, invalid IAM response envelope")
        problem = body.get("error")
        code = problem.get("code") if isinstance(problem, dict) else body.get("code")
        request_id = self._marker(body.get("request_id") or response.headers.get("X-Request-Id"))
        if allow_missing_system and status == 404 and isinstance(problem, dict) and code == "NOT_FOUND":
            return None
        if (
            not 200 <= status < 300
            or problem
            or body.get("result") is False
            or body.get("code") not in (None, 0, "0")
            or "data" not in body
        ):
            raise ModelAPIError(
                f"{method} {path}: HTTP {status}, IAM code {self._marker(code)}, request_id={request_id}"
            )
        if method == "GET" and not isinstance(body["data"], dict):
            raise ModelAPIError(f"GET {path}: invalid IAM model data, request_id={request_id}")
        return body["data"]

    def _list(self, path: str) -> list:
        page, expected = 1, None
        rows = {}
        while True:
            data = self._request("GET", path, params={"page": page, "page_size": PAGE_SIZE})
            count, items = data.get("count"), data.get("results")
            if (
                type(count) is not int
                or count < 0
                or (expected is not None and count != expected)
                or not isinstance(items, list)
                or len(items) != min(PAGE_SIZE, count - len(rows))
            ):
                raise ModelAPIError(f"GET {path}: incomplete or changed pagination")
            expected = count
            for item in items:
                if not isinstance(item, dict) or not valid_id(item.get("id")) or item["id"] in rows:
                    raise ModelAPIError(f"GET {path}: invalid or duplicate row ID")
                rows[item["id"]] = item
            if len(rows) == count:
                return list(rows.values())
            page += 1

    def fetch(self, system_id: str) -> ModelSnapshot | None:
        if not valid_id(system_id):
            raise ValueError("invalid IAM system ID")
        path = f"{SYSTEMS_PATH}{system_id}/"
        system = self._request("GET", path, allow_missing_system=True)
        if system is None:
            return None
        if system.get("id") != system_id:
            raise ModelAPIError(f"GET {path}: response system ID does not match target")
        payload = {"system": system}
        for name in ("resource_types", "actions", "roles"):
            payload[name] = self._list(path + name.replace("_", "-") + "/")
        try:
            return normalize_model(payload, strict=False)
        except ValueError as exc:
            raise ModelAPIError(f"GET {path}: remote model cannot be reconciled ({exc})") from None

    def mutate(self, method: str, path: str, *, json_body=None, params=None) -> None:
        """Execute a model-only operation. Cascade and system deletion are never supported."""
        if method not in _MUTATIONS or not _MUTATIONS[method].fullmatch(path):
            raise ValueError("unsupported IAM model operation")
        is_role_action_delete = method == "DELETE" and re.fullmatch(_ROLE_ACTIONS, path)
        if is_role_action_delete:
            if set(params or {}) != {"ids"} or not all(valid_id(i) for i in params["ids"].split(",")):
                raise ValueError("deleting role actions requires only exact action IDs")
        elif params:
            raise ValueError("query parameters are not allowed on this IAM model operation")
        if method == "DELETE" and json_body is not None:
            raise ValueError("IAM V4 deletes do not accept a body")
        self._request(method, path, json_body=json_body, params=params)
