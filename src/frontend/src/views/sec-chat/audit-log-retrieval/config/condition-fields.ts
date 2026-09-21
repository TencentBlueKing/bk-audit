/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
*/
import dayjs from 'dayjs';

import type { AiConditionItem, AiSearchCondition } from '@model/ai-assistant/types';

import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

import type { LogFieldConditionValue, SelectedSystem, SystemFieldRow } from '../../types';
import {
  resolveNestedPathLabel,
  resolveParentFieldLabel,
  resolveSystemFieldDisplayLabel,
} from '../../utils/map-ai-message';

import { isRelativeDatetimeOrigin } from '@/utils/sync-datetime-from-url';

/** 前端时间快捷项映射（展示用）；后端只存绝对起止，不回传快捷值 */
export const DATETIME_SHORTCUT_LABEL_MAP: Record<string, string> = {
  'now-1d': '近1天',
  'now-3d': '近3天',
  'now-7d': '近7天',
  'now-14d': '近14天',
  'now-1M': '近1月',
  'now-3M': '近3月',
  'now-6M': '近6月',
  'now-12M': '近12月',
};

/** 日志检索操作符展示文案（符号 + 描述，与风险 NL 条件标签一致） */
export const LOG_OPERATOR_NAME_MAP: Record<string, string> = {
  eq: '=  等于',
  neq: '!=  不等于',
  include: '包含',
  exclude: '不包含',
  like: '模糊匹配',
  not_like: '不匹配',
  gt: '>  大于',
  lt: '<  小于',
  gte: '>=  大于等于',
  lte: '<=  小于等于',
  isnull: '为空',
  notnull: '不为空',
  match_any: '匹配任一',
  match_all: '匹配全部',
  '=': '=  等于',
  '!=': '!=  不等于',
};

/** 操作符徽章上的简短展示（去掉多余空格） */
export const LOG_OPERATOR_BADGE_MAP: Record<string, string> = {
  eq: '= 等于',
  neq: '!= 不等于',
  include: '包含',
  exclude: '不包含',
  like: '模糊匹配',
  not_like: '不匹配',
  gt: '> 大于',
  lt: '< 小于',
  gte: '>= 大于等于',
  lte: '<= 小于等于',
  isnull: '为空',
  notnull: '不为空',
  match_any: '匹配任一',
  match_all: '匹配全部',
  '=': '= 等于',
  '!=': '!= 不等于',
};

/**
 * 将新条件字段追加到 searchModel 末尾（datetime 始终在最前）。
 */
export const appendSearchModelField = (
  searchModel: Record<string, any>,
  fieldName: string,
  value: any,
  datetimeDefaults?: { datetime?: any; datetimeOrigin?: any },
): Record<string, any> => {
  const next: Record<string, any> = {
    datetime: searchModel.datetime ?? datetimeDefaults?.datetime,
    datetime_origin: searchModel.datetime_origin ?? datetimeDefaults?.datetimeOrigin,
  };
  Object.keys(searchModel).forEach((key) => {
    if (key === 'datetime' || key === 'datetime_origin' || key === fieldName) return;
    next[key] = searchModel[key];
  });
  if (fieldName !== 'datetime' && fieldName !== 'datetime_origin') {
    next[fieldName] = value;
  }
  return next;
};

/** 兼容旧静态配置的通用字段 key（无 SYSTEM 字段上下文时回退） */
export const COMMON_FIELD_KEYS = [
  'datetime',
  'username',
  'user_identify_type',
  'system_id',
  'result_code',
  'access_type',
  'access_source_ip',
  'event_id',
  'request_id',
];

export const EXTEND_FIELD_KEYS = [
  'request_path',
  'http_method',
  'ins_cu_content',
];

export const FIELD_LABEL_TO_KEY: Record<string, string> = {
  操作起始时间: 'datetime',
  操作人: 'username',
  操作人账号类型: 'user_identify_type',
  来源系统: 'system_id',
  操作结果: 'result_code',
  操作途径: 'access_type',
  来源IP: 'access_source_ip',
  事件ID: 'event_id',
  请求ID: 'request_id',
};

