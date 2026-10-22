export const BATCH_SYNC_LIMIT = 500;

export const BATCH_ACTION_ORDER = ['close', 'transfer', 'package', 'misreport', 'unmisreport'] as const;

export type BatchActionId = typeof BATCH_ACTION_ORDER[number];
export type BatchDialogKind = 'confirm' | 'process';
export type PreviewActionKey = 'confirm' | 'close' | 'trans' | 'auto_process' | 'misreport' | 'unmisreport';

export interface BatchRiskRow {
  risk_id: string | number;
  status: string;
  strategy_id?: string | number | null;
  scene_id?: string | number | null;
  permission?: Record<string, boolean>;
  current_operator?: string[] | string;
}

export interface BatchPreview {
  batch_enabled: boolean;
  batch_disabled_reason: string;
  actions: Record<PreviewActionKey, { enabled: boolean; disabled_reason: string }>;
  unique_strategy_id?: number | null;
  scene_id?: number | null;
  selected_count?: number;
}

export interface BatchActionState {
  id: BatchActionId;
  enabled: boolean;
  reason: string;
}

export interface BatchAvailability {
  enabled: boolean;
  reason: string;
  dialog: BatchDialogKind | '';
  actions: BatchActionState[];
  strategyUnique: boolean;
  strategyId: string;
  sceneId: string;
  allClosed: boolean;
}

const PREVIEW_KEY_BY_ACTION: Record<BatchActionId, PreviewActionKey> = {
  close: 'close',
  transfer: 'trans',
  package: 'auto_process',
  misreport: 'misreport',
  unmisreport: 'unmisreport',
};

export const REASON_NONE = '请至少选择 1 条风险单';
export const REASON_UNLOADED = '所选风险包含未加载数据，暂无法批量处理';
export const REASON_LIMIT = '所选风险数量超过上限，请缩小范围';
export const REASON_UNSUPPORTED = '所选风险无法批量处理';

const normalizeIdentity = (value: number | null | undefined) => (
  value === null || value === undefined ? '' : String(value)
);

export const createDisabledAvailability = (reason: string): BatchAvailability => ({
  enabled: false,
  reason,
  dialog: '',
  actions: BATCH_ACTION_ORDER.map(id => ({ id, enabled: false, reason: '' })),
  strategyUnique: false,
  strategyId: '',
  sceneId: '',
  allClosed: false,
});

export const toBatchAvailability = (preview: BatchPreview, rows: BatchRiskRow[] = []): BatchAvailability => {
  const strategyId = normalizeIdentity(preview.unique_strategy_id);
  const actions = BATCH_ACTION_ORDER.map((id) => {
    const item = preview.actions?.[PREVIEW_KEY_BY_ACTION[id]];
    const enabled = Boolean(item?.enabled);
    return {
      id,
      enabled,
      reason: enabled ? '' : (item?.disabled_reason || ''),
    };
  });
  const enabled = Boolean(preview.batch_enabled);
  let dialog: BatchDialogKind | '' = '';
  if (enabled) {
    dialog = preview.actions?.confirm?.enabled ? 'confirm' : 'process';
  }
  return {
    enabled,
    reason: enabled ? '' : (preview.batch_disabled_reason || REASON_UNSUPPORTED),
    dialog,
    actions,
    strategyUnique: Boolean(strategyId),
    strategyId,
    sceneId: normalizeIdentity(preview.scene_id),
    allClosed: rows.length > 0 && rows.every(row => row.status === 'closed'),
  };
};

export const hasBatchProcessPermission = (row: BatchRiskRow, username: string) => {
  if (row.permission?.process_risk) {
    return true;
  }
  const operators = Array.isArray(row.current_operator)
    ? row.current_operator
    : String(row.current_operator || '').split(',');
  return operators
    .map(item => item.trim())
    .filter(Boolean)
    .includes(username);
};

export const defaultBatchAction = (actions: BatchActionState[]) => (
  BATCH_ACTION_ORDER.find(id => actions.find(action => action.id === id)?.enabled) || ''
);
