from bk_resource import api
from rest_framework.permissions import BasePermission

from apps.permission.handlers.drf import InstanceActionPermission
from core.models import get_request_username
from services.web.tool.exceptions import BkVisionSearchPermissionProhibited
from services.web.tool.models import Tool


class CreatorBasePermissionPermission(BasePermission):
    def has_permission(self, request, view):
        uid = view.kwargs.get("uid") or request.data.get("uid") or request.query_params.get("uid")

        if not uid:
            return False

        tool = Tool.last_version_tool(uid=uid)
        if not tool:
            return False

        current_user = get_request_username()
        return tool.created_by == current_user


class UseToolPermission(InstanceActionPermission):
    def has_permission(self, request, view):
        tool_uid = self._get_instance_id(request, view)
        tool: Tool = Tool.last_version_tool(uid=tool_uid)
        username = get_request_username()
        if username == tool.updated_by:
            return True
        return super().has_permission(request, view)


def check_bkvision_share_permission(user_id, share_uid) -> bool:
    result = api.bk_vision.check_share_auth(
        username=user_id,
        share_uid=share_uid,
    )
    check_result = result.get("result")
    if not check_result:
        raise BkVisionSearchPermissionProhibited(user_id, share_uid)
    return True
