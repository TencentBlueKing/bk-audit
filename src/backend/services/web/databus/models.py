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

from blueapps.utils.request_provider import get_local_request_id, get_request_username
from django.db import models
from django.utils.translation import gettext_lazy

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.models import OperateRecordModel, SoftDeleteModel
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    DEFAULT_ALLOCATION_MIN_DAYS,
    DEFAULT_RETENTION,
    DEFAULT_STORAGE_REPLIES,
    DEFAULT_STORAGE_SHARD_SIZE,
    DEFAULT_STORAGE_SHARDS,
    CustomTypeEnum,
    JoinDataPullType,
    JoinDataType,
    PluginSceneChoices,
    RecordLogTypeChoices,
    SelectSdkTypeChoices,
    SnapshotRunningStatus,
    SnapShotStorageChoices,
    SourcePlatformChoices,
)


class CollectorPlugin(OperateRecordModel):
    """
    采集插件
    1. 一个 Namespace 对应一个采集插件
    2. 一个采集插件所有实例都合并到一个ES存储
    """

    namespace = models.CharField(gettext_lazy("namespace"), max_length=32, db_index=True)
    collector_plugin_id = models.IntegerField(gettext_lazy("BK-LOG 采集插件ID"), db_index=True)
    collector_plugin_name = models.CharField(gettext_lazy("BK-LOG 采集插件名称"), max_length=32)
    collector_plugin_name_en = models.CharField(gettext_lazy("BK-LOG 采集插件英文名称"), max_length=64, null=True)
    bkdata_biz_id = models.IntegerField(gettext_lazy("数据所属业务"))
    table_id = models.IntegerField(gettext_lazy("结果表ID"))
    index_set_id = models.IntegerField(gettext_lazy("索引集ID"))
    etl_config = models.CharField(gettext_lazy("清洗配置"), max_length=64, null=True)
    etl_params = models.JSONField(gettext_lazy("清洗参数"), default=dict)
    storage_changed = models.BooleanField(gettext_lazy("更新集群"), default=False)
    retention = models.IntegerField(gettext_lazy("过期时间"), default=DEFAULT_RETENTION)
    allocation_min_days = models.IntegerField(gettext_lazy("冷热数据时间"), default=DEFAULT_ALLOCATION_MIN_DAYS)
    storage_replies = models.IntegerField(gettext_lazy("副本数量"), default=DEFAULT_STORAGE_REPLIES)
    storage_shards_nums = models.IntegerField(gettext_lazy("分片数量"), default=DEFAULT_STORAGE_SHARDS)
    storage_shards_size = models.IntegerField(gettext_lazy("分片大小"), default=DEFAULT_STORAGE_SHARD_SIZE)
    extra_fields = models.JSONField(gettext_lazy("额外字段"), default=list, null=True)
    plugin_scene = models.CharField(gettext_lazy("插件场景"), default=PluginSceneChoices.COLLECTOR.value, max_length=24)
    bkbase_table_id = models.CharField(gettext_lazy("清洗"), max_length=255, null=True)
    bkbase_processing_id = models.CharField(gettext_lazy("清洗"), max_length=255, null=True)
    has_storage = models.BooleanField(gettext_lazy("是否有存储"), default=False)
    has_replica_storage = models.BooleanField(gettext_lazy("是否有副存储"), default=False)
    auth_rt = models.BooleanField(gettext_lazy("是否授权"), default=False)

    class Meta:
        verbose_name = gettext_lazy("采集插件")
        verbose_name_plural = verbose_name
        ordering = ["-id"]

    @classmethod
    def make_table_id(cls, bk_biz_id, collector_plugin_name_en):
        return f"{bk_biz_id}_bklog.{collector_plugin_name_en.lower()}"

    @classmethod
    def build_result_table_id(cls, bk_biz_id, collector_plugin_name_en):
        """
        生成bkbase结果表ID
        """

        return cls.make_table_id(bk_biz_id, collector_plugin_name_en).replace(".", "_")

    @property
    def result_table_id(self) -> str:
        """
        bkbase结果表ID
        """

        return self.build_result_table_id(self.bkdata_biz_id, self.collector_plugin_name_en)

    @classmethod
    def build_collector_rt(cls, namespace: str):
        """
        根据namespace获取采集插件的result_table_id
        """

        collector_plugin_id = GlobalMetaConfig.get(
            config_key=COLLECTOR_PLUGIN_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=namespace,
        )
        plugin = CollectorPlugin.objects.get(collector_plugin_id=collector_plugin_id)
        return plugin.result_table_id


