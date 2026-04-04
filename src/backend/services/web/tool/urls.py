# -*- coding: utf-8 -*-

from bk_resource.routers import ResourceRouter
from django.urls import include, re_path

from services.web.tool import views

router = ResourceRouter()

# 通用工具 ViewSet（保持原有 URL 风格）
router.register("tool", views.ToolViewSet)
router.register("tool_apigw", views.ToolAPIGWViewSet)

# 场景工具管理：/tool/platform/ 和 /tool/scene/ 风格
router.register("tool/platform", views.PlatformSceneToolViewSet)
router.register("tool/scene", views.SceneScopeToolViewSet)

urlpatterns = [
    re_path(r"namespaces/(?P<namespace>[\w\-]+)/", include(router.urls)),
]
