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

from core.utils.data import ordered_dict_to_json
from services.web.databus.models import StorageOperateLog
from services.web.databus.storage.serializers import StorageCustomOptionSerializer
from tests.base import TestCase
from tests.test_databus.collector_plugin.constants import (
    CREATE_PLUGIN_DATA as CREATE_PLUGIN_API_RESP,
)
from tests.test_databus.storage.constants import (
    CLUSTER_ID,
    CREATE_OR_UPDATE_REDIS_DATA,
    CREATE_OR_UPDATE_REDIS_PARAMS,
    CREATE_REPLICA_STORAGE_PARAMS,
    CREATE_STORAGE_PARAMS,
    GET_STORAGES_API_RESP,
    REPLICA_STORAGE_ACTIVATE_PARAMS,
    REPLICA_WRITE_CLUSTER_ID,
    STORAGE_ACTIVATE_PARAMS,
    STORAGE_LIST_DATA,
    STORAGE_LIST_PARAMS,
    STORAGE_OPERATE_LOG_DATA,
    USERNAME,
)


class StorageTest(TestCase):
    def setUp(self) -> None:
        self.storage_operate_log = StorageOperateLog.objects.create(**STORAGE_OPERATE_LOG_DATA)

    @mock.patch("databus.storage.resources.cache.get", mock.Mock(return_value=None))
    def test_storage_activate(self):
        """StorageActivateResource"""
        result = self.resource.databus.storage.storage_activate(**STORAGE_ACTIVATE_PARAMS)
        self.assertEqual(int(result), STORAGE_ACTIVATE_PARAMS["cluster_id"])

    @mock.patch("databus.storage.resources.cache.get", mock.Mock(return_value=None))
    def test_replica_storage_activate(self):
        """StorageActivateResource"""
        result = self.resource.databus.storage.storage_activate(**REPLICA_STORAGE_ACTIVATE_PARAMS)
        self.assertEqual(int(result), REPLICA_STORAGE_ACTIVATE_PARAMS["cluster_id"])

    @mock.patch("databus.storage.resources.api.bk_log.get_storages", mock.Mock(return_value=GET_STORAGES_API_RESP))
    def test_storage_list(self):
        """StorageListResource"""
        StorageOperateLog.objects.all().update(operate_at=self.storage_operate_log.operate_at)
        result = self.resource.databus.storage.storage_list(**STORAGE_LIST_PARAMS)
        result = ordered_dict_to_json(result)
        self.assertEqual(result, STORAGE_LIST_DATA)

    @mock.patch("databus.storage.resources.cache.get", mock.Mock(return_value=None))
    @mock.patch(
        "databus.storage.resources.resource.databus.collector_plugin.create_plugin",
        mock.Mock(return_value=CREATE_PLUGIN_API_RESP),
    )
    @mock.patch("databus.storage.resources.api.bk_log.create_storage", mock.Mock(return_value=CLUSTER_ID))
    def test_create_storage(self):
        """CreateStorageResource"""
        result = self.resource.databus.storage.create_storage(**CREATE_STORAGE_PARAMS)
        self.assertEqual(result, CLUSTER_ID)

    @mock.patch("databus.storage.resources.cache.get", mock.Mock(return_value=None))
    @mock.patch(
        "databus.storage.resources.resource.databus.collector_plugin.create_plugin",
        mock.Mock(return_value=CREATE_PLUGIN_API_RESP),
    )
    @mock.patch("databus.storage.resources.api.bk_log.create_storage", mock.Mock(return_value=REPLICA_WRITE_CLUSTER_ID))
    def test_create_replica_storage(self):
        """CreateStorageResource"""
        result = self.resource.databus.storage.create_storage(**CREATE_REPLICA_STORAGE_PARAMS)
        self.assertEqual(result, REPLICA_WRITE_CLUSTER_ID)

    @mock.patch("bk_resource.api.bk_base.create_resource_set", mock.Mock(return_value={}))
    @mock.patch("services.web.databus.storage.handler.redis.get_request_username", mock.Mock(return_value=USERNAME))
    def test_create_or_update_redis(self):
        """CreateOrUpdateRedisResource"""
        result = self.resource.databus.storage.create_or_update_redis(**CREATE_OR_UPDATE_REDIS_PARAMS)
        result = ordered_dict_to_json(result)
        result.pop("redis_id", None)
        result.pop("is_deleted", None)
        self.assertEqual(result, CREATE_OR_UPDATE_REDIS_DATA)

    def test_redis_permission_mapping(self):
        """BKSEC 1578945：redis 端点按 redis_id 拆分 CREATE/EDIT 权限"""
        from services.web.databus.storage.views import StoragesViewSet

        view = StoragesViewSet()
        view.action = "redis"
        view.request = mock.Mock(data={})
        self.assertEqual(view.get_permissions()[0].actions[0].id, "create_storage")
        view.request = mock.Mock(data={"redis_id": 1})
        self.assertEqual(view.get_permissions()[0].actions[0].id, "edit_storage")

    @mock.patch("bk_resource.api.bk_base.create_resource_set", mock.Mock(return_value={}))
    @mock.patch("services.web.databus.storage.handler.redis.get_request_username", mock.Mock(return_value=USERNAME))
    def test_create_redis_response_excludes_password(self):
        """BKSEC 1578945：创建响应剔除 password，保留非敏感字段"""
        result = self.resource.databus.storage.create_or_update_redis(**CREATE_OR_UPDATE_REDIS_PARAMS)
        result = ordered_dict_to_json(result)
        self.assertNotIn("password", result["connection_info"])
        self.assertEqual(result["connection_info"]["host"], CREATE_OR_UPDATE_REDIS_PARAMS["connection_info"]["host"])

    def test_redis_framework_log_disabled(self):
        """BKSEC 1578945：框架明文请求日志已关闭（双保险）"""
        from services.web.databus.storage.resources import CreateOrUpdateRedisResource

        self.assertFalse(CreateOrUpdateRedisResource.support_data_collect)

    def test_redis_redacted_log_keeps_context_without_password(self):
        """BKSEC 1578945：自记录脱敏日志保留排障字段、剔除密码（成功路径）"""
        from services.web.databus.storage.resources import CreateOrUpdateRedisResource

        req = {
            "namespace": "default",
            "connection_info": {"host": "synth.example.com", "port": 6379, "password": "SYNTH-PWD-123"},
        }
        with self.assertLogs("app", level="INFO") as captured:
            CreateOrUpdateRedisResource()._log_redacted(req, {"redis_id": 1})
        text = "\n".join(captured.output)
        self.assertNotIn("SYNTH-PWD-123", text)
        self.assertIn("synth.example.com", text)
        self.assertIn("***", text)

    def test_redis_failure_log_records_controlled_fields_only(self):
        """BKSEC 1578945（评审P1）：失败日志只记受控字段，异常消息含合成凭据也不外泄"""
        from services.web.databus.storage.resources import CreateOrUpdateRedisResource

        req = {
            "namespace": "default",
            "connection_info": {"host": "synth.example.com", "port": 6379, "password": "SYNTH-PWD-123"},
        }
        # 上游异常消息携带未登记的合成凭据（模拟 BKBase 错误响应回显口令原文）
        err = RuntimeError("synthetic upstream failure SYNTH-LEAK-PWD-456 SYNTH-LEAK-TOKEN")
        with self.assertLogs("app", level="INFO") as captured:
            CreateOrUpdateRedisResource()._log_failure(req, err)
        text = "\n".join(captured.output)
        self.assertNotIn("SYNTH-LEAK-PWD-456", text)      # 异常消息中的凭据不落日志
        self.assertNotIn("SYNTH-LEAK-TOKEN", text)
        self.assertNotIn("synthetic upstream failure", text)  # str(err) 自由文本不落日志
        self.assertIn("RuntimeError", text)               # 异常类型（受控字段）
        self.assertIn("RequestID =>", text)               # 请求 ID（受控字段）
        self.assertIn("synth.example.com", text)          # 脱敏请求体保留排障上下文
        self.assertNotIn("SYNTH-PWD-123", text)           # 请求体密码脱敏

    def test_redis_failure_log_via_request_path(self):
        """BKSEC 1578945（评审P1）：请求路径异常分支走受控失败日志（不落 str(err)）"""
        from services.web.databus.storage.resources import CreateOrUpdateRedisResource

        with mock.patch.object(
            CreateOrUpdateRedisResource,
            "perform_request",
            side_effect=RuntimeError("synthetic bkbase error SYNTH-LEAK-PWD-789"),
        ):
            instance = CreateOrUpdateRedisResource()
            with self.assertLogs("app", level="INFO") as captured:
                with self.assertRaises(RuntimeError):
                    instance.request(request_data=CREATE_OR_UPDATE_REDIS_PARAMS)
        text = "\n".join(captured.output)
        self.assertNotIn("SYNTH-LEAK-PWD-789", text)
        self.assertNotIn("synthetic bkbase error", text)
        self.assertIn("[Failed]", text)
        self.assertIn("RuntimeError", text)

    @mock.patch("bk_resource.api.bk_base.create_resource_set", mock.Mock(return_value={}))
    @mock.patch("services.web.databus.storage.handler.redis.get_request_username", mock.Mock(return_value=USERNAME))
    def test_redis_redacted_log_direct_call_includes_kwargs(self):
        """BKSEC 1578945：resource 直调（**kwargs）场景脱敏日志含完整请求参数而非 null"""
        with self.assertLogs("app", level="INFO") as captured:
            self.resource.databus.storage.create_or_update_redis(**CREATE_OR_UPDATE_REDIS_PARAMS)
        text = "\n".join(captured.output)
        self.assertIn('"host": "host"', text)
        self.assertIn('"password": "***"', text)
        self.assertNotIn('"password": "password"', text)

    def test_admin_with_empty_string(self):
        """
        测试 admin 字段包含空字符串的情况
        根据日志: "admin": ["admin", ""] - 包含一个空字符串
        """
        # 模拟日志中返回的数据格式
        test_data = {
            "bk_biz_id": 19069,
            "hot_warm_config": {
                "is_enabled": False,
                "hot_attr_name": "",
                "hot_attr_value": "",
                "warm_attr_name": "",
                "warm_attr_value": "",
            },
            "source_type": "other",
            "visible_config": {"visible_type": "current_biz", "visible_bk_biz": [], "bk_biz_labels": {}},
            "setup_config": {
                "retention_days_default": 30,
                "number_of_replicas_default": 1,
                "retention_days_max": 30,
                "number_of_replicas_max": 1,
                "es_shards_default": 3,
                "es_shards_max": 512,
            },
            "admin": ["admin", ""],
            "description": "审计中心存储集群",
        }

        serializer = StorageCustomOptionSerializer(data=test_data)
        if serializer.is_valid():
            print(f"admin 字段值: {serializer.validated_data.get('admin')}")
        else:
            print("验证失败!")
            print(f"错误信息: {serializer.errors}")

        self.assertTrue(serializer.is_valid(), f"序列化验证失败: {serializer.errors}")
        self.assertEqual(serializer.validated_data.get('admin'), ["admin", ""])

        return serializer.is_valid()


