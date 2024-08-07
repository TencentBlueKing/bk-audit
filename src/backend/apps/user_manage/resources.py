# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from bk_resource import Resource, api
from django.utils.translation import gettext_lazy


class RetrieveLeader(Resource):
    name = gettext_lazy("获取单个用户的leader信息")

    def perform_request(self, validated_request_data):
        # 获取用户信息
        user_info = api.user_manage.retrieve_user(validated_request_data)
        # 解析出leader信息
        leader_infos = user_info.get("leader", [])
        if leader_infos:
            leader_info = leader_infos[0]
        else:
            leader_info = {}
        return leader_info.get("username")
