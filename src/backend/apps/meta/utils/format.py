from typing import Dict

from apps.permission.constants import IAMSystems


def format_resource_permission(permissions: Dict):
    result = {}
    for (action_id, is_allowed) in permissions.items():
        result["{}_{}".format(action_id, IAMSystems.BK_LOG.value)] = is_allowed
    return result
