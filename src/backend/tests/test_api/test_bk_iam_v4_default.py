# -*- coding: utf-8 -*-
from unittest import mock

from bk_resource.exceptions import APIRequestError, ValidateException
from django.test import SimpleTestCase
from requests.exceptions import HTTPError

from api.bk_iam_v4.default import (
    AddAuthorizationResource,
    BatchCreateRoleResource,
    DeleteRoleResource,
    DirectAuthByActionsResource,
    DirectAuthByResourcesResource,
    DirectAuthResource,
    GeneratePermApplyUrlResource,
    ListAuthorizationSubjectResource,
    ListAuthorizedResourceResource,
    RetrieveSystemResource,
    RevokeAuthorizationResource,
)


def _mock_response(data):
    response = mock.MagicMock()
    response.json.return_value = {"data": data, "request_id": "request-id"}
    response.raise_for_status.return_value = None
    response.request.url = "http://bkiam.test"
    return response


class TestIAMV4AuthResources(SimpleTestCase):
    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_direct_auth_uses_system_path_and_body(self, _mock_build_header):
        resource = DirectAuthResource()
        resource.session.request = mock.Mock(return_value=_mock_response({"allowed": True}))

        result = resource.request(
            {
                "system_id": "bk-audit",
                "subject": {"type": "user", "id": "admin"},
                "action_id": "manage_platform",
                "resource": {"type": "scene", "id": "scene-1"},
            }
        )

        self.assertEqual(result, {"allowed": True})
        kwargs = resource.session.request.call_args.kwargs
        self.assertEqual(kwargs["method"], "POST")
        self.assertTrue(kwargs["url"].endswith("/api/v1/open/rbac/authorization/systems/bk-audit/auth/"))
        self.assertNotIn("system_id", kwargs["json"])
        self.assertEqual(kwargs["json"]["subject"], {"type": "user", "id": "admin"})
        self.assertEqual(kwargs["json"]["action_id"], "manage_platform")
        self.assertEqual(kwargs["json"]["resource"], {"type": "scene", "id": "scene-1"})

    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_error_response_keeps_iam_v4_error_message(self, _mock_build_header):
        resource = DirectAuthResource()
        response = mock.MagicMock(status_code=400)
        response.json.return_value = {"error": {"code": "INVALID_REQUEST", "message": "action not found"}}
        response.raise_for_status.side_effect = HTTPError(response=response)
        response.request.url = "http://bkiam.test"
        resource.session.request = mock.Mock(return_value=response)

        with self.assertRaises(APIRequestError) as ctx:
            resource.request(
                {
                    "system_id": "bk-audit",
                    "subject": {"type": "user", "id": "admin"},
                    "action_id": "unknown_action",
                }
            )

        self.assertEqual(ctx.exception.data["code"], "INVALID_REQUEST")
        self.assertEqual(ctx.exception.data["message"], "action not found")

    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_direct_auth_by_actions_uses_action_ids_body(self, _mock_build_header):
        resource = DirectAuthByActionsResource()
        resource.session.request = mock.Mock(
            return_value=_mock_response([{"action_id": "view_scene", "allowed": True}])
        )

        resource.request(
            {
                "system_id": "bk-audit",
                "subject": {"type": "user", "id": "admin"},
                "action_ids": ["view_scene", "manage_scene"],
                "resource": {"type": "scene", "id": "scene-1"},
            }
        )

        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(kwargs["url"].endswith("/api/v1/open/rbac/authorization/systems/bk-audit/auth-by-actions/"))
        self.assertNotIn("system_id", kwargs["json"])
        self.assertEqual(kwargs["json"]["action_ids"], ["view_scene", "manage_scene"])

    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_direct_auth_by_resources_uses_resources_body(self, _mock_build_header):
        resource = DirectAuthByResourcesResource()
        resource.session.request = mock.Mock(return_value=_mock_response([{"resource_id": "scene-1", "allowed": True}]))

        resource.request(
            {
                "system_id": "bk-audit",
                "subject": {"type": "user", "id": "admin"},
                "action_id": "view_scene",
                "resources": [{"type": "scene", "id": "scene-1"}],
            }
        )

        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(kwargs["url"].endswith("/api/v1/open/rbac/authorization/systems/bk-audit/auth-by-resources/"))
        self.assertNotIn("system_id", kwargs["json"])
        self.assertEqual(kwargs["json"]["resources"], [{"type": "scene", "id": "scene-1"}])

    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_list_authorized_resource_uses_relation_endpoint(self, _mock_build_header):
        resource = ListAuthorizedResourceResource()
        resource.session.request = mock.Mock(return_value=_mock_response([{"type": "scene", "ids": ["scene-1"]}]))

        result = resource.request(
            {
                "system_id": "bk-audit",
                "subject": {"type": "user", "id": "admin"},
                "action_id": "view_scene",
            }
        )

        self.assertEqual(result, [{"type": "scene", "ids": ["scene-1"]}])
        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(
            kwargs["url"].endswith("/api/v1/open/rbac/authorization/systems/bk-audit/relation/authorized-resources/")
        )
        self.assertNotIn("system_id", kwargs["json"])


