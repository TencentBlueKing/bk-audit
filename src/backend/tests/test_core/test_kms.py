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

KMS 信封注入单测：脱敏、凭证包 schema、注入开关。
"""
import io
import json
import os
import sys
import tempfile
import traceback
import unittest
from unittest import mock

from django.core.exceptions import ImproperlyConfigured

from core import kms
from core.kms import (
    KMS_ENABLED_KEY,
    KMS_ENV_INJECTION_KEY,
    KMS_ENVELOPE_PATH_KEY,
    KMS_EXTRA_SECRET_KEYS_KEY,
    KMS_PRIVATE_KEY_ENV_KEY,
    _extract_secrets,
    get_secret,
    inject_kms_secrets,
    redact_startup_error,
    validate_secrets,
)
from core.sensitive import (
    clear_sensitive,
    install_redacted_excepthook,
    register_sensitive,
)

# 合成素材（仅用于测试，不含任何真实凭据）
ENVELOPE = "SYNTHETIC-ENVELOPE-BASE64-0123456789-abcdefghijklmnop"
PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\nSYNTHETIC-PRIVATE-KEY-BODY-0001\n-----END PRIVATE KEY-----\n"
PRIVATE_KEY_BODY = "SYNTHETIC-PRIVATE-KEY-BODY-0001"
PLAINTEXT_MARK = "SYNTHETIC-PLAINTEXT-SECRET-0001"


class KmsTestCaseMixin:
    """统一的 KMS 状态隔离：环境变量、进程内凭据表、敏感值登记表。"""

    def setUp(self):
        kms._SECRETS_CACHE.clear()
        clear_sensitive()
        # 默认关闭按功能开关追加的必填项，需要校验开关语义的用例自行覆盖
        switch_patcher = mock.patch.dict(
            os.environ, {"BKAPP_PLATFORM_AUTH_ENABLED": "false", "BKAPP_FEATURE_AI_CAPABILITY": "off"}
        )
        switch_patcher.start()
        self.addCleanup(switch_patcher.stop)

    def tearDown(self):
        kms._SECRETS_CACHE.clear()
        clear_sensitive()

    def _write_envelope_file(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".envelope")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def _kms_env(self, **overrides) -> dict:
        env = {
            KMS_ENABLED_KEY: "true",
            KMS_ENVELOPE_PATH_KEY: self._write_envelope_file(ENVELOPE),
            KMS_PRIVATE_KEY_ENV_KEY: PRIVATE_KEY,
        }
        env.update(overrides)
        return env


class TestKmsInject(KmsTestCaseMixin, unittest.TestCase):
    """注入主流程。"""

    @mock.patch(
        "bk_kms.decrypt",
        return_value=json.dumps(
            {"secrets": {"BKPAAS_APP_SECRET": "app-secret-0001", "REDIS_PASSWORD": "redis-pwd-0001"}}
        ),
    )
    def test_inject_success(self, mocked_decrypt):
        with mock.patch.dict(os.environ, self._kms_env()):
            inject_kms_secrets()
            self.assertEqual(os.environ["BKPAAS_APP_SECRET"], "app-secret-0001")
            self.assertEqual(os.environ["REDIS_PASSWORD"], "redis-pwd-0001")
            # 进程内凭据表始终是取值来源之一
            self.assertEqual(get_secret("REDIS_PASSWORD"), "redis-pwd-0001")
        mocked_decrypt.assert_called_once()

    @mock.patch(
        "bk_kms.decrypt",
        return_value=json.dumps({"BKPAAS_APP_SECRET": "app-secret-0001", "REDIS_PASSWORD": "redis-pwd-0001"}),
    )
    def test_flat_map_compatible(self, _mocked_decrypt):
        with mock.patch.dict(os.environ, self._kms_env()):
            inject_kms_secrets()
            self.assertEqual(os.environ["REDIS_PASSWORD"], "redis-pwd-0001")

    @mock.patch("bk_kms.decrypt", return_value=json.dumps({"secrets": {"BKPAAS_APP_SECRET": "app-secret-0001"}}))
    def test_disabled_is_noop(self, mocked_decrypt):
        with mock.patch.dict(os.environ, self._kms_env(**{KMS_ENABLED_KEY: "false"})):
            inject_kms_secrets()
            self.assertNotIn("BKPAAS_APP_SECRET", os.environ)
        mocked_decrypt.assert_not_called()

    @mock.patch("bk_kms.decrypt", return_value=json.dumps({"secrets": {"BKPAAS_APP_SECRET": "app-secret-0001"}}))
    def test_env_injection_can_be_disabled(self, _mocked_decrypt):
        env = self._kms_env(**{KMS_ENV_INJECTION_KEY: "false"})
        with mock.patch.dict(os.environ, env):
            inject_kms_secrets()
            # 明文不落 os.environ，但仍可通过 get_secret 取到
            self.assertNotIn("BKPAAS_APP_SECRET", os.environ)
            self.assertEqual(get_secret("BKPAAS_APP_SECRET"), "app-secret-0001")


class TestKmsSensitiveLeak(KmsTestCaseMixin, unittest.TestCase):
    """脱敏：异常文案、完整 traceback、stackprinter 输出、异常链。"""

    def _assert_no_sensitive(self, err: BaseException):
        outputs = [
            str(err),
            "".join(traceback.format_exception(type(err), err, err.__traceback__)),
            redact_startup_error(err),
        ]
        try:
            import stackprinter
        except ImportError:  # pragma: no cover
            stackprinter = None
        if stackprinter is not None:
            outputs.append(stackprinter.format((type(err), err, err.__traceback__)))

        for output in outputs:
            self.assertNotIn(ENVELOPE, output)
            self.assertNotIn(PRIVATE_KEY_BODY, output)
            self.assertNotIn(PLAINTEXT_MARK, output)

        # 异常链上不应残留含敏感局部变量的帧
        self.assertIsNone(err.__cause__.__traceback__)
        leaked_frames = [frame for frame in traceback.extract_tb(err.__traceback__) if frame.name == "load_kms_secrets"]
        self.assertEqual(leaked_frames, [])
        if isinstance(err.__context__, json.JSONDecodeError):
            self.assertNotIn(PLAINTEXT_MARK, err.__context__.doc or "")

    @mock.patch("bk_kms.decrypt", side_effect=RuntimeError("decrypt failed: %s" % ENVELOPE))
    def test_decrypt_failure_not_leaked(self, _mocked_decrypt):
        with mock.patch.dict(os.environ, self._kms_env()):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                inject_kms_secrets()
        self._assert_no_sensitive(ctx.exception)

    @mock.patch("bk_kms.decrypt", return_value="envelope-plaintext-%s-not-json" % PLAINTEXT_MARK)
    def test_invalid_json_not_leaked(self, _mocked_decrypt):
        with mock.patch.dict(os.environ, self._kms_env()):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                inject_kms_secrets()
        self._assert_no_sensitive(ctx.exception)
        self.assertIn("JSONDecodeError", str(ctx.exception))

    def test_excepthook_output_is_redacted(self):
        register_sensitive(PLAINTEXT_MARK)
        install_redacted_excepthook()
        self.addCleanup(setattr, sys, "excepthook", sys.__excepthook__)
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            try:
                raise ValueError("boom %s" % PLAINTEXT_MARK)
            except ValueError as err:
                sys.excepthook(type(err), err, err.__traceback__)
        output = stderr.getvalue()
        self.assertIn("ValueError", output)
        self.assertNotIn(PLAINTEXT_MARK, output)


class TestKmsSecretsSchema(KmsTestCaseMixin, unittest.TestCase):
    """凭证包 schema：wrapper 形态、键白名单、值类型、按功能开关的必填项。"""

    def test_empty_bundle_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({})

    def test_non_dict_bundle_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets(["BKPAAS_APP_SECRET"])

    def test_invalid_wrapper_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            _extract_secrets({"secrets": "invalid-wrapper"})

    def test_mixed_wrapper_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            _extract_secrets({"secrets": {"BKPAAS_APP_SECRET": "x"}, "extra": "y"})

    def test_none_value_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "REDIS_PASSWORD": None})

    def test_structured_value_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "REDIS_PASSWORD": {"a": 1}})

    def test_unknown_key_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "BKAPP_DEPLOY_SERVICE": "web"})

    def test_forbidden_control_key_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "BKAPP_KMS_ENABLED": "false"})

    def test_lowercase_key_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "redis_password": "x"})

    def test_missing_base_required_secret_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({"REDIS_PASSWORD": "redis-pwd-0001"})

    def test_feature_switch_required_secret(self):
        with mock.patch.dict(os.environ, {"BKAPP_PLATFORM_AUTH_ENABLED": "true"}):
            with self.assertRaises(ImproperlyConfigured):
                validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001"})
            self.assertEqual(
                validate_secrets(
                    {"BKPAAS_APP_SECRET": "app-secret-0001", "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN": "token-0001"}
                )["BKAPP_PLATFORM_AUTH_ACCESS_TOKEN"],
                "token-0001",
            )

    def test_feature_switch_off_not_required(self):
        with mock.patch.dict(os.environ, {"BKAPP_FEATURE_AI_CAPABILITY": "off"}):
            self.assertEqual(
                validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001"}), {"BKPAAS_APP_SECRET": "app-secret-0001"}
            )

    def test_scalar_values_normalized(self):
        validated = validate_secrets(
            {"BKPAAS_APP_SECRET": "app-secret-0001", "REDIS_PASSWORD": 123456, "APP_TOKEN": True}
        )
        self.assertEqual(
            validated, {"BKPAAS_APP_SECRET": "app-secret-0001", "REDIS_PASSWORD": "123456", "APP_TOKEN": "True"}
        )

    def test_extra_allowed_keys_from_env(self):
        with mock.patch.dict(os.environ, {KMS_EXTRA_SECRET_KEYS_KEY: "BKREPO_PASSWORD"}):
            validated = validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "BKREPO_PASSWORD": "repo-pwd"})
            self.assertEqual(validated["BKREPO_PASSWORD"], "repo-pwd")

    @mock.patch("bk_kms.decrypt", return_value=json.dumps({"secrets": {"REDIS_PASSWORD": None}}))
    def test_reject_before_env_mutation(self, _mocked_decrypt):
        os.environ.pop("REDIS_PASSWORD", None)
        self.addCleanup(os.environ.pop, "REDIS_PASSWORD", None)
        with mock.patch.dict(os.environ, self._kms_env()):
            with self.assertRaises(ImproperlyConfigured):
                inject_kms_secrets()
            # 校验失败时不得修改任何配置
            self.assertNotIn("REDIS_PASSWORD", os.environ)
            self.assertIsNone(get_secret("REDIS_PASSWORD"))
