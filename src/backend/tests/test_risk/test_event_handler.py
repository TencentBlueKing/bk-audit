# -*- coding: utf-8 -*-
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.risk.handlers.event import EventHandler


@override_settings(DEFAULT_MAX_RETRY=3, DEFAULT_RETRY_SLEEP_TIME=0, DEFAULT_MAX_RETRY_SLEEP_TIME=0)
class TestEventHandlerRetry(SimpleTestCase):
    def _search_event_params(self):
        return {
            "namespace": "default",
            "start_time": "2026-06-24 00:00:00",
            "end_time": "2026-06-24 01:00:00",
            "page": 1,
            "page_size": 10,
        }

    @mock.patch("core.utils.retry.time.sleep", return_value=None)
    @mock.patch("services.web.risk.handlers.event.GlobalMetaConfig.get", return_value=1)
    @mock.patch("services.web.risk.handlers.event.EventHandler.get_search_index_set_id", return_value=2)
    @mock.patch("services.web.risk.handlers.event.resource.query.search_all")
    def test_search_event_retries_transient_query_failure(
        self,
        mock_search_all,
        mock_get_search_index_set_id,
        mock_global_meta_get,
        mock_sleep,
    ):
        mock_search_all.side_effect = [
            RuntimeError("bklog temporary error"),
            RuntimeError("bklog temporary error"),
            {"results": [{"event_id": "event-001"}], "total": 1},
        ]

        result = EventHandler.search_event(**self._search_event_params())

        self.assertEqual(result["total"], 1)
        self.assertEqual(mock_search_all.call_count, 3)
        mock_sleep.assert_called()

    @mock.patch("core.utils.retry.time.sleep", return_value=None)
    def test_search_all_event_does_not_retry_search_event_again(self, mock_sleep):
        with mock.patch.object(EventHandler, "search_event", side_effect=RuntimeError("bklog failed")) as mock_search:
            with self.assertRaises(RuntimeError):
                EventHandler.search_all_event(**self._search_event_params())

        self.assertEqual(mock_search.call_count, 1)
