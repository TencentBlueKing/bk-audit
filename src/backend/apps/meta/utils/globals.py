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

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.conf import settings

from apps.meta.constants import (
    DEFAULT_DATA_DELIMITER,
    DEFAULT_DATA_ENCODING,
    DEFAULT_DURATION_TIME,
    DEFAULT_ES_SOURCE_TYPE,
    CollectorParamConditionMatchType,
    CollectorParamConditionTypeEnum,
    ContainerCollectorType,
    EtlConfigEnum,
)
from apps.meta.serializers import StorageDurationTimeSerializer
from core.utils.data import choices_to_dict, trans_object_local


class Globals:
    def __init__(self):
        self._bk_globals = self._get_bk_globals()

    def _get_bk_globals(self):
        try:
            return api.bk_log.get_globals()
        except APIRequestError as err:
            logger.exception(f"Get GlobalConfig Error => {err}")
            return dict()

    @property
    def globals(self):
        global_items = [item for item in self.__dir__() if not item.startswith("_") and item != "globals"]
        return {item: getattr(self, item) for item in global_items}

    @property
    def app_info(self):
        return {"app_code": settings.APP_CODE}

    @property
    def es_source_type(self):
        return self._bk_globals.get("es_source_type") or DEFAULT_ES_SOURCE_TYPE

    @property
    def storage_duration_time(self):
        serializer = StorageDurationTimeSerializer(
            data=self._bk_globals.get("storage_duration_time") or trans_object_local(DEFAULT_DURATION_TIME, ["name"]),
            many=True,
        )
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @property
    def data_delimiter(self):
        return self._bk_globals.get("data_delimiter") or DEFAULT_DATA_DELIMITER

    @property
    def data_encoding(self):
        return self._bk_globals.get("data_encoding") or DEFAULT_DATA_ENCODING

    @property
    def param_conditions_type(self):
        return choices_to_dict(CollectorParamConditionTypeEnum)

    @property
    def param_conditions_match(self):
        return choices_to_dict(CollectorParamConditionMatchType)

    @property
    def etl_config(self):
        return choices_to_dict(EtlConfigEnum, exclude_vals=EtlConfigEnum.BK_BASE_JSON.value)

    @property
    def bcs_log_type(self):
        return choices_to_dict(ContainerCollectorType)