class TestIAMV4RoleResources(SimpleTestCase):
    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_batch_create_role_posts_roles(self, _mock_build_header):
        resource = BatchCreateRoleResource()
        resource.session.request = mock.Mock(return_value=_mock_response(["scene_admin"]))

        resource.request(
            {
                "system_id": "bk-audit",
                "roles": [
                    {
                        "id": "scene_admin",
                        "name": "场景管理员",
                        "actions": [{"id": "view_scene", "resource_type_id": "scene"}],
                    }
                ],
            }
        )

        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(kwargs["url"].endswith("/api/v1/open/rbac/model/systems/bk-audit/roles/"))
        self.assertEqual(kwargs["json"][0]["id"], "scene_admin")
        self.assertEqual(kwargs["json"][0]["actions"], [{"id": "view_scene", "resource_type_id": "scene"}])

    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_delete_role_returns_none_on_no_content(self, _mock_build_header):
        resource = DeleteRoleResource()
        response = mock.MagicMock(status_code=204, content=b"")
        response.json.side_effect = ValueError("empty")
        response.raise_for_status.return_value = None
        response.request.url = "http://bkiam.test"
        resource.session.request = mock.Mock(return_value=response)

        result = resource.request({"system_id": "bk-audit", "role_id": "scene_admin"})

        self.assertIsNone(result)
        kwargs = resource.session.request.call_args.kwargs
        self.assertEqual(kwargs["method"], "DELETE")
        self.assertTrue(kwargs["url"].endswith("/api/v1/open/rbac/model/systems/bk-audit/roles/scene_admin/"))
        self.assertEqual(kwargs["json"], {})

    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_add_authorization_posts_role_authorizations(self, _mock_build_header):
        resource = AddAuthorizationResource()
        resource.session.request = mock.Mock(return_value=_mock_response(None))

        resource.request(
            {
                "system_id": "bk-audit",
                "operator": "operator_user",
                "authorizations": [
                    {
                        "role_id": "scene_admin",
                        "related_resource_type_id": "scene",
                        "subject": {"type": "user", "id": "admin"},
                        "resources": [{"type": "scene", "id": "scene-1"}],
                        "expired_at": 4102444800,
                    }
                ],
            }
        )

        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(kwargs["url"].endswith("/api/v1/open/rbac/mgmt/systems/bk-audit/authorizations/"))
        self.assertNotIn("system_id", kwargs["json"][0])
        self.assertNotIn("operator", kwargs["json"][0])
        self.assertEqual(kwargs["json"][0]["role_id"], "scene_admin")

    @mock.patch("api.bk_iam_v4.default.bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME", "system_operator")
    def test_add_authorization_uses_default_operator_header(self):
        resource = AddAuthorizationResource()

        headers = resource.build_header({})

        self.assertEqual(headers["X-Bkiam-Operator"], "system_operator")

    def test_add_authorization_uses_request_operator_header(self):
        resource = AddAuthorizationResource()

        headers = resource.build_header({"operator": "operator_user"})

        self.assertEqual(headers["X-Bkiam-Operator"], "operator_user")

    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_revoke_authorization_deletes_role_authorizations(self, _mock_build_header):
        resource = RevokeAuthorizationResource()
        response = mock.MagicMock(status_code=204, content=b"")
        response.json.side_effect = ValueError("empty")
        response.raise_for_status.return_value = None
        response.request.url = "http://bkiam.test"
        resource.session.request = mock.Mock(return_value=response)

        result = resource.request(
            {
                "system_id": "bk-audit",
                "authorizations": [
                    {
                        "role_id": "scene_admin",
                        "related_resource_type_id": "scene",
                        "subject": {"type": "user", "id": "admin"},
                        "resources": [{"type": "scene", "id": "scene-1"}],
                    }
                ],
            }
        )

        self.assertIsNone(result)
        kwargs = resource.session.request.call_args.kwargs
        self.assertEqual(kwargs["method"], "DELETE")
        self.assertTrue(kwargs["url"].endswith("/api/v1/open/rbac/mgmt/systems/bk-audit/authorizations/"))
        self.assertNotIn("system_id", kwargs["json"][0])
        self.assertEqual(kwargs["json"][0]["role_id"], "scene_admin")

    def test_add_authorization_validates_required_authorizations(self):
        resource = AddAuthorizationResource()

        with self.assertRaises(ValidateException):
            resource.request({"system_id": "bk-audit", "role_id": "scene_admin"})

    @mock.patch("api.bk_iam_v4.default.bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME", "system_operator")
    def test_revoke_authorization_uses_default_operator_header(self):
        resource = RevokeAuthorizationResource()

        headers = resource.build_header({})

        self.assertEqual(headers["X-Bkiam-Operator"], "system_operator")

    def test_revoke_authorization_uses_request_operator_header(self):
        resource = RevokeAuthorizationResource()

        headers = resource.build_header({"operator": "operator_user"})

        self.assertEqual(headers["X-Bkiam-Operator"], "operator_user")

    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_list_authorization_subject_posts_query(self, _mock_build_header):
        resource = ListAuthorizationSubjectResource()
        resource.session.request = mock.Mock(
            return_value=_mock_response({"results": [{"type": "user", "id": "admin"}]})
        )

        resource.request(
            {
                "system_id": "bk-audit",
                "role_id": "scene_admin",
                "related_resource_type_id": "scene",
                "resource": {"type": "scene", "id": "scene-1"},
                "page": 1,
                "page_size": 100,
            }
        )

        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(kwargs["url"].endswith("/api/v1/open/rbac/mgmt/systems/bk-audit/authorizations/query-subject/"))
        self.assertNotIn("system_id", kwargs["json"])
        self.assertEqual(kwargs["json"]["role_id"], "scene_admin")

    def test_list_authorization_subject_strips_operator_from_body(self):
        resource = ListAuthorizationSubjectResource()
        resource.session.request = mock.Mock(return_value=_mock_response({"results": []}))

        resource.request(
            {
                "system_id": "bk-audit",
                "operator": "operator_user",
                "role_id": "scene_admin",
                "page": 1,
                "page_size": 100,
            }
        )

        kwargs = resource.session.request.call_args.kwargs
        self.assertEqual(kwargs["headers"]["X-Bkiam-Operator"], "operator_user")
        self.assertNotIn("operator", kwargs["json"])

    @mock.patch("api.bk_iam_v4.default.bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME", "system_operator")
    def test_list_authorization_subject_uses_default_operator_header(self):
        resource = ListAuthorizationSubjectResource()

        headers = resource.build_header({})

        self.assertEqual(headers["X-Bkiam-Operator"], "system_operator")

    def test_list_authorization_subject_uses_request_operator_header(self):
        resource = ListAuthorizationSubjectResource()

        headers = resource.build_header({"operator": "operator_user"})

        self.assertEqual(headers["X-Bkiam-Operator"], "operator_user")


