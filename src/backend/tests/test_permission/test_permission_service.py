# -*- coding: utf-8 -*-
import datetime
from unittest import mock

from django.test import SimpleTestCase, override_settings
from iam import Resource

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.service import PermissionService
from services.web.risk.constants import RiskStatus
from services.web.risk.models import Risk
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.filters import BindingMetadataHelper
from services.web.scene.models import Scene
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestPermissionService(SimpleTestCase):
    @override_settings(IAM_PERMISSION_BACKEND="v3")
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_v3_backend_is_default(self, mock_permission):
        mock_permission.return_value.is_allowed.return_value = True

        result = PermissionService(username="admin").is_allowed(ActionEnum.MANAGE_PLATFORM)

        self.assertTrue(result)
        mock_permission.return_value.is_allowed.assert_called_once()

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    def test_v4_backend_selected_by_setting(self, mock_v4):
        mock_v4.return_value.has_action_any_permission.return_value = True

        result = PermissionService(username="admin").has_action_any_permission(ActionEnum.MANAGE_PLATFORM)

        self.assertTrue(result)
        mock_v4.return_value.has_action_any_permission.assert_called_once_with(ActionEnum.MANAGE_PLATFORM)

    @override_settings(
        IAM_PERMISSION_BACKEND="v3",
        IAM_V4_SHADOW_COMPARE=True,
        IAM_V4_SHADOW_SAMPLE_RATE=100,
    )
    @mock.patch("apps.permission.handlers.service.logger")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_shadow_compare_logs_difference_without_changing_v3_result(self, mock_permission, mock_v4, mock_logger):
        mock_permission.return_value.is_allowed.return_value = True
        mock_v4.return_value.is_allowed.return_value = False

        result = PermissionService(username="admin").is_allowed(ActionEnum.MANAGE_PLATFORM)

        self.assertTrue(result)
        mock_logger.warning.assert_called_once()

    @override_settings(
        IAM_PERMISSION_BACKEND="v3",
        IAM_V4_SHADOW_COMPARE=True,
        IAM_V4_SHADOW_SAMPLE_RATE=100,
    )
    @mock.patch("apps.permission.handlers.service.logger")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_shadow_compare_exception_does_not_change_v3_result(self, mock_permission, mock_v4, mock_logger):
        mock_permission.return_value.has_action_any_permission.return_value = True
        mock_v4.return_value.has_action_any_permission.side_effect = RuntimeError("v4 unavailable")

        result = PermissionService(username="admin").has_action_any_permission(ActionEnum.MANAGE_PLATFORM)

        self.assertTrue(result)
        mock_logger.exception.assert_called_once()

    @override_settings(
        IAM_PERMISSION_BACKEND="v3",
        IAM_V4_SHADOW_COMPARE=True,
        IAM_V4_SHADOW_SAMPLE_RATE=100,
    )
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_shadow_compare_does_not_call_v4_for_write_methods(self, mock_permission, mock_v4):
        resource = mock.MagicMock()
        mock_permission.return_value.grant_creator_action.return_value = None

        PermissionService(username="admin").grant_creator_action(resource)

        mock_permission.return_value.grant_creator_action.assert_called_once_with(resource)
        mock_v4.return_value.grant_creator_action.assert_not_called()

    @override_settings(
        IAM_PERMISSION_BACKEND="v3",
        IAM_V4_SHADOW_COMPARE=True,
        IAM_V4_SHADOW_SAMPLE_RATE=100,
    )
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_shadow_compare_forces_raise_exception_false(self, mock_permission, mock_v4):
        mock_permission.return_value.is_allowed.return_value = True
        mock_v4.return_value.is_allowed.return_value = False

        result = PermissionService(username="admin").is_allowed(ActionEnum.MANAGE_PLATFORM, raise_exception=True)

        self.assertTrue(result)
        mock_v4.return_value.is_allowed.assert_called_once_with(ActionEnum.MANAGE_PLATFORM, raise_exception=False)

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    def test_v4_grant_creator_action_raises_by_default(self, mock_v4):
        resource = mock.MagicMock()

        PermissionService(username="admin").grant_creator_action(resource)

        mock_v4.return_value.grant_creator_action.assert_called_once_with(resource, raise_exception=True)


