export const BATCH_SYNC_LIMIT = 500;
export const PACKAGE_SYNC_LIMIT = 100;

export const BATCH_ACTION_ORDER = ['close', 'transfer', 'package', 'misreport'] as const;

export type BatchActionId = typeof BATCH_ACTION_ORDER[number];
export type BatchDialogKind = 'confirm' | 'process';
export type PreviewActionKey = 'confirm' | 'close' | 'trans' | 'auto_process' | 'misreport';

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
}

const PREVIEW_ACTION_KEYS: PreviewActionKey[] = ['confirm', 'close', 'trans', 'auto_process', 'misreport'];

const PREVIEW_KEY_BY_ACTION: Record<BatchActionId, PreviewActionKey> = {
  close: 'close',
  transfer: 'trans',
  package: 'auto_process',
  misreport: 'misreport',
};

const STATUS_CAPABILITIES: Record<string, PreviewActionKey[]> = {
  pending_confirm: ['confirm', 'misreport'],
  await_deal: ['close', 'trans', 'auto_process', 'misreport'],
  processing: ['close', 'trans', 'auto_process', 'misreport'],
  closed: ['close'],
};

const DEAL_STATUSES = new Set(['await_deal', 'processing']);
const CLOSED_STATUS = 'closed';
const AUTO_STATUSES = new Set(['for_approve', 'auto_process']);

export const REASON_NONE = '至少选择一条风险单';
export const REASON_UNLOADED = '所选风险包含未加载数据，暂无法批量处理';
export const REASON_LIMIT = '所选风险数量超过上限，请缩小范围';
export const REASON_UNSUPPORTED = '所选风险无法批量处理';
const REASON_AUTO = '所选风险包含自动审批中/套餐处理中，不支持批量处理';
const REASON_EMPTY = '所选风险状态不同，无可用批量操作';
const REASON_MIXED_MISREPORT = '所选风险状态不同，仅支持标记误报。';
const REASON_MIXED_CLOSE = '所选风险状态不同，仅支持人工关单。';
const REASON_CLOSED_ONLY_CLOSE = '已关单风险仅支持人工关单';
const REASON_STRATEGY = '所选风险策略不同，不支持批量处理套餐';
const REASON_PACKAGE_LIMIT = '处理套餐一次最多 100 条';

const normalizeStatus = (status: string) => (
  status === 'await_confirm' ? 'pending_confirm' : status
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

export const createDisabledAvailability = (reason: string): BatchAvailability => ({
  enabled: false,
  reason,
  dialog: '',
  actions: BATCH_ACTION_ORDER.map(id => ({ id, enabled: false, reason: '' })),
  strategyUnique: false,
  strategyId: '',
  sceneId: '',
});

/**
 * 后端 batch_actions/preview 未上线前的本地实现，规则与协议保持一致。
 */
export const mockBatchPreview = (rows: BatchRiskRow[]): BatchPreview => {
  const actions = Object.fromEntries(PREVIEW_ACTION_KEYS.map(key => (
    [key, { enabled: false, disabled_reason: '' }]
  ))) as BatchPreview['actions'];
  const disabled = (reason: string): BatchPreview => ({
    batch_enabled: false,
    batch_disabled_reason: reason,
    actions,
  });

  const statuses = rows.map(row => normalizeStatus(row.status || ''));
  if (statuses.some(status => AUTO_STATUSES.has(status))) {
    return disabled(REASON_AUTO);
  }
  if (rows.length > BATCH_SYNC_LIMIT) {
    return disabled(REASON_LIMIT);
  }
  if (statuses.some(status => !STATUS_CAPABILITIES[status])) {
    return disabled(REASON_UNSUPPORTED);
  }

  const uniqueStatuses = [...new Set(statuses)];
  const intersection = PREVIEW_ACTION_KEYS.filter(key => (
    uniqueStatuses.every(status => STATUS_CAPABILITIES[status].includes(key))
  ));
  if (!intersection.length) {
    return disabled(REASON_EMPTY);
  }

  const mixed = uniqueStatuses.length > 1 && !uniqueStatuses.every(status => DEAL_STATUSES.has(status));
  let stateReason = REASON_UNSUPPORTED;
  if (mixed && intersection.includes('misreport')) {
    stateReason = REASON_MIXED_MISREPORT;
  } else if (mixed && intersection.includes('close')) {
    stateReason = REASON_MIXED_CLOSE;
  } else if (uniqueStatuses.every(status => status === CLOSED_STATUS)) {
    stateReason = REASON_CLOSED_ONLY_CLOSE;
  }

  PREVIEW_ACTION_KEYS.forEach((key) => {
    const enabled = intersection.includes(key);
    actions[key] = { enabled, disabled_reason: enabled ? '' : stateReason };
  });

  if (actions.auto_process.enabled) {
    const strategy = resolveUniqueIdentity(rows.map(row => row.strategy_id));
    const scene = resolveUniqueIdentity(rows.map(row => row.scene_id));
    if (!strategy.unique || !scene.unique) {
      actions.auto_process = { enabled: false, disabled_reason: REASON_STRATEGY };
    } else if (rows.length > PACKAGE_SYNC_LIMIT) {
      actions.auto_process = { enabled: false, disabled_reason: REASON_PACKAGE_LIMIT };
    }
  }

  return {
    batch_enabled: true,
    batch_disabled_reason: '',
    actions,
  };
};

export const toBatchAvailability = (preview: BatchPreview, rows: BatchRiskRow[]): BatchAvailability => {
  const strategy = resolveUniqueIdentity(rows.map(row => row.strategy_id));
  const scene = resolveUniqueIdentity(rows.map(row => row.scene_id));
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
    strategyUnique: strategy.unique,
    strategyId: strategy.value,
    sceneId: scene.unique ? scene.value : '',
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
