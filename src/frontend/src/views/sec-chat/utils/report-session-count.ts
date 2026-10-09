import type { AiConversationSummary } from '@model/ai-assistant/types';

/**
 * 分组数字与成功报告列表对齐，只读 AI_ANALYSIS.SUCCESS。
 * 新字段缺失时返回 null，调用方改用已加载条数。
 */
export const analysisSuccessTotal = (item: AiConversationSummary): number | null => {
  const success = item.attachment_counts_by_type_and_status?.AI_ANALYSIS?.SUCCESS;
  return typeof success === 'number' ? success : null;
};

/** 有成功数时按它判断是否还有更多；否则仍用「不满一页即全部」 */
export const resolveSessionReportsAllLoaded = (
  loadedCount: number,
  reportTotal: number | null,
  pageSize: number,
) => (
  reportTotal === null ? loadedCount < pageSize : loadedCount >= reportTotal
);

/** 按会话拉报告：只传会话 UID，不重复会话 Scope */
export const sessionReportListParams = (conversationUid: string, limit?: number) => ({
  conversation_uid: conversationUid,
  attachment_type: 'AI_ANALYSIS' as const,
  status: 'SUCCESS' as const,
  ...(limit ? { limit } : {}),
});

/** 按来源消息拉附件：只传消息 UID，不重复会话 Scope */
export const messageAttachmentListParams = (messageUid: string) => ({
  source_message_uid: messageUid,
  sort: '-created_at' as const,
});
