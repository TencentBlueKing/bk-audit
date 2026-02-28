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
from blueapps.utils.logger import logger
from django.conf import settings
from django.db.models import QuerySet
from django.utils.translation import gettext

from apps.meta.models import ResourceType, System
from apps.meta.utils.fields import (
    FIELD_TYPE_STRING,
    FIELD_TYPE_TEXT,
    INSTANCE_ID,
    RESOURCE_TYPE_ID,
    SNAPSHOT_INSTANCE_DATA,
    SNAPSHOT_INSTANCE_NAME,
    SYSTEM_ID,
)
from apps.notice.handlers import ErrorMsgHandler
from services.web.databus.collector.etl.base import EtlClean
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
    JoinDataEtlStorageHandler,
)
from services.web.databus.collector.snapshot.join.http_pull import HttpPullHandler
from services.web.databus.constants import (
    ASSET_RT_FORMAT,
    JOIN_DATA_RT_FORMAT,
    JoinDataType,
    SnapshotRunningStatus,
    SnapShotStorageChoices,
)
from services.web.databus.models import CollectorConfig, Snapshot


class JoinConfig:
    def __init__(self, result_table_id):
        self.result_table_id = result_table_id

    @property
    def config(self):
        return {
            "result_table_id": self.result_table_id,
            "join_on": [
                {"this_field": SYSTEM_ID.field_name, "target_field": "system_id"},
                {"this_field": INSTANCE_ID.field_name, "target_field": "id"},
                {"this_field": RESOURCE_TYPE_ID.field_name, "target_field": "resource_type_id"},
            ],
            "select": [
                {"field_name": "data", "type": FIELD_TYPE_TEXT, "as": SNAPSHOT_INSTANCE_DATA.field_name},
                {"field_name": "display_name", "type": FIELD_TYPE_STRING, "as": SNAPSHOT_INSTANCE_NAME.field_name},
            ],
        }

    @classmethod
    def fields(cls):
        return [
            {
                "field_name": SNAPSHOT_INSTANCE_DATA.field_name,
                "field_type": SNAPSHOT_INSTANCE_DATA.field_type,
                "field_alias": SNAPSHOT_INSTANCE_DATA.alias_name,
                "is_dimension": SNAPSHOT_INSTANCE_DATA.is_dimension,
                "field_index": 100,
            },
            {
                "field_name": SNAPSHOT_INSTANCE_NAME.field_name,
                "field_type": SNAPSHOT_INSTANCE_NAME.field_type,
                "field_alias": SNAPSHOT_INSTANCE_NAME.alias_name,
                "is_dimension": SNAPSHOT_INSTANCE_NAME.is_dimension,
                "field_index": 101,
            },
        ]


