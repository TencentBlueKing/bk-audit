# -*- coding: utf-8 -*-
from typing import Optional

from bk_resource import api


def retrieve_leader(validated_request_data: dict) -> Optional[str]:
    """
    获取单个用户的leader信息
    """

    # 获取用户信息
    user_info = api.user_manage.retrieve_user(validated_request_data)
    # 解析出leader信息
    leader_infos = user_info.get("leader", [])
    if leader_infos:
        leader_info = leader_infos[0]
    else:
        leader_info = {}
    return leader_info.get("username")
