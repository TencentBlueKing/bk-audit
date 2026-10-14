import RiskManageService from '@service/risk-manage';

import {
  type BatchActionId,
  type BatchPreview,
  type BatchRiskRow,
  mockBatchPreview,
} from './evaluate';

/**
 * 后端批量接口（preview / bulk_close / bulk_auto_process / bulk_misreport 及改造后的 bulk_trans、batch_confirm）
 * 未上线前为 true：能力检查走本地规则，提交不发请求直接返回全部成功。联调时改为 false。
 */
const BATCH_API_MOCK = true;

export interface BatchReceipt {
  success_count: number;
  failed: Array<{ risk_id: string; reason: string }>;
}

export interface PackageParamValue {
  field: string;
  value: string | string[];
}

const emptyReceipt = (riskIds: string[]): BatchReceipt => ({
  success_count: riskIds.length,
  failed: [],
});

const normalizeReceipt = (riskIds: string[], data: unknown): BatchReceipt => {
  if (!data || typeof data !== 'object') {
    return emptyReceipt(riskIds);
  }
  const payload = data as { success_count?: number; failed?: BatchReceipt['failed'] };
  if (!Array.isArray(payload.failed)) {
    return emptyReceipt(riskIds);
  }
  return {
    success_count: Number(payload.success_count ?? (riskIds.length - payload.failed.length)),
    failed: payload.failed,
  };
};

const toTransferTargets = (operators: string[]) => operators
  .filter(Boolean)
  .map(value => ({
    type: value.startsWith('$') ? 'field' as const : 'user' as const,
    value,
  }));

export const fetchBatchPreview = async (rows: BatchRiskRow[]): Promise<BatchPreview> => {
  if (BATCH_API_MOCK) {
    return mockBatchPreview(rows);
  }
  return RiskManageService.previewBatchActions({
    risk_ids: rows.map(row => String(row.risk_id)),
  });
};

const requestBatchProcess = (input: {
  action: BatchActionId;
  riskIds: string[];
  description: string;
  operators?: string[];
  paId?: string;
  paParams?: Record<string, PackageParamValue>;
  autoCloseRisk?: boolean;
}) => {
  const { action, riskIds, description } = input;
  const requests: Record<BatchActionId, () => Promise<unknown>> = {
    close: () => RiskManageService.bulkCloseRisk({ risk_ids: riskIds, description }),
    transfer: () => RiskManageService.batchTransRisk({
      risk_ids: riskIds,
      new_operators: toTransferTargets(input.operators || []),
      description,
    }),
    package: () => RiskManageService.bulkAutoProcessRisk({
      risk_ids: riskIds,
      pa_id: input.paId || '',
      pa_params: input.paParams || {},
      auto_close_risk: Boolean(input.autoCloseRisk),
      description,
    }),
    misreport: () => RiskManageService.bulkMisreportRisk({ risk_ids: riskIds, description }),
  };
  return requests[action]();
};

export const submitBatchProcess = async (input: Parameters<typeof requestBatchProcess>[0]): Promise<BatchReceipt> => {
  if (BATCH_API_MOCK) {
    return emptyReceipt(input.riskIds);
  }
  const data = await requestBatchProcess(input);
  return normalizeReceipt(input.riskIds, data);
};

export const submitBatchConfirm = async (input: {
  result: 'confirm' | 'misreport';
  riskIds: string[];
  description: string;
}): Promise<BatchReceipt> => {
  if (BATCH_API_MOCK) {
    return emptyReceipt(input.riskIds);
  }
  const params = { risk_ids: input.riskIds, description: input.description };
  const data = input.result === 'misreport'
    ? await RiskManageService.bulkMisreportRisk(params)
    : await RiskManageService.batchConfirmRisk(params);
  return normalizeReceipt(input.riskIds, data);
};
