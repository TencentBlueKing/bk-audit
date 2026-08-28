"""本地 AG-UI HTTP 服务：为日志分析专项测试提供真实流式上游。"""

import json
import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass(slots=True)
class FakeLogAnalysisAgent:
    base_url: str
    requests: list[dict[str, Any]] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    lock: threading.Lock = field(default_factory=threading.Lock)
    started: dict[str, threading.Event] = field(default_factory=dict)
    releases: dict[str, threading.Event] = field(default_factory=dict)
    user_instructions: set[str] = field(default_factory=set)
    user_pair_ready: threading.Event = field(default_factory=threading.Event)

    def record(self, payload: dict[str, Any]) -> tuple[str, int]:
        request_input = json.loads(payload["input"])
        instruction = request_input["instruction"]
        with self.lock:
            self.requests.append(payload)
            self.attempts[instruction] += 1
            if instruction.startswith("user:"):
                self.user_instructions.add(instruction)
                if len(self.user_instructions) >= 2:
                    self.user_pair_ready.set()
            return instruction, self.attempts[instruction]

    def reset(self) -> None:
        with self.lock:
            self.requests.clear()
            self.attempts.clear()
            self.started.clear()
            self.releases.clear()
            self.user_instructions.clear()
            self.user_pair_ready.clear()

    def wait_for_user_pair(self, *, timeout: float) -> None:
        if not self.user_pair_ready.wait(timeout):
            raise AssertionError("两个用户请求未并发进入 fake Agent")

    def mark_started(self, instruction: str) -> None:
        with self.lock:
            started = self.started.setdefault(instruction, threading.Event())
            self.releases.setdefault(instruction, threading.Event())
        started.set()

    def wait_until_started(self, instruction: str, *, timeout: float) -> None:
        with self.lock:
            started = self.started.setdefault(instruction, threading.Event())
        if not started.wait(timeout):
            raise AssertionError(f"等待 fake Agent 启动超时: instruction={instruction}")

    def release(self, instruction: str) -> None:
        with self.lock:
            release = self.releases.setdefault(instruction, threading.Event())
        release.set()

    def wait_until_released(self, instruction: str, *, timeout: float) -> None:
        with self.lock:
            release = self.releases.setdefault(instruction, threading.Event())
        if not release.wait(timeout):
            raise TimeoutError(f"fake Agent 等待释放超时: instruction={instruction}")


def _complete_events(markdown: str) -> list[dict[str, Any]]:
    return [
        {"type": "RUN_STARTED", "threadId": "thread-1", "runId": "run-1"},
        {
            "type": "TOOL_CALL_START",
            "toolCallId": "tool-1",
            "toolCallName": "search_logs",
            "testPadding": "x" * 600,
        },
        {"type": "TOOL_CALL_END", "toolCallId": "tool-1"},
        {"type": "TEXT_MESSAGE_START", "messageId": "message-1", "role": "assistant"},
        {"type": "TEXT_MESSAGE_CONTENT", "messageId": "message-1", "delta": markdown},
        {"type": "TEXT_MESSAGE_END", "messageId": "message-1"},
        {"type": "RUN_FINISHED", "threadId": "thread-1", "runId": "run-1", "result": {"ignored": True}},
    ]


def _scenario_events(instruction: str, attempt: int) -> list[dict[str, Any]]:
    if instruction == "run-error":
        return [
            {"type": "RUN_STARTED", "threadId": "thread-error", "runId": "run-error"},
            {"type": "RUN_ERROR", "threadId": "thread-error", "runId": "run-error", "message": "failed"},
        ]
    if instruction == "disconnect":
        return [{"type": "RUN_STARTED", "threadId": "thread-disconnect", "runId": "run-disconnect"}]
    if instruction == "retry-once" and attempt == 1:
        return [
            {"type": "RUN_STARTED", "threadId": "thread-retry", "runId": "run-retry-1"},
            {"type": "RUN_ERROR", "threadId": "thread-retry", "runId": "run-retry-1", "message": "retry"},
        ]
    if instruction == "fencing" and attempt == 2:
        return [
            {"type": "RUN_STARTED", "threadId": "thread-fencing", "runId": "run-fencing-2"},
            {
                "type": "RUN_ERROR",
                "threadId": "thread-fencing",
                "runId": "run-fencing-2",
                "message": "duplicate delivery failed",
            },
        ]
    if instruction == "fencing" and attempt == 1:
        return _complete_events("# 旧执行不应覆盖")
    markdown_by_instruction = {
        "success": "# 审计结论",
        "retry-once": "# 重试结论",
        "user:log-analysis-user-a": "# 用户 A 结论",
        "user:log-analysis-user-b": "# 用户 B 结论",
        "redelivery": "# 重投结论",
        "fencing": "# 新任务结论",
    }
    markdown = markdown_by_instruction.get(instruction, f"# {instruction}")
    return _complete_events(markdown)


def _build_handler(agent: FakeLogAnalysisAgent):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length))
            instruction, attempt = agent.record(payload)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            if instruction == "timeout":
                event = {"type": "RUN_STARTED", "threadId": "thread-timeout", "runId": "run-timeout"}
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                self.wfile.write((":" + "x" * 600 + "\n\n").encode())
                self.wfile.flush()
                agent.mark_started(instruction)
                agent.wait_until_released(instruction, timeout=20)
                self.close_connection = True
                return
            if instruction.startswith("user:") and not agent.user_pair_ready.wait(10):
                raise TimeoutError("两个用户请求未并发进入 fake Agent")
            for index, event in enumerate(_scenario_events(instruction, attempt)):
                frame = f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
                self.wfile.write(frame)
                self.wfile.flush()
                should_block = (
                    (instruction == "success" and index == 1)
                    or (instruction in {"run-error", "disconnect"} and index == 0)
                    or (instruction in {"redelivery", "fencing"} and attempt == 1 and index == 1)
                )
                if should_block:
                    self.wfile.write((":" + "x" * 600 + "\n\n").encode())
                    self.wfile.flush()
                    agent.mark_started(instruction)
                    agent.wait_until_released(instruction, timeout=20)
            self.close_connection = True

        def log_message(self, format, *args):  # noqa: A002
            return

    return Handler


@contextmanager
def running_fake_log_analysis_agent():
    """在动态本地端口启动真实 HTTP SSE 服务。"""

    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    agent = FakeLogAnalysisAgent(base_url=f"http://127.0.0.1:{server.server_port}")
    server.RequestHandlerClass = _build_handler(agent)
    thread = threading.Thread(target=server.serve_forever, name="fake-log-analysis-agent", daemon=True)
    thread.start()
    try:
        yield agent
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
