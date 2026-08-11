/**
 * 智能用户画像等 smart_page 工具的数据范围参数（cc_ids / game_ids）
 * - 有场景/系统覆盖：透传覆盖值
 * - 未覆盖或空值：不传，后端按全量数据返回
 */

export const DATA_RANGE_RAW_NAMES = ['cc_ids', 'game_ids'] as const;

export type DataRangeRawName = typeof DATA_RANGE_RAW_NAMES[number];

export interface DataRangeToolConfig {
  input_variable?: Array<{ raw_name?: string; default_value?: unknown }>;
  default_value_overrides?: {
    scenes?: Record<string, Record<string, unknown>>;
    systems?: Record<string, Record<string, unknown>>;
  };
}

export interface DataRangeScopeQuery {
  scene_id?: number;
  system_id?: string;
}

/** 兼容数组、逗号分隔字符串、单个数字 */
export const normalizeDataRangeIds = (value: unknown): number[] => {
  if (value === undefined || value === null || value === '') return [];

  let items: unknown[] = [];
  if (Array.isArray(value)) {
    items = value;
  } else if (typeof value === 'string') {
    items = value
      .split(/[,，\s]+/)
      .map(item => item.trim())
      .filter(Boolean);
  } else if (typeof value === 'number') {
    items = [value];
  } else {
    return [];
  }

  return items
    .map(item => Number(item))
    .filter((item): item is number => Number.isFinite(item));
};

const pickFirstDataRangeParams = (source: Record<string, unknown> | undefined): Record<string, number[]> => {
  if (!source || typeof source !== 'object') return {};
  for (const rawName of DATA_RANGE_RAW_NAMES) {
    if (!(rawName in source)) continue;
    const ids = normalizeDataRangeIds(source[rawName]);
    if (ids.length) return { [rawName]: ids };
  }
  return {};
};

/**
 * 从工具详情配置解析执行时需透传的数据范围参数。
 * 能解析当前场景/系统时，以 default_value_overrides 为准（未配置覆盖 = 全量）。
 * 否则回退到后端已合并的 input_variable.default_value。
 */
export const getDataRangeParamsFromToolConfig = (
  toolConfig?: DataRangeToolConfig | null,
  scopeQuery: DataRangeScopeQuery = {},
): Record<string, number[]> => {
  if (!toolConfig) return {};

  const overrides = toolConfig.default_value_overrides;
  const hasOverridesConfig = !!(overrides?.scenes || overrides?.systems);
  const hasScope = scopeQuery.scene_id !== undefined || !!scopeQuery.system_id;

  if (hasScope && hasOverridesConfig) {
    let scopeOverride: Record<string, unknown> | undefined;
    if (scopeQuery.scene_id !== undefined) {
      scopeOverride = overrides?.scenes?.[String(scopeQuery.scene_id)];
    } else if (scopeQuery.system_id) {
      scopeOverride = overrides?.systems?.[String(scopeQuery.system_id)];
    }
    // 当前可见范围未配置覆盖 → 不传，全量数据
    if (!scopeOverride || typeof scopeOverride !== 'object') {
      return {};
    }
    return pickFirstDataRangeParams(scopeOverride);
  }

  const inputVars = toolConfig.input_variable;
  if (!Array.isArray(inputVars)) return {};
  for (const rawName of DATA_RANGE_RAW_NAMES) {
    const target = inputVars.find(item => item.raw_name === rawName);
    if (!target) continue;
    const ids = normalizeDataRangeIds(target.default_value);
    if (ids.length) return { [rawName]: ids };
  }
  return {};
};