class TestIAMV4ApplyResource(SimpleTestCase):
    @mock.patch("api.bk_iam_v4.default.IAMV4BaseResource.build_header", return_value={})
    def test_generate_perm_apply_url_posts_body_without_system_path(self, _mock_build_header):
        resource = GeneratePermApplyUrlResource()
        resource.session.request = mock.Mock(return_value=_mock_response({"url": "https://iam.example/apply"}))

        result = resource.request(
            {
                "system_id": "bk-audit",
                "permissions": [
                    {
                        "action_id": "view_scene",
                        "resources": [{"type": "scene", "id": "scene-1"}],
                    }
                ],
            }
        )

        self.assertEqual(result, {"url": "https://iam.example/apply"})
        kwargs = resource.session.request.call_args.kwargs
        self.assertTrue(kwargs["url"].endswith("/api/v1/open/application/permission-apply-urls/"))
        self.assertEqual(kwargs["json"]["system_id"], "bk-audit")
        self.assertEqual(kwargs["json"]["permissions"][0]["action_id"], "view_scene")


class TestIAMV4SystemResources(SimpleTestCase):
    def test_retrieve_system_uses_rabc_path(self):
        resource = RetrieveSystemResource()

        url = resource.build_url({"system_id": "bk-audit"})

        self.assertTrue(url.endswith("/api/v1/open/rabc/share/model/systems/bk-audit/"))

    def test_retrieve_system_accepts_fields_query(self):
        resource = RetrieveSystemResource()
        resource.session.request = mock.Mock(return_value=_mock_response({"system_info": {"id": "bk-audit"}}))

        resource.request({"system_id": "bk-audit", "fields": "system_info"})

        kwargs = resource.session.request.call_args.kwargs
        self.assertEqual(kwargs["params"]["fields"], "system_info")
