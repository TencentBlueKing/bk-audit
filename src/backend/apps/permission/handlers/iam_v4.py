# -*- coding: utf-8 -*-
import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from bk_resource import api
from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_local_request
from django.conf import settings
from django.utils.translation import gettext
from iam import Resource, Subject
from iam.eval.constants import KEYWORD_BK_IAM_PATH
from iam.utils import gen_perms_apply_data

from apps.permission.handlers.actions import ActionMeta, get_action_by_id
from apps.permission.handlers.resource_types import get_resource_by_id
from core.exceptions import PermissionException


class IAMV4Permission:
    """IAM V4 permission backend with audit-center business semantics."""

    def __init__(self, username: str = "", request=None) -> None:
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
        """Convert IAM SDK resources to V4 API payload, dropping malformed ancestor nodes."""
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
        """V4 models some legacy resource actions as global actions, e.g. sensitive info access."""
        return action.iam_v4_no_resource or not action.related_resource_types

    @classmethod
    def _matched_resources_for_action(cls, action: ActionMeta, resources: Optional[List[Resource]]) -> List[Resource]:
        """Keep only resources that V4 should send for this action."""
        if cls._is_v4_no_resource_action(action):
            return []
        resources = resources or []
        related_resource_ids = {resource_type.id for resource_type in action.related_resource_types}
        return [resource for resource in resources if resource.type in related_resource_ids]

    @classmethod
    def _action_auth_resource_types(cls, action: ActionMeta) -> List[str]:
        """Return top-level resource dimensions usable for "has any permission" checks."""
        if cls._is_v4_no_resource_action(action):
            return []
        auth_resource_types = []
        for resource_type in action.related_resource_types:
            auth_resource_type = resource_type.iam_v4_auth_resource_type or resource_type.id
            auth_resource_types.append(auth_resource_type)
        return auth_resource_types

    @staticmethod
    def _chunks(items: Sequence, size: int) -> Iterable[Sequence]:
        for index in range(0, len(items), size):
            yield items[index : index + size]

    def is_allowed(
        self,
        action: Union[ActionMeta, str],
        resources: Optional[List[Resource]] = None,
        raise_exception: bool = False,
    ) -> bool:
        """Check direct authorization; all provided resources must be allowed."""
        action = self._get_action(action)
        resources = self._matched_resources_for_action(action, resources)
        resources_to_check = resources or [None]
        for resource in resources_to_check:
            try:
                payload = {
                    "system_id": settings.BK_IAM_SYSTEM_ID,
                    "subject": self.subject,
                    "action_id": action.id,
                }
                resource_payload = self._resource_to_v4(resource)
                if resource_payload is not None:
                    payload["resource"] = resource_payload
                result = api.bk_iam_v4.direct_auth.request(payload)
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "[IAMV4] direct_auth failed, action=%s, resource=%s, error=%s", action.id, resource, error
                )
                result = {"allowed": False}
            if bool(result.get("allowed")):
                continue
            if raise_exception:
                apply_data, apply_url = self.get_apply_data([action], resources)
                raise PermissionException(action_name=gettext(action.name), apply_url=apply_url, permission=apply_data)
            return False
        return True

    def batch_is_allowed(
        self, actions: List[ActionMeta], resources: List[List[Resource]]
    ) -> Dict[str, Dict[str, bool]]:
        """Emulate V3 matrix-style batch auth with V4's two batch endpoints."""
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

        no_resource_actions = [action for action in actions if self._is_v4_no_resource_action(action)]
        actions = [action for action in actions if not self._is_v4_no_resource_action(action)]
        for action in no_resource_actions:
            allowed = self.is_allowed(action, resources=[])
            for resource_result in result.values():
                resource_result[action.id] = allowed
        if not actions:
            return result

        chunk_size = settings.IAM_V4_BATCH_AUTH_CHUNK_SIZE
        if resource_items and len(resource_items) == len(resources):
            for action in actions:
                for resource_chunk in self._chunks(resource_items, chunk_size):
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
            for action_chunk in self._chunks(actions, chunk_size):
                try:
                    payload = {
                        "system_id": settings.BK_IAM_SYSTEM_ID,
                        "subject": self.subject,
                        "action_ids": [action.id for action in action_chunk],
                    }
                    resource_payload = self._resource_to_v4(resource)
                    if resource_payload is not None:
                        payload["resource"] = resource_payload
                    response = api.bk_iam_v4.direct_auth_by_actions.request(payload)
                except Exception as error:  # pylint: disable=broad-except
                    logger.exception("[IAMV4] direct_auth_by_actions failed, resource=%s, error=%s", resource_id, error)
                    continue
                for item in response or []:
                    result[resource_id][item["action_id"]] = bool(item.get("allowed"))
        return result

    def get_authorized_resource_ids(self, action: Union[ActionMeta, str], resource_type: str) -> List[str]:
        """Use IAM V4 reverse lookup only for top-level resource types."""
        action = self._get_action(action)
        if not get_resource_by_id(resource_type).iam_v4_reverse_lookup:
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
        """Approximate V3 policy-query existence checks with V4 direct auth or top-level lookup."""
        action = self._get_action(action)
        if self._is_v4_no_resource_action(action):
            return self.is_allowed(action, resources=[])
        for resource_type in self._action_auth_resource_types(action):
            if self.get_authorized_resource_ids(action, resource_type):
                return True
        return False

    @classmethod
    def _list_all_resource_ids(cls, resource_type: str) -> List[str]:
        return get_resource_by_id(resource_type).list_all_ids()

    def _build_permissions(
        self, actions: List[Union[ActionMeta, str]], resources: Optional[List[Resource]] = None
    ) -> List[dict]:
        """Build the compact permission payload expected by V4 apply-url API."""
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
    ) -> dict:
        """Keep legacy local apply-data shape while V4 supplies the actual apply URL."""
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

    def get_apply_data(
        self, actions: List[Union[ActionMeta, str]], resources: Optional[List[Resource]] = None
    ) -> Tuple[dict, str]:
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
        subject: Dict[str, str],
        resources: Optional[List[Resource]] = None,
        operator: Optional[str] = None,
    ) -> None:
        """Grant a subject to a V4 role/resource relation."""
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
        subject: Dict[str, str],
        resources: Optional[List[Resource]] = None,
        operator: Optional[str] = None,
    ) -> None:
        """Revoke the exact V4 role/resource relation previously granted."""
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

    def list_role_subjects(
        self, role_id: str, resource: Optional[Resource] = None, page_size: Optional[int] = None
    ) -> List[dict]:
        """Fetch all subjects authorized by a V4 role relation."""
        page_size = page_size or settings.IAM_V4_LIST_ROLE_SUBJECTS_PAGE_SIZE
        all_subjects = []
        page = 1
        while True:
            payload = {
                "system_id": settings.BK_IAM_SYSTEM_ID,
                "role_id": role_id,
                "page": page,
                "page_size": page_size,
                "related_resource_type_id": resource.type if resource else "",
            }
            resource_payload = self._resource_to_v4(resource) if resource else None
            if resource_payload is not None:
                payload["resource"] = resource_payload
            response = api.bk_iam_v4.list_authorization_subject.request(payload)
            results = response.get("results", [])
            all_subjects.extend(results)
            if len(all_subjects) >= response.get("count", 0) or not results:
                break
            page += 1
        return all_subjects

    def grant_creator_action(
        self,
        resource: Resource,
        creator: Optional[str] = None,
        role_id: Optional[str] = None,
        raise_exception: bool = False,
    ) -> None:
        """Grant creator permissions after creating scene-bound resources."""
        resource_meta = get_resource_by_id(resource.type)
        role_id = role_id or resource_meta.iam_v4_creator_role_id
        if not role_id:
            logger.info("[IAMV4] skip creator grant for unsupported resource type: %s", resource.type)
            return None
        subject = {"type": "user", "id": creator or self.username}
        try:
            grant_resource = resource_meta.get_iam_v4_creator_authorization_resource(resource)
            return self.grant_instance_permission(role_id=role_id, subject=subject, resources=[grant_resource])
        except Exception as error:  # pylint: disable=broad-except
            logger.exception("[IAMV4] grant_creator_action failed, resource=%s, error=%s", resource.to_dict(), error)
            if raise_exception:
                raise
            return None
