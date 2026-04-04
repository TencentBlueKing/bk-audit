# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from bk_resource.routers import ResourceRouter

from services.web.vision import views

router = ResourceRouter()

# 通用查询类 ViewSet（保持原有 URL 风格）
router.register("panels", views.PanelsViewSet)
router.register("meta", views.MetaViewSet)
router.register("dataset", views.DatasetViewSet)
router.register("field", views.FieldViewSet)
router.register("variable", views.VariableViewSet)
router.register("share", views.ShareViewSet)

# 场景报表管理：/panel/platform/ 和 /panel/scene/ 风格
router.register("panel/platform", views.PlatformPanelViewSet)
router.register("panel/scene", views.ScenePanelManageViewSet)

urlpatterns = router.urls
