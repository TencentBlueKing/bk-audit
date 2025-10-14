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
from typing import Dict, List, Optional, Tuple

from blueapps.utils.logger import logger
from blueapps.utils.request_provider import get_local_request
from django.conf import settings
from iam.collection import FancyDict
from iam.resource.provider import ListResult, ResourceProvider, SchemaResult
from iam.resource.utils import Page


class BaseResourceProvider(ResourceProvider, metaclass=abc.ABCMeta):
    def list_attr(self, **options):
        """
        处理来自 iam 的 list_attr 请求
        return: ListResult
        """
        return []

    def list_attr_value(self, filter, page, **options):
        """
        处理来自 iam 的 list_attr_value 请求
        return: ListResult
        """
        return []


class IAMResourceProvider(ResourceProvider, abc.ABC):
    """IAM资源提供基类 ."""

    def __init__(self):
        # 属性配置
        self.attr_names = {}

    @staticmethod
    def get_local_request():
        return get_local_request()

    def list_attr(self, **options: Dict) -> ListResult:
        """
        查询某个资源类型可用于配置权限的属性列表
        """
        logger.info(
            "%s list_attr: headers= %s, options = %s",
            self.__class__.__name__,
            dict(self.get_local_request().headers),
            options,
        )

        if self.attr_names:
            language = options.get("language", settings.LANGUAGE_CODE)
            attr_config = self.attr_names.get(language, {})
            if not attr_config:
                attr_config = self.attr_names.get(settings.LANGUAGE_CODE, {})
            # 返回的属性名称支持国际化
            results = [{"id": attr_id, "display_name": display_name} for attr_id, display_name in attr_config.items()]
        else:
            results = []
        count = len(results)
        logger.info("%s list_attr response results = %s, count = %s", self.__class__.__name__, results, count)

        return ListResult(results=results, count=count)

    def list_attr_value(self, filters: FancyDict, page: Page, **options: Dict) -> ListResult:
        """
        获取一个资源类型某个属性的值列表
        """
        logger.info(
            "%s list_attr_value: headers= %s, filters = %s, page = %s, options = %s",
            self.__class__.__name__,
            dict(self.get_local_request().headers),
            filters,
            page.__dict__,
            options,
        )
        try:
            results = self.list_attr_value_choices(filters.attr, page)
        except Exception as exc_info:  # pylint: disable=broad-except
            logger.exception(exc_info)
            raise
        count = len(results)
        logger.info("%s list_attr_value response results = %s, count = %s", self.__class__.__name__, results, count)
        return ListResult(results=results, count=count)

    @abc.abstractmethod
    def list_attr_value_choices(self, attr: str, page: Page) -> List:
        """
        获取一个资源类型某个属性的值列表
        """
        raise NotImplementedError()

    def list_instance(self, filters: FancyDict, page: Page, **options: Dict) -> ListResult:
        """
        根据过滤条件查询实例
        """
        logger.info(
            "%s list_instance: headers= %s, filters = %s, page = %s, options = %s",
            self.__class__.__name__,
            dict(self.get_local_request().headers),
            filters,
            page.__dict__,
            options,
        )
        # 获得父节点
        parent = filters.parent
        if parent:
            # 获得父资源的ID
            parent_id = parent["id"]
            # 获得父资源的资源类型
            resource_type = parent["type"]
        else:
            parent_id = None
            resource_type = None

        # 查询资源实例列表
        try:
            results, count = self.filter_list_instance_results(parent_id, resource_type, page)
        except Exception as exc_info:  # pylint: disable=broad-except
            logger.exception(exc_info)
            raise
        logger.info("%s list_instance response results = %s, count = %s", self.__class__.__name__, results, count)

        return ListResult(results=results, count=count)

    @abc.abstractmethod
    def filter_list_instance_results(self, parent_id: Optional[str], resource_type: Optional[str], page: Page) -> Tuple:
        """
        根据过滤条件查询资源实例
        """
        raise NotImplementedError()

    def fetch_instance_info(self, filters: FancyDict, **options) -> ListResult:
        """
        批量获取资源实例详情
        """
        logger.info(
            "%s fetch_instance_info: headers= %s, filters = %s, options = %s",
            self.__class__.__name__,
            dict(self.get_local_request().headers),
            filters,
            options,
        )

        if not filters.ids:
            # 搜索条件必填
            return ListResult(results=[], count=0)

        # 获得资源实例IDs
        ids = [str(i) for i in filters.ids]
        # 查询指定的资源实例
        try:
            results, count = self.filter_fetch_instance_results(ids)
        except Exception as exc_info:  # pylint: disable=broad-except
            logger.exception(exc_info)
            raise

        logger.info("%s fetch_instance_info response = %s", self.__class__.__name__, results)
        return ListResult(results=results, count=count)

    @abc.abstractmethod
    def filter_fetch_instance_results(self, ids: List[str]) -> Tuple:
        """
        批量查询资源实例
        """
        raise NotImplementedError()

    def search_instance(self, filters: FancyDict, page: Page, **options: Dict) -> ListResult:
        """
        根据过滤条件和搜索关键字查询实例
        """
        logger.info(
            "%s search_instance: headers= %s, filters = %s, page = %s, options = %s",
            self.__class__.__name__,
            dict(self.get_local_request().headers),
            filters,
            page.__dict__,
            options,
        )
        # 获得父节点
        parent = filters.parent
        if parent:
            # 搜索子资源
            parent_id = parent["id"]
            resource_type = parent["type"]
        else:
            # 搜索当前资源
            parent_id = None
            resource_type = None
        # 获得搜索词
        keyword = filters.keyword
        # 查询资源实例
        try:
            results, count = self.filter_search_instance_results(parent_id, resource_type, keyword, page)
        except Exception as exc_info:  # pylint: disable=broad-except
            logger.exception(exc_info)
            raise
        logger.info("%s search_instance response results = %s, count = %s", self.__class__.__name__, results, count)

        return ListResult(results=results, count=count)

    @abc.abstractmethod
    def filter_search_instance_results(
        self, parent_id: Optional[str], resource_type: Optional[str], keyword: str, page: Page
    ) -> Tuple:
        """
        根据过滤条件和搜索关键字查询实例
        """
        raise NotImplementedError()

    def fetch_instance_list(self, filters: FancyDict, page: Page, **options: Dict) -> ListResult:
        """
        处理来自 iam 的 fetch_instance_list 请求
        在审计中心生成静态资源快照时，需要实现此方法
        """
        return ListResult(results=[], count=0)

    def fetch_resource_type_schema(self, **options: Dict) -> SchemaResult:
        """
        处理来自 iam 的 fetch_resource_type_schema 请求
        在审计中心显示静态资源时，需要实现此方法
        """
        return SchemaResult({})
