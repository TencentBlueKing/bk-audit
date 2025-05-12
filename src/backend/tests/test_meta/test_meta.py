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

from apps.meta.exceptions import BKAppNotExists
from apps.meta.handlers.system_diagnosis import SystemDiagnosisPushHandler
from apps.meta.models import CustomField, Field, ResourceType, System, SystemRole
from core.utils.data import ordered_dict_to_json, trans_object_local
from services.web.databus.models import Snapshot
from tests.base import TestCase
from tests.test_meta.constants import (
    BIZS_LIST_API_RESP,
    BKLOG_PERMISSION_VERSION_API_RESP,
    BULK_SYSTEM_COLLECTORS_STATUS_API_RESP,
    CUSTOM_FIELD_DATA,
    FIELDS_DATA,
    GET_APP_INFO_DATA,
    GET_APP_INFO_PARAMS,
    GET_AUTH_SYSTEMS_API_RESP,
    GET_CUSTOM_FIELDS_DATA,
    GET_CUSTOM_FIELDS_EXCEPT_PARAMS,
    GET_CUSTOM_FIELDS_PARAMS,
    GET_GLOBAL_META_CONFIG_INFO_DATA,
    GET_GLOBAL_META_CONFIG_INFO_PARAMS,
    GET_GLOBALS_API_RESP,
    GET_GLOBALS_DATA,
    GET_SPACES_MINE_API_RESP,
    GET_SPACES_MINE_DATA,
    GET_SPACES_MINE_OF_V2_DATA,
    GET_STANDARD_FIELDS_DATA,
    GET_STANDARD_FIELDS_PARAMS,
    GLOBAL_CHOICES,
    LIST_USERS_API_RESP,
    LIST_USERS_DATA,
    LIST_USERS_PARAMS,
    RESOURCE_TYPE_DATA,
    RESOURCE_TYPE_LIST_DATA,
    RESOURCE_TYPE_LIST_DATA2,
    RESOURCE_TYPE_LIST_PARAMS,
    RESOURCE_TYPE_SCHEMA_PARAMS,
    RETRIEVE_USER_API_RESP,
    RETRIEVE_USER_DATA,
    RETRIEVE_USER_PARAMS,
    SET_GLOBAL_META_CONFIG_DATA,
    SET_GLOBAL_META_CONFIG_PARAMS,
    SNAPSHOT_DATA,
    SYSTEM_BULK_DATA,
    SYSTEM_DATA2,
    SYSTEM_FILTER_DATA,
    SYSTEM_FILTER_OF_NOT_SYSTEM_IDS_PARAMS,
    SYSTEM_FILTER_PARAMS,
    SYSTEM_INFO_DATA,
    SYSTEM_INFO_PARAMS,
    SYSTEM_LIST_ALL_DATA,
    SYSTEM_LIST_ALL_OF_ACTION_IDS_DATA,
    SYSTEM_LIST_ALL_OF_ACTION_IDS_PARAMS,
    SYSTEM_LIST_ALL_PARAMS,
    SYSTEM_LIST_DATA,
    SYSTEM_LIST_OF_NOT_SORT_DATA,
    SYSTEM_LIST_OF_NOT_SORT_PARAMS,
    SYSTEM_LIST_OF_NOT_SYSTEMS_PARAMS,
    SYSTEM_LIST_OF_SORT_EQ_DATA,
    SYSTEM_LIST_OF_SORT_EQ_PARAMS,
    SYSTEM_LIST_OF_SORT_GT_DATA,
    SYSTEM_LIST_OF_SORT_GT_PARAMS,
    SYSTEM_LIST_PARAMS,
    SYSTEM_OF_SCHEMA_DATA,
    SYSTEM_ROLE_DATA,
    UNI_APPS_QUERY_API_RESP,
    UPDATE_CUSTOM_FIELDS_PARAMS,
    PermissionMock,
)