class CollectorConfig(SoftDeleteModel):
    """
    采集项
    1. 一个 System 对应多个采集项
    2. 数据流程
     -- 采集：采集项归属于采集所属业务，数据流向采集插件所属业务
     -- 清洗：各个采集项有自己的清洗逻辑
     -- 入库：数据合流到采集插件对应的table_id
    """

    system_id = models.CharField(gettext_lazy("系统ID"), db_index=True, max_length=64)
    bk_biz_id = models.IntegerField(gettext_lazy("所属业务"), db_index=True)
    bk_data_id = models.IntegerField(gettext_lazy("DATAID"), null=True, unique=True)
    collector_plugin_id = models.IntegerField(gettext_lazy("BK-LOG 采集插件ID"), db_index=True)
    collector_config_id = models.IntegerField(gettext_lazy("BK-LOG 采集项ID"), db_index=True, unique=True)
    collector_config_name = models.CharField(gettext_lazy("BK-LOG 采集项名称"), max_length=64)
    collector_config_name_en = models.CharField(gettext_lazy("BK-LOG 采集项英文名称"), max_length=64, null=True)
    source_platform = models.CharField(
        gettext_lazy("数据来源"),
        max_length=64,
        choices=SourcePlatformChoices.choices,
        default=SourcePlatformChoices.BKLOG.value,
        db_index=True,
    )
    custom_type = models.CharField(
        gettext_lazy("自定义类型"),
        max_length=30,
        choices=CustomTypeEnum.choices,
        default=CustomTypeEnum.LOG.value,
        db_index=True,
    )
    fields = models.JSONField(gettext_lazy("字段列表"), default=list)
    bkbase_table_id = models.CharField(gettext_lazy("清洗"), max_length=255, null=True)
    processing_id = models.CharField(gettext_lazy("清洗"), max_length=255, null=True)
    has_storage = models.BooleanField(gettext_lazy("是否有入库"), default=False)
    description = models.TextField(gettext_lazy("描述"), null=True)
    etl_config = models.CharField(gettext_lazy("清洗配置"), max_length=64, null=True)
    etl_params = models.JSONField(gettext_lazy("清洗参数"), default=dict)
    join_data_rt = models.CharField(gettext_lazy("数据关联RT"), max_length=64, null=True, default=None)
    tail_log_time = models.DateTimeField(gettext_lazy("最新数据时间"), null=True)
    storage_changed = models.BooleanField(gettext_lazy("更新集群"), default=False)
    auth_rt = models.BooleanField(gettext_lazy("已授权RT"), default=False)

    record_log_type = models.CharField(
        gettext_lazy("记录日志方式"), max_length=64, choices=RecordLogTypeChoices.choices, blank=True
    )
    select_sdk_type = models.CharField(
        gettext_lazy('SDK类型'), max_length=64, choices=SelectSdkTypeChoices.choices, blank=True
    )

    class Meta:
        verbose_name = gettext_lazy("采集项")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        index_together = [["system_id", "custom_type"]]

    @classmethod
    def load_dimensions(cls, collector_config_id: int) -> dict:
        try:
            collector = cls.objects.get(collector_config_id=collector_config_id)
            return collector.dimensions
        except cls.DoesNotExist:
            return {}

    @property
    def dimensions(self) -> dict:
        return {
            "SourcePlatform": self.source_platform,
            "CollectorConfig": str(self.collector_config_id),
            "SystemID": self.system_id,
            "CustomType": self.custom_type,
            "BkBizID": str(self.bk_biz_id),
            "BkDataID": str(self.bk_data_id),
        }

    @classmethod
    def make_table_id(cls, bk_biz_id, collector_config_name_en):
        return f"{bk_biz_id}_bklog.{collector_config_name_en.lower()}"


