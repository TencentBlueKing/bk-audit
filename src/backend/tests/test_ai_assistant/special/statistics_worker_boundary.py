"""独立统计测试 Worker 的外部查询边界替身。

仅在专用环境变量存在时替换 IAM/表元数据及 Doris 响应，生产 Handler、Task、
SQL 构造、帧校验和数据库写入保持真实；不证明 Doris 引擎执行或权限系统正确。
"""

import os
from unittest import mock

from api.bk_base.default import SafeQuerySyncResource
from services.web.query.ai_assistant.log_tools.context import (
    LogQueryContext,
    LogQueryContextService,
)
from tests.test_query.test_ai_assistant.test_field_statistics import field_frames


def build_context(*, username, namespace, condition):
    """保留任务提供的身份和范围，只替换远端权限/表配置查询。"""
    return LogQueryContext(username=username, namespace=namespace, condition=condition, table="logs", conditions=())


def query_frames(requests):
    """返回手算十条日志的预检/最终统计帧，不执行 Doris SQL。"""
    if "AS group_count" in requests[0]["sql"]:
        return ({"list": [dict(group_count="3", invalid_type_count="0", invalid_number_count="0")]},)
    return ({"list": field_frames()},)


if os.getenv("BKAPP_STATISTICS_E2E_BOUNDARY") == "1":
    mock.patch.object(LogQueryContextService, "build", side_effect=build_context).start()
    mock.patch.object(SafeQuerySyncResource, "bulk_request", side_effect=query_frames).start()
