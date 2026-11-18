import type { AiSearchCondition, AiStatisticsInputData } from '@model/ai-assistant/types';

export interface StatisticsRetryPayload {
  type: 'field' | 'custom';
  prompt?: string;
}

const isSearchCondition = (value: unknown): value is AiSearchCondition => (
  Boolean(value)
    && typeof value === 'object'
    && !Array.isArray(value)
);

export interface StatisticsRetryTarget {
  uid: string;
  inputData?: { condition?: unknown } | null;
}

export type StatisticsSubmitDecision = {
  action: 'retry';
  attachmentUid: string;
  inputData: AiStatisticsInputData;
} | {
  action: 'create';
};

/** 自定义重新统计走原附件 retry；字段统计和新开统计都走新建 */
export const resolveStatisticsSubmit = (
  retryTarget: StatisticsRetryTarget | null | undefined,
  payload: StatisticsRetryPayload,
): StatisticsSubmitDecision => {
  if (!retryTarget?.uid || payload.type !== 'custom') return { action: 'create' };
  return {
    action: 'retry',
    attachmentUid: retryTarget.uid,
    inputData: buildStatisticsRetryInput(retryTarget.inputData, payload),
  };
};

/**
 * 自定义重新统计的完整 input_data。
 * 提示词用当前输入；原附件有独立 condition 时原样带回。
 */
export const buildStatisticsRetryInput = (
  original: { condition?: unknown } | null | undefined,
  payload: Pick<StatisticsRetryPayload, 'prompt'>,
): AiStatisticsInputData => {
  const conditionSource = original?.condition;
  const condition = isSearchCondition(conditionSource) ? conditionSource : undefined;
  return {
    ...(condition ? { condition } : {}),
    instruction: payload.prompt || '',
  };
};
