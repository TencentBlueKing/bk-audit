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

from iam.resource.provider import ResourceProvider


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
