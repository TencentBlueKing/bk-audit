/**
 * 风险模块共享常量
 * 风险处理状态 -> 样式映射
 */

export interface RiskStatusMapItem {
  tag: string;
  icon: string;
  color: string;
}

export interface RiskStatusThemeItem {
  theme: 'info' | 'warning' | 'success' | 'danger' | undefined;
  icon: string;
  color: string;
}

export const RISK_STATUS_TAG_MAP: Record<string, RiskStatusMapItem> = {
  new: {
    tag: 'info',
    icon: 'auto',
    color: '#3A84FF',
  },
  closed: {
    tag: '',
    icon: 'corret-fill',
    color: '#979BA5',
  },
  await_deal: {
    tag: 'warning',
    icon: 'daichuli',
    color: '#FF9E00',
  },
  for_approve: {
    tag: 'info',
    icon: 'auto',
    color: '#3A84FF',
  },
  auto_process: {
    tag: 'success',
    icon: 'taocanchulizhong',
    color: '#0CA668',
  },
  processing: {
    tag: 'info',
    icon: 'loading',
    color: '#3A84FF',
  },
  await_confirm: {
    tag: 'warning',
    icon: 'daichuli',
    color: '#FF9E00',
  },
  pending_confirm: {
    tag: 'warning',
    icon: 'daichuli',
    color: '#FF9E00',
  },
};

export const RISK_STATUS_THEME_MAP: Record<string, RiskStatusThemeItem> = {
  new: {
    theme: 'info',
    icon: 'auto',
    color: '#3A84FF',
  },
  closed: {
    theme: undefined,
    icon: 'corret-fill',
    color: '#979BA5',
  },
  await_deal: {
    theme: 'warning',
    icon: 'daichuli',
    color: '#FF9E00',
  },
  for_approve: {
    theme: 'info',
    icon: 'auto',
    color: '#3A84FF',
  },
  auto_process: {
    theme: 'success',
    icon: 'taocanchulizhong',
    color: '#0CA668',
  },
  processing: {
    theme: 'info',
    icon: 'loading',
    color: '#3A84FF',
  },
  await_confirm: {
    theme: 'warning',
    icon: 'daichuli',
    color: '#FF9E00',
  },
  pending_confirm: {
    theme: 'warning',
    icon: 'daichuli',
    color: '#FF9E00',
  },
};

const RISK_STATUS_ALIAS: Record<string, string> = {
  pending_confirm: 'await_confirm',
};

const RISK_STATUS_FALLBACK_NAME: Record<string, string> = {
  await_confirm: '待确认',
  pending_confirm: '待确认',
};

export const resolveRiskStatusName = (
  status: string,
  list: Array<{ id: string; name: string }> = [],
) => {
  const exact = list.find(item => item.id === status)?.name;
  if (exact) return exact;
  const alias = RISK_STATUS_ALIAS[status];
  if (alias) {
    const aliased = list.find(item => item.id === alias)?.name;
    if (aliased) return aliased;
  }
  return RISK_STATUS_FALLBACK_NAME[status] || '';
};
