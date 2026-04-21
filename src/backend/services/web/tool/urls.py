# -*- coding: utf-8 -*-

from bk_resource.routers import ResourceRouter
from django.urls import include, re_path

from services.web.tool import views

router = ResourceRouter()

# 通用工具 ViewSet（保持原有 URL 风格）
# 注意：tool/platform 和 tool/scene 必须在 tool 之前注册，
# 否则 "platform"/"scene" 会被 DefaultRouter 误匹配为 tool/{pk} 的 pk 值，导致 405
router.register("tool_apigw", views.ToolAPIGWViewSet)
router.register("tool/platform", views.PlatformSceneToolViewSet)
router.register("tool/scene", views.SceneScopeToolViewSet)
router.register("tool", views.ToolViewSet)

urlpatterns = [
    re_path(r"namespaces/(?P<namespace>[\w\-]+)/", include(router.urls)),
]
