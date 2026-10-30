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
import io
import json
import os
import sys
import tempfile
import threading
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
    _transform_document_bundle,
    get_secret,
    get_secret_json,
    inject_kms_secrets,
    redact_startup_error,
    validate_secrets,
)
from core.sensitive import (
    clear_sensitive,
    install_redacted_excepthook,
    register_sensitive,
    registered_sensitive,
    scrub,
)

# 合成素材（仅用于测试，不含任何真实凭据）
ENVELOPE = "SYNTHETIC-ENVELOPE-BASE64-0123456789-abcdefghijklmnop"
PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\nSYNTHETIC-PRIVATE-KEY-BODY-0001\n-----END PRIVATE KEY-----\n"
PRIVATE_KEY_BODY = "SYNTHETIC-PRIVATE-KEY-BODY-0001"
PLAINTEXT_MARK = "SYNTHETIC-PLAINTEXT-SECRET-0001"
# 模拟宿主环境（CI / 容器）里已存在的同名环境变量，用于断言「未被 KMS 覆盖」
PRE_EXISTING_SECRET = "pre-existing-secret-in-host-env"


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
        # 先放一个哨兵值：宿主环境可能本来就配了这些变量，只能断言「未被 KMS 覆盖」
        env = self._kms_env(**{KMS_ENABLED_KEY: "false", "BKPAAS_APP_SECRET": PRE_EXISTING_SECRET})
        with mock.patch.dict(os.environ, env):
            inject_kms_secrets()
            self.assertEqual(os.environ["BKPAAS_APP_SECRET"], PRE_EXISTING_SECRET)
        mocked_decrypt.assert_not_called()

    @mock.patch("bk_kms.decrypt", return_value=json.dumps({"secrets": {"BKPAAS_APP_SECRET": "app-secret-0001"}}))
    def test_env_injection_can_be_disabled(self, _mocked_decrypt):
        env = self._kms_env(**{KMS_ENV_INJECTION_KEY: "false", "BKPAAS_APP_SECRET": PRE_EXISTING_SECRET})
        with mock.patch.dict(os.environ, env):
            inject_kms_secrets()
            # 明文不落 os.environ（仍是哨兵值），但仍可通过 get_secret 取到
            self.assertEqual(os.environ["BKPAAS_APP_SECRET"], PRE_EXISTING_SECRET)
            self.assertEqual(get_secret("BKPAAS_APP_SECRET"), "app-secret-0001")


