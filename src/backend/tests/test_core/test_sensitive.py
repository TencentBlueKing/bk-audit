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

脱敏工具单测：登记值清洗、键名脱敏、异常链净化。
"""
import json
import unittest

from core.sensitive import (
    REDACTED,
    clear_sensitive,
    redact_secrets,
    register_sensitive,
    sanitize_exception,
    scrub,
    strip_traceback,
)

PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\nSYNTHETIC-PRIVATE-KEY-BODY-0001\n-----END PRIVATE KEY-----\n"
PLAIN_PASSWORD = "SYNTHETIC-PLAIN-PASSWORD-0001"


class TestScrub(unittest.TestCase):
    def setUp(self):
        clear_sensitive()

    def tearDown(self):
        clear_sensitive()

    def test_registered_value_replaced(self):
        register_sensitive(PLAIN_PASSWORD)
        self.assertNotIn(PLAIN_PASSWORD, scrub("password=%s" % PLAIN_PASSWORD))
        self.assertIn(REDACTED, scrub("password=%s" % PLAIN_PASSWORD))

    def test_private_key_pattern_replaced_without_register(self):
        self.assertNotIn("SYNTHETIC-PRIVATE-KEY-BODY-0001", scrub(PRIVATE_KEY))

    def test_short_value_ignored(self):
        register_sensitive("123")
        self.assertEqual(scrub("v=123"), "v=123")


class TestRedactSecrets(unittest.TestCase):
    def setUp(self):
        clear_sensitive()

    def tearDown(self):
        clear_sensitive()

    def test_sensitive_key_replaced(self):
        config = {"host": "127.0.0.1", "port": 9200, "password": PLAIN_PASSWORD}
        redacted = redact_secrets(config)
        self.assertEqual(redacted["password"], REDACTED)
        self.assertEqual(redacted["host"], "127.0.0.1")
        self.assertEqual(redacted["port"], 9200)

    def test_nested_auth_replaced(self):
        config = [{"cluster_name": "es-1", "auth": {"username": "admin", "password": PLAIN_PASSWORD}}]
        redacted = redact_secrets(config)
        self.assertEqual(redacted[0]["auth"], REDACTED)
        self.assertEqual(redacted[0]["cluster_name"], "es-1")

    def test_registered_plaintext_in_string_replaced(self):
        register_sensitive(PLAIN_PASSWORD)
        redacted = redact_secrets({"connection_url": "http://user:%s@host" % PLAIN_PASSWORD})
        self.assertNotIn(PLAIN_PASSWORD, json.dumps(redacted, ensure_ascii=False))

    def test_non_secret_value_kept(self):
        self.assertEqual(redact_secrets({"timeout": 30, "enable": True}), {"timeout": 30, "enable": True})


class TestSanitizeException(unittest.TestCase):
    def setUp(self):
        clear_sensitive()

    def tearDown(self):
        clear_sensitive()

    def test_reason_is_scrubbed_and_truncated(self):
        register_sensitive(PLAIN_PASSWORD)

        def load():
            plaintext = "decrypted:%s" % PLAIN_PASSWORD
            raise ValueError("bad envelope %s" % plaintext)

        try:
            load()
        except ValueError as err:
            safe = sanitize_exception(err)
            self.assertNotIn(PLAIN_PASSWORD, str(safe))
            self.assertIsNone(safe.__traceback__)
            strip_traceback(err)
            self.assertIsNone(err.__traceback__)
