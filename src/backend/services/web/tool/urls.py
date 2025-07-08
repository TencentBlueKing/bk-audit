# -*- coding: utf-8 -*-

from bk_resource.routers import ResourceRouter
from django.urls import include, re_path

from services.web.tool import views

router = ResourceRouter()
router.register_module(views)

urlpatterns = [
    re_path(r"namespaces/(?P<namespace>[\w\-]+)/", include(router.urls)),
]
