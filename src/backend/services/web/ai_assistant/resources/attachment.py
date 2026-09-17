from django.http import HttpResponse
from django.utils.http import content_disposition_header
from django.utils.translation import gettext_lazy

from core.models import get_request_username
from services.web.ai_assistant.resources.conversation import AIAssistantResource
from services.web.ai_assistant.serializers.attachment import (
    AttachmentCreateRequestSerializer,
    AttachmentDetailRequestSerializer,
    AttachmentExportRequestSerializer,
    AttachmentListItemSerializer,
    AttachmentListRequestSerializer,
    AttachmentResponseSerializer,
    AttachmentUpdateRequestSerializer,
)
from services.web.ai_assistant.services.attachment import AttachmentService


class CreateAttachment(AIAssistantResource):
    """从当前用户可见的成功消息创建附件，返回附件对象。

    message_uid 使用路径中的来源消息 UID，不放入 body。以下示例均为请求 body，
    input_data 按外层 attachment_type 选择对应 schema，不是把 oneOf 中各类型字段合并。
    程序统计和 AI 统计的来源必须是成功的 LOG_SEARCH；同一消息可以创建多个附件。

    ### Case 1：程序统计通用字段

    ```json
    {
      "attachment_type": "FIELD_STATISTICS",
      "input_data": {
        "field": {
          "raw_name": "username",
          "keys": []
        },
        "top_n": 100,
        "interval": "AUTO"
      }
    }
    ```

    ### Case 2：程序统计拓展字段

    ```json
    {
      "attachment_type": "FIELD_STATISTICS",
      "input_data": {
        "field": {
          "raw_name": "extend_data",
          "keys": [
            "duration"
          ]
        },
        "top_n": 20,
        "interval": "HOUR"
      }
    }
    ```

    字段路径应使用字段探索返回的引用；duration 仅为示意，不保证业务系统存在该字段。
    无需提交统计类型，后端按全范围真实类型决定是否返回数值摘要；field_type 不能强制转换。
    top_n 默认 100，OTHER/MISSING 不占名额；显式时间粒度超预算报错，AUTO 可自动选择。
    查询范围固定为来源消息的完整条件，不能在 input_data 中覆盖 condition、用户或租户。

    ### Case 3：AI 自定义统计

    ```json
    {
      "attachment_type": "AI_STATISTICS",
      "input_data": {
        "instruction": "统计各操作类型的数量和按小时变化趋势，生成图表并说明差异。"
      }
    }
    ```

    instruction 必填且不能为纯空白。来源检索仅提供初始上下文，Agent 可调整实际查询范围。
    最终产物是 output_data.content 原文，后端不约定 ECharts 格式，也不保证该文本为 JSON。

    ### 返回后如何处理

    同步执行返回 SUCCESS；异步通常返回 PROCESSING，也可能已经进入终态，始终按 status 判断。
    保存附件 uid 和 source_message_uid；所有异步附件均可轮询附件详情到 SUCCESS/FAILED。
    is_stream=true 仅表示可选的过程订阅。两种统计均不支持产物编辑和后端导出，失败可人工重试。
    创建请求结果不确定时，先按来源消息查询附件列表核对，避免重复创建。
    """

    name = gettext_lazy("创建附件")
    RequestSerializer = AttachmentCreateRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data["source_message_uid"] = str(request_data.pop("message_uid"))
        attachment = AttachmentService(user=get_request_username()).create(**request_data)
        attachment.refresh_from_db()
        return attachment


class ListAttachments(AIAssistantResource):
    """查询当前用户可见的附件摘要，用于卡片恢复或产物列表；不分页。

    ### Case：恢复某次检索的统计附件

    `GET /api/v1/ai_assistant/attachments/`，查询参数：
    `source_message_uid={searchMessageUid}&attachment_type=FIELD_STATISTICS,AI_STATISTICS`

    类型和状态支持单值、逗号分隔或重复参数；仅查看成功结果时追加 status=SUCCESS，
    需要恢复生成中任务时不要固定成功状态。默认返回全部匹配项，limit 可限制数量。
    列表包含来源消息与会话摘要，不包含 input_data/output_data；点击某项后用 uid 查询附件详情。
    同一来源可能有多份附件，按附件 UID 区分，不能只按来源消息覆盖结果。
    """

    name = gettext_lazy("获取附件列表")
    RequestSerializer = AttachmentListRequestSerializer
    ResponseSerializer = AttachmentListItemSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        query = dict(validated_request_data)
        attachment_types = query.pop("attachment_type", None)
        statuses = query.pop("status", None)
        conversation_uid = query.get("conversation_uid")
        source_message_uid = query.get("source_message_uid")
        query.update(
            attachment_types=attachment_types,
            statuses=statuses,
            conversation_uid=str(conversation_uid) if conversation_uid else None,
            source_message_uid=str(source_message_uid) if source_message_uid else None,
        )
        return AttachmentService(user=get_request_username()).list(**query)


