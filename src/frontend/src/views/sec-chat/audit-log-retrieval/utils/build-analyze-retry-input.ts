import type { AiAnalysisInputData, AiSearchCondition } from '@model/ai-assistant/types';

export interface AnalyzeRetryPayload {
  type: 'recommend' | 'custom';
  prompt?: string;
}

const isSearchCondition = (value: unknown): value is AiSearchCondition => (
  Boolean(value)
  && typeof value === 'object'
  && !Array.isArray(value)
);

export interface AnalyzeRetryTarget {
  uid: string;
  inputData?: { condition?: unknown } | null;
}

export type AnalyzeSubmitDecision = {
  action: 'retry';
  attachmentUid: string;
  inputData: AiAnalysisInputData;
} | {
  action: 'create';
};

/** 自定义重新分析走原附件 retry；推荐分析和新开分析都走新建 */
export const resolveAnalyzeSubmit = (
  retryTarget: AnalyzeRetryTarget | null | undefined,
  payload: AnalyzeRetryPayload,
): AnalyzeSubmitDecision => {
  if (!retryTarget?.uid || payload.type !== 'custom') return { action: 'create' };
  return {
    action: 'retry',
    attachmentUid: retryTarget.uid,
    inputData: buildAnalyzeRetryInput(retryTarget.inputData, payload),
  };
};

/**
 * 自定义重新分析的完整 input_data。
 * 提示词用当前输入；原附件有独立 condition 时原样带回。
 */
export const buildAnalyzeRetryInput = (
  original: { condition?: unknown } | null | undefined,
  payload: Pick<AnalyzeRetryPayload, 'prompt'>,
): AiAnalysisInputData => {
  const conditionSource = original?.condition;
  const condition = isSearchCondition(conditionSource) ? conditionSource : undefined;
  return {
    ...(condition ? { condition } : {}),
    analysis_mode: 'CUSTOM',
    instruction: payload.prompt || '',
  };
};
