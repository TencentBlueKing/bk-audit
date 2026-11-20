"""三个 AI 日志工具经 Query Service 路由，SQL 与错误契约不变。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings
from requests.exceptions import Timeout

from api.bk_base.default import SafeQuerySyncResource
from services.web.bkbase import query
from services.web.query.ai_assistant.exceptions import LogQueryTimeout
from services.web.query.ai_assistant.log_tools import (
    aggregation,
    field_metadata,
    search,
)
from services.web.query.ai_assistant.log_tools.errors import map_log_query_error
from services.web.query.ai_assistant.log_tools.schemas import LogFieldRef


class AIToolQueryRoutingTests(SimpleTestCase):
    def setUp(self):
        self.context = SimpleNamespace(
            table="11_logs.doris", conditions=["thedate = 20261109", "dtEventTimeStamp >= 42"]
        )
        self.request = SimpleNamespace(sort=[], page=2, page_size=7)
        self.fields = [LogFieldRef(raw_name="event_content", keys=[])]
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )

    def exercise_tools(self, service):
        data_sql = "SELECT body FROM 11_logs WHERE thedate = 20261109 AND dtEventTimeStamp >= 42 LIMIT 7 OFFSET 7"
        count_sql = "SELECT count(*) FROM 11_logs WHERE thedate = 20261109 AND dtEventTimeStamp >= 42"
        builder = SimpleNamespace(
            JSON_TYPE_FIELDS=set(),
            build_data_sql=mock.Mock(return_value=data_sql),
            build_count_sql=mock.Mock(return_value=count_sql),
            build_complete_sql=mock.Mock(return_value=data_sql),
            build_preflight_sql=mock.Mock(return_value=count_sql),
        )
        service.bulk_request.side_effect = [
            [{"list": [{"body": "x"}]}, {"list": [{"count": 1}]}],
            [{"list": [{"count": 1}]}],
        ]
        service.return_value = {"list": [{"body": "sample"}]}
        with mock.patch.object(search, "ProjectedLogSQLBuilder", return_value=builder) as build_search:
            rows, count, _ = search.LogDetailSearchService._query(
                context=self.context, request=self.request, fields=self.fields
            )
        self.assertEqual(rows, {"list": [{"body": "x"}]})
        self.assertEqual(count, {"list": [{"count": 1}]})
        self.assertEqual(build_search.call_args.kwargs["conditions"], self.context.conditions)
        result, _ = aggregation.LogAggregationService._query(builder, preflight=True)
        self.assertEqual(result, {"list": [{"count": 1}]})
        with mock.patch.object(field_metadata, "ProjectedLogSQLBuilder", return_value=builder) as build_fields:
            sample = field_metadata.LogFieldMetadataService._query_samples(self.context, self.fields[0], page_size=7)
        self.assertEqual(sample, [{"body": "sample"}])
        self.assertEqual(build_fields.call_args.kwargs["conditions"], self.context.conditions)
        self.assertEqual(
            service.bulk_request.call_args_list,
            [
                mock.call(
                    [{"sql": data_sql, "prefer_storage": "doris"}, {"sql": count_sql, "prefer_storage": "doris"}]
                ),
                mock.call([{"sql": count_sql, "prefer_storage": "doris"}]),
            ],
        )
        service.assert_called_once_with(sql=data_sql, prefer_storage="doris")

    def test_both_versions_keep_all_three_tools_on_existing_v3_resource(self):
        for version in ("v3", "v4"):
            with self.subTest(version=version), override_settings(BKBASE_API_VERSION=version), mock.patch.object(
                query.api.bk_base, "safe_query_sync"
            ) as endpoint:
                self.exercise_tools(endpoint)

    def test_routed_timeout_retains_tool_timeout_mapping_in_both_versions(self):
        builder = SimpleNamespace(build_complete_sql=lambda: "SELECT 1")
        for version in ("v3", "v4"):
            endpoint = query.api.bk_base.safe_query_sync
            with self.subTest(version=version), override_settings(BKBASE_API_VERSION=version), mock.patch.object(
                endpoint, "bulk_request", side_effect=Timeout("synthetic timeout")
            ):
                with self.assertRaises(Timeout) as raised:
                    aggregation.LogAggregationService._query(builder)
                self.assertIsInstance(map_log_query_error(raised.exception), LogQueryTimeout)


class SafeQueryLoggingTests(SimpleTestCase):
    def test_actual_request_keeps_sql_diagnostic_without_logging_authentication(self):
        resource = SafeQuerySyncResource()
        response = mock.Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": True, "code": 0, "data": {"list": []}}
        sql = "SELECT * FROM 11_logs WHERE thedate = 20261109 AND dtEventTimeStamp >= 42"
        with mock.patch.object(resource.session, "request", return_value=response) as send, mock.patch.object(
            resource, "build_header", return_value={"X-Bkapi-Authorization": "synthetic-auth"}
        ), mock.patch("api.bk_base.default.logger.info") as info:
            self.assertEqual(resource.request(sql=sql, prefer_storage="doris"), {"list": []})
        self.assertIn("/v3/queryengine/query_sync/", send.call_args.kwargs.get("url") or send.call_args.args[1])
        info.assert_any_call("[SafeQuerySyncResource] SQL => %s", sql)
        self.assertNotIn("synthetic-auth", str(info.call_args))
