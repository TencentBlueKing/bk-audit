# -*- coding: utf-8 -*-
from django.apps import AppConfig
from django.utils.translation import gettext_lazy


class SceneConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "services.web.scene"
    verbose_name = gettext_lazy("Scene")
