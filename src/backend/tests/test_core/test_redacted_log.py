# -*- coding: utf-8 -*-
"""
BKSEC 1578945 SDK 残余实证与平替验证（bk-resource==0.4.11 失败路径日志）。

背景（评审 RAJA 复核确认）：bk_resource/contrib/api.py 的 APIResource.perform_request
有 4 处 SDK 层日志打印（L150/L188/L194/L218-224），先于应用层 RedactedRequestLogMixin
记录上游错误原文，不受 support_data_collect 控制。本测试：
1. 实证：mock 上游返回携带合成凭据的错误消息，确认 SDK 日志是否出现明文；
2. 平替：安装 BkResourceLogRedactionFilter 后，SDK 日志完整保留上下文、疑似凭据打码。
"""
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError
from django.test import TestCase

SYNTH_MARK = "SYNTH-LEAK-SDK-001"
# 模拟上游错误消息回显口令原文的形态（供过滤器打码验证）
SYNTH_LEAK_KV = "password=" + SYNTH_MARK


def _mock_biz_error_response():
    """构造携带合成凭据错误消息的业务失败响应（HTTP 200 + result:false，走 contrib/api.py L218-224 路径）"""
    resp = mock.Mock(spec=requests.Response)
    resp.status_code = 200
    resp.json.return_value = {
        "result": False,
        "code": 500,
        "message": f"synthetic upstream error {SYNTH_LEAK_KV}",
    }
    resp.headers = {}
    resp.content = b"{}"
    resp.request = mock.Mock(url="https://synthetic.example.com/api/")
    return resp


class BkResourceSDKLogTest(TestCase):
    def _trigger_sdk_error(self):
        from api.bk_log.default import GetStorages

        with mock.patch.object(requests.Session, "request", return_value=_mock_biz_error_response()):
            with self.assertRaises(APIRequestError):
                GetStorages().request(page=1, page_size=10, cluster_type="storage")

    def test_sdk_error_log_leaks_upstream_message_without_filter(self):
        """实证：未安装过滤器时，SDK 日志打印含合成凭据的上游错误原文（bk-resource==0.4.11 原生行为）"""
        from core.redacted_log import BkResourceLogRedactionFilter

        bk_logger = __import__("logging").getLogger("bk_resource")
        # 临时移除过滤器（模块加载已自动安装），实证 SDK 原生行为
        original_filters = list(bk_logger.filters)
        bk_logger.filters = [f for f in original_filters if not isinstance(f, BkResourceLogRedactionFilter)]
        try:
            with self.assertLogs("bk_resource", level="ERROR") as captured:
                self._trigger_sdk_error()
            text = "\n".join(captured.output)
            self.assertIn("synthetic upstream error", text)  # 上游错误消息原文被记录
            self.assertIn(SYNTH_MARK, text)  # 实证：合成凭据明文落入 SDK 日志
        finally:
            bk_logger.filters = original_filters

    def test_sdk_error_log_redacted_with_filter(self):
        """平替：安装过滤器后，SDK 日志保留错误上下文、疑似凭据打码"""
        from core.redacted_log import BkResourceLogRedactionFilter

        bk_logger = __import__("logging").getLogger("bk_resource")
        original_filters = list(bk_logger.filters)
        if not any(isinstance(f, BkResourceLogRedactionFilter) for f in bk_logger.filters):
            bk_logger.addFilter(BkResourceLogRedactionFilter())
        try:
            with self.assertLogs("bk_resource", level="ERROR") as captured:
                self._trigger_sdk_error()
            text = "\n".join(captured.output)
            self.assertNotIn(SYNTH_MARK, text)  # 凭据不再出现
            self.assertIn("synthetic upstream error", text)  # 错误上下文完整保留
            self.assertIn("***", text)  # 打码标记存在
        finally:
            bk_logger.filters = original_filters

    def test_redis_resources_do_not_log_raw_upstream_error_in_audit_logger(self):
        from api.bk_base.default import CreateResourceSet
        from api.bk_base_v4.default import StorageAssetCreate

        connection = {"host": "redis.synthetic.test", "port": 6379, "password": SYNTH_MARK}
        cases = (
            (CreateResourceSet, {"connection_info": connection}),
            (
                StorageAssetCreate,
                {
                    "tenant": "default",
                    "project_name": "audit",
                    "asset_name": "synthetic_redis",
                    "asset_alias": "Synthetic Redis",
                    "sub_type": "Redis",
                    "belong_type": "project_private",
                    "connection": {"kind": "Redis", "config": connection},
                },
            ),
        )
        for resource, payload in cases:
            with (
                self.subTest(resource=resource.__name__),
                mock.patch.object(requests.Session, "request", return_value=_mock_biz_error_response()),
                self.assertLogs("app", level="INFO") as captured,
            ):
                with self.assertRaises(APIRequestError):
                    resource().request(payload)
                output = "\n".join(captured.output)
                self.assertIn("[Redacted][Failed]", output)
                self.assertNotIn(SYNTH_MARK, output)
