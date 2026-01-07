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

from unittest import mock
from unittest.mock import Mock

from apps.exceptions import JoinDataPreCheckFailed, SnapshotPreparingException
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, ResourceType, System
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    ContainerCollectorType,
    SnapshotReportStatus,
    SnapshotRunningStatus,
)
from services.web.databus.exceptions import SecurityForbiddenError
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot
from services.web.databus.tasks import start_snapshot
from tests.base import TestCase
from tests.test_databus.collector.constants import (
    API_BK_LOG_GET_COLLECTOR_DATA,
    COLLECTOR_DATA,
    COLLECTOR_ID,
    COLLECTOR_STATUS_RESULT,
    COLLECTOR_STATUS_RESULT_NODATA,
    COLLECTOR_STATUS_RESULT_NORMAL,
    CREATE_API_PUSH_DATA,
    CREATE_API_PUSH_RESP,
    CREATE_BCS_COLLECTOR_API_RESP,
    CREATE_BCS_COLLECTOR_DATA,
    CREATE_BCS_COLLECTOR_RESULT,
    CREATE_COLLECTOR_API_RESP,
    CREATE_COLLECTOR_DATA,
    CREATE_COLLECTOR_ETL_API_RESP,
    CREATE_COLLECTOR_ETL_DATA,
    CREATE_COLLECTOR_RESULT,
    CREATE_DEPLOY_PLAN_RESULT,
    ETL_FIELD_HISTORY_RESULT,
    ETL_PREVIEW_DATA,
    ETL_PREVIEW_RESULT,
    GET_API_PUSH_DATA,
    GET_API_PUSH_RESP,
    GET_BCS_YAML_TEMPLATE_RESULT,
    GET_COLLECTOR_INFO_DATA,
    GET_COLLECTOR_RESULT_DATA,
    PLUGIN_DATA,
    PLUGIN_ID,
    REPLICA_STORAGE_CLUSTER_CONFIG,
    RESOURCE_TYPE_ID,
    RESOURCE_TYPE_SCHEMA,
    STORAGE_CLUSTER_ID,
    STORAGE_LIST,
    SYSTEM_HOST,
    SYSTEM_TOKEN,
    TOGGLE_JOIN_DATA,
    UPDATE_BCS_COLLECTOR_API_RESP,
    UPDATE_BCS_COLLECTOR_DATA,
    UPDATE_BCS_COLLECTOR_RESULT,
    UPDATE_COLLECTOR_API_RESP,
    UPDATE_COLLECTOR_DATA,
    UPDATE_COLLECTOR_RESULT,
    ErrorSessionMock,
    SessionMock,
)


