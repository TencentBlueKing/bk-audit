# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from apps.meta.models import GlobalMetaConfig
from services.web.entry.constants import INIT_FIELDS_FINISHED_KEY
from services.web.entry.init.base import SystemInitHandler


class Command(BaseCommand):
    def handle(self, **kwargs):
        GlobalMetaConfig.set(INIT_FIELDS_FINISHED_KEY, False)
        SystemInitHandler().init_standard_fields()
