"""所有BKBase版本复用V3 Query，覆盖真实Service/SDK/HTTP边界。"""
import json
from copy import deepcopy
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings

from api.bk_base import default as sdk
from services.web.bkbase import query
from services.web.query.resources.doris import CollectorSearchAllResource


@override_settings(
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_admin",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_token",
    },
)
class UnifiedQueryRoutingTests(SimpleTestCase):
    sql = "SELECT event_content FROM 47_logs.doris WHERE thedate = 20261119 LIMIT 5 OFFSET 10"
    count = "SELECT COUNT(*) FROM 47_logs.doris WHERE thedate = 20261119"

    def setUp(self):
        self.sent = []
        self.failed = False
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(sdk.BkBaseResource, "base_url", "https://normal.test/"))
        self.enterContext(mock.patch.object(sdk.DebugBkBaseResource, "base_url", "https://debug.test/"))

    def transport(self, method, url, **kwargs):
        self.assertEqual(method, "POST")
        self.sent.append((url, deepcopy(kwargs)))
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.request = requests.Request(method, url).prepare()
        rows = [{"count": "37"}] if kwargs["json"]["sql"] == self.count else [{"event_content": "synthetic"}]
        payload = {"result": True, "code": "00", "data": {"list": rows, "total_records": 999}}
        if self.failed:
            payload = {"result": False, "code": "1500200", "message": "synthetic upstream failure", "data": None}
        response._content = json.dumps(payload).encode()
        return response

    def assert_sent(self, debug, action, sql, *, call=None):
        url, kwargs = call or self.sent[-1]
        self.assertEqual(url, ("https://debug.test" if debug else "https://normal.test") + action)
        self.assertEqual(kwargs["json"]["sql"], sql)
        self.assertEqual(kwargs["json"]["bk_username"], "synthetic_admin")
        self.assertEqual(kwargs["json"]["bk_app_code"], "synthetic_app")
        self.assertEqual(kwargs["json"]["bkdata_authentication_method"], "user")
        self.assertEqual(kwargs["timeout"], 300)
        auth = json.loads(kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(auth["bk_username"], "synthetic_admin")
        self.assertEqual(auth["access_token"], "synthetic_token")

    def assert_bulk_contract(self, debug, safe, action):
        self.sent.clear()
        results = query.query_sync_bulk(
            [{"sql": self.sql, "prefer_storage": "doris"}, {"sql": self.count}], debug=debug, safe=safe
        )
        self.assertEqual(
            results,
            [
                {"list": [{"event_content": "synthetic"}], "total_records": 999},
                {"list": [{"count": "37"}], "total_records": 999},
            ],
        )
        self.assertEqual(len(self.sent), 2)
        sent = {call[1]["json"]["sql"]: call for call in self.sent}
        self.assertEqual(set(sent), {self.sql, self.count})
        for sql, storage in ((self.sql, "doris"), (self.count, "")):
            self.assert_sent(debug, action, sql, call=sent[sql])
            self.assertEqual(sent[sql][1]["json"]["prefer_storage"], storage)

    def test_both_versions_normal_debug_and_safe_use_existing_v3_route(self):
        for version in ("v3", "v4"):
            for debug, safe in ((False, False), (True, False), (False, True), (True, True)):
                with self.subTest(version=version, debug=debug, safe=safe), override_settings(
                    BKBASE_API_VERSION=version
                ):
                    result = query.query_sync(self.sql, prefer_storage="doris", debug=debug, safe=safe)
                    self.assertEqual(result, {"list": [{"event_content": "synthetic"}], "total_records": 999})
                    self.assert_sent(debug, "/v3/queryengine/query_sync/", self.sql)
                    self.assertEqual(self.sent[-1][1]["json"]["prefer_storage"], "doris")
                    self.assert_bulk_contract(debug, safe, "/v3/queryengine/query_sync/")

    def test_custom_loaded_action_reaches_every_single_and_bulk_variant(self):
        action = "/custom/queryengine/compatible/"
        # action按现有协议在启动时由配置读入；此处模拟已载入的自定义值，不重载SDK注册表。
        with mock.patch.object(sdk.QuerySyncResource, "action", action), mock.patch.object(
            sdk.DebugQuerySyncResource, "action", action
        ):
            for version in ("v3", "v4"):
                for debug, safe in ((False, False), (True, False), (False, True), (True, True)):
                    with self.subTest(version=version, debug=debug, safe=safe), override_settings(
                        BKBASE_API_VERSION=version
                    ):
                        self.sent.clear()
                        query.query_sync(self.sql, debug=debug, safe=safe)
                        self.assert_sent(debug, action, self.sql)
                        self.assertEqual(self.sent[-1][1]["json"]["prefer_storage"], "")
                        self.assert_bulk_contract(debug, safe, action)

    def test_upstream_failure_propagates_without_another_route(self):
        self.failed = True
        for version in ("v3", "v4"):
            for debug, safe in ((False, False), (True, False), (False, True)):
                with self.subTest(version=version, debug=debug, safe=safe), override_settings(
                    BKBASE_API_VERSION=version
                ):
                    self.sent.clear()
                    with self.assertRaisesMessage(APIRequestError, "synthetic upstream failure"):
                        query.query_sync(self.sql, debug=debug, safe=safe)
                    self.assertEqual(len(self.sent), 1)
                    self.assert_sent(debug, "/v3/queryengine/query_sync/", self.sql)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_collector_retains_business_count_and_pagination(self):
        collector = CollectorSearchAllResource()
        with mock.patch.object(
            collector, "build_sql", return_value={"data": self.sql, "count": self.count}
        ), mock.patch.object(collector, "parse_data", return_value=[{"event_content": "synthetic"}]):
            result = collector.request(
                namespace="default",
                start_time="2026-11-18T10:00:00+08:00",
                end_time="2026-11-19T10:00:00+08:00",
                page=3,
                page_size=5,
                bind_system_info=False,
                conditions=[],
            )
        self.assertEqual(result["page"], 3)
        self.assertEqual(result["num_pages"], 5)
        self.assertEqual(result["total"], "37")
        self.assertEqual(result["query_sql"], self.sql)
        self.assertEqual(result["count_sql"], self.count)
        self.assertEqual(result["results"], [{"event_content": "synthetic"}])
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(all(url == "https://normal.test/v3/queryengine/query_sync/" for url, _ in self.sent))