class TestKmsStartupPrecondition(KmsTestCaseMixin, unittest.TestCase):
    """启动前置条件：开关取值、私钥/信封缺失都要 fail-fast。"""

    @mock.patch("bk_kms.decrypt", return_value=json.dumps({"secrets": {"BKPAAS_APP_SECRET": "app-secret-0001"}}))
    def test_enabled_switch_values(self, mocked_decrypt):
        for enabled_value in ("true", "True", "TRUE", "1", "yes", "on"):
            with mock.patch.dict(os.environ, self._kms_env(**{KMS_ENABLED_KEY: enabled_value})):
                inject_kms_secrets()
                self.assertEqual(os.environ["BKPAAS_APP_SECRET"], "app-secret-0001")
            mocked_decrypt.reset_mock()

    @mock.patch("bk_kms.decrypt", return_value=json.dumps({"secrets": {"BKPAAS_APP_SECRET": "app-secret-0001"}}))
    def test_disabled_switch_values(self, mocked_decrypt):
        for disabled_value in ("false", "False", "0", "no", "off", ""):
            with mock.patch.dict(os.environ, self._kms_env(**{KMS_ENABLED_KEY: disabled_value})):
                inject_kms_secrets()
            mocked_decrypt.assert_not_called()
            mocked_decrypt.reset_mock()

    @mock.patch("bk_kms.decrypt")
    def test_missing_private_key_rejected(self, mocked_decrypt):
        """私钥为空（含宿主未配置）时拒绝启动，且不调用 SDK。"""
        env = self._kms_env(**{KMS_PRIVATE_KEY_ENV_KEY: ""})
        with mock.patch.dict(os.environ, env):
            with self.assertRaises(ImproperlyConfigured):
                inject_kms_secrets()
        mocked_decrypt.assert_not_called()

    @mock.patch("bk_kms.decrypt")
    def test_empty_envelope_rejected(self, mocked_decrypt):
        env = self._kms_env(**{KMS_ENVELOPE_PATH_KEY: self._write_envelope_file("   ")})
        with mock.patch.dict(os.environ, env):
            with self.assertRaises(ImproperlyConfigured):
                inject_kms_secrets()
        mocked_decrypt.assert_not_called()

    @mock.patch("bk_kms.decrypt")
    def test_missing_envelope_rejected(self, mocked_decrypt):
        """信封文件路径与兜底环境变量都为空时拒绝启动。"""
        env = {KMS_ENABLED_KEY: "true", KMS_PRIVATE_KEY_ENV_KEY: PRIVATE_KEY, KMS_ENVELOPE_PATH_KEY: ""}
        with mock.patch.dict(os.environ, env):
            with self.assertRaises(ImproperlyConfigured):
                inject_kms_secrets()
        mocked_decrypt.assert_not_called()

    @mock.patch("bk_kms.decrypt")
    def test_envelope_file_not_found_rejected(self, mocked_decrypt):
        env = self._kms_env(**{KMS_ENVELOPE_PATH_KEY: os.path.join(tempfile.gettempdir(), "not-exist.envelope")})
        with mock.patch.dict(os.environ, env):
            with self.assertRaises(ImproperlyConfigured):
                inject_kms_secrets()
        mocked_decrypt.assert_not_called()


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
        origin_excepthook, origin_threading_hook = sys.excepthook, threading.excepthook
        install_redacted_excepthook()
        self.addCleanup(setattr, sys, "excepthook", origin_excepthook)
        self.addCleanup(setattr, threading, "excepthook", origin_threading_hook)
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
        """禁写控制项：必须命中禁写分支（而非靠白名单兜底）。"""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "BKAPP_DEPLOY_SERVICE": "web"})
        self.assertIn("控制项", str(ctx.exception))

    def test_key_outside_allowlist_rejected(self):
        """既不在禁写列表、也不在白名单的键：走真正的白名单校验分支。"""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "SOME_RANDOM_KEY": "any-value"})
        self.assertIn("不在允许覆盖清单内", str(ctx.exception))

    def test_credential_record_items_all_allowed(self):
        """
        BKAPP_INIT_*_CONFIG 按「整串 JSON 原样下发」，集群名等字段不需单独成键。
        """
        doc_items = (
            "BKPAAS_APP_ID",
            "BKPAAS_APP_SECRET",
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "RABBITMQ_USER",
            "RABBITMQ_PASSWORD",
            "REDIS_PASSWORD",
            "BKAPP_PLATFORM_AUTH_ACCESS_USERNAME",
            "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN",
            "BKAPP_BKBASE_DATA_TOKEN",
            "BKAPP_OTEL_BK_DATA_TOKEN",
            "BKAPP_OTEL_LOG_BK_DATA_TOKEN",
            "BKAPP_AI_AUDIT_LOG_SEARCH_SECRET_KEY",
            "BKAPP_AI_USER_INTENT_SECRET_KEY",
            "BKAPP_ALERT_ACCESS_TOKEN",
            "BKAPP_LOG_EXPORT_STATUS_ACCESS_TOKEN",
            "BKREPO_PASSWORD",
        )
        for key in doc_items:
            with self.subTest(key=key):
                validated = validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", key: "value-0001"})
                self.assertEqual(validated[key], "value-0001")

    def test_extract_secrets_non_dict_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            _extract_secrets(["BKPAAS_APP_SECRET"])

    def test_get_secret_json_missing_returns_default(self):
        """凭据缺失且给了 default 时返回 default，不抛错。"""
        self.assertEqual(get_secret_json("BKAPP_KMS_ABSENT_KEY_FOR_TEST", default=[]), [])

    def test_get_secret_json_missing_without_default_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            get_secret_json("BKAPP_KMS_ABSENT_KEY_FOR_TEST")

    def test_forbidden_control_key_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "BKAPP_KMS_ENABLED": "false"})

    def test_lowercase_key_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001", "redis_password": "x"})

    def test_missing_base_required_secret_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_secrets({"REDIS_PASSWORD": "redis-pwd-0001"})

    def test_base_required_secret_not_fallback_to_host_env(self):
        """宿主环境残留旧明文时，凭证包仍必须提供 BKPAAS_APP_SECRET，否则等于静默降级。"""
        with mock.patch.dict(os.environ, {"BKPAAS_APP_SECRET": "host-existing-secret"}):
            with self.assertRaises(ImproperlyConfigured):
                validate_secrets({"REDIS_PASSWORD": "redis-pwd-0001"})

    def test_feature_switch_required_secret(self):
        """平台鉴权凭据全部为空时才拒绝；凭证包里提供 token 即通过。"""
        empty_auth = {
            "BKAPP_PLATFORM_AUTH_ENABLED": "true",
            "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN": "",
            "BKAPP_PLATFORM_AUTH_ACCESS_USERNAME": "",
        }
        with mock.patch.dict(os.environ, empty_auth):
            with self.assertRaises(ImproperlyConfigured):
                validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001"})
            self.assertEqual(
                validate_secrets(
                    {"BKPAAS_APP_SECRET": "app-secret-0001", "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN": "token-0001"}
                )["BKAPP_PLATFORM_AUTH_ACCESS_TOKEN"],
                "token-0001",
            )

    def test_platform_auth_username_only_accepted(self):
        """bk_resource 只要求 token / username 二者其一，凭证包里只配用户名也是合法配置。"""
        with mock.patch.dict(os.environ, {"BKAPP_PLATFORM_AUTH_ENABLED": "true"}):
            validated = validate_secrets(
                {"BKPAAS_APP_SECRET": "app-secret-0001", "BKAPP_PLATFORM_AUTH_ACCESS_USERNAME": "admin"}
            )
            self.assertEqual(validated["BKAPP_PLATFORM_AUTH_ACCESS_USERNAME"], "admin")

    def test_platform_auth_host_username_accepted(self):
        """宿主环境已配用户名时，不应强制把它搬进 KMS 凭证包。"""
        env = {"BKAPP_PLATFORM_AUTH_ENABLED": "true", "BKAPP_PLATFORM_AUTH_ACCESS_USERNAME": "service-user"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(
                validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001"}), {"BKPAAS_APP_SECRET": "app-secret-0001"}
            )

    def test_platform_auth_default_username_accepted(self):
        """未配置用户名时，config/default.py 默认使用 admin，同样视为有效凭据。"""
        env = {
            "BKAPP_PLATFORM_AUTH_ENABLED": "true",
            "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN": "",
            "BKAPP_PLATFORM_AUTH_ACCESS_USERNAME": "",
        }
        with mock.patch.dict(os.environ, env):
            os.environ.pop("BKAPP_PLATFORM_AUTH_ACCESS_USERNAME", None)
            self.assertEqual(
                validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001"}), {"BKPAAS_APP_SECRET": "app-secret-0001"}
            )

    def test_platform_auth_credentials_empty_rejected(self):
        """token 与 username 都被显式置空时才拒绝（运行期会抛 PlatformAuthParamsNotExist）。"""
        empty_auth = {
            "BKAPP_PLATFORM_AUTH_ENABLED": "true",
            "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN": "",
            "BKAPP_PLATFORM_AUTH_ACCESS_USERNAME": "",
        }
        with mock.patch.dict(os.environ, empty_auth):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001"})
            message = str(ctx.exception)
            self.assertIn("BKAPP_PLATFORM_AUTH_ACCESS_TOKEN", message)
            self.assertIn("BKAPP_PLATFORM_AUTH_ACCESS_USERNAME", message)

    def test_platform_auth_switch_off_not_required(self):
        with mock.patch.dict(os.environ, {"BKAPP_PLATFORM_AUTH_ENABLED": "false"}):
            self.assertEqual(
                validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001"}), {"BKPAAS_APP_SECRET": "app-secret-0001"}
            )

    def test_ai_capability_without_override_keys(self):
        """AI 能力可回退到 settings.SECRET_KEY（由 BKPAAS_APP_SECRET 提供），override 密钥不是必需项。"""
        for switch_value in ("available", "on", "true"):
            with mock.patch.dict(os.environ, {"BKAPP_FEATURE_AI_CAPABILITY": switch_value}):
                self.assertEqual(
                    validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001"}),
                    {"BKPAAS_APP_SECRET": "app-secret-0001"},
                    "BKAPP_FEATURE_AI_CAPABILITY=%s 时不该要求 AI override 密钥" % switch_value,
                )

    def test_ai_capability_default_equals_explicit_available(self):
        """开关不写时运行期默认 available，校验口径必须与显式配置一致。"""
        secrets = {"BKPAAS_APP_SECRET": "app-secret-0001"}
        os.environ.pop("BKAPP_FEATURE_AI_CAPABILITY", None)
        default_result = validate_secrets(dict(secrets))
        with mock.patch.dict(os.environ, {"BKAPP_FEATURE_AI_CAPABILITY": "available"}):
            explicit_result = validate_secrets(dict(secrets))
        self.assertEqual(default_result, explicit_result)

    def test_feature_switch_off_not_required(self):
        with mock.patch.dict(os.environ, {"BKAPP_FEATURE_AI_CAPABILITY": "off"}):
            self.assertEqual(
                validate_secrets({"BKPAAS_APP_SECRET": "app-secret-0001"}), {"BKPAAS_APP_SECRET": "app-secret-0001"}
            )

    def test_get_secret_json_registers_nested_values(self):
        """JSON 型凭据解析后必须递归登记，否则异常出口匹配不到嵌套 password。"""
        config = [{"host": "127.0.0.1", "auth": {"username": "admin", "password": "nested-pwd-0001"}}]
        with mock.patch.dict(os.environ, {"BKAPP_INIT_ES_CONFIG": json.dumps(config)}):
            parsed = get_secret_json("BKAPP_INIT_ES_CONFIG")
            self.assertEqual(parsed, config)
            self.assertIn("nested-pwd-0001", registered_sensitive())

    def test_get_secret_json_invalid_json_not_leaked(self):
        """JSON 格式错误时：异常对象、异常链、stackprinter 输出均不得含密码。

        stackprinter 会截断并换行长字符串，整串 scrub 匹配不到，
        因此必须保证 json 库帧（其局部变量 s 携带原文）根本不出现在异常链上。
        """
        padding = "x" * 400
        broken = '[{"auth": {"password": "BROKEN-JSON-PWD-0001"}, "note": "%s"' % padding
        with mock.patch.dict(os.environ, {"BKAPP_INIT_ES_CONFIG": broken}):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                get_secret_json("BKAPP_INIT_ES_CONFIG")

        formatted = "".join(traceback.format_exception(type(ctx.exception), ctx.exception, ctx.exception.__traceback__))
        self.assertNotIn("BROKEN-JSON-PWD-0001", scrub(formatted))

        # 异常链上不得残留 json 库内部的帧
        frames = traceback.extract_tb(ctx.exception.__traceback__)
        self.assertEqual([f for f in frames if "json" in f.filename and "decoder" in f.filename], [])
        self.assertIsNone(ctx.exception.__cause__.__traceback__)

        try:
            import stackprinter
        except ImportError:  # pragma: no cover
            stackprinter = None
        if stackprinter is not None:
            output = stackprinter.format((type(ctx.exception), ctx.exception, ctx.exception.__traceback__))
            self.assertNotIn("BROKEN-JSON-PWD-0001", scrub(output))

    def test_get_secret_json_deep_nesting_not_leaked(self):
        """深层嵌套触发 RecursionError 时，同样要净化异常链（json 库帧的 s 携带原文）。"""
        password = "DEEP-NESTED-PWD-0001"
        deep = '{{"password": "{}", "data": {}{}'.format(password, "[" * 1600, "]" * 1600)
        with mock.patch.dict(os.environ, {"BKAPP_INIT_ES_CONFIG": deep}):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                get_secret_json("BKAPP_INIT_ES_CONFIG")
        # 确认走的是 RecursionError 而非语法错误路径
        self.assertIn("RecursionError", str(ctx.exception.__cause__))
        frames = traceback.extract_tb(ctx.exception.__traceback__)
        self.assertEqual([f for f in frames if "json" in f.filename and "decoder" in f.filename], [])
        self.assertIsNone(ctx.exception.__cause__.__traceback__)
        formatted = "".join(traceback.format_exception(type(ctx.exception), ctx.exception, ctx.exception.__traceback__))
        self.assertNotIn(password, formatted)

    def test_optional_empty_token_does_not_break_scrub(self):
        """可选凭据允许为空串；空串不得进登记表，否则之后所有异常文本会被插满标记。"""
        env = {
            KMS_ENABLED_KEY: "true",
            KMS_ENVELOPE_PATH_KEY: self._write_envelope_file(ENVELOPE),
            KMS_PRIVATE_KEY_ENV_KEY: PRIVATE_KEY,
            "BKAPP_PLATFORM_AUTH_ENABLED": "true",
            "BKAPP_PLATFORM_AUTH_ACCESS_USERNAME": "service-user",
        }
        secrets = {"BKPAAS_APP_SECRET": "app-secret-0001", "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN": ""}
        with mock.patch("bk_kms.decrypt", return_value=json.dumps({"secrets": secrets})):
            with mock.patch.dict(os.environ, env):
                inject_kms_secrets()
        self.assertNotIn("", registered_sensitive())
        # 关键断言：脱敏不应破坏正常文本
        self.assertEqual(scrub("connect to 10.0.0.17 failed"), "connect to 10.0.0.17 failed")

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
        env = self._kms_env(**{"REDIS_PASSWORD": PRE_EXISTING_SECRET})
        with mock.patch.dict(os.environ, env):
            with self.assertRaises(ImproperlyConfigured):
                inject_kms_secrets()
            # 校验失败时不得修改任何配置（env 与取值层都保持原样）
            self.assertEqual(os.environ["REDIS_PASSWORD"], PRE_EXISTING_SECRET)
            self.assertEqual(get_secret("REDIS_PASSWORD"), PRE_EXISTING_SECRET)


class TestDocumentBundleEndToEnd(KmsTestCaseMixin, unittest.TestCase):
    """
    验证 inject_kms_secrets 能把它拍平成扁平 env 并成功注入，且初始化消费者能解析出密码。
    """

    # 与 bk-audit 敏感凭据格式记录.md「凭据声明」同形的合成值（不含真实凭据）
    DOCUMENT_BUNDLE = {
        "bkapp_id_secret": {"default": {"app_code": "bk_audit", "app_secret": "doc-app-secret-0001"}},
        "mysql": {"default": {"username": "doc-mysql-user", "password": "doc-mysql-pwd-0001"}},
        "rabbitmq": {"default": {"username": "doc-mq-user", "password": "doc-mq-pwd-0001"}},
        "redis": {
            "default": {"password": "doc-redis-pwd-0001"},
            "init": {"password": "doc-init-redis-pwd-0001"},
        },
        "elasticsearch": {"default": {"username": "doc-es-user", "password": "doc-es-pwd-0001"}},
        "doris": {"default": {"username": "doc-doris-user", "password": "doc-doris-pwd-0001"}},
        "platform": {"default": {"username": "doc-platform-user", "access_token": "doc-platform-token-0001"}},
        "bkbase": {"default": {"token": "doc-bkbase-token-0001"}},
        "telemetry": {
            "trace": {"token": "doc-trace-token-0001"},
            "audit_log": {"token": "doc-audit-log-token-0001"},
        },
        "ai": {
            "audit_log_search": {"secret_key": "doc-ai-search-0001"},
            "user_intent": {"secret_key": "doc-ai-intent-0001"},
        },
        "tokens": {
            "alert": {"token": "doc-alert-token-0001"},
            "log_export_status": {"token": "doc-log-export-token-0001"},
        },
        "bkrepo": {"default": {"password": "doc-bkrepo-pwd-0001"}},
    }

    # Chart 实际注入的初始化配置（非敏感字段齐全，密码位置留空），对应 _helpers.tpl 的 *_CONFIG
    CHART_INIT_ENV = {
        "BKAPP_INIT_ES_CONFIG": json.dumps(
            [
                {
                    "namespace": "default",
                    "cluster_name": "bkaudit-es",
                    "bkbase_cluster_en_name": "bkaudit-es",
                    "domain_name": "es.bkop.internal",
                    "source_type": "other",
                    "port": "9200",
                    "schema": "http",
                    "auth_info": {"username": "chart-user", "password": ""},
                    "enable_hot_warm": False,
                    "setup_config": {
                        "retention_days_max": 30,
                        "retention_days_default": 30,
                        "number_of_replicas_max": 1,
                        "number_of_replicas_default": 1,
                    },
                    "admin": ["admin"],
                    "description": "审计中心存储集群",
                }
            ],
            ensure_ascii=False,
        ),
        "BKAPP_INIT_DORIS_CONFIG": json.dumps(
            [
                {
                    "cluster_name": "bkaudit-doris",
                    "auth_info": {"username": "chart-doris-user", "password": ""},
                    "pre_defined": True,
                    "pre_defined_extra_config": {"cluster_id": "102"},
                }
            ],
            ensure_ascii=False,
        ),
        "BKAPP_INIT_REDIS_CONFIG": json.dumps(
            [
                {
                    "namespace": "default",
                    "redis_name_en": "bkaudit-redis",
                    "redis_name": "审计中心存储",
                    "connection_info": {
                        "enable_sentinel": False,
                        "host": "redis.bkop.internal",
                        "port": 6379,
                        "password": "",
                    },
                    "version": "6.2",
                }
            ],
            ensure_ascii=False,
        ),
    }

    def _document_env(self):
        return self._kms_env(
            **{
                KMS_ENABLED_KEY: "true",
                "BKAPP_PLATFORM_AUTH_ENABLED": "false",
                "BKAPP_FEATURE_AI_CAPABILITY": "off",
            }
        )

    def test_document_shape_inject_succeeds(self):
        """inject_kms_secrets 必须成功且拍平成扁平 env。"""
        import types

        bk_kms_shim = types.ModuleType("bk_kms")
        bk_kms_shim.decrypt = lambda *, envelope, private_key: json.dumps(self.DOCUMENT_BUNDLE)
        with mock.patch.dict(sys.modules, {"bk_kms": bk_kms_shim}):
            with mock.patch.dict(os.environ, self._document_env()):
                # 清理宿主可能预置的同名变量，避免污染断言；
                # 断言必须留在 with 块内：patch.dict 退出时会把 os.environ 回滚到进入前状态
                for key in (
                    "BKPAAS_APP_ID",
                    "BKPAAS_APP_SECRET",
                    "MYSQL_USER",
                    "MYSQL_PASSWORD",
                    "RABBITMQ_USER",
                    "RABBITMQ_PASSWORD",
                    "REDIS_PASSWORD",
                    "BKAPP_PLATFORM_AUTH_ACCESS_USERNAME",
                    "BKAPP_PLATFORM_AUTH_ACCESS_TOKEN",
                    "BKAPP_BKBASE_DATA_TOKEN",
                    "BKAPP_OTEL_BK_DATA_TOKEN",
                    "BKAPP_OTEL_LOG_BK_DATA_TOKEN",
                    "BKAPP_AI_AUDIT_LOG_SEARCH_SECRET_KEY",
                    "BKAPP_AI_USER_INTENT_SECRET_KEY",
                    "BKAPP_ALERT_ACCESS_TOKEN",
                    "BKAPP_LOG_EXPORT_STATUS_ACCESS_TOKEN",
                    "BKREPO_PASSWORD",
                ):
                    os.environ.pop(key, None)
                inject_kms_secrets()  # 若契约未对齐会在此处抛「非法的环境变量名」并 fail-fast
                # 运行时凭据：分类.实例.字段 -> 扁平 env 名
                self.assertEqual(os.environ["BKPAAS_APP_ID"], "bk_audit")
                self.assertEqual(os.environ["BKPAAS_APP_SECRET"], "doc-app-secret-0001")
                self.assertEqual(os.environ["MYSQL_USER"], "doc-mysql-user")
                self.assertEqual(os.environ["MYSQL_PASSWORD"], "doc-mysql-pwd-0001")
                self.assertEqual(os.environ["RABBITMQ_USER"], "doc-mq-user")
                self.assertEqual(os.environ["RABBITMQ_PASSWORD"], "doc-mq-pwd-0001")
                self.assertEqual(os.environ["REDIS_PASSWORD"], "doc-redis-pwd-0001")
                self.assertEqual(os.environ["BKAPP_PLATFORM_AUTH_ACCESS_USERNAME"], "doc-platform-user")
                self.assertEqual(os.environ["BKAPP_PLATFORM_AUTH_ACCESS_TOKEN"], "doc-platform-token-0001")
                self.assertEqual(os.environ["BKAPP_BKBASE_DATA_TOKEN"], "doc-bkbase-token-0001")
                self.assertEqual(os.environ["BKAPP_OTEL_BK_DATA_TOKEN"], "doc-trace-token-0001")
                self.assertEqual(os.environ["BKAPP_OTEL_LOG_BK_DATA_TOKEN"], "doc-audit-log-token-0001")
                self.assertEqual(os.environ["BKAPP_AI_AUDIT_LOG_SEARCH_SECRET_KEY"], "doc-ai-search-0001")
                self.assertEqual(os.environ["BKAPP_AI_USER_INTENT_SECRET_KEY"], "doc-ai-intent-0001")
                self.assertEqual(os.environ["BKAPP_ALERT_ACCESS_TOKEN"], "doc-alert-token-0001")
                self.assertEqual(os.environ["BKAPP_LOG_EXPORT_STATUS_ACCESS_TOKEN"], "doc-log-export-token-0001")
                self.assertEqual(os.environ["BKREPO_PASSWORD"], "doc-bkrepo-pwd-0001")

    def test_document_shape_init_config_synthesized(self):
        """初始化凭据（只给 username/password）合成完整 BKAPP_INIT_*_CONFIG，可被 init 消费者解析出密码。"""
        import types

        bk_kms_shim = types.ModuleType("bk_kms")
        bk_kms_shim.decrypt = lambda *, envelope, private_key: json.dumps(self.DOCUMENT_BUNDLE)
        with mock.patch.dict(sys.modules, {"bk_kms": bk_kms_shim}):
            with mock.patch.dict(os.environ, self._document_env()):
                for key in ("BKAPP_INIT_ES_CONFIG", "BKAPP_INIT_DORIS_CONFIG", "BKAPP_INIT_REDIS_CONFIG"):
                    os.environ.pop(key, None)
                inject_kms_secrets()
                # 断言留在 with 块内：patch.dict 退出会回滚 os.environ；
                # 这里走 get_secret_json -> _SECRETS_CACHE（模块级，不随 patch 回滚）
                es_configs = get_secret_json("BKAPP_INIT_ES_CONFIG")
                self.assertEqual(es_configs[0]["auth_info"]["username"], "doc-es-user")
                self.assertEqual(es_configs[0]["auth_info"]["password"], "doc-es-pwd-0001")

                doris_configs = get_secret_json("BKAPP_INIT_DORIS_CONFIG")
                self.assertEqual(doris_configs[0]["auth_info"]["username"], "doc-doris-user")
                self.assertEqual(doris_configs[0]["auth_info"]["password"], "doc-doris-pwd-0001")

                redis_configs = get_secret_json("BKAPP_INIT_REDIS_CONFIG")
                self.assertEqual(redis_configs[0]["connection_info"]["password"], "doc-init-redis-pwd-0001")

    def test_init_config_merged_keeps_chart_fields(self):
        """真实录入形态：Chart 提供结构（域名/端口/集群名/保留策略），KMS 只覆盖 auth 字段。

        凭据合并不得把非敏感字段清空，否则初始化会拿着空地址去建集群。
        """
        import types

        bk_kms_shim = types.ModuleType("bk_kms")
        bk_kms_shim.decrypt = lambda *, envelope, private_key: json.dumps(self.DOCUMENT_BUNDLE)
        with mock.patch.dict(sys.modules, {"bk_kms": bk_kms_shim}):
            with mock.patch.dict(os.environ, {**self._document_env(), **self.CHART_INIT_ENV}):
                inject_kms_secrets()

                es = get_secret_json("BKAPP_INIT_ES_CONFIG")[0]
                # 凭据被替换
                self.assertEqual(es["auth_info"]["username"], "doc-es-user")
                self.assertEqual(es["auth_info"]["password"], "doc-es-pwd-0001")
                # Chart 的非敏感字段原样保留
                self.assertEqual(es["domain_name"], "es.bkop.internal")
                self.assertEqual(es["port"], "9200")
                self.assertEqual(es["cluster_name"], "bkaudit-es")
                self.assertEqual(es["admin"], ["admin"])
                self.assertEqual(es["setup_config"]["retention_days_max"], 30)
                self.assertEqual(es["description"], "审计中心存储集群")

                doris = get_secret_json("BKAPP_INIT_DORIS_CONFIG")[0]
                self.assertEqual(doris["auth_info"]["password"], "doc-doris-pwd-0001")
                self.assertEqual(doris["cluster_name"], "bkaudit-doris")
                self.assertTrue(doris["pre_defined"])
                self.assertEqual(doris["pre_defined_extra_config"], {"cluster_id": "102"})

                redis = get_secret_json("BKAPP_INIT_REDIS_CONFIG")[0]
                self.assertEqual(redis["connection_info"]["password"], "doc-init-redis-pwd-0001")
                self.assertEqual(redis["connection_info"]["host"], "redis.bkop.internal")
                self.assertEqual(redis["connection_info"]["port"], 6379)
                self.assertEqual(redis["redis_name"], "审计中心存储")

    @mock.patch("services.web.entry.init.base.resource.databus.storage.storage_activate")
    @mock.patch("services.web.entry.init.base.resource.databus.storage.create_storage", return_value=101)
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.set")
    @mock.patch("services.web.entry.init.base.GlobalMetaConfig.get", return_value=False)
    def test_init_handler_consumes_merged_config(self, _mock_get, _mock_set, mock_create, _mock_activate):
        """走一遍 init 消费者：合并后的配置必须能过 _init_es / _init_doris 的前置校验。"""
        import types

        from services.web.entry.init.base import SystemInitHandler

        bk_kms_shim = types.ModuleType("bk_kms")
        bk_kms_shim.decrypt = lambda *, envelope, private_key: json.dumps(self.DOCUMENT_BUNDLE)
        with mock.patch.dict(sys.modules, {"bk_kms": bk_kms_shim}):
            with mock.patch.dict(os.environ, {**self._document_env(), **self.CHART_INIT_ENV}):
                inject_kms_secrets()

                handler = SystemInitHandler()
                # Doris 非预定义会直接抛 ParamsNotValid，这里必须不抛
                handler.init_es()
                handler.init_doris()

        sent_es = mock_create.call_args_list[0][0][0]
        self.assertEqual(sent_es["domain_name"], "es.bkop.internal")
        self.assertEqual(sent_es["auth_info"]["password"], "doc-es-pwd-0001")

        sent_doris = mock_create.call_args_list[1][0][0]
        self.assertEqual(sent_doris["cluster_name"], "bkaudit-doris")
        self.assertTrue(sent_doris["pre_defined"])
        self.assertEqual(sent_doris["auth_info"]["password"], "doc-doris-pwd-0001")

    def test_init_config_unparsable_env_not_overridden(self):
        """Chart 配置存在但不可解析时，不做覆盖，交由下游暴露原始错误。"""
        with mock.patch.dict(os.environ, {"BKAPP_INIT_ES_CONFIG": '[{"auth_info":'}):
            flat = _transform_document_bundle({"elasticsearch": {"default": {"password": "PWD"}}})
        self.assertNotIn("BKAPP_INIT_ES_CONFIG", flat)

    def test_init_config_multi_instance_matched_by_cluster_name(self):
        """多集群：default 对首个元素，default__<cluster_name> 按集群名匹配，互不串号。"""
        env = {
            "BKAPP_INIT_ES_CONFIG": json.dumps(
                [
                    {"cluster_name": "bk-audit-es-system", "domain_name": "es-system.internal", "auth_info": {}},
                    {"cluster_name": "bk-audit-es-tencent", "domain_name": "es-tencent.internal", "auth_info": {}},
                ]
            )
        }
        with mock.patch.dict(os.environ, env):
            flat = _transform_document_bundle(
                {
                    "elasticsearch": {
                        "default": {"username": "u1", "password": "P1"},
                        "default__bk-audit-es-tencent": {"username": "u2", "password": "P2"},
                    }
                }
            )
        configs = json.loads(flat["BKAPP_INIT_ES_CONFIG"])
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0]["domain_name"], "es-system.internal")
        self.assertEqual(configs[0]["auth_info"]["password"], "P1")
        self.assertEqual(configs[1]["domain_name"], "es-tencent.internal")
        self.assertEqual(configs[1]["auth_info"]["password"], "P2")

    def test_transform_document_bundle_flatten_only(self):
        """无初始化凭据时，仅扁平 env 映射，不合成 *CONFIG。"""
        flat = _transform_document_bundle(
            {
                "bkapp_id_secret": {"default": {"app_code": "bk_audit", "app_secret": "s"}},
                "mysql": {"default": {"username": "u", "password": "p"}},
            }
        )
        self.assertEqual(flat["BKPAAS_APP_ID"], "bk_audit")
        self.assertEqual(flat["MYSQL_PASSWORD"], "p")
        self.assertNotIn("BKAPP_INIT_ES_CONFIG", flat)

    def test_unknown_category_warning_does_not_log_keys(self):
        """未识别分类键只提示「存在」，不得把键名或值写进日志（CodeQL 敏感信息明文落日志）。"""
        with self.assertLogs("core.kms", level="WARNING") as ctx:
            flat = _transform_document_bundle(
                {
                    "mysql": {"default": {"password": "MYSQL-PWD-0001"}},
                    "unknownCategoryName": {"secret_key": "UNKNOWN-CAT-VALUE-0001"},
                }
            )
        output = "\n".join(ctx.output)
        self.assertIn("未识别的分类键", output)
        self.assertNotIn("unknownCategoryName", output)
        self.assertNotIn("UNKNOWN-CAT-VALUE-0001", output)
        # 已知分类照常转换，未识别分类被忽略
        self.assertEqual(flat["MYSQL_PASSWORD"], "MYSQL-PWD-0001")

    def test_transform_document_bundle_empty_init_skipped(self):
        """初始化字段为空的分类不合成 *CONFIG（避免写入空串/空结构）。"""
        flat = _transform_document_bundle({"elasticsearch": {"default": {}}})
        self.assertNotIn("BKAPP_INIT_ES_CONFIG", flat)

    def test_init_config_fallback_matches_init_preconditions(self):
        """Chart 未注入初始化配置时按模板兜底，且兜底结果必须满足 init 前置校验。

        Doris 兜底若给 pre_defined=False，_init_doris 会直接抛 ParamsNotValid。
        """
        with mock.patch.dict(os.environ, {"BKAPP_INIT_DORIS_CONFIG": "", "BKAPP_INIT_ES_CONFIG": ""}):
            flat = _transform_document_bundle(
                {
                    "doris": {"default": {"username": "u", "password": "P"}},
                    "elasticsearch": {"default": {"password": "E"}},
                }
            )
        doris = json.loads(flat["BKAPP_INIT_DORIS_CONFIG"])[0]
        self.assertTrue(doris["pre_defined"])
        self.assertEqual(doris["auth_info"]["password"], "P")
        es = json.loads(flat["BKAPP_INIT_ES_CONFIG"])[0]
        self.assertNotIn("", es["admin"])

    def test_init_config_fallback_cluster_key_only(self):
        """兜底路径下只给 default__<cluster> 时，不得额外留下没有集群名的空白元素。"""
        with mock.patch.dict(os.environ, {"BKAPP_INIT_ES_CONFIG": ""}):
            flat = _transform_document_bundle({"elasticsearch": {"default__bk-audit-es": {"password": "P"}}})
        configs = json.loads(flat["BKAPP_INIT_ES_CONFIG"])
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["cluster_name"], "bk-audit-es")
        self.assertEqual(configs[0]["auth_info"]["password"], "P")

    def test_redis_default_and_init_are_distinct_instances(self):
        """redis.default（应用缓存）与 redis.init（初始化存储）是两个独立实例。

        redis 的运行时凭据不与 Redis 初始化凭据自动共用，两者是独立用途。
        转换层必须分别从两个键取密码，落到不同 env，且二者不可互相覆盖。
        """
        flat = _transform_document_bundle(
            {
                "redis": {
                    "default": {"password": "CACHE-REDIS-PWD"},
                    "init": {"password": "INIT-REDIS-PWD"},
                }
            }
        )
        # R04：应用缓存 Redis 密码 -> REDIS_PASSWORD
        self.assertEqual(flat["REDIS_PASSWORD"], "CACHE-REDIS-PWD")
        # D03：初始化存储 Redis 密码 -> 合成 BKAPP_INIT_REDIS_CONFIG
        redis_configs = json.loads(flat["BKAPP_INIT_REDIS_CONFIG"])
        self.assertEqual(redis_configs[0]["connection_info"]["password"], "INIT-REDIS-PWD")
        # 二者互不包含、互不覆盖
        self.assertNotEqual(flat["REDIS_PASSWORD"], redis_configs[0]["connection_info"]["password"])
