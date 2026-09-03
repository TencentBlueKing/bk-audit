import json
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from django.conf import settings

EnvelopePredicate = Callable[[dict], bool]


@dataclass(frozen=True, slots=True)
class SSEFrame:
    event: str | None
    stream_id: str | None
    data: object
    is_heartbeat: bool = False


def iter_sse_frames(lines: Iterable[bytes | str], *, include_heartbeats: bool = False) -> Iterator[SSEFrame]:
    """解析 SSE 的 event/id/data 与空行边界；默认跳过 heartbeat 注释。"""

    event: str | None = None
    stream_id: str | None = None
    data_lines: list[str] = []
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        line = line.rstrip("\r\n")
        if line.startswith(":"):
            if include_heartbeats:
                yield SSEFrame(event=None, stream_id=None, data=None, is_heartbeat=True)
            event = None
            stream_id = None
            data_lines = []
            continue
        if line == "":
            if data_lines:
                yield SSEFrame(event=event, stream_id=stream_id, data=json.loads("\n".join(data_lines)))
            event = None
            stream_id = None
            data_lines = []
            continue
        field, _, value = line.partition(":")
        value = value.lstrip(" ")
        if field == "event":
            event = value
        elif field == "id":
            stream_id = value
        elif field == "data":
            data_lines.append(value)

    if data_lines:
        yield SSEFrame(event=event, stream_id=stream_id, data=json.loads("\n".join(data_lines)))


def wait_for_http_json(
    *,
    session,
    url: str,
    predicate: EnvelopePredicate,
    timeout: float | None = None,
) -> dict:
    """短间隔轮询 GET，直到统一响应 ``data.status`` 满足 predicate。"""

    deadline = time.monotonic() + (timeout or settings.CELERY_TEST_TASK_TIMEOUT)
    last_http_status = None
    last_business_status = None
    while time.monotonic() < deadline:
        response = session.get(url)
        last_http_status = response.status_code
        payload = response.json()
        data = payload.get("data") or {}
        last_business_status = data.get("status")
        if predicate(data):
            return payload
        time.sleep(0.05)
    raise AssertionError(f"等待 HTTP JSON 超时: url={url}, http_status={last_http_status}, status={last_business_status}")


def iter_http_sse_frames(
    response, *, timeout: float | None = None, include_heartbeats: bool = False
) -> Iterator[SSEFrame]:
    """读取真实 HTTP SSE，并在硬超时后失败，避免测试线程挂起。"""

    deadline = time.monotonic() + (timeout or settings.CELERY_TEST_TASK_TIMEOUT)

    def lines() -> Iterator[bytes]:
        # SSE 必须逐行下发；默认 512B chunk 会把小事件攒批，无法验证首帧实时性。
        for line in response.iter_lines(chunk_size=1):
            if time.monotonic() > deadline:
                raise TimeoutError(f"SSE 读取超时: url={getattr(response, 'url', '')}")
            yield line

    yield from iter_sse_frames(lines(), include_heartbeats=include_heartbeats)


def start_http_sse_collector(
    *,
    session,
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    terminal_event: str | None = None,
    include_heartbeats: bool = False,
    timeout: float | None = None,
):
    """后台线程发起 SSE，避免 LiveServer 缓冲把 get() 卡到流结束。"""

    frames: list[SSEFrame] = []
    done = threading.Event()
    errors: list[BaseException] = []
    read_timeout = timeout or settings.CELERY_TEST_TASK_TIMEOUT

    def run():
        response = None
        try:
            response = session.get(
                url,
                params=params or {},
                headers=headers or {},
                stream=True,
                timeout=(3.05, read_timeout),
            )
            if response.status_code != 200:
                raise AssertionError(f"SSE HTTP {response.status_code}: {response.text}")
            for frame in iter_http_sse_frames(response, timeout=read_timeout, include_heartbeats=include_heartbeats):
                frames.append(frame)
                if terminal_event and frame.event == terminal_event:
                    break
        except Exception as error:  # noqa: BLE001
            errors.append(error)
        finally:
            if response is not None:
                response.close()
            done.set()

    thread = threading.Thread(target=run, name="http-sse-collector", daemon=True)
    thread.start()
    # LiveServer 接受连接后才会进入 Redis 订阅；短等待只覆盖建连，不用来推测业务完成。
    time.sleep(0.2)
    return frames, done, thread, errors
