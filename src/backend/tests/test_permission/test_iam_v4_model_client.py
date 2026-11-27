import json
from unittest.mock import Mock

import pytest
from requests import Response

from apps.permission.iam_v4_model.client import ModelAPIError, ModelClient

GATEWAY = "https://gateway.example.test/api/bkiam/prod"
BASE = "/api/v1/open/rbac/model/systems/"
SYSTEM = {
    "id": "bk-audit",
    "name": "Audit",
    "description": "",
    "callback_url": "",
    "clients": ["audit"],
    "managers": [],
}


def reply(status, body=None):
    response = Response()
    response.status_code = status
    response._content = b"" if body is None else json.dumps(body).encode()
    return response


def page(count, results):
    return reply(200, {"data": {"count": count, "results": results}})


def client_with(*responses, tenant_id="system"):
    session = Mock()
    session.request.side_effect = responses
    return ModelClient(GATEWAY, "audit", "opaque-app-secret", tenant_id, session=session), session


@pytest.mark.parametrize("tenant_id", ["system", None])
def test_model_read_uses_explicit_gateway_app_auth_and_tenant(tenant_id):
    client, session = client_with(
        reply(200, {"data": SYSTEM}), page(0, []), page(0, []), page(0, []), tenant_id=tenant_id
    )
    assert client.fetch("bk-audit").system["id"] == "bk-audit"
    assert [call.args[1] for call in session.request.call_args_list] == [
        GATEWAY + BASE + "bk-audit/",
        GATEWAY + BASE + "bk-audit/resource-types/",
        GATEWAY + BASE + "bk-audit/actions/",
        GATEWAY + BASE + "bk-audit/roles/",
    ]
    for call in session.request.call_args_list:
        assert call.args[0] == "GET"
        assert call.kwargs["allow_redirects"] is False
        assert call.kwargs.get("verify", True) is True
        assert "json" not in call.kwargs
        headers = call.kwargs["headers"]
        assert headers.get("X-Bk-Tenant-Id") == tenant_id
        assert json.loads(headers["X-Bkapi-Authorization"]) == {
            "bk_app_code": "audit",
            "bk_app_secret": "opaque-app-secret",
        }


def test_documented_missing_system_is_not_a_gateway_404():
    client, _ = client_with(reply(404, {"error": {"code": "NOT_FOUND"}, "request_id": "call-1"}))
    assert client.fetch("bk-audit") is None


@pytest.mark.parametrize(
    "response",
    [
        reply(403, {"error": {"code": "NOT_FOUND"}, "request_id": "call-1"}),
        reply(404, {"code": 404, "message": "route not found"}),
        reply(302),
        reply(200, {"result": False, "data": SYSTEM}),
        reply(200, {"data": {**SYSTEM, "id": "another_system"}}),
    ],
)
def test_failed_or_wrong_system_lookup_never_becomes_empty_model(response):
    client, _ = client_with(response)
    with pytest.raises(ModelAPIError):
        client.fetch("bk-audit")


def test_reads_all_pages_of_resources():
    resources = [{"id": f"type_{i}", "name": f"Type {i}", "ancestors": []} for i in range(101)]
    client, session = client_with(
        reply(200, {"data": SYSTEM}), page(101, resources[:100]), page(101, resources[100:]), page(0, []), page(0, [])
    )
    assert "type_100" in client.fetch("bk-audit").resource_types
    assert session.request.call_args_list[2].kwargs["params"] == {"page": 2, "page_size": 100}


@pytest.mark.parametrize(
    "response",
    [page(1, []), page(2, [{"id": "r", "name": "R"}] * 2), page(1, [{"id": "r", "name": "R"}])],
)
def test_missing_or_partial_role_associations_are_rejected(response):
    client, _ = client_with(reply(200, {"data": SYSTEM}), page(0, []), page(0, []), response)
    with pytest.raises(ModelAPIError):
        client.fetch("bk-audit")


def test_mutation_accepts_204_and_redacts_failure():
    client, session = client_with(
        reply(204), reply(400, {"error": {"code": "DENIED", "message": "opaque-app-secret"}, "request_id": "call-2"})
    )
    path = BASE + "bk-audit/roles/my_role/actions/"
    client.mutate("DELETE", path, params={"ids": "old_action"})
    assert session.request.call_args.kwargs["params"] == {"ids": "old_action"}
    with pytest.raises(ModelAPIError, match="call-2") as failure:
        client.mutate("DELETE", path, params={"ids": "old_action"})
    assert "opaque-app-secret" not in str(failure.value)


def test_client_refuses_cascade_and_unmanaged_paths_without_sending_requests():
    client, session = client_with()
    with pytest.raises(ValueError):
        client.mutate("DELETE", BASE + "bk-audit/")
    with pytest.raises(ValueError):
        client.mutate(
            "DELETE", BASE + "bk-audit/roles/r/actions/", params={"ids": "a", "cascade": "rbac_authorization"}
        )
    with pytest.raises(ValueError):
        client.mutate("DELETE", BASE + "bk-audit/../other_system/actions/a/")
    session.request.assert_not_called()


@pytest.mark.parametrize(
    "resources,actions,roles,missing",
    [
        ([{"id": "r", "name": "R"}], [], [], "ancestors"),
        ([], [{"id": "a", "name": "A"}], [], "resource_type_id"),
        ([], [], [{"id": "r", "name": "R", "actions": []}], "description"),
        (
            [],
            [{"id": "a", "name": "A", "resource_type_id": ""}],
            [{"id": "r", "name": "R", "description": "", "actions": [{"id": "a"}]}],
            "resource_type_id",
        ),
    ],
)
def test_remote_omits_required_managed_fields_instead_of_returning_empty_values(resources, actions, roles, missing):
    client, _ = client_with(
        reply(200, {"data": SYSTEM}),
        page(len(resources), resources),
        page(len(actions), actions),
        page(len(roles), roles),
    )
    with pytest.raises(ModelAPIError, match=missing):
        client.fetch("bk-audit")
