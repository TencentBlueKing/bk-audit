export const BATCH_SYNC_LIMIT = 500;
export const PACKAGE_SYNC_LIMIT = 100;

export const BATCH_ACTION_ORDER = ['close', 'transfer', 'package', 'misreport'] as const;

export type BatchActionId = typeof BATCH_ACTION_ORDER[number];
export type BatchDialogKind = 'confirm' | 'process';

export interface BatchRiskRow {
  risk_id: string | number;
  status: string;
  strategy_id?: string | number | null;
  scene_id?: string | number | null;
  permission?: Record<string, boolean>;
  current_operator?: string[] | string;
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
  sceneUnique: boolean;
  sceneId: string;
  sceneIds: string[];
  strategyId: string;
}

const CONFIRM_STATUS = 'pending_confirm';
const DEAL_STATUSES = new Set(['await_deal', 'processing']);
const CLOSED_STATUS = 'closed';
const BLOCK_STATUSES = new Set(['new', 'stand_by']);
const AUTO_STATUSES = new Set(['for_approve', 'auto_process']);
const MISREPORT_STATUSES = new Set([CONFIRM_STATUS, ...DEAL_STATUSES, CLOSED_STATUS]);

const REASON_NONE = '至少选择一条风险单';
const REASON_UNLOADED = '所选风险包含未加载数据，暂无法批量处理';
const REASON_UNSUPPORTED = '所选风险无法批量处理';
const REASON_AUTO = '自动化处理规则正在处理流程中，无法批量处理';
const REASON_LIMIT = '一次最多处理 500 条风险';
const REASON_CLOSED_ONLY_MISREPORT = '已关单风险仅支持标记误报';
const REASON_CLOSED_NO_PACKAGE = '已关单风险不支持处理套餐';
const REASON_STRATEGY = '批量处理仅适用于同一审计策略生成的风险单';
const REASON_MIXED = '所选风险状态不同，仅支持标记误报。';
const REASON_PACKAGE_LIMIT = '处理套餐一次最多 100 条';

const normalizeStatus = (status: string) => (
  status === 'await_confirm' ? CONFIRM_STATUS : status
);

const normalizeIdentity = (value: string | number | null | undefined) => {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value).trim();
};

const resolveUniqueIdentity = (values: Array<string | number | null | undefined>) => {
  const normalized = values.map(normalizeIdentity);
  if (normalized.length <= 1) {
    return { unique: true, value: normalized[0] || '' };
  }
  const first = normalized[0];
  if (!first || normalized.some(item => item !== first)) {
    return { unique: false, value: '' };
  }
  return { unique: true, value: first };
};

const emptyActions = (): BatchActionState[] => BATCH_ACTION_ORDER.map(id => ({
  id,
  enabled: false,
  reason: '',
}));

export const evaluateBatchSelection = (
  rows: BatchRiskRow[],
  options: { count: number; incomplete: boolean },
): BatchAvailability => {
  const actions = emptyActions();
  const base: BatchAvailability = {
    enabled: false,
    reason: '',
    dialog: '',
    actions,
    strategyUnique: false,
    sceneUnique: false,
    sceneId: '',
    sceneIds: [],
    strategyId: '',
  };

  if (options.count <= 0) {
    return { ...base, reason: REASON_NONE };
  }
  if (options.incomplete || rows.length !== options.count) {
    return { ...base, reason: REASON_UNLOADED };
  }

  const statuses = rows.map(row => normalizeStatus(row.status || ''));
  if (statuses.some(status => BLOCK_STATUSES.has(status))) {
    return { ...base, reason: REASON_UNSUPPORTED };
  }
  if (statuses.some(status => AUTO_STATUSES.has(status))) {
    return { ...base, reason: REASON_AUTO };
  }
  if (options.count > BATCH_SYNC_LIMIT) {
    return { ...base, reason: REASON_LIMIT };
  }

  const strategy = resolveUniqueIdentity(rows.map(row => row.strategy_id));
  const scene = resolveUniqueIdentity(rows.map(row => row.scene_id));
  const sceneIds = [...new Set(rows.map(row => normalizeIdentity(row.scene_id)).filter(Boolean))];
  const allConfirm = statuses.every(status => status === CONFIRM_STATUS);
  const allDeal = statuses.every(status => DEAL_STATUSES.has(status));
  const allClosed = statuses.every(status => status === CLOSED_STATUS);
  const misreportEnabled = statuses.every(status => MISREPORT_STATUSES.has(status));
  const hasClosed = statuses.some(status => status === CLOSED_STATUS);
  const mixedMisreportOnly = misreportEnabled && !allDeal && !allConfirm;

  let statusReason = REASON_UNSUPPORTED;
  if (mixedMisreportOnly && allClosed) {
    statusReason = REASON_CLOSED_ONLY_MISREPORT;
  } else if (mixedMisreportOnly) {
    statusReason = REASON_MIXED;
  }

  const setAction = (id: BatchActionId, enabled: boolean, reason: string) => {
    const action = actions.find(item => item.id === id);
    if (action) {
      action.enabled = enabled;
      action.reason = enabled ? '' : reason;
    }
  };

  const mixedReason = mixedMisreportOnly && !allClosed ? REASON_MIXED : '';
  const closedActionReason = mixedReason || (hasClosed ? REASON_CLOSED_ONLY_MISREPORT : statusReason);
  setAction('close', allDeal, closedActionReason);
  setAction('transfer', allDeal, closedActionReason);

  let packageReason = mixedReason || statusReason;
  if (!mixedReason && !allDeal && hasClosed) {
    packageReason = REASON_CLOSED_NO_PACKAGE;
  } else if (allDeal && !strategy.unique) {
    packageReason = REASON_STRATEGY;
  } else if (allDeal && options.count > PACKAGE_SYNC_LIMIT) {
    packageReason = REASON_PACKAGE_LIMIT;
  }
  const packageEnabled = allDeal
    && strategy.unique
    && options.count <= PACKAGE_SYNC_LIMIT;
  setAction('package', packageEnabled, packageReason);
  setAction('misreport', misreportEnabled, REASON_UNSUPPORTED);

  const enabled = allConfirm || actions.some(action => action.enabled);
  let dialog: BatchDialogKind | '' = '';
  if (enabled && allConfirm) {
    dialog = 'confirm';
  } else if (enabled) {
    dialog = 'process';
  }
  return {
    enabled,
    reason: enabled ? '' : REASON_UNSUPPORTED,
    dialog,
    actions,
    strategyUnique: strategy.unique,
    sceneUnique: scene.unique,
    sceneId: scene.value,
    sceneIds,
    strategyId: strategy.value,
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
