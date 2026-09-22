import RiskManageService from '@service/risk-manage';

import type { BatchActionId } from './evaluate';

export interface BatchReceipt {
  success_count: number;
  failed: Array<{ risk_id: string; reason: string }>;
}

export interface TransferTarget {
  type: 'user' | 'field';
  value: string | string[];
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

/**
 * 确认、指定人员转单走现有接口。
 * 关单、套餐、误报，以及「转给单据字段」还没有批量接口，先返回约定回执，联调时替换。
 */
export const submitBatchProcess = async (input: {
  action: BatchActionId;
  riskIds: string[];
  description: string;
  transfer?: TransferTarget;
  paId?: string;
  paParams?: Record<string, PackageParamValue>;
  autoCloseRisk?: boolean;
}): Promise<BatchReceipt> => {
  const { action, riskIds, description, transfer } = input;
  if (action === 'transfer' && transfer?.type === 'user') {
    const operators = Array.isArray(transfer.value) ? transfer.value : [transfer.value];
    const data = await RiskManageService.batchTransRisk({
      risk_ids: riskIds,
      new_operators: operators.filter(Boolean),
      description,
    });
    return normalizeReceipt(riskIds, data);
  }
  return emptyReceipt(riskIds);
};

export const submitBatchConfirm = async (input: {
  result: 'confirm' | 'misreport';
  riskIds: string[];
  description: string;
}): Promise<BatchReceipt> => {
  const data = input.result === 'misreport'
    ? await RiskManageService.batchConfirmAsMisreport({
      risk_ids: input.riskIds,
      description: input.description,
    })
    : await RiskManageService.batchConfirmRisk({
      risk_ids: input.riskIds,
      description: input.description,
    });
  return normalizeReceipt(input.riskIds, data);
};
