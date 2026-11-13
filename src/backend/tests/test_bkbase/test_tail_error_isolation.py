"""单个采集项取样映射失败不影响后续采集项。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus import tasks
from services.web.databus.collector.handlers import BkBaseTailLogHandler
from services.web.databus.constants import SourcePlatformChoices


class TailErrorIsolationTests(SimpleTestCase):
    def test_mapping_error_does_not_stop_following_collector(self):
        collectors = [
            SimpleNamespace(
                collector_config_id=i,
                bk_data_id=i,
                tail_log_time=None,
                source_platform=SourcePlatformChoices.BKBASE.value,
                save=mock.Mock(),
            )
            for i in (11, 12)
        ]
        secret_sample = '{"start_time": 1700000000000, "secret": "synthetic_value"}'
        with mock.patch.object(tasks.CollectorConfig.objects, "all", return_value=collectors), mock.patch(
            "services.web.databus.collector.handlers.bkbase_source.get_rawdata_tail",
            side_effect=[BKBaseResourceMappingError(message="synthetic mapping"), [{"value": secret_sample}]],
        ) as tail, mock.patch("core.lock.CacheLock._init", return_value=True), mock.patch(
            "core.lock.CacheLock.release", return_value=True
        ), mock.patch(
            "services.web.databus.collector.handlers.logger.warning"
        ) as warning:
            tasks.sync_tail_log_time.run()
        self.assertEqual(tail.call_count, 2)
        self.assertIsNotNone(collectors[1].tail_log_time)
        collectors[1].save.assert_called_once_with(update_fields=["tail_log_time"])
        self.assertNotIn("synthetic_value", str(warning.call_args_list))

    def test_parse_failure_does_not_log_raw_tail(self):
        collector = SimpleNamespace(
            collector_config_id=11,
            bk_data_id=11,
            tail_log_time=None,
            source_platform=SourcePlatformChoices.BKBASE.value,
            save=mock.Mock(),
        )
        with mock.patch(
            "services.web.databus.collector.handlers.bkbase_source.get_rawdata_tail",
            return_value=[{"value": "sensitive_not_json"}],
        ), mock.patch("services.web.databus.collector.handlers.logger.warning") as warning:
            BkBaseTailLogHandler(collector).sync()
        self.assertNotIn("sensitive_not_json", str(warning.call_args_list))