export interface ILogFieldConfig extends IFieldConfig {
  fieldMeta?: SystemFieldRow;
  defaultOperator?: string;
  allowOperators?: string[];
}

export const createDefaultDatetime = () => ([
  dayjs(Date.now() - (86400000 * 1)).format('YYYY-MM-DD HH:mm:ss'),
  dayjs().format('YYYY-MM-DD HH:mm:ss'),
]);

export const createDefaultDatetimeOrigin = () => ([
  'now-1d',
  'now',
]);

/** 将后端绝对起止转为展示用 datetime_origin（不做快捷项反推） */
export const absoluteDatetimeOriginFromCondition = (
  startTime?: string,
  endTime?: string,
): string[] => {
  const start = dayjs(startTime);
  const end = dayjs(endTime);
  if (!start.isValid() || !end.isValid()) {
    // 无效时退回绝对默认窗口，避免误显示「近1天」快捷文案
    return createDefaultDatetime();
  }
  return [
    start.format('YYYY-MM-DD HH:mm:ss'),
    end.format('YYYY-MM-DD HH:mm:ss'),
  ];
};

export const resolveDatetimeOriginForDisplay = (
  startTime?: string,
  endTime?: string,
  preferredOrigin?: string[],
): string[] => {
  if (preferredOrigin && isRelativeDatetimeOrigin(preferredOrigin)) {
    return [...preferredOrigin];
  }
  return absoluteDatetimeOriginFromCondition(startTime, endTime);
};

const toIsoTime = (value: string) => {
  const parsed = dayjs(value);
  if (!parsed.isValid()) return value;
  return parsed.format('YYYY-MM-DDTHH:mm:ss+08:00');
};

export const pickDefaultOperator = (allowOperators: string[] = []) => {
  if (allowOperators.includes('eq')) return 'eq';
  if (allowOperators.includes('=')) return '=';
  return allowOperators[0] || 'eq';
};

/** 标准字段：根据值类型推断 include / eq */
export const resolveStandardOperator = (
  config: ILogFieldConfig,
  value: any,
): string => {
  const ops = config.allowOperators || config.fieldMeta?.allowOperators || [];
  if (ops.length === 1) return ops[0];
  if (config.type === 'select' || config.type === 'user-selector') {
    if (ops.includes('include')) return 'include';
  }
  if (ops.includes('include') && ops.includes('eq')) {
    if (Array.isArray(value)) {
      return value.length > 1 ? 'include' : 'eq';
    }
    return 'eq';
  }
  if (ops.includes('like') && !ops.includes('eq')) return 'like';
  return config.defaultOperator || pickDefaultOperator(ops);
};

const isLogFieldValue = (value: any): value is LogFieldConditionValue => (
  value !== null
  && typeof value === 'object'
  && !Array.isArray(value)
  && 'operator' in value
);

const fieldConfigFromRow = (
  field: SystemFieldRow,
  fieldCatalog: SystemFieldRow[] = [],
): ILogFieldConfig => {
  const operators = field.allowOperators || [];
  const options = field.options || [];
  const hasOptions = options.length > 0;
  const isUser = /user|username/i.test(field.rawName) || field.nlName.includes('操作人');
  const label = resolveSystemFieldDisplayLabel(field, fieldCatalog);
  const metaExtras = {
    fieldMeta: field,
    allowOperators: operators,
  };

  // 扩展字段且允许多操作符 → 展示操作符徽章
  if (field.isExtension && operators.length > 1) {
    return {
      label,
      type: 'log-field',
      required: false,
      defaultOperator: pickDefaultOperator(operators),
      ...metaExtras,
    };
  }

  // 标准字段：options 有值 → 下拉
  if (hasOptions) {
    return {
      label,
      type: 'select',
      required: false,
      service: () => Promise.resolve(options),
      labelName: 'name',
      valName: 'id',
      defaultOperator: operators.includes('include') ? 'include' : pickDefaultOperator(operators),
      ...metaExtras,
    };
  }

  if (isUser) {
    return {
      label,
      type: 'user-selector',
      required: false,
      defaultOperator: operators.includes('include') ? 'include' : pickDefaultOperator(operators),
      ...metaExtras,
    };
  }

  // 扩展字段仅一个操作符 / 标准文本字段 → 输入框 + 冒号
  return {
    label,
    type: 'string',
    required: false,
    defaultOperator: pickDefaultOperator(operators),
    ...metaExtras,
  };
};

