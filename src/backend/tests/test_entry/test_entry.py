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

from types import SimpleNamespace
from unittest import mock
from uuid import uuid1

from bkcrypto.contrib.django.ciphers import get_asymmetric_cipher
from django.test import SimpleTestCase

from apps.bk_crypto.crypto import FakeAsymmetricCipher, asymmetric_cipher
from services.web.entry.handler.entry import EntryHandler
from tests.base import TestCase


class EntryHandlerTest(SimpleTestCase):
    @staticmethod
    def _build_request(username="admin"):
        return SimpleNamespace(user=SimpleNamespace(username=username))

    @staticmethod
    def _get_global_meta_config(configs=None):
        configs = configs or {}

        def _get(config_key, *args, **kwargs):
            return configs.get(config_key, kwargs.get("default"))

        return _get

    @mock.patch("services.web.entry.handler.entry.resource.permission.check_permission")
    @mock.patch("services.web.entry.handler.entry.GlobalMetaConfig.get")
    def test_entry_returns_empty_platform_admin_users_by_default(self, mock_get, mock_check_permission):
        mock_check_permission.return_value = {}
        mock_get.side_effect = self._get_global_meta_config()

        data = EntryHandler.entry(self._build_request())

        self.assertEqual(data["platform_admin_users"], [])

    @mock.patch("services.web.entry.handler.entry.resource.permission.check_permission")
    @mock.patch("services.web.entry.handler.entry.GlobalMetaConfig.get")
    def test_entry_returns_platform_admin_users_from_global_meta_config(self, mock_get, mock_check_permission):
        mock_check_permission.return_value = {}
        mock_get.side_effect = self._get_global_meta_config({"platform_admin_users": ["admin", "operator"]})

        data = EntryHandler.entry(self._build_request())

        self.assertEqual(data["platform_admin_users"], ["admin", "operator"])


class EntryTest(TestCase):
    def test_default_crypto(self) -> None:
        """测试加密"""

        random_text: str = uuid1().hex
        encrypt_text: str = asymmetric_cipher.encrypt(random_text)
        decrypt_text: str = asymmetric_cipher.decrypt(encrypt_text)
        self.assertEquals(random_text, decrypt_text)
        self.assertTrue(asymmetric_cipher.verify(plaintext=random_text, signature=asymmetric_cipher.sign(random_text)))

    def test_fake_crypto(self) -> None:
        """
        测试虚拟加密
        """

        random_text: str = uuid1().hex
        encrypt_text: str = FakeAsymmetricCipher().encrypt(random_text)
        self.assertEquals(random_text, encrypt_text)

    def test_asymmetric_crypto(self) -> None:
        """测试非对称加密"""

        random_text: str = uuid1().hex
        cipher = get_asymmetric_cipher()
        encrypt_text: str = cipher.encrypt(random_text)
        decrypt_text: str = cipher.decrypt(encrypt_text)
        self.assertEquals(random_text, decrypt_text)
        self.assertTrue(cipher.verify(plaintext=random_text, signature=cipher.sign(random_text)))
