import { describe, expect, it } from 'vitest';

import type { AiConversationSummary } from '@model/ai-assistant/types';

import {
  analysisSuccessTotal,
  messageAttachmentListParams,
  resolveSessionReportsAllLoaded,
  sessionReportListParams,
} from '@views/sec-chat/utils/report-session-count';

const summary = (success?: number): AiConversationSummary => ({
  uid: 'conv-1',
  title: '会话',
  attachment_counts_by_type: { AI_ANALYSIS: 12 },
  attachment_count: 20,
  ...(typeof success === 'number'
    ? { attachment_counts_by_type_and_status: { AI_ANALYSIS: { SUCCESS: success, FAILED: 2, PROCESSING: 1 } } }
    : {}),
});

describe('报告列表成功数与按 UID 查询', () => {
  it('分组数字只取 AI_ANALYSIS 的 SUCCESS，不用类型总数', () => {
    expect(analysisSuccessTotal(summary(8))).toBe(8);
    expect(analysisSuccessTotal(summary(0))).toBe(0);
  });

  it('状态计数字段缺失时不回退到含失败的类型总数', () => {
    expect(analysisSuccessTotal(summary())).toBeNull();
  });

  it('成功数已知时用它判断是否已加载全部', () => {
    expect(resolveSessionReportsAllLoaded(10, 10, 10)).toBe(true);
    expect(resolveSessionReportsAllLoaded(10, 15, 10)).toBe(false);
  });

  it('成功数缺失时仍按不满一页视为全部', () => {
    expect(resolveSessionReportsAllLoaded(9, null, 10)).toBe(true);
    expect(resolveSessionReportsAllLoaded(10, null, 10)).toBe(false);
  });

  it('按会话拉报告不带 Scope', () => {
    expect(sessionReportListParams('conv-1', 10)).toEqual({
      conversation_uid: 'conv-1',
      attachment_type: 'AI_ANALYSIS',
      status: 'SUCCESS',
      limit: 10,
    });
    expect(sessionReportListParams('conv-1')).not.toHaveProperty('scope_type');
    expect(sessionReportListParams('conv-1')).not.toHaveProperty('limit');
  });

  it('按来源消息拉附件不带 Scope', () => {
    expect(messageAttachmentListParams('msg-1')).toEqual({
      source_message_uid: 'msg-1',
      sort: '-created_at',
    });
    expect(messageAttachmentListParams('msg-1')).not.toHaveProperty('scope_type');
  });
});
