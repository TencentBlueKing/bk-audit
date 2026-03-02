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
from django.conf import settings
from django.utils.translation import gettext_lazy


class CoreException(BlueException):
    PLATFORM_CODE = settings.PLATFORM_CODE
    MODULE_CODE = "01"

    class Modules(object):
        META = "01"
        DATABUS = "02"
        STRATEGY_V2 = "03"
        ANALYZE = "04"
        TOOL = "05"
        RISK = "06"
        LOG_SUBSCRIPTION = "07"
        IAM = "99"


class SystemNotExistException(CoreException):
    MESSAGE = gettext_lazy("系统不存在")
    ERROR_CODE = "001"


class MetaConfigNotExistException(CoreException):
    MESSAGE = gettext_lazy("配置不存在")
    ERROR_CODE = "002"


class ParamsNotValid(CoreException):
    MESSAGE = gettext_lazy("参数异常")
    ERROR_CODE = "003"


class SnapshotPreparingException(CoreException):
    MESSAGE = gettext_lazy("关联任务处理中，请勿重复操作")
    ERROR_CODE = "004"


class StorageChanging(CoreException):
    MESSAGE = gettext_lazy("存储变更中")
    ERROR_CODE = "005"


class JoinDataPreCheckFailed(CoreException):
    MESSAGE = gettext_lazy("资源同步预检查失败，请检查系统资源回调地址及接口是否正确")
    ERROR_CODE = "006"


class FindDelimiterError(CoreException):
    MESSAGE = gettext_lazy("未能匹配分隔符，请确认")
    ERROR_CODE = "007"


class JsonLoadsError(CoreException):
    MESSAGE = gettext_lazy("JSON语法异常，请确认")
    ERROR_CODE = "008"


class RegexpExpressionError(CoreException):
    MESSAGE = gettext_lazy("正则表达式有误")
    ERROR_CODE = "009"


class TimeFieldMissing(CoreException):
    MESSAGE = gettext_lazy("必须设置时间字段")
    ERROR_CODE = "010"


class LangCodeError(CoreException):
    MESSAGE = gettext_lazy("语言标识[language]为空或有误")
    ERROR_CODE = "011"


class InitSystemDisabled(CoreException):
    MESSAGE = gettext_lazy("未开启系统初始化")
    ERROR_CODE = "012"


class EsQueryMaxLimit(CoreException):
    MESSAGE = gettext_lazy("检索数量超过限制，仅允许检索前%(count)s条")
    ERROR_CODE = "013"


class FeatureNotExist(CoreException):
    MESSAGE = gettext_lazy("特性[%s]不存在")
    ERROR_CODE = "014"


class FeatureIDInvalid(CoreException):
    MESSAGE = gettext_lazy("特性ID[%s]不合法")
    ERROR_CODE = "015"


class PageParamsInValid(CoreException):
    MESSAGE = gettext_lazy("页码错误，请重新选择")
    ERROR_CODE = "016"


class NoticeGroupNotExists(CoreException):
    MESSAGE = gettext_lazy("通知组不存在")
    ERROR_CODE = "017"


class HealthzCheckFailed(CoreException):
    MESSAGE = gettext_lazy("Healthz状态异常")
    ERROR_CODE = "018"


class FlowConfigChanging(CoreException):
    MESSAGE = gettext_lazy("策略变更中，请稍后操作")
    ERROR_CODE = "019"


class ExtractLogError(CoreException):
    MESSAGE = gettext_lazy("解析Log失败")
    ERROR_CODE = "020"
