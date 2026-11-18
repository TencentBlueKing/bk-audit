"""Finite Redis tail I/O uses isolated, bounded pools and fixed role clients."""

import socket
import threading
import time
from contextlib import contextmanager
from unittest import mock

from django.core.cache import caches
from django.test import SimpleTestCase, override_settings
from redis import ConnectionPool, Redis, SSLConnection
from ui_stream.exceptions import LiveUnavailable

from services.web.ai_assistant.schemas import UIStreamEvent
from services.web.ai_assistant.streaming import redis as stream_redis


@contextmanager
def silent_redis():
    """Accept loopback TCP and deliberately never answer a Redis command."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    listener.settimeout(0.05)
    stop = threading.Event()
    connections = []

    def serve():
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
                connections.append(connection)
            except socket.timeout:
                continue
            except OSError:
                break
        for connection in connections:
            connection.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield listener.getsockname()[1]
    finally:
        stop.set()
        worker.join(1)
        listener.close()


@override_settings(
    AI_ASSISTANT_STREAM_REDIS_IO_TIMEOUT=0.05,
    AI_ASSISTANT_STREAM_STATE_POLL_INTERVAL=0.05,
    AI_ASSISTANT_STREAM_REDIS_READ_MAX_CONNECTIONS=2,
    AI_ASSISTANT_STREAM_REDIS_WRITE_MAX_CONNECTIONS=1,
)
class StreamRedisPoolTest(SimpleTestCase):
    def setUp(self):
        self.pools = []

        def make_pool(*args, **kwargs):
            pool = ConnectionPool(*args, **kwargs)
            self.pools.append(pool)
            return pool

        pool_patch = mock.patch.object(stream_redis, "ConnectionPool", side_effect=make_pool)
        pool_patch.start()
        self.addCleanup(pool_patch.stop)
        self.addCleanup(self.clear_clients)
        self.clear_clients()

    def clear_clients(self):
        clear = getattr(stream_redis._stream_client, "cache_clear", None)
        if clear is not None:
            clear()
        for pool in self.pools:
            pool.disconnect()
        self.pools.clear()

    def source_client(self, **kwargs):
        parameters = {"host": "127.0.0.1", "port": 1, "db": 2}
        parameters.update(kwargs)
        pool = ConnectionPool(**parameters)
        self.pools.append(pool)
        return Redis(connection_pool=pool)

    def test_stream_pools_are_separate_bounded_and_preserve_tls_auth_and_namespace(self):
        source = self.source_client(
            connection_class=SSLConnection,
            password="synthetic",
            socket_timeout=None,
            ssl_cert_reqs="required",
        )
        original_kwargs = dict(source.connection_pool.connection_kwargs)
        with mock.patch.object(stream_redis, "get_redis_connection", return_value=source):
            writer = stream_redis.RedisLiveStore()
            reader = stream_redis.RedisLiveStore(for_read=True)
        write_pool = writer._client.connection_pool
        read_pool = reader._client.connection_pool
        self.assertIsNot(write_pool, source.connection_pool)
        self.assertIsNot(read_pool, source.connection_pool)
        self.assertIsNot(write_pool, read_pool)
        self.assertEqual(write_pool.max_connections, 1)
        self.assertEqual(read_pool.max_connections, 2)
        self.assertEqual(source.connection_pool.connection_kwargs, original_kwargs)
        self.assertIs(read_pool.connection_class, SSLConnection)
        self.assertEqual(read_pool.connection_kwargs["ssl_cert_reqs"], "required")
        for name in ("host", "port", "password", "db"):
            self.assertEqual(read_pool.connection_kwargs[name], original_kwargs[name])
        self.assertEqual(read_pool.connection_kwargs["socket_connect_timeout"], 0.05)
        self.assertEqual(read_pool.connection_kwargs["socket_timeout"], 5.05)
        self.assertEqual(write_pool.connection_kwargs["socket_timeout"], 0.05)
        self.assertFalse(read_pool.connection_kwargs["retry_on_timeout"])
        self.assertEqual(reader.physical_key("synthetic"), caches["redis"].make_key("synthetic"))

    def test_warm_clients_are_reused_by_role_until_process_restart(self):
        source = self.source_client()
        with mock.patch.object(stream_redis, "get_redis_connection", return_value=source) as connection:
            writer = stream_redis.RedisLiveStore()
            reader = stream_redis.RedisLiveStore(for_read=True)
            connection.return_value = self.source_client(port=2)
            with override_settings(AI_ASSISTANT_STREAM_REDIS_IO_TIMEOUT=0.25):
                self.assertIs(stream_redis.RedisLiveStore()._client, writer._client)
                self.assertIs(stream_redis.RedisLiveStore(for_read=True)._client, reader._client)
        self.assertEqual(connection.call_count, 2)

    def test_read_timeout_follows_poll_interval_with_a_five_second_margin(self):
        for interval, expected in ((2, 7), (60, 20)):
            with self.subTest(interval=interval):
                self.clear_clients()
                with override_settings(AI_ASSISTANT_STREAM_STATE_POLL_INTERVAL=interval):
                    with mock.patch.object(stream_redis, "get_redis_connection", return_value=self.source_client()):
                        reader = stream_redis.RedisLiveStore(for_read=True)
                self.assertEqual(reader._client.connection_pool.connection_kwargs["socket_timeout"], expected)

    def test_pool_exhaustion_fails_without_waiting_for_a_slot(self):
        with mock.patch.object(stream_redis, "get_redis_connection", return_value=self.source_client()):
            writer = stream_redis.RedisLiveStore()
        writer._client.connection_pool.make_connection()
        started = time.monotonic()
        with mock.patch.object(
            writer._client.connection_pool.connection_class,
            "connect",
            side_effect=AssertionError("must fail at pool admission"),
        ):
            with self.assertRaises(LiveUnavailable):
                writer.append(redis_key="synthetic", event=UIStreamEvent(data={"text": "synthetic"}))
        self.assertLess(time.monotonic() - started, 0.5)

    def assert_silent_failure_is_bounded(self, *, for_read):
        with silent_redis() as port:
            source = self.source_client(port=port, socket_timeout=None)
            # Shorten only the fixed margin in this loopback probe; production stays at 5s.
            with mock.patch.object(stream_redis, "READ_TIMEOUT_MARGIN_SECONDS", 0.1, create=True):
                with mock.patch.object(stream_redis, "get_redis_connection", return_value=source):
                    store = stream_redis.RedisLiveStore(for_read=for_read)
            failures = []

            def request():
                try:
                    if for_read:
                        store.read(redis_key="synthetic", after_id="0-0", block_ms=50)
                    else:
                        store.append(redis_key="synthetic", event=UIStreamEvent(data=1))
                except LiveUnavailable as exc:
                    failures.append(type(exc).__name__)

            worker = threading.Thread(target=request, daemon=True)
            self.addCleanup(worker.join, 1)
            started = time.monotonic()
            worker.start()
            worker.join(0.6)
            self.assertFalse(worker.is_alive(), "Redis still waiting for a reply")
            self.assertEqual(failures, ["LiveUnavailable"])
            self.assertLess(time.monotonic() - started, 0.6)

    def test_silent_redis_write_returns_a_bounded_failure(self):
        self.assert_silent_failure_is_bounded(for_read=False)

    def test_silent_redis_read_returns_a_bounded_failure(self):
        self.assert_silent_failure_is_bounded(for_read=True)
