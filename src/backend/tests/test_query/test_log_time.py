"""日志范围的显式时区、分区和时间顺序必须指向同一绝对时刻。"""

import pytest
from django.test import override_settings
from pydantic import ValidationError

from services.web.query.ai_assistant.log_tools.schemas import AgentSearchCondition
from services.web.query.ai_assistant.schemas import SearchCondition
from services.web.query.serializers import CollectorSearchAllReqSerializer
from services.web.query.utils.doris import DorisQuerySQLBuilder


@pytest.fixture(autouse=True)
def local_timezone():
    """固定日志存储时区，避免开发机时区影响分区断言。"""

    with override_settings(TIME_ZONE="Asia/Shanghai"):
        yield


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-09-23 00:00:00", "2026-09-23 00:00:20"),
        ("2026-09-23T00:00:00+08:00", "2026-09-23T00:00:20+08:00"),
        ("2026-09-22T16:00:00Z", "2026-09-22T16:00:20Z"),
        ("2026-09-22T16:00:00+00:00", "2026-09-22T16:00:20+00:00"),
        ("2026-09-22T16:00:00+0000", "2026-09-22T16:00:20+0000"),
        ("2026-09-22T11:00:00-05:00", "2026-09-22T11:00:20-05:00"),
        ("2026-09-23T06:00:00+14:00", "2026-09-23T06:00:20+14:00"),
    ],
)
def test_equivalent_ranges_have_same_partition_and_timestamp(start, end):
    """相同短窗的本地/UTC/其他偏移表示必须生成相同Doris条件。"""

    conditions = CollectorSearchAllReqSerializer._build_time_conditions({"start_time": start, "end_time": end})
    assert [item["filters"] for item in conditions] == [["20260923"], ["20260923"], [1790092800000], [1790092820000]]


def test_utc_range_crosses_local_partition_boundary():
    """分区边界以存储时区为准，不使用输入字符串的UTC日期。"""

    conditions = CollectorSearchAllReqSerializer._build_time_conditions(
        {"start_time": "2026-09-22T15:59:50Z", "end_time": "2026-09-22T16:00:20Z"}
    )
    assert [item["filters"] for item in conditions] == [["20260922"], ["20260923"], [1790092790000], [1790092820000]]


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026/09/23", "2026/09/24"),
        ("2026/09/22 16:00:00Z", "2026/09/23 16:00:00Z"),
        ("2026/09/22 11:00:00-05:00", "2026/09/23 11:00:00-05:00"),
    ],
)
def test_collector_keeps_legacy_date_format(start, end):
    """Collector历史日期仍可解析，其显式时区也不得被丢弃。"""

    conditions = CollectorSearchAllReqSerializer._build_time_conditions({"start_time": start, "end_time": end})
    assert [item["filters"] for item in conditions] == [["20260923"], ["20260924"], [1790092800000], [1790179200000]]


@pytest.mark.parametrize("value", ["09/23/2026", "23/09/2026", "September 23, 2026"])
def test_collector_does_not_expand_ambiguous_date_formats(value):
    """保留原有日期格式边界，不静默引入日/月顺序不明确的格式。"""

    with pytest.raises(ValueError):
        CollectorSearchAllReqSerializer._build_time_conditions({"start_time": value, "end_time": value})


@pytest.mark.parametrize("schema", [SearchCondition, AgentSearchCondition])
@pytest.mark.parametrize("reversed_range", [False, True])
def test_daylight_saving_range_uses_absolute_time(schema, reversed_range):
    """夏令时回拨的重复小时按真实时刻排序，不能按墙上时间排序。"""

    start, end = "2024-11-03T01:30:00-04:00", "2024-11-03T01:15:00-05:00"
    if reversed_range:
        start, end = end, start
    with override_settings(TIME_ZONE="America/New_York"):
        if reversed_range:
            with pytest.raises(ValidationError, match="start_time must not exceed end_time"):
                schema(scope_id="test_system", start_time=start, end_time=end)
        else:
            assert schema(scope_id="test_system", start_time=start, end_time=end).end_time == end


def test_search_condition_accepts_chronological_mixed_offsets():
    """不同偏移的墙上时间可逆序，但真实开始时刻不得被误拒绝。"""

    condition = SearchCondition(
        scope_id="test_system", start_time="2026-09-18T02:00:00+08:00", end_time="2026-09-18T00:00:00Z"
    )
    assert condition.end_time == "2026-09-18T00:00:00Z"


def test_search_condition_rejects_reversed_mixed_offsets():
    """显式UTC不得被当作本地时间，导致倒置窗口被接受。"""

    with pytest.raises(ValidationError, match="start_time must not exceed end_time"):
        SearchCondition(scope_id="test_system", start_time="2026-09-18T00:00:00Z", end_time="2026-09-18T02:00:00+08:00")


def test_equivalent_times_generate_identical_search_and_count_sql():
    """实际Doris数据及计数SQL不得因等价时区输入而改变查询范围。"""

    queries = []
    for start, end in [
        ("2026-09-23T00:00:00+08:00", "2026-09-23T00:00:20+08:00"),
        ("2026-09-22T16:00:00Z", "2026-09-22T16:00:20Z"),
    ]:
        builder = DorisQuerySQLBuilder(
            table="test_rt",
            conditions=CollectorSearchAllReqSerializer._build_time_conditions({"start_time": start, "end_time": end}),
            page=1,
            page_size=10,
            sort_list=[],
        )
        queries.append((str(builder.build_data_sql()), str(builder.build_count_sql())))
    assert queries[0] == queries[1]
    assert "1790092800000" in queries[0][0]
