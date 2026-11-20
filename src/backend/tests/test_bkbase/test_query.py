"""验证统一V3查询入口及调用的业务边界。"""
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from services.web.bkbase import query
from services.web.bkbase.common import get_bkbase_version


class QueryServiceTests(SimpleTestCase):
    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_delegates_original_query(self):
        with mock.patch(
            "services.web.bkbase.query.api.bk_base.query_sync", return_value={"list": [{"count": 100}]}
        ) as call:
            self.assertEqual(query.query_sync("SELECT COUNT(*)"), {"list": [{"count": 100}]})
            call.assert_called_once_with(sql="SELECT COUNT(*)")

    @override_settings(BKBASE_API_VERSION="invalid")
    def test_invalid_version_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            get_bkbase_version()

    @override_settings(BKBASE_API_VERSION="v4")
    def test_bulk_order_and_debug_route(self):
        values = [{"list": [{"tag": "first"}]}, {"list": [{"tag": "second"}]}]
        with mock.patch(
            "services.web.bkbase.query.api.bk_base.debug_query_sync.bulk_request", return_value=values
        ) as call:
            self.assertEqual(query.query_sync_bulk([{"sql": "first"}, {"sql": "second"}], debug=True), values)
            call.assert_called_once_with([{"sql": "first"}, {"sql": "second"}])

    @override_settings(BKBASE_API_VERSION="v4")
    def test_configured_v3_query_failure_propagates(self):
        with mock.patch(
            "services.web.bkbase.query.api.bk_base.query_sync",
            side_effect=RuntimeError("upstream unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "upstream unavailable"):
                query.query_sync("SELECT 1")