class FakeSM2Cipher:
    """模拟真实 SM2 的「密文/明文不可互换」：只接受自己产出的密文。"""

    PREFIX = "SM2#"

    def encrypt(self, plaintext: str) -> str:
        return "{}{}".format(self.PREFIX, plaintext)

    def decrypt(self, ciphertext: str) -> str:
        if not (isinstance(ciphertext, str) and ciphertext.startswith(self.PREFIX)):
            raise ValueError("decrypt failed: not a ciphertext")
        return ciphertext[len(self.PREFIX) :]


class StoragePasswordContractTest(TestCase):
    """CreateStorageResource 的密码是接口契约：入参密文，送 bk_log 前解密为明文。"""

    def setUp(self):
        for target in (
            "databus.storage.resources.StorageConfig",
            "databus.storage.resources.StorageOperateLog",
            "databus.storage.resources.GlobalMetaConfig",
        ):
            patcher = mock.patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)
        cipher_patcher = mock.patch("databus.storage.resources.asymmetric_cipher", new=FakeSM2Cipher())
        cipher_patcher.start()
        self.addCleanup(cipher_patcher.stop)

    @staticmethod
    def _params(password: str) -> dict:
        params = {**CREATE_STORAGE_PARAMS}
        params["auth_info"] = {"username": "u", "password": password}
        return params

    def test_plaintext_password_rejected(self):
        """明文直接进资源层会解密失败——即初始化链路原样透传时的故障形态。"""
        with self.assertRaises(ValueError):
            self.resource.databus.storage.create_storage(**self._params("PLAIN-PWD"))

    def test_ciphertext_password_decrypted_for_api(self):
        """边界加密后的值交给资源层，真正送给 bk_log 的必须是原始口令。"""
        api_mock = mock.Mock(return_value=CLUSTER_ID)
        with mock.patch("databus.storage.resources.api.bk_log.create_storage", api_mock):
            self.resource.databus.storage.create_storage(**self._params("SM2#PLAIN-PWD"))
        sent = api_mock.call_args[0][0]
        self.assertEqual(sent["auth_info"]["password"], "PLAIN-PWD")