class TestPermissionServiceShadowResourceIds(SimpleTestCase):
    @override_settings(
        IAM_PERMISSION_BACKEND="v3",
        IAM_V4_SHADOW_COMPARE=True,
        IAM_V4_SHADOW_SAMPLE_RATE=100,
    )
    @mock.patch("apps.permission.handlers.service.logger")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_shadow_get_authorized_resource_ids_logs_mismatch(self, mock_permission, mock_v4, mock_logger):
        mock_permission.return_value.get_policies_for_action.return_value = None
        mock_v4.return_value.get_authorized_resource_ids.return_value = ["1"]

        result = PermissionService(username="admin").get_authorized_resource_ids(ActionEnum.VIEW_SCENE, "scene")

        self.assertEqual(result, [])
        mock_v4.return_value.get_authorized_resource_ids.assert_called_once()
        mock_logger.warning.assert_called_once()

    @override_settings(
        IAM_PERMISSION_BACKEND="v3",
        IAM_V4_SHADOW_COMPARE=True,
        IAM_V4_SHADOW_SAMPLE_RATE=100,
    )
    @mock.patch("apps.permission.handlers.service.logger")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_shadow_get_authorized_resource_ids_exception_does_not_change_v3(
        self, mock_permission, mock_v4, mock_logger
    ):
        mock_permission.return_value.get_policies_for_action.return_value = None
        mock_v4.return_value.get_authorized_resource_ids.side_effect = RuntimeError("v4 down")

        result = PermissionService(username="admin").get_authorized_resource_ids(ActionEnum.VIEW_SCENE, "scene")

        self.assertEqual(result, [])
        mock_logger.exception.assert_called_once()


class TestPermissionServiceV3FilterRegression(SimpleTestCase):
    @override_settings(IAM_PERMISSION_BACKEND="v3")
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_v3_filter_authorized_resources_uses_v3_batch(self, mock_permission):
        allowed = Resource("bk-audit", "strategy", "100", {"name": "allowed"})
        denied = Resource("bk-audit", "strategy", "200", {"name": "denied"})
        mock_permission.return_value.batch_is_allowed.return_value = {
            "100": {ActionEnum.EDIT_STRATEGY.id: True},
            "200": {ActionEnum.EDIT_STRATEGY.id: False},
        }

        result = PermissionService(username="admin").filter_authorized_resources(
            ActionEnum.EDIT_STRATEGY,
            "strategy",
            [allowed, denied],
        )

        self.assertEqual(result, [allowed])
        mock_permission.return_value.batch_is_allowed.assert_called_once()


class TestPermissionServiceScopeResolver(SimpleTestCase):
    @override_settings(IAM_PERMISSION_BACKEND="v4")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    def test_v4_top_level_resource_ids_use_reverse_lookup(self, mock_v4):
        mock_v4.return_value.get_authorized_resource_ids.return_value = ["1", "2"]

        result = PermissionService(username="admin").get_authorized_resource_ids(ActionEnum.VIEW_SCENE, "scene")

        self.assertEqual(result, ["1", "2"])
        mock_v4.return_value.get_authorized_resource_ids.assert_called_once_with(ActionEnum.VIEW_SCENE, "scene")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    def test_v4_secondary_resource_ids_without_candidates_return_empty(self, mock_v4):
        result = PermissionService(username="admin").get_authorized_resource_ids(ActionEnum.EDIT_STRATEGY, "strategy")

        self.assertEqual(result, [])
        mock_v4.return_value.get_authorized_resource_ids.assert_not_called()


