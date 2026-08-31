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

import type { SelectedSystem, SystemFieldRow } from '../../types';

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

export const createDefaultDatetime = () => ([
  dayjs(Date.now() - (86400000 * 1)).format('YYYY-MM-DD HH:mm:ss'),
  dayjs().format('YYYY-MM-DD HH:mm:ss'),
]);

export const createDefaultDatetimeOrigin = () => ([
  'now-1d',
  'now',
]);

const DATETIME_SHORTCUT_CONFIGS = [
  { days: 1, origin: 'now-1d' },
  { days: 3, origin: 'now-3d' },
  { days: 7, origin: 'now-7d' },
  { days: 14, origin: 'now-14d' },
  { days: 30, origin: 'now-1M' },
  { days: 90, origin: 'now-3M' },
  { days: 182, origin: 'now-6M' },
  { days: 365, origin: 'now-12M' },
];

/** 根据 start/end 推断 datetime_origin，避免回显固定为「近1天」 */
export const inferDatetimeOrigin = (startTime?: string, endTime?: string): string[] => {
  const start = dayjs(startTime);
  const end = dayjs(endTime);
  if (!start.isValid() || !end.isValid()) {
    return createDefaultDatetimeOrigin();
  }

  const formatted = [
    start.format('YYYY-MM-DD HH:mm:ss'),
    end.format('YYYY-MM-DD HH:mm:ss'),
  ];

  const now = dayjs();
  if (Math.abs(end.diff(now, 'minute')) > 5) {
    return formatted;
  }

  const diffMinutes = end.diff(start, 'minute');
  const matched = DATETIME_SHORTCUT_CONFIGS.find(
    item => Math.abs(diffMinutes - (item.days * 24 * 60)) <= 2,
  );
  if (matched) {
    return [matched.origin, 'now'];
  }

  return formatted;
};

const toIsoTime = (value: string) => {
  const parsed = dayjs(value);
  if (!parsed.isValid()) return value;
  return parsed.format('YYYY-MM-DDTHH:mm:ss+08:00');
};

const pickDefaultOperator = (allowOperators: string[] = []) => {
  if (allowOperators.includes('eq')) return 'eq';
  if (allowOperators.includes('=')) return '=';
  return allowOperators[0] || 'eq';
};

const fieldConfigFromRow = (field: SystemFieldRow): IFieldConfig => {
  const operators = field.allowOperators || [];
  // 用户类字段用 user-selector；其余默认字符串输入
  const isUser = /user|username|operator/i.test(field.rawName) || field.nlName.includes('操作人');
  return {
    label: field.displayName || field.rawName,
    type: isUser ? 'user-selector' : 'string',
    required: false,
    // 透传元数据，拼 condition 时使用
    ...({
      fieldMeta: field,
      defaultOperator: pickDefaultOperator(operators),
    } as any),
  };
};

/**
 * 由 SYSTEM_SELECTION 字段列表生成条件筛选 fieldConfig。
 * 始终包含 datetime；其余字段按 raw_name 挂载。
 */
export const createConditionFieldConfigFromSystemFields = (
  standardFields: SystemFieldRow[] = [],
  extensionFields: SystemFieldRow[] = [],
): Record<string, IFieldConfig> => {
  const config: Record<string, IFieldConfig> = {
    datetime: {
      label: '操作起始时间',
      type: 'datetimerange',
      required: true,
    },
  };

  [...standardFields, ...extensionFields].forEach((field) => {
    if (!field.rawName || field.rawName === 'datetime') return;
    // 扩展字段用 raw_name + keys 路径做唯一 key，避免冲突
    const key = field.keys?.length
      ? `${field.rawName}.${field.keys.join('.')}`
      : field.rawName;
    config[key] = fieldConfigFromRow(field);
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

  const matched = Object.entries(fieldConfig).find(([, config]) => {
    const meta = (config as IFieldConfig & { fieldMeta?: SystemFieldRow }).fieldMeta;
    if (!meta) return false;
    const metaKey = fieldCatalogKey(meta.rawName, meta.keys || []);
    return metaKey === exactKey || meta.rawName === rawName;
  });
  if (matched) return matched[0];
  if (fieldConfig[rawName]) return rawName;
  return null;
};

/** 将 AiSearchCondition 转为条件筛选 searchModel（与 buildAiSearchCondition 互逆） */
export const parseAiSearchConditionToSearchModel = (
  condition: AiSearchCondition,
  fieldConfig: Record<string, IFieldConfig>,
): Record<string, any> => {
  const searchModel: Record<string, any> = {
    datetime: [
      fromIsoTime(condition.start_time),
      fromIsoTime(condition.end_time),
    ],
    datetime_origin: inferDatetimeOrigin(condition.start_time, condition.end_time),
  };

  (condition.conditions || []).forEach((item) => {
    const rawName = String(item?.field?.raw_name || '');
    const keys = Array.isArray(item?.field?.keys) ? item.field.keys.map(String) : [];
    const fieldKey = resolveConditionFieldKey(rawName, keys, fieldConfig);
    if (!fieldKey) return;

    const config = fieldConfig[fieldKey];
    const filters = Array.isArray(item.filters)
      ? item.filters.filter(v => v !== undefined && v !== null && v !== '')
      : [];
    if (!filters.length) return;

    if (config.type === 'user-selector' || config.type === 'select') {
      searchModel[fieldKey] = filters;
    } else {
      searchModel[fieldKey] = filters.length === 1 ? filters[0] : filters.join(',');
    }
  });

  return searchModel;
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
    const config = fieldConfig[fieldKey] as IFieldConfig & {
      fieldMeta?: SystemFieldRow;
      defaultOperator?: string;
    };
    if (!config) return;

    const value = searchModel[fieldKey];
    const hasValue = Array.isArray(value)
      ? value.some(item => item !== undefined && item !== null && item !== '')
      : value !== undefined && value !== null && value !== '';
    if (!hasValue) return;

    const meta = config.fieldMeta;
    const rawName = meta?.rawName || fieldKey.split('.')[0];
    let keys: string[] = [];
    if (meta?.keys?.length) {
      keys = meta.keys;
    } else if (fieldKey.includes('.')) {
      keys = fieldKey.split('.').slice(1);
    }
    const operator = config.defaultOperator || pickDefaultOperator(meta?.allowOperators);
    const filters = Array.isArray(value) ? value.filter(item => item !== undefined && item !== null && item !== '') : [value];

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
export const createConditionFieldConfig = (systems: SelectedSystem[] = []): Record<string, IFieldConfig> => {
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
