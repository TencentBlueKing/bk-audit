from rest_framework.permissions import BasePermission

from core.models import get_request_username
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
