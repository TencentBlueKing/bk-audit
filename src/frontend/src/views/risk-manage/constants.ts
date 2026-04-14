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
};
