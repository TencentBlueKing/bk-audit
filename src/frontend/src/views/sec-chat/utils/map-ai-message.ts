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

import type {
  AiMessage,
  AiNlRecognitionError,
  AiSearchCondition,
  AiSystemFieldItem,
  AiSystemInfo,
} from '@model/ai-assistant/types';

import type {
  ChatMessage,
  RetrievalFilterCondition,
  RetrievalResultPayload,
  SelectedSystem,
  SystemFieldRow,
} from '../types';

const formatDisplayDateTime = (value?: string | null) => {
  if (!value) return '';
  const parsed = dayjs(value);
  if (!parsed.isValid()) return String(value);
  return parsed.format('YYYY-MM-DD HH:mm:ss');
};

const formatSampleValue = (value: any): string => {
  if (value === undefined || value === null) return '';
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

const mapFieldItem = (
  item: AiSystemFieldItem,
  system?: Pick<AiSystemInfo, 'system_id' | 'name'>,
): SystemFieldRow => ({
  rawName: String(item.raw_name || ''),
  keys: Array.isArray(item.keys) ? item.keys.map(String) : [],
  displayName: String(item.display_name || item.raw_name || ''),
  nlName: String(item.nl_name || item.display_name || item.raw_name || ''),
  description: String(item.description || ''),
  allowOperators: Array.isArray(item.allow_operators) ? item.allow_operators.map(String) : ['eq'],
  sampleValue: item.sample_value,
  systemId: system?.system_id,
  systemName: system?.name,
});

const pickSystems = (data?: Record<string, any> | null): SelectedSystem[] => {
  if (!data) return [];
  if (Array.isArray(data.systems)) {
    return data.systems
      .map((item: any) => ({
        id: String(item?.system_id ?? item?.id ?? ''),
        name: String(item?.name ?? item?.system_name ?? item?.system_id ?? item?.id ?? ''),
      }))
      .filter((item: SelectedSystem) => item.id);
  }
  if (Array.isArray(data.system_ids)) {
    return data.system_ids.map((id: string) => ({
      id: String(id),
      name: String(id),
    }));
  }
  return [];
};

const pickOperations = (list?: Array<{ query_text?: string }> | null): string[] => {
  if (!Array.isArray(list)) return [];
  return list
    .map(item => String(item?.query_text || '').trim())
    .filter(Boolean)
    .slice(0, 10);
};

const pickSystemFields = (output?: Record<string, any> | null) => {
  const systemList = output?.systems;
  const systems = Array.isArray(systemList) ? systemList as AiSystemInfo[] : [];
  const standardFields: SystemFieldRow[] = [];
  const extensionFields: SystemFieldRow[] = [];

  systems.forEach((system) => {
    (system.standard_fields || []).forEach((field) => {
      standardFields.push(mapFieldItem(field, system));
    });
    (system.extension_fields || []).forEach((field) => {
      extensionFields.push(mapFieldItem(field, system));
    });
  });

  return { standardFields, extensionFields };
};

const formatFilterValue = (filters: any[]): string => {
  if (!Array.isArray(filters) || !filters.length) return '';
  return filters.map(item => formatSampleValue(item)).filter(Boolean)
    .join('，');
};

const fieldCatalogKey = (rawName: string, keys: string[] = []) => (
  keys.length ? `${rawName}.${keys.join('.')}` : rawName
);

/** 用 SYSTEM_SELECTION 字段表把 raw_name 映射为中文展示名 */
export const resolveConditionFieldLabel = (
  rawName: string,
  keys: string[] = [],
  fieldCatalog: SystemFieldRow[] = [],
): string => {
  if (!rawName) return keys.length ? keys.join('.') : '条件';
  if (!fieldCatalog.length) return rawName;

  const exactKey = fieldCatalogKey(rawName, keys);
  const exact = fieldCatalog.find((field) => {
    const key = fieldCatalogKey(field.rawName, field.keys || []);
    return key === exactKey;
  });
  if (exact) return exact.displayName || exact.nlName || rawName;

  const byRaw = fieldCatalog.find(field => field.rawName === rawName);
  if (byRaw) return byRaw.displayName || byRaw.nlName || rawName;

  return rawName;
};

export const mapConditionToFilterTags = (
  condition?: AiSearchCondition | null,
  fieldCatalog: SystemFieldRow[] = [],
): RetrievalFilterCondition[] => {
  if (!condition) return [];
  const tags: RetrievalFilterCondition[] = [];
  if (condition.start_time || condition.end_time) {
    tags.push({
      field: '时间范围',
      value: [condition.start_time, condition.end_time]
        .filter(Boolean)
        .map(item => formatDisplayDateTime(String(item)))
        .join(' ~ '),
    });
  }
  (condition.conditions || []).forEach((item) => {
    const rawName = String(item?.field?.raw_name || '');
    const keys = Array.isArray(item?.field?.keys) ? item.field.keys.map(String) : [];
    tags.push({
      field: resolveConditionFieldLabel(rawName, keys, fieldCatalog),
      value: formatFilterValue(item.filters || []),
    });
  });
  return tags;
};

export const mapLogSearchOutputToResult = (
  message: AiMessage,
  fieldCatalog: SystemFieldRow[] = [],
): RetrievalResultPayload | undefined => {
  const output = message.output_data;
  if (!output || typeof output !== 'object') return undefined;

  const columns = Array.isArray(output.columns)
    ? output.columns.map((col: any) => ({
      rawName: String(col?.raw_name || ''),
      displayName: String(col?.display_name || col?.raw_name || ''),
      description: col?.description ? String(col.description) : undefined,
    })).filter((col: { rawName: string }) => col.rawName)
    : [];

  const samples = Array.isArray(output.samples) ? output.samples : [];
  const rows = samples.map((sample: Record<string, any>) => {
    if (!columns.length) return { ...sample };
    const row: Record<string, any> = {};
    columns.forEach((col) => {
      row[col.rawName] = sample?.[col.rawName] ?? '';
    });
    return row;
  });

  const totalHit = Number(output.total ?? 0);
  const previewCount = rows.length;
  const condition = (message.input_data?.condition || undefined) as AiSearchCondition | undefined;
  const conditionTags = mapConditionToFilterTags(condition, fieldCatalog);
  const tookMs = Number(output.query_summary?.took_ms ?? 0);

  return {
    conditions: conditionTags,
    toolCount: output.query_summary?.source === 'natural_language' ? 3 : 2,
    thinkSeconds: tookMs > 0 ? Math.max(1, Math.round(tookMs / 1000)) : 1,
    title: '审计日志检索结果',
    totalHit,
    previewCount,
    showPreviewHint: totalHit > previewCount,
    columns,
    rows,
  };
};

export interface MapAiMessageOptions {
  /** 来自 SYSTEM_SELECTION 的字段表，用于条件标签中文映射 */
  fieldCatalog?: SystemFieldRow[];
}

/** NL 消息在 SUCCESS 时若 output_data.error 非空，表示识别失败（非任务 FAILED） */
export const getNlRecognitionError = (message: AiMessage): AiNlRecognitionError | null => {
  if (message.message_type !== 'NATURAL_LANGUAGE_SEARCH') return null;
  if (message.status !== 'SUCCESS') return null;
  const error = message.output_data?.error;
  if (!error || typeof error !== 'object') return null;
  const errorCode = String(error.error_code || '').trim();
  if (!errorCode) return null;
  return {
    error_code: errorCode,
    error_message: String(error.error_message || '').trim(),
  };
};

/**
 * 将后端消息映射为当前 UI 卡片模型。
 */
export const mapAiMessageToChatMessage = (
  message: AiMessage,
  options: MapAiMessageOptions = {},
): ChatMessage => {
  const fieldCatalog = options.fieldCatalog || [];
  const outputSystems = pickSystems(message.output_data);
  const systems = outputSystems.length ? outputSystems : pickSystems(message.input_data);
  const systemIds = systems.map(item => item.id);
  const baseMeta = {
    apiStatus: message.status,
    messageType: message.message_type,
    errorCode: message.error_code || undefined,
    errorMessage: message.error_message || undefined,
    parentMessageUid: message.parent_message_uid,
  };

  if (message.message_type === 'SYSTEM_SELECTION') {
    if (message.status === 'SUCCESS' && (systems.length || message.output_data)) {
      const { standardFields, extensionFields } = pickSystemFields(message.output_data);
      return {
        id: message.uid,
        role: 'assistant',
        type: 'retrieval-guide',
        systems,
        systemIds,
        commonOperations: pickOperations(message.output_data?.common_operations),
        historicalOperations: pickOperations(message.output_data?.historical_operations),
        standardFields,
        extensionFields,
        ...baseMeta,
      };
    }
    return {
      id: message.uid,
      role: 'assistant',
      type: 'select-system',
      status: message.status === 'FAILED' ? 'closed' : 'pending',
      systems,
      systemIds,
      ...baseMeta,
    };
  }

  if (message.message_type === 'NATURAL_LANGUAGE_SEARCH') {
    const queryText = String(message.input_data?.query_text ?? '');
    const recognitionError = getNlRecognitionError(message);
    if (recognitionError) {
      return {
        id: message.uid,
        role: 'assistant',
        type: 'retrieval-result',
        content: queryText,
        result: undefined,
        recognitionError: {
          code: recognitionError.error_code,
          message: recognitionError.error_message,
        },
        ...baseMeta,
      };
    }
    return {
      id: message.uid,
      role: 'assistant',
      type: 'retrieval-result',
      content: queryText,
      // NL SUCCESS 的表格在子 LOG_SEARCH；此处不填 result，避免双卡
      result: undefined,
      ...baseMeta,
    };
  }

  if (message.message_type === 'LOG_SEARCH') {
    const result = message.status === 'SUCCESS'
      ? mapLogSearchOutputToResult(message, fieldCatalog)
      : undefined;
    return {
      id: message.uid,
      role: 'assistant',
      type: 'retrieval-result',
      content: '',
      result,
      ...baseMeta,
    };
  }

  return {
    id: message.uid,
    role: 'assistant',
    type: 'text',
    content: message.error_message || message.message_type,
    ...baseMeta,
  };
};

/** 合并会话内字段表，供条件标签映射 */
export const buildFieldCatalog = (
  standardFields: SystemFieldRow[] = [],
  extensionFields: SystemFieldRow[] = [],
): SystemFieldRow[] => [...standardFields, ...extensionFields];

/** 从 SYSTEM_SELECTION 消息提取字段表 */
export const extractFieldCatalogFromSystemMessage = (message: AiMessage | null): SystemFieldRow[] => {
  if (!message?.output_data) return [];
  const { standardFields, extensionFields } = pickSystemFields(message.output_data);
  return buildFieldCatalog(standardFields, extensionFields);
};

/** 从消息窗口中取最近一条成功的 SYSTEM_SELECTION */
export const findLatestSuccessSystemSelection = (messages: AiMessage[]): AiMessage | null => {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const item = messages[i];
    if (item.message_type === 'SYSTEM_SELECTION' && item.status === 'SUCCESS') {
      return item;
    }
  }
  return null;
};
