from typing import Dict

from apps.permission.constants import IAMSystems


def format_resource_permission(permissions: Dict):
    result = {}
    for (action_id, is_allowed) in permissions.items():
        result["{}_{}".format(action_id, IAMSystems.BK_LOG.value)] = is_allowed
    return result

# 预处理 create_params，自动转换所有 list 为逗号拼接字符串
def preprocess_data(data):
    if isinstance(data, dict):
        return {k: preprocess_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return ", ".join(str(item) for item in data)
    return data