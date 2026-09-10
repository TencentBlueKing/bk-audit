"""日志分析上游的无 DB HTTP 传输回归测试。"""

import json
import unittest

import requests

from tests.test_ai_assistant.special.fake_log_analysis_agent import (
    _complete_events,
    running_fake_log_analysis_agent,
)


class FakeLogAnalysisTransportTest(unittest.TestCase):
    """不依赖 DB，验证 fake 上游确实触发 Requests 传输异常。"""

    def test_empty_artifact_eof_is_normal_http_close(self):
        """无产物场景是合法 EOF，不得误称为传输异常。"""

        instruction = "empty-artifact-eof"
        with running_fake_log_analysis_agent() as agent:
            agent.release(instruction)
            with requests.post(
                agent.base_url,
                json={"input": json.dumps({"instruction": instruction})},
                stream=True,
                timeout=(3.05, 5),
            ) as response:
                self.assertEqual(response.status_code, 200)
                received = [json.loads(line[6:]) for line in response.iter_lines() if line.startswith(b"data: ")]
                self.assertNotIn("Transfer-Encoding", response.headers)
                self.assertNotIn("Content-Length", response.headers)
            self.assertEqual(received, [{"type": "RUN_STARTED", "threadId": "thread-eof", "runId": "run-eof"}])

    def test_chunked_truncation_after_complete_text(self):
        """完整正文必须先交付，再因缺少 HTTP 终止块抛错。"""

        instruction = "truncated-chunked"
        with running_fake_log_analysis_agent() as agent:
            received = []
            try:
                with requests.post(
                    agent.base_url,
                    json={"input": json.dumps({"instruction": instruction})},
                    stream=True,
                    timeout=(3.05, 5),
                ) as response:
                    self.assertEqual(response.status_code, 200)
                    with self.assertRaises(requests.exceptions.ChunkedEncodingError):
                        for line in response.iter_lines():
                            if line.startswith(b"data: "):
                                event = json.loads(line[6:])
                                received.append(event)
                                if event["type"] == "TEXT_MESSAGE_END":
                                    agent.release(instruction)
                    self.assertEqual(response.headers.get("Transfer-Encoding"), "chunked")
            finally:
                agent.release(instruction)
            self.assertEqual(received, _complete_events("# 截断前完整结论")[:-1])
