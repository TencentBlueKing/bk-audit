import RiskManageService from '@service/risk-manage';

import type { BatchActionId, BatchPreview } from './evaluate';

export interface BatchReceipt {
  success_count: number;
  failed: Array<{ risk_id: string; reason: string }>;
}

export interface PackageParamValue {
  field: string;
  value: string | string[];
}

const normalizeReceipt = (riskIds: string[], data: unknown): BatchReceipt => {
  const payload = (data && typeof data === 'object' ? data : {}) as Partial<BatchReceipt>;
  const failed = Array.isArray(payload.failed) ? payload.failed : [];
  return {
    success_count: Number(payload.success_count ?? (riskIds.length - failed.length)),
    failed,
  };
};

export const fetchBatchPreview = (riskIds: string[]): Promise<BatchPreview> => (
  RiskManageService.previewBatchActions({ risk_ids: riskIds })
);

const requestBatchProcess = (input: {
  action: BatchActionId;
  riskIds: string[];
  description: string;
  operators?: string[];
  paId?: string | number;
  paParams?: Record<string, PackageParamValue>;
  autoCloseRisk?: boolean;
}) => {
  const { action, riskIds, description } = input;
  const requests: Record<BatchActionId, () => Promise<unknown>> = {
    close: () => RiskManageService.bulkCloseRisk({ risk_ids: riskIds, description }),
    // $OPERATOR / $OPERATOR_LEADER 等人员变量也按 user 传，由后端展开
    transfer: () => RiskManageService.batchTransRisk({
      risk_ids: riskIds,
      new_operators: (input.operators || [])
        .filter(Boolean)
        .map(value => ({ type: 'user' as const, value })),
      description,
    }),
    package: () => RiskManageService.bulkAutoProcessRisk({
      risk_ids: riskIds,
      pa_id: Number(input.paId),
      pa_params: input.paParams || {},
      auto_close_risk: Boolean(input.autoCloseRisk),
    }),
    misreport: () => RiskManageService.bulkMisreportRisk({ risk_ids: riskIds, description }),
  };
  return requests[action]();
};

export const submitBatchProcess = async (input: Parameters<typeof requestBatchProcess>[0]): Promise<BatchReceipt> => {
  const data = await requestBatchProcess(input);
  return normalizeReceipt(input.riskIds, data);
};

export const submitBatchConfirm = async (input: {
  result: 'confirm' | 'misreport';
  riskIds: string[];
  description: string;
}): Promise<BatchReceipt> => {
  const params = { risk_ids: input.riskIds, description: input.description };
  const data = input.result === 'misreport'
    ? await RiskManageService.bulkMisreportRisk(params)
    : await RiskManageService.batchConfirmRisk(params);
  return normalizeReceipt(input.riskIds, data);
};
