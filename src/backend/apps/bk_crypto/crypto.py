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

import typing
from uuid import uuid1

from bkcrypto import types
from bkcrypto.asymmetric.ciphers import BaseAsymmetricCipher
from bkcrypto.asymmetric.options import SM2AsymmetricOptions
from bkcrypto.constants import AsymmetricCipherType
from bkcrypto.contrib.django.ciphers import get_asymmetric_cipher, get_symmetric_cipher
from bkcrypto.symmetric.ciphers import BaseSymmetricCipher
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import ProgrammingError

from apps.bk_crypto.constants import PRIVATE_KEY_CONFIG_NAME
from apps.exceptions import MetaConfigNotExistException
from apps.meta.constants import GLOBAL_CONFIG_LEVEL_INSTANCE, ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig


class FakeAsymmetricCipher(BaseAsymmetricCipher):
    _public_key = uuid1().hex
    _private_key = uuid1().hex

    @staticmethod
    def get_block_size(key_obj: typing.Any, is_encrypt: bool = True) -> typing.Optional[int]:
        return None

    def export_public_key(self) -> str:
        return self._public_key

    def export_private_key(self) -> str:
        return self._private_key

    def _load_public_key(self, public_key_string: types.PublicKeyString) -> str:
        return self._public_key

    def _load_private_key(self, private_key_string: types.PrivateKeyString) -> str:
        return self._private_key

    @staticmethod
    def load_public_key_from_pkey(private_key: typing.Any) -> str:
        return FakeAsymmetricCipher._public_key

    def generate_key_pair(self) -> typing.Tuple[types.PrivateKeyString, types.PublicKeyString]:
        return self._private_key, self._public_key

    def _encrypt(self, plaintext_bytes: bytes) -> bytes:
        return plaintext_bytes

    def _decrypt(self, ciphertext_bytes: bytes) -> bytes:
        return ciphertext_bytes

    def _sign(self, plaintext_bytes: bytes) -> bytes:
        return plaintext_bytes

    def _verify(self, plaintext_bytes: bytes, signature_types: bytes) -> bool:
        return plaintext_bytes == signature_types

    def encrypt(self, plaintext: str) -> str:
        return plaintext

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext


class AsymmetricCipher:
    """
    加解密
    """

    symmetric_cipher: BaseSymmetricCipher = get_symmetric_cipher(common={"key": settings.SECRET_KEY})

    def get_cipher(self):
        if settings.ENABLE_BKCRYPTO:
            try:
                private_key_string = GlobalMetaConfig.get(
                    config_key=PRIVATE_KEY_CONFIG_NAME,
                    config_level=ConfigLevelChoices.GLOBAL,
                    instance_key=GLOBAL_CONFIG_LEVEL_INSTANCE,
                )
                private_key_string = self.symmetric_cipher.decrypt(private_key_string)
            except (MetaConfigNotExistException, ProgrammingError):
                logger.warning(
                    "[PrivateKetNotExists] %s, %s, %s",
                    PRIVATE_KEY_CONFIG_NAME,
                    ConfigLevelChoices.GLOBAL,
                    GLOBAL_CONFIG_LEVEL_INSTANCE,
                )
                private_key_string = ""
            return get_asymmetric_cipher(
                cipher_options={
                    AsymmetricCipherType.SM2.value: SM2AsymmetricOptions(private_key_string=private_key_string)
                }
            )
        return FakeAsymmetricCipher()

    def init_private_key(self, *args, **kwargs):
        try:
            GlobalMetaConfig.get(
                config_key=PRIVATE_KEY_CONFIG_NAME,
                config_level=ConfigLevelChoices.GLOBAL,
                instance_key=GLOBAL_CONFIG_LEVEL_INSTANCE,
            )
        except (MetaConfigNotExistException, ProgrammingError):
            private_key = self.symmetric_cipher.encrypt(get_asymmetric_cipher().export_private_key())
            GlobalMetaConfig.set(
                config_key=PRIVATE_KEY_CONFIG_NAME,
                config_value=private_key,
                config_level=ConfigLevelChoices.GLOBAL,
                instance_key=GLOBAL_CONFIG_LEVEL_INSTANCE,
            )

    def encrypt_private_key(self, private_key: str) -> str:
        return self.symmetric_cipher.encrypt(private_key)

    def decrypt_private_key(self, private_key: str) -> str:
        return self.symmetric_cipher.decrypt(private_key)


asymmetric_cipher: BaseAsymmetricCipher = AsymmetricCipher().get_cipher()
