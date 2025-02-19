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

import abc

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings

from services.web.databus.models import CollectorPlugin, Snapshot


class BaseAuthHandler:
    """
    Auth RT to Project
    """

    def auth(self) -> None:
        """
        do auth
        """

        params = {
            "ticket_type": self.ticket_type,
            "permissions": [
                {
                    "subject_id": settings.BKBASE_PROJECT_ID,
                    "subject_class": self.auth_subject_class,
                    "subject_name": str(settings.BKBASE_PROJECT_NAME),
                    "action": self.auth_action,
                    "object_class": self.auth_object_class,
                    "scope": {"result_table_id": self.build_result_table_id()},
                }
            ],
            "reason": self.auth_reason,
        }
        try:
            resp = api.bk_base.auth_tickets(**params)
            logger.info(
                "[%sSuccess] RT => %s; Result => %s", self.__class__.__name__, self.build_result_table_id(), resp
            )
            result = True
        except APIRequestError as err:
            logger.exception(
                "[%sFailed] RT => %s; Result => %s",
                self.__class__.__name__,
                self.build_result_table_id(),
                err,
            )
            result = False
        self.post_auth(result=result)

    @abc.abstractmethod
    def post_auth(self, result: bool) -> None:
        """
        perform after auth
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def build_result_table_id(self) -> str:
        """
        build auth rt
        """

        raise NotImplementedError()

    @property
    def ticket_type(self) -> str:
        return "project_biz"

    @property
    def auth_subject_class(self) -> str:
        return "project"

    @property
    def auth_action(self) -> str:
        return "result_table.query_data"

    @property
    def auth_object_class(self) -> str:
        return "project"

    @property
    def auth_reason(self) -> str:
        return "BkAudit AIOPS Strategy"


class CollectorPluginAuthHandler(BaseAuthHandler):
    """
    Auth Collector Plugin
    """

    def __init__(self, collector_plugin: CollectorPlugin):
        self.collector_plugin = collector_plugin

    def post_auth(self, result: bool) -> None:
        if result:
            self.collector_plugin.auth_rt = True
            self.collector_plugin.save(update_fields=["auth_rt"])

    def build_result_table_id(self) -> str:
        return CollectorPlugin.make_table_id(
            settings.DEFAULT_BK_BIZ_ID, self.collector_plugin.collector_plugin_name_en
        ).replace(".", "_")


class AssetAuthHandler(BaseAuthHandler):
    """
    Auth Asset
    """

    def __init__(self, asset: Snapshot):
        self.asset = asset

    def post_auth(self, result: bool) -> None:
        if result:
            self.asset.auth_rt = True
            self.asset.save(update_fields=["auth_rt"])

    def build_result_table_id(self) -> str:
        return self.asset.bkbase_table_id