class TestPermissionServiceCandidateFiltering(SimpleTestCase):
    @override_settings(IAM_PERMISSION_BACKEND="v4")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    def test_filter_authorized_resources_uses_batch_auth_for_strategy_candidates(self, mock_v4):
        allowed = Resource("bk-audit", "strategy", "100", {"name": "allowed"})
        denied = Resource("bk-audit", "strategy", "200", {"name": "denied"})
        mock_v4.return_value.batch_is_allowed.return_value = {
            "100": {ActionEnum.EDIT_STRATEGY.id: True},
            "200": {ActionEnum.EDIT_STRATEGY.id: False},
        }

        result = PermissionService(username="admin").filter_authorized_resources(
            ActionEnum.EDIT_STRATEGY,
            "strategy",
            [allowed, denied],
        )

        self.assertEqual(result, [allowed])
        mock_v4.return_value.batch_is_allowed.assert_called_once_with(
            [ActionEnum.EDIT_STRATEGY],
            [[allowed], [denied]],
        )

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission")
    def test_get_authorized_resource_ids_uses_candidate_filtering_for_strategy(self, mock_v4):
        resource = Resource("bk-audit", "strategy", "100", {"name": "strategy"})
        mock_v4.return_value.batch_is_allowed.return_value = {"100": {ActionEnum.EDIT_STRATEGY.id: True}}

        result = PermissionService(username="admin").get_authorized_resource_ids(
            ActionEnum.EDIT_STRATEGY,
            "strategy",
            candidates=[resource],
        )

        self.assertEqual(result, ["100"])


class TestPermissionServiceRiskFilter(TestCase):
    @override_settings(IAM_PERMISSION_BACKEND="v3")
    @mock.patch("services.web.risk.converter.queryset.RiskPathEqDjangoQuerySetConverter")
    @mock.patch("apps.permission.handlers.permission.Permission")
    def test_v3_risk_filter_uses_policy_converter(self, mock_permission, mock_converter):
        mock_permission.return_value.make_request.return_value = mock.sentinel.request
        mock_permission.return_value.iam_client._do_policy_query.return_value = {"some": "policy"}
        mock_converter.return_value.convert.return_value = mock.sentinel.risk_filter

        result = PermissionService(username="admin").get_risk_filter(ActionEnum.LIST_RISK)

        self.assertEqual(result, mock.sentinel.risk_filter)
        mock_permission.return_value.make_request.assert_called_once()
        mock_permission.return_value.iam_client._do_policy_query.assert_called_once_with(mock.sentinel.request)

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission.get_authorized_resource_ids")
    def test_v4_risk_filter_uses_authorized_scene_bindings(self, mock_scene_ids):
        scene = Scene.objects.create(name="risk-v4-scene")
        bound_strategy = Strategy.objects.create(
            strategy_id=9101,
            strategy_name="risk-v4-bound-strategy",
            risk_level=RiskLevel.HIGH.value,
        )
        other_strategy = Strategy.objects.create(
            strategy_id=9102,
            strategy_name="risk-v4-other-strategy",
            risk_level=RiskLevel.HIGH.value,
        )
        BindingMetadataHelper.create_resource_binding(
            resource_id=str(bound_strategy.strategy_id),
            resource_type=ResourceVisibilityType.STRATEGY,
            scene_id=scene.scene_id,
        )
        bound_risk = Risk.objects.create(
            risk_id="R-V4-BOUND",
            title="bound-risk",
            strategy=bound_strategy,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        Risk.objects.create(
            risk_id="R-V4-OTHER",
            title="other-risk",
            strategy=other_strategy,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
        )
        mock_scene_ids.return_value = [str(scene.scene_id)]

        q = PermissionService(username="admin").get_risk_filter(ActionEnum.LIST_RISK)

        self.assertEqual(list(Risk.objects.filter(q).values_list("risk_id", flat=True)), [bound_risk.risk_id])
        mock_scene_ids.assert_called_once_with(ActionEnum.VIEW_SCENE, "scene")

    @override_settings(IAM_PERMISSION_BACKEND="v4")
    @mock.patch("apps.permission.handlers.iam_v4.IAMV4Permission.get_authorized_resource_ids")
    def test_v4_risk_filter_empty_scene_scope_returns_empty_q(self, mock_scene_ids):
        mock_scene_ids.return_value = []

        q = PermissionService(username="admin").get_risk_filter(ActionEnum.LIST_RISK)

        self.assertFalse(Risk.objects.filter(q).exists())
        mock_scene_ids.assert_called_once_with(ActionEnum.VIEW_SCENE, "scene")