class MetaTest(TestCase):
    def setUp(self) -> None:
        System.objects.bulk_create(SYSTEM_BULK_DATA)
        SystemRole.objects.create(**SYSTEM_ROLE_DATA)
        ResourceType.objects.create(**RESOURCE_TYPE_DATA)
        self.snapshot = Snapshot.objects.create(**SNAPSHOT_DATA)
        Field.objects.create(**FIELDS_DATA)
        CustomField.objects.create(**CUSTOM_FIELD_DATA)
        self.patcher_1 = mock.patch("meta.resources.default_cache.set", mock.Mock(return_value=None))
        self.patcher_2 = mock.patch("meta.resources.default_cache.get", mock.Mock(return_value=None))
        self.patcher_1.start()
        self.patcher_2.start()

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()

    @mock.patch(
        "meta.resources.resource.databus.collector.bulk_system_collectors_status",
        mock.Mock(return_value=BULK_SYSTEM_COLLECTORS_STATUS_API_RESP),
    )
    @mock.patch("meta.resources.wrapper_permission_field", PermissionMock.wrapper_permission_field)
    def test_system_list(self):
        """SystemListResource"""
        result_of_ordered = self.resource.meta.system_list(**SYSTEM_LIST_PARAMS)
        result_of_json = ordered_dict_to_json(result_of_ordered)
        result = [item for item in result_of_json if item.pop("id", None)]
        self.assertEqual(result, SYSTEM_LIST_DATA)

    @mock.patch("meta.resources.wrapper_permission_field", PermissionMock.wrapper_permission_field)
    def test_system_list_of_not_systems(self):
        """SystemListResource"""
        result = self.resource.meta.system_list(**SYSTEM_LIST_OF_NOT_SYSTEMS_PARAMS)
        self.assertEqual(result, [])

    @mock.patch(
        "meta.resources.resource.databus.collector.bulk_system_collectors_status",
        mock.Mock(return_value=BULK_SYSTEM_COLLECTORS_STATUS_API_RESP),
    )
    @mock.patch("meta.resources.wrapper_permission_field", PermissionMock.wrapper_permission_field)
    def test_system_list_of_not_sort(self):
        """SystemListResource"""
        result_of_ordered = self.resource.meta.system_list(**SYSTEM_LIST_OF_NOT_SORT_PARAMS)
        result_of_json = ordered_dict_to_json(result_of_ordered)
        result = [item for item in result_of_json if item.pop("id", None)]
        self.assertEqual(result, SYSTEM_LIST_OF_NOT_SORT_DATA)

    @mock.patch(
        "meta.resources.resource.databus.collector.bulk_system_collectors_status",
        mock.Mock(return_value=BULK_SYSTEM_COLLECTORS_STATUS_API_RESP),
    )
    @mock.patch("meta.resources.wrapper_permission_field", PermissionMock.wrapper_permission_field)
    def test_system_list_of_sort_eq(self):
        """SystemListResource"""
        result = self.resource.meta.system_list(**SYSTEM_LIST_OF_SORT_EQ_PARAMS)
        result_of_json = ordered_dict_to_json(result)
        result = [item for item in result_of_json if item.pop("id", None)]
        self.assertEqual(result, SYSTEM_LIST_OF_SORT_EQ_DATA)

    @mock.patch(
        "meta.resources.resource.databus.collector.bulk_system_collectors_status",
        mock.Mock(return_value=BULK_SYSTEM_COLLECTORS_STATUS_API_RESP),
    )
    @mock.patch("meta.resources.wrapper_permission_field", PermissionMock.wrapper_permission_field)
    def test_system_list_of_sort_gt(self):
        """SystemListResource"""
        result = self.resource.meta.system_list(**SYSTEM_LIST_OF_SORT_GT_PARAMS)
        result_of_json = ordered_dict_to_json(result)
        result = [item for item in result_of_json if item.pop("id", None)]
        self.assertEqual(result, SYSTEM_LIST_OF_SORT_GT_DATA)

    @mock.patch("meta.resources.wrapper_permission_field", PermissionMock.wrapper_permission_field)
    def test_system_list_all(self):
        """SystemListAllResource"""
        result = self.resource.meta.system_list_all(**SYSTEM_LIST_ALL_PARAMS)
        self.assertEqual(result, SYSTEM_LIST_ALL_DATA)

    @mock.patch("meta.resources.wrapper_permission_field", PermissionMock.wrapper_permission_field)
    def test_system_list_all_of_not_action_ids(self):
        """SystemListAllResource"""
        System.objects.filter().delete()
        System.objects.create(**SYSTEM_DATA2)
        result = self.resource.meta.system_list_all(**SYSTEM_LIST_ALL_OF_ACTION_IDS_PARAMS)
        self.assertEqual(result, SYSTEM_LIST_ALL_OF_ACTION_IDS_DATA)

    def test_system_info(self):
        """SystemInfoResource"""
        result = self.resource.meta.system_info(**SYSTEM_INFO_PARAMS)
        result.pop("id", None)
        result["provider_config"].pop("token", None)
        self.assertEqual(result, SYSTEM_INFO_DATA)

    def test_resource_type_list(self):
        """ResourceTypeListResource"""
        result = self.resource.meta.resource_type_list(**RESOURCE_TYPE_LIST_PARAMS)
        result = ordered_dict_to_json(result)
        resource_type_ids = ",".join([resource_type["resource_type_id"] for resource_type in result])
        snapshot_status_dict = self.resource.databus.collector.snapshot_status(
            system_id=self.snapshot.system_id, resource_type_ids=resource_type_ids
        )
        for resource_type in result:
            resource_type.update(snapshot_status_dict[resource_type["resource_type_id"]])
        self.assertEqual(result, [RESOURCE_TYPE_LIST_DATA])

    def test_resource_type_list_of_not_item(self):
        """ResourceTypeListResource"""
        Snapshot.objects.filter(system_id=self.snapshot.system_id).delete()
        result = self.resource.meta.resource_type_list(**RESOURCE_TYPE_LIST_PARAMS)
        result = ordered_dict_to_json(result)
        resource_type_ids = ",".join([resource_type["resource_type_id"] for resource_type in result])
        snapshot_status_list = self.resource.databus.collector.snapshot_status(
            system_id=self.snapshot.system_id, resource_type_ids=resource_type_ids
        )
        for resource_type in result:
            resource_type.update(snapshot_status_list[resource_type["resource_type_id"]])
        self.assertEqual(result, [RESOURCE_TYPE_LIST_DATA2])

    @mock.patch(
        "meta.resources.SearchLogPermission.get_auth_systems", mock.Mock(return_value=GET_AUTH_SYSTEMS_API_RESP)
    )
    def test_system_filter(self):
        """SystemFilter"""
        result = self.resource.meta.resource_type_search_list(**SYSTEM_FILTER_PARAMS)
        self.assertEqual(result, SYSTEM_FILTER_DATA)

    @mock.patch(
        "meta.resources.SearchLogPermission.get_auth_systems", mock.Mock(return_value=GET_AUTH_SYSTEMS_API_RESP)
    )
    def test_system_filter_of_not_system_ids(self):
        """SystemFilter"""
        result = self.resource.meta.resource_type_search_list(**SYSTEM_FILTER_OF_NOT_SYSTEM_IDS_PARAMS)
        self.assertEqual(result, SYSTEM_FILTER_DATA)

    @mock.patch("meta.utils.globals.api.bk_log.get_globals", mock.Mock(return_value=GET_GLOBALS_API_RESP))
    def test_get_globals(self):
        """GetGlobalsResource"""
        result = self.resource.meta.get_globals()
        storage_duration_time_of_json = ordered_dict_to_json(result["storage_duration_time"])
        storage_duration_timeof_id = trans_object_local([item for item in storage_duration_time_of_json], ["id"])
        result.update({"storage_duration_time": storage_duration_timeof_id})
        self.assertEqual(result, GET_GLOBALS_DATA)

    def test_get_standard_fields(self):
        """GetStandardFieldsResource"""
        result = self.resource.meta.get_standard_fields(**GET_STANDARD_FIELDS_PARAMS)
        self.assertEqual(result, GET_STANDARD_FIELDS_DATA)

    def test_get_custom_fields(self):
        """GetCustomFieldsResource"""
        result = self.resource.meta.get_custom_fields(**GET_CUSTOM_FIELDS_PARAMS)
        self.assertEqual(result, GET_CUSTOM_FIELDS_DATA)

    def test_get_custom_fields_of_except(self):
        """GetCustomFieldsResource"""
        result = self.resource.meta.get_custom_fields(**GET_CUSTOM_FIELDS_EXCEPT_PARAMS)
        self.assertEqual(result, None)

    def test_update_custom_fields(self):
        """UpdateCustomFieldsResource"""
        result = self.resource.meta.update_custom_fields(**UPDATE_CUSTOM_FIELDS_PARAMS)
        self.assertEqual(result, None)

    @mock.patch("meta.resources.api.bk_paas.uni_apps_query", mock.Mock(return_value=UNI_APPS_QUERY_API_RESP))
    @mock.patch("meta.resources.SearchLogPermission.any_search_log_permission", mock.Mock(return_value=None))
    def test_get_app_info(self):
        """GetAppInfoResource"""
        self.resource.meta.get_app_info(**GET_APP_INFO_PARAMS)
        result = self.resource.meta.get_app_info(**GET_APP_INFO_PARAMS)
        result = ordered_dict_to_json(result)
        self.assertEqual(result, GET_APP_INFO_DATA)

    @mock.patch("meta.resources.api.bk_paas.uni_apps_query", mock.Mock(return_value=[]))
    @mock.patch("meta.resources.SearchLogPermission.any_search_log_permission", mock.Mock(return_value=None))
    def test_get_app_info_of_not_resp(self):
        """GetAppInfoResource"""
        with self.assertRaises(BKAppNotExists):
            self.resource.meta.get_app_info(**GET_APP_INFO_PARAMS)

    def test_resource_type_schema(self):
        """ResourceTypeSchema"""
        System.objects.filter().delete()
        System.objects.create(**SYSTEM_OF_SCHEMA_DATA)
        self.resource.meta.resource_type_schema(**RESOURCE_TYPE_SCHEMA_PARAMS)
        result = self.resource.meta.resource_type_schema(**RESOURCE_TYPE_SCHEMA_PARAMS)
        self.assertEqual(result, [])

    def test_set_global_meta_config(self):
        """SetGlobalMetaConfigResource"""
        result = self.resource.meta.set_global_meta_config(**SET_GLOBAL_META_CONFIG_PARAMS)
        self.assertEqual(result, SET_GLOBAL_META_CONFIG_DATA)

    def test_get_global_meta_config_info(self):
        """GetGlobalMetaConfigInfoResource"""
        self.test_set_global_meta_config()
        result = self.resource.meta.get_global_meta_config_info(**GET_GLOBAL_META_CONFIG_INFO_PARAMS)
        self.assertEqual(result, GET_GLOBAL_META_CONFIG_INFO_DATA)

    @mock.patch("meta.resources.api.bk_log.bizs_list", mock.Mock(return_value=BIZS_LIST_API_RESP))
    @mock.patch(
        "meta.resources.settings.BKLOG_PERMISSION_VERSION",
        mock.Mock(return_value=BKLOG_PERMISSION_VERSION_API_RESP),
    )
    def test_get_spaces_mine(self):
        """GetSpacesMineResource"""
        result = self.resource.meta.get_spaces_mine()
        result = ordered_dict_to_json(result)
        self.assertEqual(result, GET_SPACES_MINE_DATA)

    @mock.patch("meta.resources.api.bk_log.get_spaces_mine", mock.Mock(return_value=GET_SPACES_MINE_API_RESP))
    def test_get_spaces_mine_of_v2(self):
        """GetSpacesMineResource"""
        result = self.resource.meta.get_spaces_mine()
        result = ordered_dict_to_json(result)
        self.assertEqual(result, GET_SPACES_MINE_OF_V2_DATA)

    @mock.patch("meta.resources.api.user_manage.list_users", mock.Mock(return_value=LIST_USERS_API_RESP))
    def test_list_users(self):
        """ListUsersResource"""
        result = self.resource.meta.list_users(**LIST_USERS_PARAMS)
        self.assertEqual(result, LIST_USERS_DATA)

    @mock.patch("meta.resources.api.user_manage.retrieve_user", mock.Mock(return_value=RETRIEVE_USER_API_RESP))
    def test_retrieve_user(self):
        """RetrieveUserResource"""
        self.resource.meta.retrieve_user(**RETRIEVE_USER_PARAMS)
        result = self.resource.meta.retrieve_user(**RETRIEVE_USER_PARAMS)
        self.assertEqual(result, RETRIEVE_USER_DATA)

    def test_get_global_choices(self):
        """GetGlobalChoicesResource"""
        result = self.resource.meta.get_global_choices()
        self.assertEqual(result, GLOBAL_CHOICES)


