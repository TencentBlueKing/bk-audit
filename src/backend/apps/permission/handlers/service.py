# -*- coding: utf-8 -*-
import random
from typing import List, Union

from blueapps.utils.logger import logger
from django.conf import settings
from django.db.models import Q

from apps.permission.handlers.actions import ActionMeta, get_action_by_id
from apps.permission.handlers.scope_resolver import (
    TOP_LEVEL_REVERSE_LOOKUP_RESOURCE_TYPES,
    AuthorizationScopeResolver,
)

SHADOW_COMPARE_METHODS = {"is_allowed", "batch_is_allowed", "has_action_any_permission", "get_authorized_resource_ids"}


class PermissionService:
    """Business-facing permission facade for IAM V3/V4 migration."""

    def __init__(self, username: str = "", request=None):
        self.username = username
        self.request = request
        self.backend_name = getattr(settings, "IAM_PERMISSION_BACKEND", "v3")
        self._v3 = None
        self._v4 = None

    @property
    def v3(self):
        if self._v3 is None:
            from apps.permission.handlers.permission import Permission

            self._v3 = (
                Permission(username=self.username, request=self.request)
                if self.username
                else Permission(request=self.request)
            )
        return self._v3

    @property
    def v4(self):
        if self._v4 is None:
            from apps.permission.handlers.iam_v4 import IAMV4Permission

            self._v4 = IAMV4Permission(username=self.username, request=self.request)
        return self._v4

    @property
    def active_backend(self):
        return self.v4 if self.backend_name == "v4" else self.v3

    @property
    def scope_resolver(self):
        return AuthorizationScopeResolver(self)

    def _shadow_enabled(self) -> bool:
        if self.backend_name != "v3":
            return False
        if not getattr(settings, "IAM_V4_SHADOW_COMPARE", False):
            return False
        sample_rate = int(getattr(settings, "IAM_V4_SHADOW_SAMPLE_RATE", 0))
        if sample_rate <= 0:
            return False
        if sample_rate >= 100:
            return True
        return random.randint(1, 100) <= sample_rate

    def _call(self, method_name: str, *args, **kwargs):
        result = getattr(self.active_backend, method_name)(*args, **kwargs)
        if self._shadow_enabled() and method_name in SHADOW_COMPARE_METHODS and hasattr(self.v4, method_name):
            self._shadow_compare(method_name, result, *args, **kwargs)
        return result

    def _shadow_compare(self, method_name: str, v3_result, *args, **kwargs):
        try:
            shadow_kwargs = dict(kwargs)
            if "raise_exception" in shadow_kwargs:
                shadow_kwargs["raise_exception"] = False
            v4_result = getattr(self.v4, method_name)(*args, **shadow_kwargs)
        except Exception as error:  # pylint: disable=broad-except
            logger.exception(
                "[IAMShadow] V4 shadow call failed, method=%s, args=%s, error=%s", method_name, args, error
            )
            return
        if v3_result != v4_result:
            logger.warning(
                "[IAMShadow] result mismatch, method=%s, username=%s, v3_result=%s, v4_result=%s, args=%s",
                method_name,
                self.username,
                v3_result,
                v4_result,
                args,
            )

    def _v3_authorized_resource_ids(self, action: Union[ActionMeta, str], resource_type: str) -> List[str]:
        if resource_type not in TOP_LEVEL_REVERSE_LOOKUP_RESOURCE_TYPES:
            return []
        action = get_action_by_id(action)
        policies = self.v3.get_policies_for_action(action)
        if not policies:
            return []
        if resource_type == "scene":
            from services.web.scene.converter import SceneDjangoQuerySetConverter
            from services.web.scene.models import Scene

            filters = SceneDjangoQuerySetConverter().convert(policies)
            return [str(scene_id) for scene_id in Scene.objects.filter(filters).values_list("scene_id", flat=True)]
        if resource_type == "system":
            from apps.meta.converter import SystemDjangoQuerySetConverter
            from apps.meta.models import System

            filters = SystemDjangoQuerySetConverter().convert(policies)
            return list(System.objects.filter(filters).values_list("system_id", flat=True))
        if resource_type == "tag":
            from iam import DjangoQuerySetConverter

            from apps.meta.models import Tag

            filters = DjangoQuerySetConverter({"tag.id": "tag_id"}).convert(policies)
            return [str(tag_id) for tag_id in Tag.objects.filter(filters).values_list("tag_id", flat=True)]
        return []

    def is_allowed(self, *args, **kwargs):
        return self._call("is_allowed", *args, **kwargs)

    def batch_is_allowed(self, *args, **kwargs):
        return self._call("batch_is_allowed", *args, **kwargs)

    def has_action_any_permission(self, *args, **kwargs):
        return self._call("has_action_any_permission", *args, **kwargs)

    def get_authorized_resource_ids(self, action, resource_type: str, candidates=None):
        if self.backend_name == "v4":
            return self.scope_resolver.get_authorized_resource_ids(action, resource_type, candidates=candidates)
        result = self._v3_authorized_resource_ids(action, resource_type)
        if self._shadow_enabled():
            self._shadow_compare("get_authorized_resource_ids", result, action, resource_type)
        return result

    def filter_authorized_resources(self, action, resource_type: str, candidates):
        action = get_action_by_id(action)
        if self.backend_name == "v4":
            return self.scope_resolver.filter_authorized_resources(action, resource_type, candidates)
        batch_result = self.v3.batch_is_allowed(actions=[action], resources=[[resource] for resource in candidates])
        return [resource for resource in candidates if batch_result.get(str(resource.id), {}).get(action.id, False)]

    def get_risk_filter(self, action: Union[ActionMeta, str]) -> Q:
        action = get_action_by_id(action)
        if self.backend_name == "v4":
            return self.scope_resolver.get_risk_filter()

        from services.web.risk.converter.queryset import (
            RiskPathEqDjangoQuerySetConverter,
        )

        request = self.v3.make_request(action=action, resources=[])
        policies = self.v3.iam_client._do_policy_query(request)
        if policies:
            return RiskPathEqDjangoQuerySetConverter().convert(policies)
        return Q(pk__in=[])

    def get_apply_data(self, *args, **kwargs):
        return self._call("get_apply_data", *args, **kwargs)

    def get_policies_for_action(self, *args, **kwargs):
        """V3-only escape hatch for first-wave excluded policy-query scenarios."""
        return self.v3.get_policies_for_action(*args, **kwargs)

    def make_request(self, *args, **kwargs):
        """V3-only escape hatch for first-wave excluded policy-query scenarios."""
        return self.v3.make_request(*args, **kwargs)

    @property
    def iam_client(self):
        """V3-only IAM SDK client for resource callbacks and excluded policy-query scenarios."""
        return self.v3.iam_client

    def grant_creator_action(self, *args, **kwargs):
        if self.backend_name == "v4" and "raise_exception" not in kwargs:
            kwargs["raise_exception"] = True
        return self._call("grant_creator_action", *args, **kwargs)

    def grant_instance_permission(self, *args, **kwargs):
        return self._call("grant_instance_permission", *args, **kwargs)

    def revoke_instance_permission(self, *args, **kwargs):
        return self._call("revoke_instance_permission", *args, **kwargs)

    def list_role_subjects(self, *args, **kwargs):
        return self._call("list_role_subjects", *args, **kwargs)

    @classmethod
    def make_resource(cls, *args, **kwargs):
        from apps.permission.handlers.permission import Permission

        return Permission.make_resource(*args, **kwargs)

    @classmethod
    def batch_make_resource(cls, *args, **kwargs):
        from apps.permission.handlers.permission import Permission

        return Permission.batch_make_resource(*args, **kwargs)