/**
 * 由 SYSTEM_SELECTION 字段列表生成条件筛选 fieldConfig。
 * 始终包含 datetime；其余字段按 raw_name 挂载。
 */
export const createConditionFieldConfigFromSystemFields = (
  standardFields: SystemFieldRow[] = [],
  extensionFields: SystemFieldRow[] = [],
): Record<string, ILogFieldConfig> => {
  const config: Record<string, ILogFieldConfig> = {
    datetime: {
      label: '操作起始时间',
      type: 'datetimerange',
      required: true,
    },
  };

  const fieldCatalog = [...standardFields, ...extensionFields];
  fieldCatalog.forEach((field) => {
    if (!field.rawName || field.rawName === 'datetime') return;
    const key = field.keys?.length
      ? `${field.rawName}.${field.keys.join('.')}`
      : field.rawName;
    config[key] = fieldConfigFromRow(field, fieldCatalog);
  });

  return config;
};

export const getPrimaryFieldNames = (standardFields: SystemFieldRow[] = []) => (
  ['datetime', ...standardFields.map((field) => {
    if (field.keys?.length) return `${field.rawName}.${field.keys.join('.')}`;
    return field.rawName;
  }).filter(Boolean)]
);

export const getSecondaryFieldNames = (extensionFields: SystemFieldRow[] = []) => (
  extensionFields.map((field) => {
    if (field.keys?.length) return `${field.rawName}.${field.keys.join('.')}`;
    return field.rawName;
  }).filter(Boolean)
);

/** 条件字段默认值 */
export const getConditionDefaultValue = (config: IFieldConfig): any => {
  const logConfig = config as ILogFieldConfig;
  if (config.type === 'log-field') {
    return {
      operator: logConfig.defaultOperator || pickDefaultOperator(logConfig.allowOperators),
      value: '',
    } satisfies LogFieldConditionValue;
  }
  if (config.type === 'select' || config.type === 'user-selector') {
    return [];
  }
  if (config.type === 'datetimerange') {
    return createDefaultDatetime();
  }
  return '';
};

/** 样本值转条件初值 */
export const sampleToConditionValue = (config: IFieldConfig, sample?: string): any => {
  if (!sample) {
    return getConditionDefaultValue(config);
  }
  if (config.type === 'log-field') {
    const logConfig = config as ILogFieldConfig;
    return {
      operator: logConfig.defaultOperator || pickDefaultOperator(logConfig.allowOperators),
      value: sample,
    } satisfies LogFieldConditionValue;
  }
  if (config.type === 'user-selector' || config.type === 'select') {
    return [sample];
  }
  return sample;
};

const fieldCatalogKey = (rawName: string, keys: string[] = []) => (
  keys.length ? `${rawName}.${keys.join('.')}` : rawName
);

const fromIsoTime = (value?: string) => {
  if (!value) return '';
  const parsed = dayjs(value);
  if (!parsed.isValid()) return String(value);
  return parsed.format('YYYY-MM-DD HH:mm:ss');
};

/** 将 AiSearchCondition 中的字段项映射到 fieldConfig 的 key */
export const resolveConditionFieldKey = (
  rawName: string,
  keys: string[] = [],
  fieldConfig: Record<string, IFieldConfig> = {},
): string | null => {
  const exactKey = fieldCatalogKey(rawName, keys);
  if (fieldConfig[exactKey]) return exactKey;

  // 有 keys 时只允许精确命中，禁止回退到父字段（否则标签会丢下钻路径）
  if (keys.length) {
    const matched = Object.entries(fieldConfig).find(([, config]) => {
      const meta = (config as ILogFieldConfig).fieldMeta;
      if (!meta) return false;
      return fieldCatalogKey(meta.rawName, meta.keys || []) === exactKey;
    });
    return matched?.[0] || null;
  }

  const matched = Object.entries(fieldConfig).find(([, config]) => {
    const meta = (config as ILogFieldConfig).fieldMeta;
    if (!meta) return false;
    return meta.rawName === rawName && !(meta.keys?.length);
  });
  if (matched) return matched[0];
  if (fieldConfig[rawName]) return rawName;
  return null;
};

