export const BATCH_SYNC_LIMIT = 500;

export const BATCH_ACTION_ORDER = ['close', 'transfer', 'package', 'misreport', 'unmisreport'] as const;

export type BatchActionId = typeof BATCH_ACTION_ORDER[number] | 'whitelist';
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

const PREVIEW_KEY_BY_ACTION: Record<Exclude<BatchActionId, 'whitelist'>, PreviewActionKey> = {
  close: 'close',
  transfer: 'trans',
  package: 'auto_process',
  misreport: 'misreport',
  unmisreport: 'unmisreport',
};

export const REASON_NONE = '请至少选择 1 条风险单';
export const REASON_UNLOADED = '所选风险包含未加载数据，暂无法批量处理';
export const REASON_LIMIT = '所选风险数量超过上限：500，请缩小范围';
export const REASON_UNSUPPORTED = '所选风险无法批量处理';
export const REASON_APPROVING = '加白审批中，无法批量处理';
export const REASON_MIXED = '所选风险状态不同，仅支持标记误报';
export const REASON_STRATEGY = '所选风险不属于同一审计策略，无法批量加白';
export const REASON_CLOSED_WHITELIST = '已关单的风险不能单独加白，请通过标记误报同时加白';

const CONFIRM_STATUSES = new Set(['await_confirm', 'pending_confirm']);

const normalizeStatus = (status: string) => (
  CONFIRM_STATUSES.has(status) ? 'await_confirm' : status
);

const strategyIdsOf = (rows: BatchRiskRow[]) => {
  const ids = new Set<string>();
  rows.forEach((row) => {
    if (row.strategy_id === null || row.strategy_id === undefined || row.strategy_id === '') {
      return;
    }
    ids.add(String(row.strategy_id));
  });
  return ids;
};

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
  if (rows.some(row => row.status === 'whitelist_approving')) {
    return createDisabledAvailability(REASON_APPROVING);
  }
  const rowStrategyIds = strategyIdsOf(rows);
  const previewStrategyId = normalizeIdentity(preview.unique_strategy_id);
  const strategyId = previewStrategyId || (rowStrategyIds.size === 1 ? [...rowStrategyIds][0] : '');
  const strategyUnique = Boolean(strategyId) && rowStrategyIds.size <= 1;
  const statuses = new Set(rows.map(row => normalizeStatus(String(row.status || ''))));
  const mixed = statuses.size > 1;
  const allClosed = rows.length > 0 && rows.every(row => row.status === 'closed');
  let actions: BatchActionState[] = BATCH_ACTION_ORDER.map((id) => {
    const item = preview.actions?.[PREVIEW_KEY_BY_ACTION[id]];
    const enabled = Boolean(item?.enabled);
    return {
      id,
      enabled,
      reason: enabled ? '' : (item?.disabled_reason || ''),
    };
  });
  if (mixed) {
    actions = actions.map(action => (
      action.id === 'misreport'
        ? { ...action, enabled: true, reason: '' }
        : { ...action, enabled: false, reason: REASON_MIXED }
    ));
  }
  let whitelistReason = '';
  const whitelistEnabled = strategyUnique && !mixed && !allClosed;
  if (!whitelistEnabled) {
    if (mixed) {
      whitelistReason = REASON_MIXED;
    } else if (!strategyUnique) {
      whitelistReason = REASON_STRATEGY;
    } else if (allClosed) {
      whitelistReason = REASON_CLOSED_WHITELIST;
    }
  }
  actions = [...actions, { id: 'whitelist', enabled: whitelistEnabled, reason: whitelistReason }];
  const enabled = mixed ? true : Boolean(preview.batch_enabled);
  let dialog: BatchDialogKind | '' = '';
  if (enabled) {
    dialog = !mixed && preview.actions?.confirm?.enabled ? 'confirm' : 'process';
  }
  return {
    enabled,
    reason: enabled ? '' : (preview.batch_disabled_reason || REASON_UNSUPPORTED),
    dialog,
    actions,
    strategyUnique,
    strategyId,
    sceneId: normalizeIdentity(preview.scene_id),
    allClosed,
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

export const defaultBatchAction = (actions: BatchActionState[]) => {
  const preferred = BATCH_ACTION_ORDER.find(id => actions.find(action => action.id === id)?.enabled);
  if (preferred) {
    return preferred;
  }
  return actions.find(action => action.enabled)?.id || '';
};