class CollectorTest(TestCase):
    """
    Test BkLog Collector
    """

    def setUp(self) -> None:
        self.collector = CollectorConfig.objects.create(**COLLECTOR_DATA)
        CollectorPlugin.objects.create(**PLUGIN_DATA)
        System.objects.create(
            instance_id=self.system_id,
            namespace=self.namespace,
            provider_config={"host": SYSTEM_HOST, "token": SYSTEM_TOKEN},
            callback_url=SYSTEM_HOST,
            auth_token=SYSTEM_TOKEN,
        )
        ResourceType.objects.create(
            system_id=self.system_id,
            resource_type_id=RESOURCE_TYPE_ID,
            sensitivity=0,
            version=0,
            provider_config={"path": ""},
            path="",
        )
        GlobalMetaConfig.set(
            COLLECTOR_PLUGIN_ID,
            PLUGIN_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )
        GlobalMetaConfig.set(
            DEFAULT_STORAGE_CONFIG_KEY,
            STORAGE_CLUSTER_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )
        GlobalMetaConfig.set(
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
            REPLICA_STORAGE_CLUSTER_CONFIG,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=self.namespace,
        )

    def test_get_collectors(self):
        """GetCollectorsResource"""
        result = self.resource.databus.collector.get_collectors(system_id=self.system_id)
        self.assertEqual(dict(result[0]), GET_COLLECTOR_RESULT_DATA)

    def test_get_collector(self):
        """GetCollectorResource"""
        result = self.resource.databus.collector.get_collector(collector_config_id=self.collector.collector_config_id)
        self.assertEqual(dict(result), GET_COLLECTOR_RESULT_DATA)

    @mock.patch(
        "databus.collector.resources.api.bk_log.get_collector",
        mock.Mock(return_value=API_BK_LOG_GET_COLLECTOR_DATA),
    )
    def test_get_collector_info(self):
        """GetCollectorInfoResource"""
        result = self.resource.databus.collector.get_collector_info(
            collector_config_id=self.collector.collector_config_id
        )
        self.assertEqual(dict(result), GET_COLLECTOR_INFO_DATA)

    @mock.patch(
        "databus.collector.resources.api.bk_log.create_collector",
        mock.Mock(return_value=CREATE_COLLECTOR_API_RESP),
    )
    def test_create_collector(self):
        """CreateCollectorResource"""
        result = self.resource.databus.collector.create_collector(**CREATE_COLLECTOR_DATA)
        result.pop("id", None)
        self.assertEqual(result, CREATE_COLLECTOR_RESULT)

    @mock.patch(
        "databus.collector.resources.api.bk_log.update_collector",
        mock.Mock(return_value=UPDATE_COLLECTOR_API_RESP),
    )
    def test_update_collector(self):
        """UpdateCollectorResource"""
        result = self.resource.databus.collector.update_collector(**UPDATE_COLLECTOR_DATA)
        result.pop("id", None)
        self.assertEqual(result, UPDATE_COLLECTOR_RESULT)

    def test_get_bcs_yaml_template(self):
        """GetBcsYamlTemplateResource"""
        result = self.resource.databus.collector.get_bcs_yaml_template(
            log_config_type=ContainerCollectorType.CONTAINER.value
        )
        self.assertEqual(result, GET_BCS_YAML_TEMPLATE_RESULT)

    @mock.patch(
        "databus.collector.resources.api.bk_log.create_collector_normal",
        mock.Mock(return_value=CREATE_BCS_COLLECTOR_API_RESP),
    )
    def test_create_bcs_collector(self):
        """CreateBcsCollectorResource"""
        result = self.resource.databus.collector.create_bcs_collector(**CREATE_BCS_COLLECTOR_DATA)
        result.pop("id", None)
        self.assertEqual(result, CREATE_BCS_COLLECTOR_RESULT)

    @mock.patch(
        "databus.collector.resources.api.bk_log.update_collector_normal",
        mock.Mock(return_value=UPDATE_BCS_COLLECTOR_API_RESP),
    )
    def test_update_bcs_collector(self):
        """UpdateBcsCollectorResource"""
        result = self.resource.databus.collector.update_bcs_collector(**UPDATE_BCS_COLLECTOR_DATA)
        result.pop("id", None)
        self.assertEqual(result, UPDATE_BCS_COLLECTOR_RESULT)

    @mock.patch("databus.collector.resources.api.bk_log.stop_subscription", mock.Mock())
    def test_delete_collector(self):
        """DeleteCollectorResource"""
        self.resource.databus.collector.delete_collector(collector_config_id=self.collector.collector_config_id)
        with self.assertRaises(CollectorConfig.DoesNotExist):
            CollectorConfig.objects.get(collector_config_id=self.collector.collector_config_id)

    def test_system_collectors_status(self):
        """SystemCollectorsStatusResource"""
        # NoData
        result = self.resource.databus.collector.system_collectors_status(
            namespace=self.namespace, system_id=self.system_id
        )
        self.assertEqual(result, COLLECTOR_STATUS_RESULT)
        # NoCollector
        result = self.resource.databus.collector.system_collectors_status(
            namespace=self.namespace, system_id=self.system_id + "test"
        )
        self.assertEqual(result, COLLECTOR_STATUS_RESULT_NODATA)
        # Normal
        CollectorConfig.objects.all().update(tail_log_time="2022-01-01 00:00:00")
        result = self.resource.databus.collector.system_collectors_status(
            namespace=self.namespace, system_id=self.system_id
        )
        self.assertEqual(result, COLLECTOR_STATUS_RESULT_NORMAL)

    def test_bulk_system_collectors_status(self):
        """BulkSystemCollectorsStatusResource"""
        result = self.resource.databus.collector.bulk_system_collectors_status(
            namespace=self.namespace, system_ids=f"{self.system_id}"
        )
        self.assertEqual(result, {self.system_id: COLLECTOR_STATUS_RESULT})

    @mock.patch("databus.storage.resources.api.bk_log.get_storages", mock.Mock(return_value=STORAGE_LIST))
    @mock.patch(
        "databus.collector.etl.base.api.bk_base.databus_cleans_post",
        mock.Mock(return_value=CREATE_COLLECTOR_ETL_API_RESP),
    )
    @mock.patch("databus.collector.etl.base.api.bk_base.databus_tasks_post", mock.Mock())
    @mock.patch("databus.collector.etl.base.api.bk_base.databus_storages_post", mock.Mock())
    def test_collector_etl(self):
        """CollectorEtlResource"""
        self.resource.databus.collector.collector_etl(**CREATE_COLLECTOR_ETL_DATA)

    def test_etl_preview(self):
        """EtlPreviewResource"""
        result = self.resource.databus.collector.etl_preview(**ETL_PREVIEW_DATA)
        self.assertEqual(result, ETL_PREVIEW_RESULT)

    @mock.patch("databus.collector.resources.requests.session", SessionMock())
    def test_toggle_join_data(self):
        """ToggleJoinDataResource"""
        self.resource.databus.collector.toggle_join_data(**TOGGLE_JOIN_DATA)
        with self.assertRaises(SnapshotPreparingException):
            self.resource.databus.collector.toggle_join_data(**TOGGLE_JOIN_DATA)

    @mock.patch("databus.collector.resources.requests.session", SessionMock())
    @mock.patch("databus.collector.snapshot.join.base.api.bk_base.stop_collector", mock.Mock())
    def test_toggle_join_data_stop(self):
        """ToggleJoinDataResource"""
        self.resource.databus.collector.toggle_join_data(**{**TOGGLE_JOIN_DATA})
        s = Snapshot.objects.get(system_id=self.system_id, resource_type_id=RESOURCE_TYPE_ID)
        s.status = SnapshotRunningStatus.RUNNING
        s.save()
        self.resource.databus.collector.toggle_join_data(**{**TOGGLE_JOIN_DATA, "is_enabled": False})

    def test_toggle_join_data_check_failed(self):
        """ToggleJoinDataResource"""
        with self.assertRaises(JoinDataPreCheckFailed):
            self.resource.databus.collector.toggle_join_data(**TOGGLE_JOIN_DATA)

    @mock.patch("databus.collector.resources.requests.session", ErrorSessionMock())
    def test_toggle_join_data_check_status_failed(self):
        """ToggleJoinDataResource"""
        with self.assertRaises(JoinDataPreCheckFailed):
            self.resource.databus.collector.toggle_join_data(**TOGGLE_JOIN_DATA)

    def test_etl_field_history(self):
        """EtlFieldHistory"""
        result = self.resource.databus.collector.etl_field_history(collector_config_id=COLLECTOR_ID)
        self.assertEqual(result, ETL_FIELD_HISTORY_RESULT)

    def test_bulk_system_snapshots_status_no_snapshot(self):
        """Test BulkSystemSnapshotsStatusResource with no snapshot"""
        result = self.resource.databus.collector.bulk_system_snapshots_status(
            namespace=self.namespace, system_ids=str(self.system_id)
        )
        self.assertEqual(result[self.system_id]["status"], SnapshotReportStatus.UNSET.value)

    def test_bulk_system_snapshots_status_normal(self):
        """Test BulkSystemSnapshotsStatusResource with normal snapshot"""
        Snapshot.objects.create(
            system_id=self.system_id,
            resource_type_id=RESOURCE_TYPE_ID,
            status=SnapshotRunningStatus.RUNNING.value,
        )
        result = self.resource.databus.collector.bulk_system_snapshots_status(
            namespace=self.namespace, system_ids=str(self.system_id)
        )
        self.assertEqual(result[self.system_id]["status"], SnapshotReportStatus.NORMAL.value)

    def test_bulk_system_snapshots_status_abnormal(self):
        """Test BulkSystemSnapshotsStatusResource with failed snapshot"""
        Snapshot.objects.create(
            system_id=self.system_id,
            resource_type_id=RESOURCE_TYPE_ID,
            status=SnapshotRunningStatus.FAILED.value,
        )
        result = self.resource.databus.collector.bulk_system_snapshots_status(
            namespace=self.namespace, system_ids=str(self.system_id)
        )
        self.assertEqual(result[self.system_id]["status"], SnapshotReportStatus.ABNORMAL.value)

    @mock.patch("databus.collector.resources.requests.session", SessionMock())
    @mock.patch(
        "databus.collector.snapshot.join.http_pull.api.bk_base.create_deploy_plan",
        Mock(return_value=CREATE_DEPLOY_PLAN_RESULT),
    )
    @mock.patch(
        "databus.collector.etl.base.api.bk_base.databus_cleans_post",
        mock.Mock(return_value=CREATE_COLLECTOR_ETL_API_RESP),
    )
    @mock.patch("databus.collector.snapshot.join.etl_storage.api.bk_base.databus_tasks_post", mock.Mock())
    @mock.patch("databus.collector.snapshot.join.etl_storage.api.bk_base.databus_storages_post", mock.Mock())
    @mock.patch("databus.collector.snapshot.join.etl_storage.api.bk_base.databus_storages_put", mock.Mock())
    @mock.patch(
        "databus.collector.snapshot.join.etl_storage.resource.meta.resource_type_schema",
        mock.Mock(return_value=RESOURCE_TYPE_SCHEMA),
    )
    def test_start_snapshot(self):
        """StartSnapshotResource"""
        self.resource.databus.collector.toggle_join_data(**{**TOGGLE_JOIN_DATA})
        start_snapshot.__wrapped__.__wrapped__()
        s = Snapshot.objects.get(system_id=self.system_id, resource_type_id=RESOURCE_TYPE_ID)
        self.assertEqual(s.status, SnapshotRunningStatus.RUNNING)
        s = System.objects.get(system_id=self.system_id)
        s.callback_url = "ftp://example.com"
        s.save()
        with self.assertRaises(SecurityForbiddenError):
            self.resource.databus.collector.toggle_join_data(**{**TOGGLE_JOIN_DATA, "is_enabled": True})
        s = System.objects.get(system_id=self.system_id)
        s.callback_url = "http://example.com:7001"
        s.save()
        with self.assertRaises(SecurityForbiddenError):
            self.resource.databus.collector.toggle_join_data(**{**TOGGLE_JOIN_DATA, "is_enabled": True})

    def __create_api_push(self):
        create_result = self.resource.databus.collector.create_api_push(**CREATE_API_PUSH_DATA)
        return create_result

    @mock.patch(
        "databus.collector.resources.api.bk_log.create_api_push",
        mock.Mock(return_value=CREATE_API_PUSH_RESP),
    )
    def test_create_api_push(self):
        """CreateAPIPushResource"""
        result = self.__create_api_push()
        self.assertIsNotNone(result.get("collector_config_id"))

    @mock.patch(
        "databus.collector.resources.api.bk_log.get_report_token",
        mock.Mock(return_value=GET_API_PUSH_RESP),
    )
    def test_get_api_push(self):
        """GetAPIPushResource"""
        self.test_create_api_push()

        search_result = self.resource.databus.collector.get_api_push(**GET_API_PUSH_DATA)
        self.assertEqual(search_result.get("token"), GET_API_PUSH_RESP.get("bk_data_token"))
        self.assertEqual(
            list(search_result.keys()),
            ['token', 'collector_config_id', 'bk_data_id', 'collector_config_name', 'collector_config_name_en'],
        )
