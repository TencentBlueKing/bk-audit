# -*- coding: utf-8 -*-
from unittest import mock

from django.test import SimpleTestCase, override_settings
from iam import Resource

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.iam_v4 import IAMV4Permission


class TestIAMV4Permission(SimpleTestCase):
    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.direct_auth")
    def test_is_allowed_calls_direct_auth_with_resource(self, mock_direct_auth):
        mock_direct_auth.return_value = {"allowed": True}
        resource = Resource("bk-audit", "scene", "100", {"name": "scene-100"})

        result = IAMV4Permission(username="admin").is_allowed(ActionEnum.VIEW_SCENE, [resource])

        self.assertTrue(result)
        mock_direct_auth.assert_called_once_with(
            system_id="bk-audit",
            subject={"type": "user", "id": "admin"},
            action_id=ActionEnum.VIEW_SCENE.id,
            resource={"type": "scene", "id": "100"},
        )

    def test_resource_to_v4_skips_invalid_path_node(self):
        resource = Resource("bk-audit", "strategy", "100", {"_bk_iam_path_": "/invalid/scene,1/"})

        result = IAMV4Permission._resource_to_v4(resource)

        self.assertEqual(result, {"type": "strategy", "id": "100", "ancestors": [{"type": "scene", "id": "1"}]})

    def test_resource_to_v4_skips_empty_path_node(self):
        resource = Resource("bk-audit", "strategy", "100", {"_bk_iam_path_": "/scene,/system,bklog/"})

        result = IAMV4Permission._resource_to_v4(resource)

        self.assertEqual(result, {"type": "strategy", "id": "100", "ancestors": [{"type": "system", "id": "bklog"}]})

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.direct_auth")
    def test_is_allowed_requires_all_resources_allowed(self, mock_direct_auth):
        mock_direct_auth.side_effect = [{"allowed": True}, {"allowed": False}]
        resources = [
            Resource("bk-audit", "tag", "1", {"name": "tag-1"}),
            Resource("bk-audit", "tag", "2", {"name": "tag-2"}),
        ]

        result = IAMV4Permission(username="admin").is_allowed(ActionEnum.VIEW_TAG_PANEL, resources)

        self.assertFalse(result)
        self.assertEqual(mock_direct_auth.call_count, 2)

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.direct_auth")
    def test_is_allowed_calls_direct_auth_without_resource_for_global_action(self, mock_direct_auth):
        mock_direct_auth.return_value = {"allowed": False}

        result = IAMV4Permission(username="admin").is_allowed(ActionEnum.MANAGE_PLATFORM)

        self.assertFalse(result)
        mock_direct_auth.assert_called_once_with(
            system_id="bk-audit",
            subject={"type": "user", "id": "admin"},
            action_id=ActionEnum.MANAGE_PLATFORM.id,
            resource=None,
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.direct_auth")
    def test_is_allowed_ignores_resources_for_global_action(self, mock_direct_auth):
        mock_direct_auth.return_value = {"allowed": True}
        resource = Resource("bk-audit", "scene", "100", {"name": "scene-100"})

        result = IAMV4Permission(username="admin").is_allowed(ActionEnum.MANAGE_PLATFORM, [resource])

        self.assertTrue(result)
        mock_direct_auth.assert_called_once_with(
            system_id="bk-audit",
            subject={"type": "user", "id": "admin"},
            action_id=ActionEnum.MANAGE_PLATFORM.id,
            resource=None,
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.direct_auth")
    def test_sensitive_info_is_no_resource_action_in_v4(self, mock_direct_auth):
        mock_direct_auth.return_value = {"allowed": True}
        resource = Resource("bk-audit", "sensitive_object", "so-1", {"name": "secret"})

        result = IAMV4Permission(username="admin").is_allowed(
            ActionEnum.ACCESS_AUDIT_SENSITIVE_INFO,
            [resource],
        )

        self.assertTrue(result)
        mock_direct_auth.assert_called_once_with(
            system_id="bk-audit",
            subject={"type": "user", "id": "admin"},
            action_id=ActionEnum.ACCESS_AUDIT_SENSITIVE_INFO.id,
            resource=None,
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.list_authorized_resource")
    def test_get_authorized_resource_ids_filters_top_level_resource_type(self, mock_list):
        mock_list.return_value = [
            {"type": "scene", "ids": ["1", "2"]},
            {"type": "system", "ids": ["bk_log"]},
        ]

        result = IAMV4Permission(username="admin").get_authorized_resource_ids(ActionEnum.VIEW_SCENE, "scene")

        self.assertEqual(result, ["1", "2"])
        mock_list.assert_called_once_with(
            system_id="bk-audit",
            subject={"type": "user", "id": "admin"},
            action_id=ActionEnum.VIEW_SCENE.id,
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch.object(IAMV4Permission, "_list_all_resource_ids", return_value=["1", "2"])
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.list_authorized_resource")
    def test_get_authorized_resource_ids_expands_wildcard(self, mock_list, _mock_all_ids):
        mock_list.return_value = [{"type": "scene", "ids": ["*"]}]

        result = IAMV4Permission(username="admin").get_authorized_resource_ids(ActionEnum.VIEW_SCENE, "scene")

        self.assertEqual(result, ["1", "2"])

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.list_authorized_resource")
    def test_has_action_any_permission_does_not_reverse_lookup_secondary_resources(self, mock_list):
        mock_list.return_value = [{"type": "scene", "ids": ["100"]}]

        result = IAMV4Permission(username="admin").has_action_any_permission(ActionEnum.EDIT_STRATEGY)

        self.assertFalse(result)
        mock_list.assert_not_called()

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.list_authorized_resource")
    def test_has_action_any_permission_uses_scene_dimension_for_risk(self, mock_list):
        mock_list.return_value = [{"type": "scene", "ids": ["100"]}]

        result = IAMV4Permission(username="admin").has_action_any_permission(ActionEnum.LIST_RISK)

        self.assertTrue(result)
        mock_list.assert_called_once_with(
            system_id="bk-audit",
            subject={"type": "user", "id": "admin"},
            action_id=ActionEnum.LIST_RISK.id,
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.direct_auth_by_resources")
    def test_batch_is_allowed_uses_resource_batch_api(self, mock_by_resources):
        mock_by_resources.side_effect = [
            [{"resource_id": "100", "allowed": True}, {"resource_id": "200", "allowed": False}],
            [{"resource_id": "100", "allowed": False}, {"resource_id": "200", "allowed": True}],
        ]
        resources = [
            [Resource("bk-audit", "scene", "100", {"name": "scene-100"})],
            [Resource("bk-audit", "scene", "200", {"name": "scene-200"})],
        ]

        result = IAMV4Permission(username="admin").batch_is_allowed(
            [ActionEnum.VIEW_SCENE, ActionEnum.MANAGE_SCENE],
            resources,
        )

        self.assertEqual(
            result,
            {
                "100": {ActionEnum.VIEW_SCENE.id: True, ActionEnum.MANAGE_SCENE.id: False},
                "200": {ActionEnum.VIEW_SCENE.id: False, ActionEnum.MANAGE_SCENE.id: True},
            },
        )
        self.assertEqual(mock_by_resources.call_count, 2)
        mock_by_resources.assert_any_call(
            system_id="bk-audit",
            subject={"type": "user", "id": "admin"},
            action_id=ActionEnum.VIEW_SCENE.id,
            resources=[{"type": "scene", "id": "100"}, {"type": "scene", "id": "200"}],
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.direct_auth_by_actions")
    def test_batch_is_allowed_keeps_action_batch_api_for_empty_resource(self, mock_by_actions):
        mock_by_actions.return_value = [{"action_id": ActionEnum.MANAGE_PLATFORM.id, "allowed": True}]

        result = IAMV4Permission(username="admin").batch_is_allowed(
            [ActionEnum.MANAGE_PLATFORM],
            [[]],
        )

        self.assertEqual(result, {"": {ActionEnum.MANAGE_PLATFORM.id: True}})
        mock_by_actions.assert_called_once_with(
            system_id="bk-audit",
            subject={"type": "user", "id": "admin"},
            action_ids=[ActionEnum.MANAGE_PLATFORM.id],
            resource=None,
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit", IAM_V4_AUTHORIZATION_EXPIRED_DAYS=365)
    @mock.patch("apps.permission.handlers.iam_v4.time.time", return_value=1000)
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.add_authorization")
    def test_grant_instance_permission_posts_role_authorization(self, mock_add, _mock_time):
        resource = Resource("bk-audit", "scene", "100", {"name": "scene-100"})

        IAMV4Permission(username="admin").grant_instance_permission(
            role_id="scene_admin",
            subject={"type": "user", "id": "tom"},
            resources=[resource],
            operator="admin",
        )

        mock_add.assert_called_once_with(
            system_id="bk-audit",
            operator="admin",
            authorizations=[
                {
                    "role_id": "scene_admin",
                    "subject": {"type": "user", "id": "tom"},
                    "related_resource_type_id": "scene",
                    "resources": [{"type": "scene", "id": "100"}],
                    "expired_at": 31537000,
                }
            ],
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.generate_perm_apply_url")
    def test_get_apply_data_uses_v4_apply_url(self, mock_apply_url):
        mock_apply_url.return_value = {"url": "https://iam.example/apply"}

        data, url = IAMV4Permission(username="admin").get_apply_data([ActionEnum.MANAGE_PLATFORM])

        self.assertEqual(url, "https://iam.example/apply")
        self.assertEqual(data["system_id"], "bk-audit")
        mock_apply_url.assert_called_once_with(
            system_id="bk-audit",
            permissions=[{"action_id": ActionEnum.MANAGE_PLATFORM.id}],
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.generate_perm_apply_url")
    def test_sensitive_info_apply_data_is_no_resource_in_v4(self, mock_apply_url):
        mock_apply_url.return_value = {"url": "https://iam.example/apply"}
        resource = Resource("bk-audit", "sensitive_object", "so-1", {"name": "secret"})

        _data, url = IAMV4Permission(username="admin").get_apply_data(
            [ActionEnum.ACCESS_AUDIT_SENSITIVE_INFO],
            [resource],
        )

        self.assertEqual(url, "https://iam.example/apply")
        mock_apply_url.assert_called_once_with(
            system_id="bk-audit",
            permissions=[{"action_id": ActionEnum.ACCESS_AUDIT_SENSITIVE_INFO.id}],
        )

    @override_settings(BK_IAM_SYSTEM_ID="bk-audit", IAM_V4_AUTHORIZATION_EXPIRED_DAYS=365)
    @mock.patch("services.web.scene.models.ResourceBindingScene.objects.filter")
    @mock.patch("apps.permission.handlers.iam_v4.api.bk_iam_v4.add_authorization")
    def test_grant_creator_action_uses_bound_scene_admin_for_strategy(self, mock_add, mock_filter):
        mock_filter.return_value.values_list.return_value.first.return_value = "100"
        resource = Resource("bk-audit", "strategy", "200", {"name": "strategy-200"})

        IAMV4Permission(username="creator").grant_creator_action(resource)

        self.assertEqual(mock_add.call_args.kwargs["authorizations"][0]["role_id"], "scene_admin")
        self.assertEqual(mock_add.call_args.kwargs["authorizations"][0]["subject"], {"type": "user", "id": "creator"})
        self.assertEqual(mock_add.call_args.kwargs["authorizations"][0]["related_resource_type_id"], "scene")
        self.assertEqual(mock_add.call_args.kwargs["authorizations"][0]["resources"], [{"type": "scene", "id": "100"}])
