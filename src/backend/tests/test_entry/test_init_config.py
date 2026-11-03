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
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

初始化流程单测：完成标记写入、重复执行跳过、资源调用失败时不泄漏嵌套凭据。
"""
import io
import json
import os
import sys
import threading
import uuid
from unittest import mock

from django.test import SimpleTestCase
from django.test.utils import override_settings

from core.kms import (
    INIT_PASSWORD_ENCODING_CIPHERTEXT,
    INIT_PASSWORD_ENCODING_FIELD,
    INIT_PASSWORD_ENCODING_PLAINTEXT,
    get_secret_json,
)
from core.sensitive import clear_sensitive, install_redacted_excepthook
from services.web.entry.constants import (
    INIT_DORIS_FISHED_KEY,
    INIT_ES_FISHED_KEY,
    INIT_REDIS_FISHED_KEY,
)
from services.web.entry.init.base import SystemInitHandler, adapt_auth_password

# 合成配置（含嵌套凭据），不含任何真实凭据
ES_CONFIG = [{"cluster_name": "es-1", "auth_info": {"username": "admin", "password": "SYNTHETIC-ES-PWD-0001"}}]
REDIS_CONFIG = [{"name": "redis-1", "password": "SYNTHETIC-REDIS-PWD-0001"}]
DORIS_CONFIG = [
    {
        "cluster_name": "doris-1",
        "pre_defined": True,
        "pre_defined_extra_config": {"auth": {"password": "SYNTHETIC-DORIS-PWD-0001"}},
    }
]
NESTED_PASSWORDS = ["SYNTHETIC-ES-PWD-0001", "SYNTHETIC-REDIS-PWD-0001", "SYNTHETIC-DORIS-PWD-0001"]


@override_settings(BKAPP_INIT_SYSTEM="True")
class TestInitFinishedFlag(SimpleTestCase):
    """首轮初始化必须写入完成标记，已完成的必须跳过。"""

    def setUp(self):
        clear_sensitive()

    def tearDown(self):
        clear_sensitive()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch("services.web.entry.init.base.get_secret_json", return_value=[])
    def test_init_es_marks_finished_on_first_run(self, _mock_secret_json, _mock_get, mock_set):
        SystemInitHandler().init_es()
        mock_set.assert_any_call(INIT_ES_FISHED_KEY, True)

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch("services.web.entry.init.base.get_secret_json", return_value=[])
    def test_init_doris_marks_finished_on_first_run(self, _mock_secret_json, _mock_get, mock_set):
        SystemInitHandler().init_doris()
        mock_set.assert_any_call(INIT_DORIS_FISHED_KEY, True)

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch("services.web.entry.init.base.get_secret_json", return_value=[])
    def test_init_redis_marks_finished_on_first_run(self, _mock_secret_json, _mock_get, mock_set):
        SystemInitHandler().init_redis()
        mock_set.assert_any_call(INIT_REDIS_FISHED_KEY, True)

    @mock.patch("services.web.entry.init.base.get_secret_json")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=True)
    def test_init_es_skipped_when_already_finished(self, _mock_get, mock_secret_json):
        SystemInitHandler().init_es()
        mock_secret_json.assert_not_called()

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch("services.web.entry.init.base.get_secret_json", return_value=[{"cluster_name": "es-1"}])
    @mock.patch.object(SystemInitHandler, "_init_es")
    def test_init_es_with_config_marks_finished(self, mock_init_es, _mock_secret_json, _mock_get, mock_set):
        """非空配置：逐项初始化完成后同样要写入完成标记。"""
        SystemInitHandler().init_es()
        mock_init_es.assert_called_once_with({"cluster_name": "es-1"})
        mock_set.assert_any_call(INIT_ES_FISHED_KEY, True)


@override_settings(BKAPP_INIT_SYSTEM="True")
class TestInitFailureNotLeak(SimpleTestCase):
    """资源调用失败时，完整 stderr 不得包含嵌套在配置里的密码。"""

    def setUp(self):
        clear_sensitive()
        origin_excepthook, origin_threading_hook = sys.excepthook, threading.excepthook
        install_redacted_excepthook()
        self.addCleanup(setattr, sys, "excepthook", origin_excepthook)
        self.addCleanup(setattr, threading, "excepthook", origin_threading_hook)

    def tearDown(self):
        clear_sensitive()

    def _capture_excepthook(self, func):
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            try:
                func()
            except Exception as err:  # noqa: BLE001 - 走 excepthook 输出，断言其内容
                sys.excepthook(type(err), err, err.__traceback__)
        return stderr.getvalue()

    def _loaded(self, env_key, config):
        """走真实取值链（含递归登记嵌套敏感值），确保测试与生产同一条路径。"""
        with mock.patch.dict(os.environ, {env_key: json.dumps(config)}):
            self.addCleanup(clear_sensitive)
            return get_secret_json(env_key)

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    def test_es_malformed_json_not_leak(self, _mock_get):
        """初始化配置 JSON 非法（缺闭合括号）时，完整 stderr 不得含合成密码。

        哨兵在运行时生成，且用命中敏感变量名规则的变量保存：
        固定字面量会被 stackprinter 连同本用例的源码行一起展示，造成误报。
        """
        password = "SYNTHETIC-MALFORMED-%s" % uuid.uuid4().hex
        padding = "x" * 400
        with mock.patch.dict(
            os.environ,
            {"BKAPP_INIT_ES_CONFIG": '[{{"auth": {{"password": "{}"}}, "note": "{}"'.format(password, padding)},
        ):
            output = self._capture_excepthook(lambda: SystemInitHandler().init_es())
        self.assertNotIn(password, output)

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch(
        "services.web.entry.init.base.resource.databus.storage.create_storage",
        side_effect=RuntimeError("create_storage failed"),
    )
    def test_es_failure_not_leak(self, _mock_storage, _mock_get):
        es_configs = self._loaded("BKAPP_INIT_ES_CONFIG", ES_CONFIG)
        output = self._capture_excepthook(lambda: SystemInitHandler()._init_es(es_configs[0]))
        self.assertIn("create_storage failed", output)
        for password in NESTED_PASSWORDS:
            self.assertNotIn(password, output)

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch(
        "services.web.entry.init.base.resource.databus.storage.create_storage",
        side_effect=RuntimeError("create_storage failed"),
    )
    def test_doris_failure_not_leak(self, _mock_storage, _mock_get):
        doris_configs = self._loaded("BKAPP_INIT_DORIS_CONFIG", DORIS_CONFIG)
        output = self._capture_excepthook(lambda: SystemInitHandler()._init_doris(doris_configs[0]))
        self.assertIn("create_storage failed", output)
        for password in NESTED_PASSWORDS:
            self.assertNotIn(password, output)

    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    @mock.patch(
        "services.web.entry.init.base.resource.databus.storage.create_or_update_redis",
        side_effect=RuntimeError("create_or_update_redis failed"),
    )
    def test_redis_failure_not_leak(self, _mock_redis, _mock_get):
        redis_configs = self._loaded("BKAPP_INIT_REDIS_CONFIG", REDIS_CONFIG)
        output = self._capture_excepthook(lambda: SystemInitHandler()._init_redis(redis_configs[0]))
        self.assertIn("create_or_update_redis failed", output)
        for password in NESTED_PASSWORDS:
            self.assertNotIn(password, output)


class FakeRoundTripCipher:
    """模拟真实 SM2 的「密文/明文不可互换」：只接受自己产出的密文。"""

    PREFIX = "SM2#"

    def encrypt(self, plaintext: str) -> str:
        return "{}{}".format(self.PREFIX, plaintext)

    def decrypt(self, ciphertext: str) -> str:
        if not (isinstance(ciphertext, str) and ciphertext.startswith(self.PREFIX)):
            raise ValueError("decrypt failed: not a ciphertext")
        return ciphertext[len(self.PREFIX) :]


@override_settings(BKAPP_INIT_SYSTEM="True")
class TestInitPasswordEncoding(SimpleTestCase):
    """初始化边界按显式编码声明适配 auth_info.password：原始口令加密，已有密文透传。"""

    LEGACY_CIPHERTEXT = "SM2#REAL-PWD"

    @staticmethod
    def _config(password: str, encoding: str = INIT_PASSWORD_ENCODING_CIPHERTEXT) -> dict:
        """encoding 默认「已有密文」：宿主环境变量与扁平 KMS 包都是这个来源。"""
        return {
            "cluster_name": "es-1",
            "auth_info": {"username": "u", "password": password, INIT_PASSWORD_ENCODING_FIELD: encoding},
        }

    @override_settings(ENABLE_BKCRYPTO=False)
    @mock.patch("services.web.entry.init.base.asymmetric_cipher", new=FakeRoundTripCipher())
    def test_switch_off_keeps_plaintext(self):
        """业务加密关闭：FakeAsymmetricCipher 加解密恒等，口令原样传递。"""
        config = self._config("PLAIN-PWD", INIT_PASSWORD_ENCODING_PLAINTEXT)
        adapt_auth_password(config)
        self.assertEqual(config["auth_info"]["password"], "PLAIN-PWD")

    @override_settings(ENABLE_BKCRYPTO=True)
    @mock.patch("services.web.entry.init.base.asymmetric_cipher", new=FakeRoundTripCipher())
    def test_plaintext_encrypted_when_bkcrypto_enabled(self):
        """声明为原始口令：加密成资源层要求的 C。"""
        config = self._config("PLAIN-PWD", INIT_PASSWORD_ENCODING_PLAINTEXT)
        adapt_auth_password(config)
        self.assertEqual(config["auth_info"]["password"], "SM2#PLAIN-PWD")

    @override_settings(ENABLE_BKCRYPTO=True)
    @mock.patch("services.web.entry.init.base.asymmetric_cipher", new=FakeRoundTripCipher())
    def test_password_looking_like_ciphertext_still_encrypted(self):
        """声明为原始口令的串，即使恰好可被解开也必须加密，不能靠「能否解密」猜编码。"""
        config = self._config("SM2#inner", INIT_PASSWORD_ENCODING_PLAINTEXT)
        adapt_auth_password(config)
        self.assertEqual(config["auth_info"]["password"], "SM2#SM2#inner")
        self.assertEqual(FakeRoundTripCipher().decrypt(config["auth_info"]["password"]), "SM2#inner")

    @override_settings(ENABLE_BKCRYPTO=True)
    @mock.patch("services.web.entry.init.base.asymmetric_cipher", new=FakeRoundTripCipher())
    def test_legacy_ciphertext_not_encrypted_twice(self):
        config = self._config(self.LEGACY_CIPHERTEXT)
        adapt_auth_password(config)
        self.assertEqual(config["auth_info"]["password"], self.LEGACY_CIPHERTEXT)
        self.assertEqual(FakeRoundTripCipher().decrypt(config["auth_info"]["password"]), "REAL-PWD")

    @override_settings(ENABLE_BKCRYPTO=True)
    @mock.patch("services.web.entry.init.base.asymmetric_cipher", new=FakeRoundTripCipher())
    def test_legacy_ciphertext_explicitly_marked_kept(self):
        """显式声明为密文的输入同样不得二次加密（保留两种输入的契约）。"""
        config = self._config(self.LEGACY_CIPHERTEXT, INIT_PASSWORD_ENCODING_CIPHERTEXT)
        adapt_auth_password(config)
        self.assertEqual(config["auth_info"]["password"], self.LEGACY_CIPHERTEXT)

    @override_settings(ENABLE_BKCRYPTO=True)
    @mock.patch("services.web.entry.init.base.asymmetric_cipher", new=FakeRoundTripCipher())
    def test_flat_kms_ciphertext_kept_when_bkcrypto_enabled(self):
        """KMS 开启但凭证包是旧扁平形态：整串 *CONFIG 直接给出密文，不得再加密。"""
        config = self._config(self.LEGACY_CIPHERTEXT)
        adapt_auth_password(config)
        self.assertEqual(config["auth_info"]["password"], self.LEGACY_CIPHERTEXT)
        self.assertEqual(FakeRoundTripCipher().decrypt(config["auth_info"]["password"]), "REAL-PWD")

    @override_settings(ENABLE_BKCRYPTO=True)
    @mock.patch("services.web.entry.init.base.asymmetric_cipher", new=FakeRoundTripCipher())
    @mock.patch("services.web.entry.init.base.resource.databus.storage.storage_activate")
    @mock.patch("services.web.entry.init.base.resource.databus.storage.create_storage", return_value=101)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    def test_init_es_sends_ciphertext_to_resource(self, _mock_set, mock_create, _mock_activate):
        SystemInitHandler()._init_es(self._config("PLAIN-PWD", INIT_PASSWORD_ENCODING_PLAINTEXT))
        sent = mock_create.call_args[0][0]["auth_info"]
        self.assertEqual(sent["password"], "SM2#PLAIN-PWD")
        self.assertEqual(FakeRoundTripCipher().decrypt(sent["password"]), "PLAIN-PWD")

    @override_settings(ENABLE_BKCRYPTO=True)
    @mock.patch("services.web.entry.init.base.asymmetric_cipher", new=FakeRoundTripCipher())
    @mock.patch("services.web.entry.init.base.resource.databus.storage.storage_activate")
    @mock.patch("services.web.entry.init.base.resource.databus.storage.create_storage", return_value=101)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    def test_init_es_sends_legacy_ciphertext_as_is(self, _mock_set, mock_create, _mock_activate):
        """旧宿主/扁平 KMS 密文的实际请求回归：资源层收到的仍是原密文，且编码声明不外泄。"""
        SystemInitHandler()._init_es(self._config(self.LEGACY_CIPHERTEXT))
        sent = mock_create.call_args[0][0]["auth_info"]
        self.assertEqual(sent["password"], self.LEGACY_CIPHERTEXT)
        self.assertEqual(FakeRoundTripCipher().decrypt(sent["password"]), "REAL-PWD")
        self.assertNotIn(INIT_PASSWORD_ENCODING_FIELD, sent)

    @override_settings(ENABLE_BKCRYPTO=True)
    @mock.patch("services.web.entry.init.base.asymmetric_cipher", new=FakeRoundTripCipher())
    @mock.patch("services.web.entry.init.base.resource.databus.storage.storage_activate")
    @mock.patch("services.web.entry.init.base.resource.databus.storage.create_storage", return_value=102)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    def test_init_doris_sends_legacy_ciphertext_as_is(self, _mock_set, mock_create, _mock_activate):
        """Doris 同口径：已有密文原样下发，编码声明不外泄。"""
        config = {
            "cluster_name": "doris-1",
            "pre_defined": True,
            "pre_defined_extra_config": {},
            "auth_info": {"username": "u", "password": self.LEGACY_CIPHERTEXT},
        }
        SystemInitHandler()._init_doris(config)
        sent = mock_create.call_args[0][0]["auth_info"]
        self.assertEqual(sent["password"], self.LEGACY_CIPHERTEXT)
        self.assertNotIn(INIT_PASSWORD_ENCODING_FIELD, sent)
