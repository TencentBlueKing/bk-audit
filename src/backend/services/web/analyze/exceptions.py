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

from django.utils.translation import gettext_lazy

from apps.exceptions import CoreException

CONTROL_VERSION_START = 1


class AnalyzeException(CoreException):
    MODULE_CODE = CoreException.Modules.STRATEGY_V2


class ClusterNotExists(AnalyzeException):
    STATUS_CODE = 500
    ERROR_CODE = "001"
    MESSAGE = gettext_lazy("Cluster Not Exists")


class ControlNotExist(AnalyzeException):
    STATUS_CODE = 400
    ERROR_CODE = "002"
    MESSAGE = gettext_lazy("Control Not Exists")
