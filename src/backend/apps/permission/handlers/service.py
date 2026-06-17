# -*- coding: utf-8 -*-
from typing import Any, List, Optional, Sequence, Union

from blueapps.utils.logger import logger
from django.conf import settings
from django.db.models import Q
from iam import Resource

from apps.permission.handlers.actions import ActionMeta, get_action_by_id
from apps.permission.handlers.backends import is_iam_v4_backend
from apps.permission.handlers.resource_types import get_resource_by_id
from apps.permission.handlers.scope_resolver import AuthorizationScopeResolver

SHADOW_COMPARE_METHODS = {"is_allowed", "batch_is_allowed", "has_action_any_permission", "get_authorized_resource_ids"}


class PermissionService:
    """Business-facing permission facade for IAM V3/V4 migration."""

    def __init__(self, username: str = "", request=None) -> None:
        self.username = username
        self.request = request
        self._v3 = None
        self._v4 = None

    @property
    def v3(self) -> Any:
        if self._v3 is None:
            from apps.permission.handlers.permission import Permission

            self._v3 = (
                Permission(username=self.username, request=self.request)
                if self.username
                else Permission(request=self.request)
            )
        return self._v3

    @property
    def v4(self) -> Any:
        if self._v4 is None:
            from apps.permission.handlers.iam_v4 import IAMV4Permission

            self._v4 = IAMV4Permission(username=self.username, request=self.request)
        return self._v4

    @property
    def active_backend(self) -> Any:
        return self.v4 if is_iam_v4_backend() else self.v3

    @property
    def scope_resolver(self) -> AuthorizationScopeResolver:
        """V4 range queries need business strategies beyond IAM's top-level reverse lookup."""
        return AuthorizationScopeResolver(self)

    def _shadow_enabled(self) -> bool:
        # Shadow only runs when V3 is the source of truth; V4 errors must never affect V3 responses.
        if is_iam_v4_backend():
            return False
        if not getattr(settings, "IAM_V4_SHADOW_COMPARE", False):
            return False
        sample_rate = int(getattr(settings, "IAM_V4_SHADOW_SAMPLE_RATE", 0))
        if sample_rate <= 0:
            return False
        if sample_rate >= 100:
            return True
        from random import randint

        return randint(1, 100) <= sample_rate

    def _call(self, method_name: str, *args, **kwargs) -> Any:
        result = getattr(self.active_backend, method_name)(*args, **kwargs)
        if self._shadow_enabled() and method_name in SHADOW_COMPARE_METHODS and hasattr(self.v4, method_name):
            self._shadow_compare(method_name, result, *args, **kwargs)
        return result

    def _shadow_compare(self, method_name: str, v3_result: Any, *args, **kwargs) -> None:
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
        """Translate V3 policy-query results into concrete top-level resource IDs."""
        if not get_resource_by_id(resource_type).iam_v4_reverse_lookup:
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

    def is_allowed(self, *args, **kwargs) -> bool:
        return self._call("is_allowed", *args, **kwargs)

    def batch_is_allowed(self, *args, **kwargs) -> dict:
        return self._call("batch_is_allowed", *args, **kwargs)

    def has_action_any_permission(self, *args, **kwargs) -> bool:
        return self._call("has_action_any_permission", *args, **kwargs)

    def get_authorized_resource_ids(
        self,
        action: Union[ActionMeta, str],
        resource_type: str,
        candidates: Optional[Sequence[Resource]] = None,
    ) -> List[str]:
        if is_iam_v4_backend():
            return self.scope_resolver.get_authorized_resource_ids(action, resource_type, candidates=candidates)
        result = self._v3_authorized_resource_ids(action, resource_type)
        if self._shadow_enabled():
            self._shadow_compare("get_authorized_resource_ids", result, action, resource_type)
        return result

    def filter_authorized_resources(
        self,
        action: Union[ActionMeta, str],
        resource_type: str,
        candidates: Sequence[Resource],
    ) -> List[Resource]:
        """Filter candidate resources without exposing V3/V4 strategy differences to callers."""
        action = get_action_by_id(action)
        if is_iam_v4_backend():
            return self.scope_resolver.filter_authorized_resources(action, resource_type, candidates)
        batch_result = self.v3.batch_is_allowed(actions=[action], resources=[[resource] for resource in candidates])
        return [resource for resource in candidates if batch_result.get(str(resource.id), {}).get(action.id, False)]

    def get_sensitive_object_permissions(self, sensitive_object_ids: List[str]) -> dict[str, bool]:
        """Return per-sensitive-object visibility while hiding V3/V4 model differences."""
        from apps.permission.handlers.actions import ActionEnum
        from apps.permission.handlers.resource_types import ResourceEnum

        action = ActionEnum.ACCESS_AUDIT_SENSITIVE_INFO
        sensitive_object_ids = [str(sensitive_object_id) for sensitive_object_id in sensitive_object_ids]
        if is_iam_v4_backend():
            allowed = self.is_allowed(action, resources=[])
            return {sensitive_object_id: allowed for sensitive_object_id in sensitive_object_ids}

        resources = [
            [ResourceEnum.SENSITIVE_OBJECT.create_instance(sensitive_object_id)]
            for sensitive_object_id in sensitive_object_ids
        ]
        batch_result = self.batch_is_allowed(actions=[action], resources=resources)
        return {
            sensitive_object_id: batch_result.get(sensitive_object_id, {}).get(action.id, False)
            for sensitive_object_id in sensitive_object_ids
        }

    def get_risk_filter(self, action: Union[ActionMeta, str]) -> Q:
        action = get_action_by_id(action)
        if is_iam_v4_backend():
            return self.scope_resolver.get_risk_filter()

        from services.web.risk.converter.queryset import (
            RiskPathEqDjangoQuerySetConverter,
        )

        request = self.v3.make_request(action=action, resources=[])
        policies = self.v3.iam_client._do_policy_query(request)
        if policies:
            return RiskPathEqDjangoQuerySetConverter().convert(policies)
        return Q(pk__in=[])

    def get_apply_data(self, *args, **kwargs) -> Any:
        return self._call("get_apply_data", *args, **kwargs)

    def get_policies_for_action(self, *args, **kwargs) -> Any:
        """V3-only escape hatch for first-wave excluded policy-query scenarios."""
        return self.v3.get_policies_for_action(*args, **kwargs)

    def make_request(self, *args, **kwargs) -> Any:
        """V3-only escape hatch for first-wave excluded policy-query scenarios."""
        return self.v3.make_request(*args, **kwargs)

    @property
    def iam_client(self) -> Any:
        """V3-only IAM SDK client for resource callbacks and excluded policy-query scenarios."""
        return self.v3.iam_client

    def grant_creator_action(self, *args, **kwargs) -> Any:
        if is_iam_v4_backend() and "raise_exception" not in kwargs:
            kwargs["raise_exception"] = True
        return self._call("grant_creator_action", *args, **kwargs)

    def grant_instance_permission(self, *args, **kwargs) -> Any:
        return self._call("grant_instance_permission", *args, **kwargs)

    def revoke_instance_permission(self, *args, **kwargs) -> Any:
        return self._call("revoke_instance_permission", *args, **kwargs)

    def list_role_subjects(self, *args, **kwargs) -> List[dict]:
        return self._call("list_role_subjects", *args, **kwargs)

    @classmethod
    def make_resource(cls, *args, **kwargs) -> Any:
        from apps.permission.handlers.permission import Permission

        return Permission.make_resource(*args, **kwargs)

    @classmethod
    def batch_make_resource(cls, *args, **kwargs) -> Any:
        from apps.permission.handlers.permission import Permission

        return Permission.batch_make_resource(*args, **kwargs)
