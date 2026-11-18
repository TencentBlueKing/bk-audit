# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from django.urls import resolve
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.permission.handlers.actions import ActionEnum
from services.web.risk.models import Risk, TicketPermission, UserType
from services.web.scene.constants import BindingType, ResourceVisibilityType
from services.web.scene.models import ResourceBinding, ResourceBindingScene, Scene
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


@override_settings(ROOT_URLCONF="services.web.urls")
class TestReportPreviewPermissions(TestCase):
    """编辑或同场景创建能力与样本可见性同时满足，才允许渲染。"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.allowed = set()
        self.checks = []
        self.scene = Scene.objects.create(name="synthetic-preview-scene")
        self.other_scene = Scene.objects.create(name="synthetic-other-preview-scene")
        self.strategy = Strategy.objects.create(namespace=self.namespace, strategy_name="synthetic-preview-strategy")
        self.other_strategy = Strategy.objects.create(
            namespace=self.namespace, strategy_name="synthetic-other-strategy"
        )
        self.binding = self._bind(self.strategy, self.scene)
        self._bind(self.other_strategy, self.other_scene)
        self.risk = Risk.objects.create(
            risk_id="synthetic-preview-risk",
            title="synthetic sample",
            strategy=self.strategy,
            event_time=timezone.now(),
        )
        self.other_risk = Risk.objects.create(
            risk_id="synthetic-other-risk",
            title="other sample",
            strategy=self.other_strategy,
            event_time=timezone.now(),
        )
        self.enterContext(
            patch("apps.permission.handlers.drf.PermissionService.is_allowed", side_effect=self._is_allowed)
        )
        self.task = self.enterContext(
            patch(
                "services.web.risk.report.task_submitter.render_template.delay",
                return_value=SimpleNamespace(id="synthetic-preview-task"),
            )
        )
        self.payload = {
            "risk_id": self.risk.risk_id,
            "report_config": {"template": "safe preview marker", "ai_variables": []},
        }

    @staticmethod
    def _bind(strategy, scene):
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.STRATEGY,
            resource_id=str(strategy.strategy_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene=scene)
        return binding

    def _grant(self, action, resource_type=None, resource_id=None):
        self.allowed.add((action.id, resource_type, str(resource_id) if resource_id is not None else None))

    def _is_allowed(self, action, resources=None, raise_exception=False):
        resources = resources or []
        self.checks.append((action.id, [(r.type, str(r.id)) for r in resources]))
        allowed = (
            all((action.id, r.type, str(r.id)) in self.allowed for r in resources)
            if resources
            else (action.id, None, None) in self.allowed
        )
        if not allowed and raise_exception:
            raise PermissionDenied("synthetic permission denied")
        return allowed

    def _post(self, query=""):
        path = f"/api/v1/namespaces/{self.namespace}/report/preview/"
        match = resolve(path)
        request = self.factory.post(path + query, deepcopy(self.payload), format="json")
        force_authenticate(request, user=SimpleNamespace(username="preview-user", is_authenticated=True))
        return match.func(request, **match.kwargs)

    def _grant_risk(self):
        self._grant(ActionEnum.LIST_RISK, "risk", self.risk.risk_id)

    def _grant_edit(self):
        self._grant(ActionEnum.EDIT_STRATEGY, "strategy", self.strategy.strategy_id)

    def _assert_allowed(self):
        response = self._post()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {"task_id": "synthetic-preview-task", "status": "PENDING"})
        self.task.assert_called_once()

    def _assert_denied(self, query="", status=403):
        response = self._post(query)
        self.assertEqual(response.status_code, status, response.data)
        self.task.assert_not_called()

    def test_editor_with_visible_sample_can_preview(self):
        self._grant_risk()
        self._grant_edit()
        self._assert_allowed()

    def test_clone_creator_does_not_need_source_edit_permission(self):
        self._grant_risk()
        self._grant(ActionEnum.CREATE_STRATEGY, "scene", self.scene.scene_id)
        self._assert_allowed()
        self.assertIn((ActionEnum.CREATE_STRATEGY.id, [("scene", str(self.scene.scene_id))]), self.checks)

    def test_editor_without_sample_visibility_is_denied(self):
        self._grant_edit()
        self._assert_denied()

    def test_clone_creator_without_sample_visibility_is_denied(self):
        self._grant(ActionEnum.CREATE_STRATEGY, "scene", self.scene.scene_id)
        self._assert_denied()

    def test_visible_sample_alone_is_insufficient(self):
        self._grant_risk()
        self._assert_denied()

    def test_creator_in_another_scene_is_denied(self):
        self._grant_risk()
        self._grant(ActionEnum.CREATE_STRATEGY, "scene", self.other_scene.scene_id)
        self.payload.update(scene_id=self.other_scene.scene_id, mode="clone", is_superuser=True, swagger_fake_view=True)
        self._assert_denied()

    def test_local_risk_visibility_is_preserved(self):
        TicketPermission.objects.create(
            risk_id=self.risk.risk_id,
            user="preview-user",
            user_type=UserType.NOTICE_USER,
            action=ActionEnum.LIST_RISK.id,
        )
        self._grant_edit()
        self._assert_allowed()

    def test_query_risk_cannot_authorize_another_body_risk(self):
        self._grant_risk()
        self._grant_edit()
        self.payload["risk_id"] = self.other_risk.risk_id
        self._assert_denied(query=f"?risk_id={self.risk.risk_id}")

    def test_query_risk_cannot_override_authorized_body_risk(self):
        self._grant_risk()
        self._grant_edit()
        response = self._post(query=f"?risk_id={self.other_risk.risk_id}")
        self.assertEqual(response.status_code, 200, response.data)
        self.task.assert_called_once()
        self.assertEqual(self.task.call_args.kwargs["variables"]["risk"]["risk_id"], self.risk.risk_id)

    def test_platform_clone_requires_platform_action(self):
        self.binding.binding_type = BindingType.PLATFORM_BINDING
        self.binding.save(update_fields=["binding_type"])
        self._grant_risk()
        self._grant(ActionEnum.MANAGE_PLATFORM)
        self._assert_allowed()

    def test_platform_visible_scene_is_not_an_owning_scene(self):
        self.binding.binding_type = BindingType.PLATFORM_BINDING
        self.binding.save(update_fields=["binding_type"])
        self._grant_risk()
        self._grant(ActionEnum.CREATE_STRATEGY, "scene", self.scene.scene_id)
        self._assert_denied()

    def test_missing_risk_does_not_submit(self):
        self.payload["risk_id"] = "synthetic-missing-risk"
        self._assert_denied(status=404)

    def test_missing_strategy_does_not_submit(self):
        Risk.objects.filter(pk=self.risk.pk).update(strategy_id=999999)
        self._grant_risk()
        self._assert_denied(status=404)

    def test_deleted_risk_does_not_submit(self):
        self.risk.delete()
        self._grant_risk()
        self._grant_edit()
        self._assert_denied(status=404)

    def test_deleted_strategy_does_not_submit(self):
        self.strategy.delete()
        self._grant_risk()
        self._grant_edit()
        self._assert_denied(status=404)

    def test_strategy_in_another_namespace_does_not_submit(self):
        self.strategy.namespace = "synthetic-other-namespace"
        self.strategy.save(update_fields=["namespace"])
        self._grant_risk()
        self._grant_edit()
        self._assert_denied(status=404)

    def test_missing_binding_does_not_submit(self):
        self.binding.delete()
        self._grant_risk()
        self._grant_edit()
        self._assert_denied(status=404)

    def test_deleted_scene_does_not_submit(self):
        self.scene.delete()
        self._grant_risk()
        self._grant_edit()
        self._assert_denied(status=404)

    def test_multiple_owning_scenes_are_not_accepted(self):
        ResourceBindingScene.objects.create(binding=self.binding, scene=self.other_scene)
        self._grant_risk()
        self._grant_edit()
        self._assert_denied(status=404)

    def test_metadata_routes_remain_available_without_business_grants(self):
        for endpoint in ["risk_variables", "aggregation_functions"]:
            path = f"/api/v1/namespaces/{self.namespace}/report/{endpoint}/"
            match = resolve(path)
            request = self.factory.get(path)
            force_authenticate(request, user=SimpleNamespace(username="preview-user", is_authenticated=True))
            response = match.func(request, **match.kwargs)
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.checks, [])
        self.task.assert_not_called()

    def test_openapi_generation_does_not_require_a_preview_sample(self):
        schema = SchemaGenerator(urlconf="services.web.strategy_v2.urls").get_schema(public=True)
        preview = schema["paths"]["/namespaces/{namespace}/report/preview/"]["post"]
        self.assertIn("requestBody", preview)
        self.assertEqual(self.checks, [])
        self.task.assert_not_called()
