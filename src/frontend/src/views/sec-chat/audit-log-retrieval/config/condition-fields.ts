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

import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

import type { AiConditionItem, AiSearchCondition } from '@model/ai-assistant/types';

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
    ...( {
      __meta: field,
      __operator: pickDefaultOperator(operators),
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

  const datetime = searchModel.datetime;
  if (!Array.isArray(datetime) || datetime.length < 2) return null;

  const conditions: AiConditionItem[] = [];

  Object.keys(searchModel).forEach((fieldKey) => {
    if (fieldKey === 'datetime' || fieldKey === 'datetime_origin' || fieldKey === 'sort') return;
    const config = fieldConfig[fieldKey] as IFieldConfig & { __meta?: SystemFieldRow; __operator?: string };
    if (!config) return;

    const value = searchModel[fieldKey];
    const hasValue = Array.isArray(value)
      ? value.some(item => item !== undefined && item !== null && item !== '')
      : value !== undefined && value !== null && value !== '';
    if (!hasValue) return;

    const meta = config.__meta;
    const rawName = meta?.rawName || fieldKey.split('.')[0];
    const keys = meta?.keys?.length
      ? meta.keys
      : (fieldKey.includes('.') ? fieldKey.split('.').slice(1) : []);
    const operator = config.__operator || pickDefaultOperator(meta?.allowOperators);
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
