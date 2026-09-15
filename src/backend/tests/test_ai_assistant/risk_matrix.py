"""AI 助手平台风险矩阵：供 CI 校验测试 ID 可加载，不读取 debug 文档。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskCase:
    risk_id: str
    layer: str
    test_id: str
    ci_suite: str
    invariant: str


RISK_CASES: tuple[RiskCase, ...] = (
    RiskCase(
        'R01',
        '契约',
        "tests.test_ai_assistant.test_handler_contracts.ProductionMessageHandlerContractTest"
        ".test_production_message_registry_matches_contract_manifest",
        'regular',
        '每个已注册 Message Handler 都有可加载的行为契约',
    ),
    RiskCase(
        'R02',
        '契约',
        "tests.test_ai_assistant.test_handler_contracts.ProductionAttachmentHandlerContractTest"
        ".test_production_attachment_registry_matches_contract_manifest",
        'regular',
        '每个已注册 Attachment Handler 都有可加载的行为契约',
    ),
    RiskCase(
        'R03',
        '契约',
        "tests.test_ai_assistant.test_message_resources.MessageOpenAPIStartupContractTest"
        ".test_first_openapi_generation_includes_registered_handlers_and_freezes",
        'regular',
        '首次生成 OpenAPI 即包含已注册 Handler 并冻结 oneOf',
    ),
    RiskCase(
        'R04',
        '状态',
        "tests.test_ai_assistant.test_message_resources.MessageResourceTest"
        ".test_create_sync_message_returns_success_without_internal_fields",
        'regular',
        '同步消息直接 SUCCESS，且不暴露内部字段',
    ),
    RiskCase(
        'R05',
        '状态',
        "tests.test_ai_assistant.test_message_resources.MessageResourceTest"
        ".test_create_async_message_returns_processing_and_detail_observes_success",
        'regular',
        '异步消息先 PROCESSING，详情可观察到 SUCCESS',
    ),
    RiskCase(
        'R06',
        'HTTP',
        "tests.test_ai_assistant.test_http_integration.HttpIntegrationTest"
        ".test_async_message_creates_and_reaches_success_over_http",
        'regular',
        '真实 HTTP 异步消息能收敛到 SUCCESS',
    ),
    RiskCase(
        'R07',
        '重试',
        "tests.test_ai_assistant.test_http_integration.HttpIntegrationTest"
        ".test_async_attachment_creates_and_retries_after_failure_over_http",
        'regular',
        '失败附件可通过 HTTP 重试并回到 SUCCESS',
    ),
    RiskCase(
        'R08',
        'fencing',
        "tests.test_ai_assistant.test_celery_integration.CeleryExecutionIntegrationTest"
        ".test_manual_retry_uses_new_task_id_and_old_task_cannot_overwrite",
        'regular',
        '手动重试更换 task_id，旧任务不能覆盖新结果',
    ),
    RiskCase(
        'R09',
        'fencing',
        'tests.test_ai_assistant.test_attachment_task.AttachmentTaskTest.test_old_task_id_delivery_is_ignored',
        'regular',
        '过期 task_id 投递被忽略，不改写当前附件',
    ),
    RiskCase(
        'R10',
        'fencing',
        "tests.test_ai_assistant.test_celery_integration.CeleryExecutionIntegrationTest"
        ".test_stream_duplicate_delivery_keeps_only_current_execution_result",
        'regular',
        '重复投递只保留当前 execution 的归档和产物',
    ),
    RiskCase(
        'R11',
        'Worker重投',
        "tests.test_ai_assistant.special.test_worker_redelivery.WorkerRedeliveryTest"
        ".test_sigkill_redelivers_same_task_and_rotates_execution",
        'special',
        'SIGKILL 后 RabbitMQ 重投同一 task_id，并切换到新 execution',
    ),
    RiskCase(
        'R12',
        '存储故障',
        "tests.test_ai_assistant.special.test_stream_failures.StreamFailureSpecialTest"
        ".test_redis_append_failure_still_succeeds_with_degraded_archive",
        'special',
        'Redis 持续失败时任务仍 SUCCESS，归档 DEGRADED 且无 stream_id',
    ),
    RiskCase(
        'R13',
        '存储故障',
        "tests.test_ai_assistant.special.test_stream_failures.StreamFailureSpecialTest"
        ".test_checkpoint_first_failure_keeps_pending_and_finalizes_ordered_events",
        'special',
        'checkpoint 首次失败保留 pending，最终按序归档完整事件',
    ),
    RiskCase(
        'R14',
        '存储故障',
        "tests.test_ai_assistant.special.test_stream_failures.StreamFailureSpecialTest"
        ".test_finalize_first_failure_retries_with_new_execution",
        'special',
        'finalize 首次失败后重试换 execution，旧流收到 reset',
    ),
    RiskCase(
        'R15',
        '重试竞争',
        "tests.test_ai_assistant.special.test_stream_failures.StreamFailureSpecialTest"
        ".test_manual_retry_fences_old_worker_and_keeps_new_execution",
        'special',
        '旧 Worker 与手动重试竞争时，最终产物只来自新 execution',
    ),
    RiskCase(
        'R16',
        'SSE',
        "tests.test_ai_assistant.test_http_integration.HttpIntegrationTest"
        ".test_stream_attachment_emits_business_events_and_terminal_over_http",
        'regular',
        '真实 HTTP SSE 输出业务事件和 platform.stream_end',
    ),
    RiskCase(
        'R17',
        'SSE',
        "tests.test_ai_assistant.test_http_integration.HttpIntegrationTest"
        ".test_last_event_id_filters_consumed_event_over_http",
        'regular',
        'HTTP Last-Event-ID 游标过滤已消费事件；不覆盖浏览器断开生命周期',
    ),
    RiskCase(
        'R18',
        'SSE',
        "tests.test_ai_assistant.test_http_integration.HttpIntegrationTest"
        ".test_stream_retry_resets_old_execution_and_rebuilds_snapshot",
        'regular',
        '切流后旧连接收到 reset，新 snapshot 独立重建',
    ),
    RiskCase(
        'R19',
        'SSE',
        "tests.test_ai_assistant.test_stream_resources.AttachmentStreamIterationTest"
        ".test_iter_events_closes_after_terminal_event",
        'regular',
        '读到 terminal 后 SSE 迭代必须结束',
    ),
    RiskCase(
        'R20',
        '稳定性',
        "tests.test_ai_assistant.special.test_stream_concurrency.StreamIdleHttpSpecialTest"
        ".test_idle_http_stream_closes_after_heartbeat",
        'special',
        '无业务事件的 PROCESSING 流在空闲超时后先心跳再断开',
    ),
    RiskCase(
        'R21',
        '隔离',
        'tests.test_ai_assistant.test_message_resources.MessageResourceTest.test_cross_user_resources_are_hidden',
        'regular',
        '跨用户消息和会话对当前用户不可见',
    ),
    RiskCase(
        'R22',
        '隔离',
        "tests.test_ai_assistant.special.test_stream_concurrency.StreamConcurrencySpecialTest"
        ".test_soft_deleted_conversation_hides_user_apis_but_task_can_finish",
        'special',
        '软删除后内部任务可收敛，用户接口不再暴露数据',
    ),
    RiskCase(
        'R23',
        '并发',
        "tests.test_ai_assistant.special.test_stream_concurrency.StreamConcurrencySpecialTest"
        ".test_two_consumers_read_the_same_sequence_and_terminal",
        'special',
        '两个消费者读到同一业务序列和 terminal，不是竞争消费',
    ),
    RiskCase(
        'R24',
        '并发',
        "tests.test_ai_assistant.special.test_stream_concurrency.StreamConcurrencySpecialTest"
        ".test_concurrent_attachments_are_isolated_and_one_failure_does_not_affect_others",
        'special',
        '并发附件 execution/Redis key 唯一，单个失败不影响其他附件',
    ),
    RiskCase(
        'R25',
        '容量',
        "tests.test_ai_assistant.special.test_stream_capacity.StreamCapacitySpecialTest"
        ".test_max_event_bytes_equal_and_over_by_one",
        'special',
        '单事件刚好等于上限 COMPLETE，超过 1 字节 TRUNCATED 且任务仍成功',
    ),
    RiskCase(
        'R26',
        '容量',
        "tests.test_ai_assistant.special.test_stream_capacity.StreamCapacitySpecialTest"
        ".test_max_events_equal_and_over_by_one",
        'special',
        '事件条数刚好等于上限 COMPLETE，超过 1 条后归档截断、Redis 仍可继续',
    ),
    RiskCase(
        'R27',
        '容量',
        "tests.test_ai_assistant.special.test_stream_capacity.StreamCapacitySpecialTest"
        ".test_redis_max_bytes_equal_and_over_by_one",
        'special',
        'Redis 字节刚好等于上限仍写入，超过 1 字节 DEGRADED 但归档继续',
    ),
    RiskCase(
        'R28',
        '容量',
        "tests.test_ai_assistant.special.test_stream_capacity.StreamCapacitySpecialTest"
        ".test_archive_max_bytes_equal_and_over_by_one",
        'special',
        '归档字节刚好等于上限 COMPLETE，超过 1 字节 TRUNCATED 且最终产物完整',
    ),
    RiskCase(
        'R29',
        '反馈',
        "tests.test_ai_assistant.test_feedback_resources.FeedbackResourceTest"
        ".test_cross_user_and_soft_deleted_sources_are_hidden",
        'regular',
        '跨用户和软删除来源不能被反馈接口读写',
    ),
    RiskCase(
        'R30',
        '编辑',
        "tests.test_ai_assistant.test_attachment_resources.AttachmentResourceTest"
        ".test_update_supports_title_and_editable_ai_analysis_output",
        'regular',
        '仅允许编辑公开产物字段，不暴露内部快照',
    ),
    RiskCase(
        'R31',
        '导出',
        "tests.test_ai_assistant.test_attachment_resources.AttachmentResourceTest"
        ".test_export_resource_returns_raw_file_response_through_request_and_viewset",
        'regular',
        '导出走原始文件响应，不把内部字段写进 HTTP 信封',
    ),
    RiskCase(
        'R32',
        '内部字段',
        "tests.test_ai_assistant.test_attachment_resources.AttachmentResourceTest"
        ".test_create_sync_attachment_returns_success_without_internal_fields",
        'regular',
        '附件创建响应不含 task_id/context_data/stream_config',
    ),
    RiskCase(
        'R33',
        '环境',
        "tests.test_ai_assistant.special.test_environment.SpecialEnvironmentTest"
        ".test_real_mysql_redis_and_rabbitmq_are_available",
        'special',
        '专项门禁必须连上真实 MySQL 5.7、Redis 和 RabbitMQ',
    ),
    RiskCase(
        "R34",
        "SSE实时性",
        "tests.test_ai_assistant.special.test_sse_e2e.GunicornSSESpecialTest"
        ".test_first_event_arrives_before_task_finishes",
        "special",
        "Gunicorn/gevent 真实 socket 在任务终态前下发首条业务事件",
    ),
    RiskCase(
        "R35",
        "SSE续传",
        "tests.test_ai_assistant.special.test_sse_e2e.GunicornSSESpecialTest"
        ".test_last_event_id_resumes_without_replaying_consumed_event",
        "special",
        "客户端断开后按 Last-Event-ID 续传，不重放已消费事件",
    ),
    RiskCase(
        "R36",
        "SSE切流",
        "tests.test_ai_assistant.special.test_sse_e2e.GunicornSSESpecialTest"
        ".test_retry_resets_live_old_connection_and_new_stream_completes",
        "special",
        "Celery 重试使旧连接实时 reset，新 execution 独立完成",
    ),
)
