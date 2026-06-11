# -*- coding: utf-8 -*-
from typing import List, Sequence, Union

from blueapps.utils.logger import logger
from django.db.models import Q
from iam import Resource

from apps.permission.handlers.actions import ActionEnum, ActionMeta, get_action_by_id

TOP_LEVEL_REVERSE_LOOKUP_RESOURCE_TYPES = {"scene", "system", "tag"}
SECONDARY_BATCH_RESOURCE_TYPES = {"strategy", "link_table", "notice_group"}
RISK_RESOURCE_TYPE = "risk"


class AuthorizationScopeResolver:
    """Resolve V4 range authorization without secondary-resource reverse lookup."""

    def __init__(self, service):
        self.service = service

    def get_authorized_resource_ids(
        self,
        action: Union[ActionMeta, str],
        resource_type: str,
        candidates: Sequence[Resource] = None,
    ) -> List[str]:
        action = get_action_by_id(action)
        if resource_type in TOP_LEVEL_REVERSE_LOOKUP_RESOURCE_TYPES:
            return self.service.v4.get_authorized_resource_ids(action, resource_type)
        if resource_type in SECONDARY_BATCH_RESOURCE_TYPES:
            resources = self.filter_authorized_resources(action, resource_type, candidates or [])
            return [str(resource.id) for resource in resources]
        return []

    def filter_authorized_resources(
        self,
        action: Union[ActionMeta, str],
        resource_type: str,
        candidates: Sequence[Resource],
    ) -> List[Resource]:
        action = get_action_by_id(action)
        if resource_type not in SECONDARY_BATCH_RESOURCE_TYPES:
            return []
        resources = [resource for resource in candidates if resource.type == resource_type]
        if not resources:
            return []
        batch_result = self.service.v4.batch_is_allowed([action], [[resource] for resource in resources])
        return [resource for resource in resources if batch_result.get(str(resource.id), {}).get(action.id, False)]

    def get_risk_filter(self) -> Q:
        from services.web.scene.constants import ResourceVisibilityType
        from services.web.scene.models import ResourceBindingScene

        scene_ids = self.service.v4.get_authorized_resource_ids(ActionEnum.VIEW_SCENE, "scene")
        if not scene_ids:
            return Q(pk__in=[])
        raw_strategy_ids = ResourceBindingScene.objects.filter(
            scene_id__in=scene_ids,
            scene__is_deleted=False,
            binding__resource_type=ResourceVisibilityType.STRATEGY,
        ).values_list("binding__resource_id", flat=True)
        strategy_ids = []
        for strategy_id in raw_strategy_ids:
            try:
                strategy_ids.append(int(strategy_id))
            except (TypeError, ValueError):
                logger.warning("[PermissionService] skip invalid strategy id from scene binding: %s", strategy_id)
        if not strategy_ids:
            return Q(pk__in=[])
        return Q(strategy_id__in=strategy_ids)
