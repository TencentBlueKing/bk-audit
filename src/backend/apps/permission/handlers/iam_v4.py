# -*- coding: utf-8 -*-
import time
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Union

from bk_resource import api
from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_local_request
from django.conf import settings
from django.utils.translation import gettext
from iam import Resource, Subject
from iam.eval.constants import KEYWORD_BK_IAM_PATH
from iam.utils import gen_perms_apply_data

from apps.permission.handlers.actions import ActionMeta, get_action_by_id
from core.exceptions import PermissionException


def _get_v4_config(name: str, default):
    return getattr(settings, name, default)


TOP_LEVEL_RESOURCE_TYPES = set(_get_v4_config("IAM_V4_TOP_LEVEL_RESOURCE_TYPES", {"scene", "system", "tag"}))
V4_NO_RESOURCE_ACTION_IDS = set(_get_v4_config("IAM_V4_NO_RESOURCE_ACTION_IDS", {"access_audit_sensitive_info"}))
SCENE_AUTH_RESOURCE_TYPES = set(_get_v4_config("IAM_V4_SCENE_AUTH_RESOURCE_TYPES", {"risk"}))
DEFAULT_CREATOR_ROLE_BY_RESOURCE_TYPE = dict(
    _get_v4_config(
        "IAM_V4_CREATOR_ROLE_BY_RESOURCE_TYPE",
        {"strategy": "scene_admin", "link_table": "scene_admin", "notice_group": "scene_admin"},
    )
)
CREATOR_SCENE_BOUND_RESOURCE_TYPES = set(DEFAULT_CREATOR_ROLE_BY_RESOURCE_TYPE)


