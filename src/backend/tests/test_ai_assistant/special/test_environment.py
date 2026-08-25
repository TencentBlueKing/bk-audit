import pytest
from blueapps.core.celery import celery_app
from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase
from django_redis import get_redis_connection

pytestmark = pytest.mark.special


class SpecialEnvironmentTest(TransactionTestCase):
    def test_real_mysql_redis_and_rabbitmq_are_available(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            mysql_version = cursor.fetchone()[0]
        self.assertTrue(mysql_version.startswith("5.7."), mysql_version)
        self.assertTrue(get_redis_connection("redis").ping())
        # 日常 Celery 走 Redis；专项门禁必须探测独立的 RabbitMQ 测试 Broker。
        with celery_app.connection_for_write(url=settings.CELERY_TEST_BROKER_URL) as broker:
            broker.ensure_connection(max_retries=0)
            self.assertEqual(broker.transport.driver_type, "amqp")