/**
 * 目录无对应下钻字段时，按 raw_name + keys 动态挂载 fieldConfig。
 * 返回可用的 fieldConfig key；无法挂载时返回 null。
 */
export const ensureNestedConditionFieldConfig = (
  fieldConfig: Record<string, IFieldConfig>,
  rawName: string,
  keys: string[] = [],
  fieldCatalog: SystemFieldRow[] = [],
): string | null => {
  if (!rawName) return null;
  const existing = resolveConditionFieldKey(rawName, keys, fieldConfig);
  if (existing) return existing;
  if (!keys.length) return null;

  const exactKey = fieldCatalogKey(rawName, keys);
  const sibling = Object.values(fieldConfig).find((config) => {
    const meta = (config as ILogFieldConfig).fieldMeta;
    return meta?.rawName === rawName;
  }) as ILogFieldConfig | undefined;

  const label = resolveNestedPathLabel(
    rawName,
    keys,
    resolveParentFieldLabel(rawName, fieldCatalog),
  );
  const syntheticField: SystemFieldRow = {
    rawName,
    keys: [...keys],
    displayName: label,
    nlName: label,
    description: '',
    allowOperators: sibling?.allowOperators
      || sibling?.fieldMeta?.allowOperators
      || ['eq', 'include', 'like'],
    fieldType: sibling?.fieldMeta?.fieldType || 'string',
    isExtension: true,
  };
  // 动态挂载到传入的 fieldConfig（调用方持有可变副本）
  // eslint-disable-next-line no-param-reassign
  fieldConfig[exactKey] = fieldConfigFromRow(syntheticField, fieldCatalog);
  return exactKey;
};

/** 根据 AiSearchCondition 把缺失的下钻字段补进 fieldConfig */
export const ensureConditionFieldsFromAiSearch = (
  fieldConfig: Record<string, IFieldConfig>,
  condition?: AiSearchCondition | null,
  fieldCatalog: SystemFieldRow[] = [],
) => {
  if (!condition?.conditions?.length) return fieldConfig;
  condition.conditions.forEach((item) => {
    const rawName = String(item?.field?.raw_name || '');
    const keys = Array.isArray(item?.field?.keys) ? item.field.keys.map(String) : [];
    if (!rawName || !keys.length) return;
    ensureNestedConditionFieldConfig(fieldConfig, rawName, keys, fieldCatalog);
  });
  return fieldConfig;
};

const normalizeFiltersToModelValue = (
  config: IFieldConfig,
  filters: any[],
  operator?: string,
) => {
  if (config.type === 'log-field') {
    const logConfig = config as ILogFieldConfig;
    return {
      operator: operator || logConfig.defaultOperator || 'eq',
      value: filters.length === 1 ? String(filters[0]) : filters.map(String).join(','),
    } satisfies LogFieldConditionValue;
  }
  if (config.type === 'user-selector' || config.type === 'select') {
    return filters.map(String);
  }
  return filters.length === 1 ? filters[0] : filters.join(',');
};

/** 将 AiSearchCondition 转为条件筛选 searchModel（与 buildAiSearchCondition 互逆） */
export const parseAiSearchConditionToSearchModel = (
  condition: AiSearchCondition,
  fieldConfig: Record<string, IFieldConfig>,
  fieldCatalog: SystemFieldRow[] = [],
  options?: { datetimeOrigin?: string[] },
): Record<string, any> => {
  const searchModel: Record<string, any> = {
    datetime: [
      fromIsoTime(condition.start_time),
      fromIsoTime(condition.end_time),
    ],
    datetime_origin: resolveDatetimeOriginForDisplay(
      condition.start_time,
      condition.end_time,
      options?.datetimeOrigin,
    ),
  };

  (condition.conditions || []).forEach((item) => {
    const rawName = String(item?.field?.raw_name || '');
    const keys = Array.isArray(item?.field?.keys) ? item.field.keys.map(String) : [];
    const fieldKey = ensureNestedConditionFieldConfig(
      fieldConfig,
      rawName,
      keys,
      fieldCatalog,
    );
    if (!fieldKey) return;

    const config = fieldConfig[fieldKey];
    if (!config) return;
    const filters = Array.isArray(item.filters)
      ? item.filters.filter(v => v !== undefined && v !== null && v !== '')
      : [];
    if (!filters.length) return;

    searchModel[fieldKey] = normalizeFiltersToModelValue(config, filters, item.operator);
  });

  return searchModel;
};