class IAMV4Permission:
    """IAM V4 permission backend with audit-center business semantics."""

    def __init__(self, username: str = "", request=None):
        if username:
            self.username = username
            return
        request = request or get_local_request()
        if not request:
            raise ValueError("must provide `username` or `request` param to init")
        self.username = request.user.username

    @property
    def subject(self) -> Dict[str, str]:
        return {"type": "user", "id": self.username}

    @staticmethod
    def _get_action(action: Union[ActionMeta, str]) -> ActionMeta:
        return get_action_by_id(action)

    @staticmethod
    def _resource_to_v4(resource: Optional[Resource]) -> Optional[dict]:
        if resource is None:
            return None
        payload = {"type": resource.type, "id": str(resource.id)}
        path = (resource.attribute or {}).get(KEYWORD_BK_IAM_PATH) or (resource.attribute or {}).get("_bk_iam_path_")
        if path:
            ancestors = []
            for node in path.strip("/").split("/"):
                if not node:
                    continue
                if "," not in node:
                    logger.warning("[IAMV4] skip invalid iam path node: %s", node)
                    continue
                node_type, node_id = node.split(",", 1)
                if not node_type or not node_id:
                    logger.warning("[IAMV4] skip invalid iam path node: %s", node)
                    continue
                ancestors.append({"type": node_type, "id": node_id})
            if ancestors:
                payload["ancestors"] = ancestors
        return payload

    @staticmethod
    def _is_v4_no_resource_action(action: ActionMeta) -> bool:
        return action.id in V4_NO_RESOURCE_ACTION_IDS or not action.related_resource_types

    @classmethod
    def _matched_resources_for_action(cls, action: ActionMeta, resources: Optional[List[Resource]]) -> List[Resource]:
        if cls._is_v4_no_resource_action(action):
            return []
        resources = resources or []
        related_resource_ids = {resource_type.id for resource_type in action.related_resource_types}
        return [resource for resource in resources if resource.type in related_resource_ids]

    _AUTH_RESOURCE_TYPE_REMAP: Dict[str, str] = {}

    @classmethod
    def register_auth_resource_type_remap(cls, from_type: str, to_type: str):
        """Register a resource type remapping for authorization scope lookup.

        Example: register_auth_resource_type_remap("risk", "scene") makes risk actions
        use scene-dimension authorization instead of direct risk reverse lookup.
        """
        cls._AUTH_RESOURCE_TYPE_REMAP[from_type] = to_type

    @classmethod
    def _action_auth_resource_types(cls, action: ActionMeta) -> List[str]:
        if cls._is_v4_no_resource_action(action):
            return []
        resource_types = [resource_type.id for resource_type in action.related_resource_types]
        remap = cls._AUTH_RESOURCE_TYPE_REMAP or {rt: "scene" for rt in SCENE_AUTH_RESOURCE_TYPES}
        return [remap.get(rt, rt) for rt in resource_types]

    @staticmethod
    def _chunks(items: Sequence, size: int = 20) -> Iterable[Sequence]:
        for index in range(0, len(items), size):
            yield items[index : index + size]

    def is_allowed(
        self,
        action: Union[ActionMeta, str],
        resources: Optional[List[Resource]] = None,
        raise_exception: bool = False,
    ) -> bool:
        action = self._get_action(action)
        resources = self._matched_resources_for_action(action, resources)
        resources_to_check = resources or [None]
        allowed = True
        for resource in resources_to_check:
            try:
                result = api.bk_iam_v4.direct_auth(
                    system_id=settings.BK_IAM_SYSTEM_ID,
                    subject=self.subject,
                    action_id=action.id,
                    resource=self._resource_to_v4(resource),
                )
                if not bool(result.get("allowed")):
                    allowed = False
                    break
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "[IAMV4] direct_auth failed, action=%s, resource=%s, error=%s", action.id, resource, error
                )
                allowed = False
                break
        if not allowed and raise_exception:
            apply_data, apply_url = self.get_apply_data([action], resources)
            raise PermissionException(action_name=gettext(action.name), apply_url=apply_url, permission=apply_data)
        return allowed

    def batch_is_allowed(
        self, actions: List[ActionMeta], resources: List[List[Resource]]
    ) -> Dict[str, Dict[str, bool]]:
        actions = [self._get_action(action) for action in actions]
        result: Dict[str, Dict[str, bool]] = {}
        action_ids = [action.id for action in actions]

        resource_items = []
        for resource_group in resources:
            resource = resource_group[0] if resource_group else None
            resource_id = str(resource.id) if resource else ""
            result[resource_id] = {action_id: False for action_id in action_ids}
            if resource is not None:
                resource_items.append((resource_id, resource))

        if resource_items and len(resource_items) == len(resources):
            for action in actions:
                for resource_chunk in self._chunks(resource_items, 20):
                    try:
                        response = api.bk_iam_v4.direct_auth_by_resources(
                            system_id=settings.BK_IAM_SYSTEM_ID,
                            subject=self.subject,
                            action_id=action.id,
                            resources=[self._resource_to_v4(resource) for _, resource in resource_chunk],
                        )
                    except Exception as error:  # pylint: disable=broad-except
                        logger.exception(
                            "[IAMV4] direct_auth_by_resources failed, action=%s, error=%s", action.id, error
                        )
                        continue
                    for item in response or []:
                        resource_id = str(item.get("resource_id", ""))
                        if resource_id in result:
                            result[resource_id][action.id] = bool(item.get("allowed"))
            return result

        for resource_group in resources:
            resource = resource_group[0] if resource_group else None
            resource_id = str(resource.id) if resource else ""
            for action_chunk in self._chunks(actions, 20):
                try:
                    response = api.bk_iam_v4.direct_auth_by_actions(
                        system_id=settings.BK_IAM_SYSTEM_ID,
                        subject=self.subject,
                        action_ids=[action.id for action in action_chunk],
                        resource=self._resource_to_v4(resource),
                    )
                except Exception as error:  # pylint: disable=broad-except
                    logger.exception("[IAMV4] direct_auth_by_actions failed, resource=%s, error=%s", resource_id, error)
                    continue
                for item in response or []:
                    result[resource_id][item["action_id"]] = bool(item.get("allowed"))
        return result

    def get_authorized_resource_ids(self, action: Union[ActionMeta, str], resource_type: str) -> List[str]:
        action = self._get_action(action)
        if resource_type not in TOP_LEVEL_RESOURCE_TYPES:
            return []
        try:
            result = api.bk_iam_v4.list_authorized_resource(
                system_id=settings.BK_IAM_SYSTEM_ID,
                subject=self.subject,
                action_id=action.id,
            )
        except Exception as error:  # pylint: disable=broad-except
            logger.exception("[IAMV4] list_authorized_resource failed, action=%s, error=%s", action.id, error)
            return []
        for item in result or []:
            if item.get("type") == resource_type:
                resource_ids = [str(resource_id) for resource_id in item.get("ids", [])]
                if "*" in resource_ids:
                    return self._list_all_resource_ids(resource_type)
                return resource_ids
        return []

    def has_action_any_permission(self, action: Union[ActionMeta, str]) -> bool:
        action = self._get_action(action)
        if self._is_v4_no_resource_action(action):
            return self.is_allowed(action, resources=[])
        for resource_type in self._action_auth_resource_types(action):
            if self.get_authorized_resource_ids(action, resource_type):
                return True
        return False

    _RESOURCE_LISTERS: Dict[str, Callable[[], List[str]]] = {}

    @classmethod
    def register_resource_lister(cls, resource_type: str, lister: Callable[[], List[str]]):
        """Register a callback to list all valid resource IDs for a given type.

        Used when IAM V4 returns wildcard '*' for authorized resources and needs
        to expand to concrete IDs. Register in AppConfig.ready() for each resource type.
        """
        cls._RESOURCE_LISTERS[resource_type] = lister

    @classmethod
    def _list_all_resource_ids(cls, resource_type: str) -> List[str]:
        lister = cls._RESOURCE_LISTERS.get(resource_type)
        if lister:
            return lister()
        return cls._default_list_all_resource_ids(resource_type)

    @staticmethod
    def _default_list_all_resource_ids(resource_type: str) -> List[str]:
        if resource_type == "scene":
            from services.web.scene.constants import SceneStatus
            from services.web.scene.models import Scene

            return [
                str(scene_id)
                for scene_id in Scene.objects.filter(status=SceneStatus.ENABLED).values_list("scene_id", flat=True)
            ]
        if resource_type == "system":
            from apps.meta.models import System

            return list(System.objects.values_list("system_id", flat=True))
        if resource_type == "tag":
            from apps.meta.models import Tag

            return [str(tag_id) for tag_id in Tag.objects.values_list("tag_id", flat=True)]
        return []

    def _build_permissions(self, actions: List[Union[ActionMeta, str]], resources: Optional[List[Resource]] = None):
        resources = resources or []
        permissions = []
        for action in actions:
            action = self._get_action(action)
            if self._is_v4_no_resource_action(action):
                permissions.append({"action_id": action.id})
                continue
            matched_resources = [
                self._resource_to_v4(resource) for resource in self._matched_resources_for_action(action, resources)
            ]
            permission = {"action_id": action.id}
            if matched_resources:
                permission["resources"] = matched_resources
            permissions.append(permission)
        return permissions

    def _build_apply_permission_data(
        self, actions: List[Union[ActionMeta, str]], resources: Optional[List[Resource]] = None
    ):
        from apps.permission.handlers.permission import Permission

        resources = resources or []
        action_to_resources_list = []
        for action in actions:
            action = self._get_action(action)
            action_resources = self._matched_resources_for_action(action, resources)
            action_to_resources_list.append({"action": action, "resources_list": [action_resources]})
        Permission.setup_meta()
        data = gen_perms_apply_data(
            system=settings.BK_IAM_SYSTEM_ID,
            subject=Subject("user", self.username),
            action_to_resources_list=action_to_resources_list,
        )
        return Permission.translate_apply_data(data=data)

    def get_apply_data(self, actions: List[Union[ActionMeta, str]], resources: Optional[List[Resource]] = None):
        permissions = self._build_permissions(actions, resources)
        permission_data = self._build_apply_permission_data(actions, resources)
        try:
            apply_url = api.bk_iam_v4.generate_perm_apply_url(
                system_id=settings.BK_IAM_SYSTEM_ID,
                permissions=permissions,
            )
            if isinstance(apply_url, dict):
                apply_url = apply_url.get("url", "")
        except Exception as error:  # pylint: disable=broad-except
            logger.exception("[IAMV4] generate_perm_apply_url failed, actions=%s, error=%s", actions, error)
            apply_url = ""
        return permission_data, apply_url

    def _authorization_expired_at(self) -> int:
        return int(time.time()) + int(settings.IAM_V4_AUTHORIZATION_EXPIRED_DAYS) * 24 * 60 * 60

    def grant_instance_permission(
        self,
        role_id: str,
        subject: dict,
        resources: Optional[List[Resource]] = None,
        operator: Optional[str] = None,
    ):
        resources = resources or []
        related_resource_type_id = resources[0].type if resources else ""
        authorization = {
            "role_id": role_id,
            "subject": subject,
            "related_resource_type_id": related_resource_type_id,
            "resources": [self._resource_to_v4(resource) for resource in resources],
            "expired_at": self._authorization_expired_at(),
        }
        api.bk_iam_v4.add_authorization(
            system_id=settings.BK_IAM_SYSTEM_ID,
            operator=operator or self.username,
            authorizations=[authorization],
        )

    def revoke_instance_permission(
        self,
        role_id: str,
        subject: dict,
        resources: Optional[List[Resource]] = None,
        operator: Optional[str] = None,
    ):
        resources = resources or []
        authorization = {
            "role_id": role_id,
            "subject": subject,
            "related_resource_type_id": resources[0].type if resources else "",
            "resources": [self._resource_to_v4(resource) for resource in resources],
        }
        api.bk_iam_v4.revoke_authorization(
            system_id=settings.BK_IAM_SYSTEM_ID,
            operator=operator or self.username,
            authorizations=[authorization],
        )

    def list_role_subjects(self, role_id: str, resource: Optional[Resource] = None, page_size: int = 100) -> List[dict]:
        all_subjects = []
        page = 1
        while True:
            response = api.bk_iam_v4.list_authorization_subject(
                system_id=settings.BK_IAM_SYSTEM_ID,
                role_id=role_id,
                page=page,
                page_size=page_size,
                related_resource_type_id=resource.type if resource else "",
                resource=self._resource_to_v4(resource) if resource else None,
            )
            results = response.get("results", [])
            all_subjects.extend(results)
            if len(all_subjects) >= response.get("count", 0) or not results:
                break
            page += 1
        return all_subjects

    _CREATOR_RESOURCE_RESOLVER: Optional[Callable[[Resource], Resource]] = None

    @classmethod
    def register_creator_resource_resolver(cls, resolver: Callable[[Resource], Resource]):
        """Register a callback to resolve the actual authorization resource for creator grants.

        For example, when granting creator permission on a strategy, the resolver can
        look up the bound scene and return the scene resource instead.
        Register in AppConfig.ready().
        """
        cls._CREATOR_RESOURCE_RESOLVER = resolver

    def _get_creator_authorization_resource(self, resource: Resource) -> Resource:
        if resource.type not in CREATOR_SCENE_BOUND_RESOURCE_TYPES:
            return resource
        if self._CREATOR_RESOURCE_RESOLVER:
            return self._CREATOR_RESOURCE_RESOLVER(resource)
        return self._default_creator_resource_resolver(resource)

    @staticmethod
    def _default_creator_resource_resolver(resource: Resource) -> Resource:
        from services.web.scene.models import ResourceBindingScene

        scene_id = (
            ResourceBindingScene.objects.filter(
                scene__is_deleted=False,
                binding__resource_type=resource.type,
                binding__resource_id=str(resource.id),
            )
            .values_list("scene_id", flat=True)
            .first()
        )
        if not scene_id:
            raise ValueError(f"resource {resource.type}:{resource.id} has no active scene binding")
        return Resource(settings.BK_IAM_SYSTEM_ID, "scene", str(scene_id), {"name": str(scene_id)})

    def grant_creator_action(self, resource: Resource, creator: str = None, role_id: str = None, raise_exception=False):
        role_id = role_id or DEFAULT_CREATOR_ROLE_BY_RESOURCE_TYPE.get(resource.type)
        if not role_id:
            logger.info("[IAMV4] skip creator grant for unsupported resource type: %s", resource.type)
            return None
        subject = {"type": "user", "id": creator or self.username}
        try:
            grant_resource = self._get_creator_authorization_resource(resource)
            return self.grant_instance_permission(role_id=role_id, subject=subject, resources=[grant_resource])
        except Exception as error:  # pylint: disable=broad-except
            logger.exception("[IAMV4] grant_creator_action failed, resource=%s, error=%s", resource.to_dict(), error)
            if raise_exception:
                raise
            return None
