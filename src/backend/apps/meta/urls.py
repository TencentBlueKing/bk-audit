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

from bk_resource.routers import ResourceRouter
from django.conf.urls import include
from django.urls import path, re_path

from apps.meta.views import (
    biz_views,
    custom_field_views,
    datamap_views,
    field_views,
    general_config_views,
    global_views,
    meta_views,
    namespace_views,
    paas_views,
    system_diagnosis_views,
    system_views,
    tag_views,
    user_manage_views,
)

base_router = ResourceRouter()
base_router.register_module(namespace_views)
base_router.register_module(biz_views)
base_router.register_module(global_views)
base_router.register_module(field_views)
base_router.register_module(custom_field_views)
base_router.register_module(datamap_views)
base_router.register_module(meta_views)

router = ResourceRouter()
router.register_module(system_views)
router.register_module(paas_views)
router.register_module(user_manage_views)
router.register_module(tag_views)
router.register_module(system_diagnosis_views)
router.register_module(general_config_views)

urlpatterns = [
    path("", include(base_router.urls)),
    re_path(r"namespaces/(?P<namespace>[\w\-]+)/", include(router.urls)),
]
