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

from uuid import uuid1

from bkcrypto.contrib.django.ciphers import get_asymmetric_cipher
from django.conf import settings

from apps.bk_crypto.crypto import FakeAsymmetricCipher, asymmetric_cipher
from tests.base import TestCase


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


class EntryHandlerUserApiGwUrlTest(TestCase):
    """测试 EntryHandler.get_user_web_apigw_url 方法"""

    def test_get_user_web_apigw_url_default(self) -> None:
        """测试默认配置下的 URL 生成"""
        from unittest import mock

        from services.web.entry.handler.entry import EntryHandler

        with mock.patch.object(settings, 'BK_API_URL_TMPL', 'https://api.example.com/api/{api_name}'):
            with mock.patch.dict('os.environ', {'BKPAAS_ENVIRONMENT': 'prod'}):
                url = EntryHandler.get_user_web_apigw_url()
                self.assertEqual(url, 'https://api.example.com/api/bk-user-web/prod')
