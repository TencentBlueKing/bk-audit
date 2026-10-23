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

bk-crypto-python-sdk 2.0.1 -> 4.1.1 兼容性单测。

以下固定样例由 bk-crypto-python-sdk==2.0.1 在 SM4 / SM2 下生成（合成数据，非真实凭据），
用于验证升级后仍能解密 GlobalMetaConfig 中保存的业务私钥、并使用历史 SM2 私钥解密/验签。
"""
import unittest
from importlib.metadata import version

from bkcrypto.asymmetric.options import SM2AsymmetricOptions
from bkcrypto.constants import AsymmetricCipherType, SymmetricCipherType
from bkcrypto.contrib.basic.ciphers import get_asymmetric_cipher, get_symmetric_cipher

SDK_VERSION = version("bk-crypto-python-sdk")

# ---- 2.0.1 生成的固定样例 ----
SYMMETRIC_KEY = "bkaudit-compat-fixture-key-0123456789abcdef"
PRIVATE_KEY_PLAINTEXT = "bkaudit-compat-fixture-business-private-key-0001"
ENCRYPTED_PRIVATE_KEY = "elXyK7jYqr4OT9M/ENoJSs76ReERKiU3xxVojDumBgUb4wO0t00qp3OsF+rim+N8dG1eO+M+VIQVxpi/EcorXA=="

SM2_PRIVATE_KEY = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIOCGBdOA+m4CXSzEDFRPvHp3n4UQ2T2M2JD5OdKcb234oAoGCCqBHM9V
AYItoUQDQgAErBLeiL2TpSm4GoW5MjB9TkARvTOFejklKf4z3tyuvfW79BevUM98
cK2a2axWo788adB2rmzU57gUQ4ZQiDw2rw==
-----END EC PRIVATE KEY-----
"""

MESSAGE = "bk-audit-compat-message-001"
SM2_CIPHERTEXT = (
    "MIGDAiB2/SWafpQ2pnwx6MtmGhJiZhqV6hrQ8gxOSpcqx9MqOwIgB43GhHqtRlbJc1Xu4LK6IG1KwwDiIZDGCSEa1wq3SBQEIEZZS3k5"
    "pm857LLb2PSZWLu+Vh5SrzCEsxVpIQkaI7uxBBsEDzJShkefsss4EbAIy9e2oSuIFsqhjPFAFpA="
)
SM2_SIGNATURE = "MEUCIHHHJVKhGDVcOR2IA6b2WGvUotatJ/0jnHIlvVhF34gVAiEAilx0vJ+JZ6VQ/u0q6wiXT+I02qNbl3lqSU5EWvugNkA="


class TestLegacySdkFixtureCompat(unittest.TestCase):
    """2.0.1 生成的密文/签名在当前版本下必须可解密/验签。"""

    def test_sm4_decrypt_legacy_private_key(self):
        cipher = get_symmetric_cipher(cipher_type=SymmetricCipherType.SM4.value, common={"key": SYMMETRIC_KEY})
        decrypted = cipher.decrypt(ENCRYPTED_PRIVATE_KEY)
        self.assertEqual(
            decrypted,
            PRIVATE_KEY_PLAINTEXT,
            "bk-crypto-python-sdk==%s 无法解密 2.0.1 生成的业务私钥" % SDK_VERSION,
        )

    def test_sm2_decrypt_legacy_ciphertext(self):
        cipher = get_asymmetric_cipher(
            cipher_type=AsymmetricCipherType.SM2.value,
            cipher_options={AsymmetricCipherType.SM2.value: SM2AsymmetricOptions(private_key_string=SM2_PRIVATE_KEY)},
        )
        self.assertEqual(cipher.decrypt(SM2_CIPHERTEXT), MESSAGE, "SM2 私钥在 %s 下无法解密 2.0.1 密文" % SDK_VERSION)

    def test_sm2_verify_legacy_signature(self):
        cipher = get_asymmetric_cipher(
            cipher_type=AsymmetricCipherType.SM2.value,
            cipher_options={AsymmetricCipherType.SM2.value: SM2AsymmetricOptions(private_key_string=SM2_PRIVATE_KEY)},
        )
        self.assertTrue(
            cipher.verify(plaintext=MESSAGE, signature=SM2_SIGNATURE),
            "SM2 签名在 %s 下验签失败" % SDK_VERSION,
        )

    def test_sm4_round_trip_current_version(self):
        cipher = get_symmetric_cipher(cipher_type=SymmetricCipherType.SM4.value, common={"key": SYMMETRIC_KEY})
        self.assertEqual(cipher.decrypt(cipher.encrypt(PRIVATE_KEY_PLAINTEXT)), PRIVATE_KEY_PLAINTEXT)


class TestProjectCipherStack(unittest.TestCase):
    """项目实际使用的 cipher 组装方式（含 Django settings 与 Fake 子类）。"""

    def test_sm2_cipher_built_from_django_settings(self):
        # 与 apps/bk_crypto/crypto.py 的组装方式保持一致：走 django contrib + settings.BKCRYPTO
        from bkcrypto.contrib.django.ciphers import (
            get_asymmetric_cipher as get_django_asymmetric_cipher,
        )

        cipher = get_django_asymmetric_cipher(
            cipher_options={AsymmetricCipherType.SM2.value: SM2AsymmetricOptions(private_key_string=SM2_PRIVATE_KEY)}
        )
        self.assertEqual(cipher.decrypt(SM2_CIPHERTEXT), MESSAGE)

    def test_fake_asymmetric_cipher_compatible(self):
        """Fake 子类必须仍满足当前版本 BaseAsymmetricCipher 的契约。"""
        from apps.bk_crypto.crypto import FakeAsymmetricCipher

        cipher = FakeAsymmetricCipher()
        self.assertEqual(cipher.encrypt(MESSAGE), MESSAGE)
        self.assertEqual(cipher.decrypt(MESSAGE), MESSAGE)
        self.assertTrue(cipher.verify(plaintext=MESSAGE, signature=cipher.sign(MESSAGE)))
        self.assertEqual(cipher.generate_key_pair(), (cipher._private_key, cipher._public_key))
        self.assertTrue(cipher.export_private_key())

    def test_symmetric_cipher_of_bk_crypto_module(self):
        """apps.bk_crypto 的对称 cipher 在当前版本下可正常加解密业务私钥。"""
        from apps.bk_crypto.crypto import AsymmetricCipher

        symmetric_cipher = AsymmetricCipher.symmetric_cipher
        self.assertEqual(
            symmetric_cipher.decrypt(symmetric_cipher.encrypt(PRIVATE_KEY_PLAINTEXT)), PRIVATE_KEY_PLAINTEXT
        )
