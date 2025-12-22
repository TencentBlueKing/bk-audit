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
from bk_resource.viewsets import ResourceRoute, ResourceViewSet

from core.view_sets import APIGWViewSet
from services.web.log_subscription.resources import QueryLogSubscription


class LogSubscriptionApigwViewSet(APIGWViewSet):
    """
    日志订阅 APIGW 接口

    提供给第三方系统通过 APIGW 调用的日志订阅查询接口。
    """

    resource_routes = [
        ResourceRoute("POST", QueryLogSubscription, endpoint="query"),
    ]


class LogSubscriptionViewSet(ResourceViewSet):
    """
    日志订阅用户接口

    提供给用户进行日志订阅查询的接口（包括 Admin 调试）。
    """

    resource_routes = [
        ResourceRoute("POST", QueryLogSubscription, endpoint="query"),
    ]
