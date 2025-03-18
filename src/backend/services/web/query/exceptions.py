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

from blueapps.core.exceptions import BlueException
from django.utils.translation import gettext_lazy


class ClusterNotExist(BlueException):
    MODULE_CODE = "21"
    MESSAGE = gettext_lazy("集群不存在")


class FilterKeyParseError(BlueException):
    MODULE_CODE = "22"
    MESSAGE = gettext_lazy("过滤条件 Key 解析错误: {key}")

    def __init__(self, key, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(key=key)
        super().__init__(*args, **kwargs)