class RedisConfig(SoftDeleteModel):
    """
    Redis配置
    """

    redis_id = models.BigAutoField(gettext_lazy("ID"), primary_key=True)
    namespace = models.CharField(gettext_lazy("命名空间"), max_length=64)
    redis_name_en = models.CharField(gettext_lazy("资源ID"), unique=True, max_length=64)
    redis_name = models.CharField(gettext_lazy("资源名称"), max_length=64)
    admin = models.JSONField(gettext_lazy("管理员"), default=list, null=True)
    connection_info = models.JSONField(gettext_lazy("连接信息"))
    version = models.CharField(gettext_lazy("版本"), max_length=32)
    extra = models.JSONField(gettext_lazy("补充信息"), default=dict)

    class Meta:
        verbose_name = gettext_lazy("Redis Config")
        verbose_name_plural = verbose_name
        ordering = ["-redis_id"]


class Snapshot(SoftDeleteModel):
    """
    快照配置
    - 每一个data_id记录对应一个清洗任务，一个data_id可能有多条不同storage_type的记录
    """

    system_id = models.CharField(gettext_lazy("系统ID"), max_length=64)
    resource_type_id = models.CharField(gettext_lazy("资源类型ID"), max_length=64)
    bkbase_data_id = models.IntegerField(gettext_lazy("接入ID"), null=True, blank=True)
    bkbase_processing_id = models.CharField(gettext_lazy("清洗ID"), max_length=255, null=True, blank=True)
    bkbase_table_id = models.CharField(gettext_lazy("入库表"), max_length=255, null=True, blank=True)
    is_public = models.BooleanField(gettext_lazy("是否公共"), default=False)
    status = models.CharField(
        gettext_lazy("状态"),
        max_length=32,
        choices=SnapshotRunningStatus.choices,
        default=SnapshotRunningStatus.CLOSED.value,
        db_index=True,
    )
    join_data_type = models.CharField(
        gettext_lazy('关联数据类型'), max_length=32, choices=JoinDataType.choices, default=JoinDataType.ASSET
    )
    pull_type = models.CharField(
        gettext_lazy("拉取类型"), max_length=16, choices=JoinDataPullType.choices, default=JoinDataPullType.PARTIAL
    )
    pull_config = models.JSONField(gettext_lazy("拉取配置"), default=dict, null=True, blank=True)
    custom_config = models.JSONField(gettext_lazy("自定义配置"), default=dict, null=True, blank=True)
    status_msg = models.TextField(gettext_lazy("状态信息"), null=True, blank=True)
    auth_rt = models.BooleanField(gettext_lazy("is RT Authorized"), default=False)

    class Meta:
        verbose_name = gettext_lazy("快照配置")
        verbose_name_plural = verbose_name
        unique_together = [["system_id", "resource_type_id"]]


class SnapshotStorage(models.Model):
    snapshot = models.ForeignKey(
        Snapshot, on_delete=models.CASCADE, related_name='storages', verbose_name=gettext_lazy("快照")
    )
    storage_type = models.CharField(
        gettext_lazy("存储类型"),
        max_length=32,
        choices=SnapShotStorageChoices.choices,
        db_index=True,
    )
    status = models.CharField(
        gettext_lazy("状态"),
        max_length=32,
        choices=SnapshotRunningStatus.choices,
        default=SnapshotRunningStatus.CLOSED.value,
        db_index=True,
    )

    class Meta:
        verbose_name = gettext_lazy("快照存储关联")
        verbose_name_plural = verbose_name
        unique_together = (("snapshot", "storage_type"),)


class StorageOperateLog(models.Model):
    """
    存储集群创建更新配置
    """

    cluster_id = models.BigIntegerField(gettext_lazy("集群ID"))
    operator = models.CharField(gettext_lazy("操作人"), max_length=32, null=True, blank=True)
    operate_at = models.DateTimeField(gettext_lazy("操作时间"), auto_now_add=True)
    request_id = models.CharField(gettext_lazy("请求ID"), max_length=64, null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("集群操作记录")
        verbose_name_plural = verbose_name
        ordering = ["-id"]

    @classmethod
    def create(cls, cluster_id):
        cls.objects.create(cluster_id=cluster_id, operator=get_request_username(), request_id=get_local_request_id())


class SnapshotCheckStatistic(models.Model):
    system_id = models.CharField(max_length=64)
    resource_type_id = models.CharField(max_length=64)
    join_data_type = models.CharField(max_length=32)
    http_pull_count = models.IntegerField(default=0)
    doris_storage_count = models.IntegerField(default=0)
    hdfs_storage_count = models.IntegerField(default=0)
    result = models.BooleanField(default=False)

    class Meta:
        unique_together = [["system_id", "resource_type_id", "join_data_type"]]
