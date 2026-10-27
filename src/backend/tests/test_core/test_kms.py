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
        self.assertIn("仅允许密钥类", str(ctx.exception))

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
