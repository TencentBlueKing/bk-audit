export type RiskViewType = 'all' | 'scene' | 'todo' | 'watch' | 'processed';

/** 与 ListRiskBaseRequestSerializer + RiskScopeQuerySerializer 一致的 filters 字段 */
export const RISK_LIST_FILTER_KEYS = [
  'risk_id',
  'strategy_id',
  'scene_id',
  'operator',
  'status',
  'start_time',
  'end_time',
  'event_type',
  'current_operator',
  'notice_users',
  'tags',
  'event_content',
  'risk_label',
  'risk_level',
  'title',
  'event_filters',
  'sort',
  'has_report',
  'scope_type',
  'scope_id',
] as const;

export interface RiskExportFilters extends Partial<Record<typeof RISK_LIST_FILTER_KEYS[number], any>> {
  event_filters?: Array<{
    field: string;
    display_name: string;
    operator: string;
    value: unknown;
  }>;
}

const isEmptyFilterValue = (value: unknown) => {
  if (value === '' || value === undefined || value === null) {
    return true;
  }
  if (Array.isArray(value) && value.length === 0) {
    return true;
  }
  return false;
};

const normalizeHasReport = (value: unknown): boolean | undefined => {
  if (typeof value === 'boolean') {
    return value;
  }
  if (Array.isArray(value) && value.length > 0) {
    return String(value[0]) === 'true';
  }
  if (value === 'true' || value === 'false') {
    return value === 'true';
  }
  return undefined;
};

/** 将列表请求参数规范为导出 filters（剔除 page/page_size 及 UI 内部字段） */
export function normalizeRiskListExportFilters(params: Record<string, any> = {}): RiskExportFilters {
  const source: Record<string, any> = { ...params };

  if (!source.start_time && Array.isArray(source.datetime) && source.datetime[0]) {
    const [startTime, endTime] = source.datetime;
    source.start_time = startTime;
    source.end_time = endTime;
  }

  const result: RiskExportFilters = {};

  RISK_LIST_FILTER_KEYS.forEach((key) => {
    const value = source[key];
    if (isEmptyFilterValue(value)) {
      return;
    }
    if (key === 'has_report') {
      const normalized = normalizeHasReport(value);
      if (normalized !== undefined) {
        result.has_report = normalized;
      }
      return;
    }
    result[key] = value;
  });

  return result;
}

export interface RiskExportSubmitParams {
  risk_view_type: RiskViewType | string;
  risk_ids?: string[];
  filters?: RiskExportFilters;
  async?: boolean;
}

export interface RiskExportDataOptions {
  async?: boolean;
  showSuccessMessage?: boolean;
  filters?: RiskExportFilters;
}