class TestChangeSystemDiagnosisPushResource(TestCase):
    @mock.patch.object(SystemDiagnosisPushHandler, "change_push_status", return_value=True)
    def test_change_push_enable_success(self, mock_change_push_status):
        """
        测试启用系统诊断推送时，接口返回成功（True）。
        """
        system = System.objects.create(**SYSTEM_DATA2)
        validated_request_data = {"system_id": system.system_id, "enable": True}
        response = self.resource.meta.change_system_diagnosis_push(validated_request_data)
        self.assertEqual(response, {"success": True})
        # 验证调用时传入的参数
        mock_change_push_status.assert_called_once_with(enable_push=True)

    @mock.patch.object(SystemDiagnosisPushHandler, "change_push_status", return_value=True)
    def test_change_push_disable_success(self, mock_change_push_status):
        """
        测试禁用系统诊断推送时，接口返回成功（True）。
        """
        system = System.objects.create(**SYSTEM_DATA2)
        validated_request_data = {"system_id": system.system_id, "enable": False}
        response = self.resource.meta.change_system_diagnosis_push(validated_request_data)
        self.assertEqual(response, {"success": True})
        mock_change_push_status.assert_called_once_with(enable_push=False)


class TestDeleteSystemDiagnosisPushResource(TestCase):
    @mock.patch.object(SystemDiagnosisPushHandler, "delete_push")
    def test_delete_push(self, mock_delete_push):
        """
        测试删除系统诊断推送时，delete_push 方法被正确调用。
        该接口不返回数据，默认返回 None。
        """
        system = System.objects.create(**SYSTEM_DATA2)
        validated_request_data = {"system_id": system.system_id}
        result = self.resource.meta.delete_system_diagnosis_push(validated_request_data)
        self.assertIsNone(result)
        mock_delete_push.assert_called_once_with()