const extractFieldValue = (config: ILogFieldConfig, value: any) => {
  if (config.type === 'log-field' && isLogFieldValue(value)) {
    return {
      operator: value.operator || config.defaultOperator || 'eq',
      rawValue: value.value,
    };
  }
  return {
    operator: resolveStandardOperator(config, value),
    rawValue: value,
  };
};

const valueToFilters = (config: ILogFieldConfig, rawValue: any): any[] => {
  if (Array.isArray(rawValue)) {
    return rawValue.filter(item => item !== undefined && item !== null && item !== '');
  }
  if (rawValue === undefined || rawValue === null || rawValue === '') {
    return [];
  }
  return [rawValue];
};

/**
 * 将条件筛选表单转为文档同构的 AiSearchCondition。
 */
export const buildAiSearchCondition = (params: {
  scopeId: string;
  searchModel: Record<string, any>;
  fieldConfig: Record<string, IFieldConfig>;
}): AiSearchCondition | null => {
  const { scopeId, searchModel, fieldConfig } = params;
  if (!scopeId) return null;

  const { datetime } = searchModel;
  if (!Array.isArray(datetime) || datetime.length < 2) return null;

  const conditions: AiConditionItem[] = [];

  Object.keys(searchModel).forEach((fieldKey) => {
    if (fieldKey === 'datetime' || fieldKey === 'datetime_origin' || fieldKey === 'sort') return;
    const config = fieldConfig[fieldKey] as ILogFieldConfig;
    if (!config) return;

    const value = searchModel[fieldKey];
    let hasValue = false;
    if (config.type === 'log-field') {
      hasValue = isLogFieldValue(value) && value.value !== undefined && value.value !== null && value.value !== '';
    } else if (Array.isArray(value)) {
      hasValue = value.some(item => item !== undefined && item !== null && item !== '');
    } else {
      hasValue = value !== undefined && value !== null && value !== '';
    }
    if (!hasValue) return;

    const meta = config.fieldMeta;
    const rawName = meta?.rawName || fieldKey.split('.')[0];
    let keys: string[] = [];
    if (meta?.keys?.length) {
      keys = meta.keys;
    } else if (fieldKey.includes('.')) {
      keys = fieldKey.split('.').slice(1);
    }

    const { operator, rawValue } = extractFieldValue(config, value);
    const filters = valueToFilters(config, rawValue);
    if (!filters.length) return;

    conditions.push({
      field: {
        raw_name: rawName,
        keys,
      },
      operator,
      filters,
    });
  });

  return {
    scope_type: 'system',
    scope_id: scopeId,
    start_time: toIsoTime(String(datetime[0])),
    end_time: toIsoTime(String(datetime[1])),
    conditions,
  };
};

/** @deprecated 仅作无 SYSTEM 字段时的兜底；联调主路径用 createConditionFieldConfigFromSystemFields */
export const createConditionFieldConfig = (systems: SelectedSystem[] = []): Record<string, ILogFieldConfig> => {
  const systemOptions = systems.map(item => ({ id: item.id, name: item.name }));
  return {
    datetime: {
      label: '操作起始时间',
      type: 'datetimerange',
      required: true,
    },
    username: {
      label: '操作人',
      type: 'user-selector',
      required: false,
    },
    system_id: {
      label: '来源系统',
      type: 'select',
      required: false,
      service: () => Promise.resolve(systemOptions),
      formatLabel: item => `${item.name}(${item.id})`,
    },
  };
};
