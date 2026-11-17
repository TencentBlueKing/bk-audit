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
import io
import json
import os
import sys
import unittest
from unittest import mock

from core import sensitive
from core.sensitive import (
    REDACTED,
    clear_sensitive,
    install_redacted_excepthook,
    redact_secrets,
    register_sensitive,
    registered_sensitive,
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

    def test_empty_string_not_registered(self):
        """顶层传入空串不得登记：否则之后所有异常文本会被插满标记。"""
        register_sensitive("")
        self.assertNotIn("", registered_sensitive())
        self.assertEqual(scrub("abc"), "abc")

    def test_top_level_string_always_registered(self):
        """顶层显式传入的字符串无条件登记（信封 / 私钥 / 整段明文），不受长度限制。"""
        register_sensitive("123")
        self.assertIn("123", registered_sensitive())
        self.assertEqual(scrub("v=123"), "v=%s" % REDACTED)

    def test_host_ip_not_registered(self):
        """配置里的 host / IP 不登记：异常堆栈里仍需保留排障信息。"""
        register_sensitive({"host": "10.0.0.17", "auth": {"username": "admin", "password": "p@ss"}})
        self.assertIn("p@ss", registered_sensitive())
        self.assertNotIn("10.0.0.17", registered_sensitive())
        self.assertEqual(scrub("connect to 10.0.0.17 failed"), "connect to 10.0.0.17 failed")

    def test_short_password_under_sensitive_key_is_registered(self):
        """键名命中的短密码必须登记：真实密码可能短于 MIN_REDACT_LENGTH。"""
        register_sensitive([{"auth": {"username": "admin", "password": "p@ss"}}])
        self.assertIn("p@ss", registered_sensitive())
        self.assertNotIn("p@ss", scrub("pwd=p@ss"))

    def test_short_non_secret_value_under_normal_key_ignored(self):
        register_sensitive({"port": "80"})
        self.assertEqual(scrub("port=80"), "port=80")


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

    def test_depth_limit(self):
        """超过递归深度上限时整体打码，避免自引用结构打爆栈。"""
        nested = {"password": PLAIN_PASSWORD}
        for _ in range(20):
            nested = {"level": nested}
        redacted = redact_secrets(nested)
        self.assertNotIn(PLAIN_PASSWORD, json.dumps(redacted))
        self.assertIn(REDACTED, json.dumps(redacted))


class TestScrubExtraValues(unittest.TestCase):
    def setUp(self):
        clear_sensitive()

    def tearDown(self):
        clear_sensitive()

    def test_extra_values_replaced(self):
        self.assertNotIn("extra-pwd-0001", scrub("v=extra-pwd-0001", extra_values=["extra-pwd-0001"]))

    def test_extra_short_values_ignored(self):
        self.assertEqual(scrub("v=123", extra_values=["123"]), "v=123")

    def test_empty_entries_do_not_corrupt_output(self):
        """登记表若被塞入空串（防御性场景），不得把占位符插进每个字符之间。"""
        sensitive._sensitive_values.add("")
        try:
            self.assertEqual(scrub("abc"), "abc")
            self.assertEqual(scrub("abc", extra_values=[""]), "abc")
        finally:
            sensitive._sensitive_values.discard("")


class TestOsEnvironNotDumped(unittest.TestCase):
    """异常帧里引用 os.environ 时，不得打印整个环境变量字典。"""

    def setUp(self):
        clear_sensitive()

    def tearDown(self):
        clear_sensitive()
        os.environ.pop("BKAPP_TEST_ENV_SECRET", None)

    def test_environ_not_expanded(self):
        register_sensitive("ENV-SECRET-0001")
        os.environ["BKAPP_TEST_ENV_SECRET"] = "ENV-SECRET-0001"
        origin_excepthook = sys.excepthook
        install_redacted_excepthook()
        self.addCleanup(setattr, sys, "excepthook", origin_excepthook)

        # 必须走 excepthook（真实出口），裸调 stackprinter.format 不会带上 suppressed_vars
        stderr = io.StringIO()
        try:
            if os.environ.get("BKAPP_TEST_ENV_SECRET"):
                raise RuntimeError("boom")
        except RuntimeError as err:
            with mock.patch.object(sys, "stderr", stderr):
                sys.excepthook(type(err), err, err.__traceback__)
        output = stderr.getvalue()

        self.assertIn("RuntimeError", output)
        self.assertNotIn("ENV-SECRET-0001", scrub(output))
        # 环境变量字典本身不得被展开：里面可能有注入到 env 的明文，且过长会被截断无法按整串替换
        self.assertNotIn("environ(", output)


class TestThreadingExcepthook(unittest.TestCase):
    def setUp(self):
        clear_sensitive()

    def tearDown(self):
        clear_sensitive()

    def test_threading_excepthook_output_is_redacted(self):
        """线程内未捕获异常同样走脱敏出口。"""
        import threading

        register_sensitive(PLAIN_PASSWORD)
        origin_excepthook, origin_threading_hook = sys.excepthook, threading.excepthook
        install_redacted_excepthook()
        self.addCleanup(setattr, sys, "excepthook", origin_excepthook)
        self.addCleanup(setattr, threading, "excepthook", origin_threading_hook)

        try:
            raise ValueError("boom %s" % PLAIN_PASSWORD)
        except ValueError as err:
            hook_args = mock.Mock(exc_type=type(err), exc_value=err, exc_traceback=err.__traceback__)

        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            threading.excepthook(hook_args)
        output = stderr.getvalue()
        self.assertIn("ValueError", output)
        self.assertNotIn(PLAIN_PASSWORD, output)


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