class BaseJoinDataHandler(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def join_data_type(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def etl_storage_handler_cls(self) -> JoinDataEtlStorageHandler:
        pass

    def __init__(self, system_id: str, resource_type_id: str, storage_type: str):
        self.system_id = system_id
        self.system = System.objects.get(system_id=system_id)
        self.resource_type_id = resource_type_id
        self.resource_type = ResourceType.objects.get(system_id=system_id, resource_type_id=resource_type_id)
        self.collectors = self.load_collectors()
        self.snapshot = self.get_snapshot_instance()
        self.storage_type = storage_type

    def get_snapshot_instance(self):
        snapshot, _ = Snapshot.objects.get_or_create(system_id=self.system_id, resource_type_id=self.resource_type_id)
        return snapshot

    def load_collectors(self) -> QuerySet:
        return CollectorConfig.objects.filter(system_id=self.system_id, is_deleted=False, join_data_rt=None).exclude(
            bkbase_table_id=None
        )

    def start(self, multiple_storage: bool = False):
        """
        如果是建立多个存储，则需要独立设置成功标记位
        """
        try:
            # 创建DATAID
            self.create_data_id()
            # 创建清洗
            self.create_data_etl()
            # 创建入库
            self.create_data_storage()
            # 更新采集项清洗链路
            self.update_log_clean_link()
            # 更新状态
            if not multiple_storage:
                self.update_status(SnapshotRunningStatus.RUNNING.value)
                self.snapshot.status_msg = ""
                self.snapshot.save()
            return True
        except Exception as err:  # NOCC:broad-except(需要处理所有错误)
            self.update_status(SnapshotRunningStatus.FAILED.value)
            self.snapshot.status_msg = str(err)
            self.snapshot.save()
            title = gettext("JoinDataCreateFailed")
            content = gettext("Error: %s") % str(err)
            ErrorMsgHandler(title, content).send()
            logger.exception(
                "[Start Join Data Failed] SystemID => %s, ResourceTypeID => %s, SnapshotID => %s; Err => %s",
                self.system_id,
                self.resource_type_id,
                self.snapshot.id,
                err,
            )
            return False

    def update_status(self, status: str) -> None:
        self.snapshot.status = status

    def stop(self, multiple_storage: bool = False):
        # 直接停止采集任务
        try:
            params = {
                "bkbase_data_id": self.snapshot.bkbase_data_id,
                "data_scenario": "http",
                "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
                "config_mode": "full",
                "scope": [{"deploy_plan_id": 0, "hosts": []}],
            }
            api.bk_base.stop_collector(**params)
            # 更新状态
            if not multiple_storage:
                self.update_status(SnapshotRunningStatus.CLOSED.value)
                self.snapshot.save()
            return True
        except Exception as err:  # NOCC:broad-except(需要处理所有错误)
            title = gettext("JoinDataStopFailed")
            content = gettext("Error: %s") % str(err)
            ErrorMsgHandler(title, content).send()
            logger.exception(
                "[Stop Join Data Failed] SystemID => %s, ResourceTypeID => %s, SnapshotID => %s; Err => %s",
                self.system_id,
                self.resource_type_id,
                self.snapshot.id,
                err,
            )
        return False

    def create_data_id(self):
        # 判断是否已有
        logger.info(f"{self.__class__.__name__} Update or Create Collector; SnapshotID => {self.snapshot.id}")
        http_pull_handler = HttpPullHandler(self.system, self.resource_type, self.snapshot, self.join_data_type)
        self.snapshot.bkbase_data_id = http_pull_handler.update_or_create()
        self.snapshot.save()

    def create_data_etl(self):
        etl_storage_handler = self.etl_storage_handler_cls(
            self.snapshot.bkbase_data_id,
            self.system,
            self.resource_type,
            self.storage_type,
            snapshot=self.snapshot,
        )
        # 已有清洗链路则更新
        if self._get_table_id():
            logger.info(f"{self.__class__.__name__} Update Etl; SnapshotID => {self.snapshot.id}")
            self.snapshot.bkbase_processing_id, self.snapshot.bkbase_table_id = etl_storage_handler.create_clean(
                update=True
            )
        else:
            # 没有清洗链路则创建
            logger.info(f"{self.__class__.__name__} Create Etl; SnapshotID => {self.snapshot.id}")
            self.snapshot.bkbase_processing_id, self.snapshot.bkbase_table_id = etl_storage_handler.create_clean()
        self.snapshot.save()

    def create_data_storage(self):
        etl_storage_handler = self.etl_storage_handler_cls(
            self.snapshot.bkbase_data_id,
            self.system,
            self.resource_type,
            self.storage_type,
            snapshot=self.snapshot,
        )
        # 已有入库不做调整
        storage = self.snapshot.storages.filter(storage_type=self.storage_type).first()
        try:
            if storage.status == SnapshotRunningStatus.RUNNING:
                logger.info(f"{self.__class__.__name__} update Storage; SnapshotID => {self.snapshot.id}")
                etl_storage_handler.create_storage(update=True)
            elif storage.status == SnapshotRunningStatus.FAILED:
                etl_storage_handler.create_storage(update=True)
            else:
                etl_storage_handler.create_storage()
            storage.status = SnapshotRunningStatus.RUNNING.value
            storage.save()
        except Exception as err:  # NOCC:broad-except(需要处理所有错误)
            storage.status == SnapshotRunningStatus.FAILED
            storage.save()
            title = gettext("CreateJoinDataStorageFailed")
            content = gettext("Error: %s") % str(err)
            ErrorMsgHandler(title, content).send()
            logger.exception(
                "[Creat Join Data Storage Failed] SystemID => %s, ResourceTypeID => %s, "
                "SnapshotID => %s, StorageType => %s; Err => %s",
                self.system_id,
                self.resource_type_id,
                self.snapshot.id,
                self.storage_type,
                err,
            )
            raise

    def _get_table_id(self) -> str:
        return self.snapshot.bkbase_table_id

    def update_log_clean_link(self):
        logger.info("%s Update Collector Clean Configs; SnapshotID => %s", self.__class__.__name__, self.snapshot.id)
        for collector in self.collectors:
            # 更新采集项清洗规则
            etl_storage: EtlClean = EtlClean.get_instance(collector.etl_config)
            etl_storage.update_or_create(
                collector.collector_config_id,
                collector.etl_params,
                collector.fields,
                self.system.namespace,
            )

    @property
    def result_table_id(self):
        return JOIN_DATA_RT_FORMAT.format(system_id=self.system_id, resource_type_id=self.resource_type_id)


class BasicJoinHandler(BaseJoinDataHandler):
    """基础关联数据处理"""

    join_data_type = JoinDataType.BASIC.value
    etl_storage_handler_cls = JoinDataEtlStorageHandler

    def __init__(self, system_id: str, resource_type_id: str, storage_type: str = SnapShotStorageChoices.REDIS.value):
        super().__init__(system_id, resource_type_id, storage_type)


class AssetHandler(BaseJoinDataHandler):
    """资产数据处理"""

    join_data_type = JoinDataType.ASSET.value
    etl_storage_handler_cls = AssetEtlStorageHandler

    def __init__(self, system_id: str, resource_type_id: str, storage_type: str = SnapShotStorageChoices.HDFS.value):
        super().__init__(system_id, resource_type_id, storage_type)

    def load_collectors(self) -> QuerySet:
        """Asset更新无需更新相关日志采集项，因此直接返回空"""
        return CollectorConfig.objects.none()

    @property
    def result_table_id(self):
        return ASSET_RT_FORMAT.format(system_id=self.system_id, resource_type_id=self.resource_type_id)
