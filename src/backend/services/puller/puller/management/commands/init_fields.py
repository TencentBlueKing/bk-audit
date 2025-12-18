# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    放置在bin中，不建议去除，使用Mock手段避免部署报错
    """

    def handle(self, **kwargs):
        return
