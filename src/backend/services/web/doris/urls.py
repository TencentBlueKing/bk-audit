# -*- coding: utf-8 -*-
from bk_resource.routers import ResourceRouter
from django.urls import include, path

from services.web.doris import views

router = ResourceRouter()
router.register_module(views)

urlpatterns = [
    path("", include(router.urls)),
]