class GetAttachment(AIAssistantResource):
    """读取附件状态与完整产物，也是所有异步附件的轮询入口。

    ### Case 1：只看最终统计结果

    持续 GET 当前附件，PROCESSING 时继续等待；SUCCESS 读取 output_data；FAILED 展示
    error_code/error_message 并停止轮询。即使 is_stream=true，也无需连接 SSE 或取得 execution_id。
    一次读取失败仅重试读取，不重新创建附件。任务 ID、内部上下文和事件归档不在详情中暴露。

    ### Case 2：按附件类型读取成功产物

    - FIELD_STATISTICS：output_data 含 overview、distribution、time_series、numeric_summary 等。
      用 group_id 关联分布与时序，counts 与 bucket_starts 一一对应；OTHER/MISSING 按 kind 判断。
      比例是 0–1 小数，无数据时可为 null；空结果是成功空态。数值摘要的 median 为近似值。
    - AI_STATISTICS：output_data 为 {"content":"最终消息原文"}，图表协议由前端与 Agent 约定。
      解析失败可展示原文，不代表附件执行失败。
    - AI_ANALYSIS：读取 output_data.markdown；不可将此字段用于 AI_STATISTICS。

    output_data 的 oneOf 由 attachment_type 决定；仅在 SUCCESS 时将其作为有效产物渲染。
    SSE 流结束后也应读取本接口确定业务终态，而不是拼接中间事件作为最终产物。
    """

    name = gettext_lazy("获取附件详情")
    RequestSerializer = AttachmentDetailRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        return AttachmentService(user=get_request_username()).get(
            attachment_uid=str(validated_request_data["attachment_uid"]),
        )


class ExportAttachment(AIAssistantResource):
    """实时导出成功 Attachment；格式读取详情 export_formats，文件不会被平台留存。"""

    name = gettext_lazy("导出附件")
    RequestSerializer = AttachmentExportRequestSerializer

    def perform_request(self, validated_request_data):
        result = AttachmentService(user=get_request_username()).export(
            attachment_uid=str(validated_request_data["attachment_uid"]),
            export_format=validated_request_data["export_format"],
        )
        response = HttpResponse(result.content, content_type=result.content_type)
        response["Content-Disposition"] = content_disposition_header(
            as_attachment=True,
            filename=result.filename,
        )
        return response


class UpdateAttachment(AIAssistantResource):
    """修改附件标题或开放编辑能力的成功产物。

    ### Case：修改统计卡片标题

    ```json
    {
      "title": "登录操作统计"
    }
    ```

    attachment_uid 通过路径传入。标题不受执行状态限制；FIELD_STATISTICS 和 AI_STATISTICS
    仅支持修改标题，不支持提交 output_data，也不能修改 input_data。
    改字段、统计选项或 AI 需求时，从来源消息创建新附件。
    对于支持正文编辑的其他类型，output_data 是完整替换，且只允许 SUCCESS 状态编辑。
    """

    name = gettext_lazy("编辑附件")
    RequestSerializer = AttachmentUpdateRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data["attachment_uid"] = str(request_data["attachment_uid"])
        return AttachmentService(user=get_request_username()).update(**request_data)


class RetryAttachment(AIAssistantResource):
    """原样重试 FAILED 异步附件，复用原 UID 和输入快照，不创建新附件。

    ### Case：统计失败后重试

    `POST /api/v1/ai_assistant/attachments/{attachment_uid}/retry/`，无需业务请求体。
    FIELD_STATISTICS 和 AI_STATISTICS 都支持人工重试，没有 supports_retry 开关；
    非 FAILED 状态或同步类型不能重试，执行仍需通过权限和来源有效性校验。

    返回附件对象后按 status 处理。仅轮询时继续查询同一 UID，无需读取执行标识。
    使用 SSE 时先关闭旧流，等待新的 execution_id 后恢复；排队期间旧快照不代表新执行。
    修改输入要求属于创建新附件，不通过本接口完成。
    """

    name = gettext_lazy("重试附件")
    RequestSerializer = AttachmentDetailRequestSerializer
    ResponseSerializer = AttachmentResponseSerializer

    def perform_request(self, validated_request_data):
        attachment = AttachmentService(user=get_request_username()).retry(
            attachment_uid=str(validated_request_data["attachment_uid"]),
        )
        attachment.refresh_from_db()
        return attachment
