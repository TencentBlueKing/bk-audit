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
  AiDerivedMessageRef,
  AiMessage,
  AiNlRecognitionError,
  AiSearchCondition,
  AiSystemFieldItem,
  AiSystemInfo,
  AiUserIntentOutput,
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

/** 空对象 / 空数组文案与空值一致，表格侧会展示为 -- */
const isBlankSampleText = (text: string) => {
  const trimmed = text.trim();
  return !trimmed || trimmed === '{}' || trimmed === '[]';
};

export const formatSampleValue = (value: any): string => {
  if (value === undefined || value === null) return '';
  if (typeof value === 'object') {
    if (Array.isArray(value) && value.length === 0) return '';
    if (!Array.isArray(value) && Object.keys(value).length === 0) return '';
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  const text = String(value);
  return isBlankSampleText(text) ? '' : text;
};

/** 解析字段「最近一条数据」展示文案：优先 sample_value_display，其次 options，最后回退原始值 */
export const resolveFieldSampleDisplay = (field: {
  sampleValue?: any;
  sampleValueDisplay?: string | null;
  options?: Array<{ id: string; name: string }>;
}): string => {
  const display = field.sampleValueDisplay;
  if (display !== undefined && display !== null && !isBlankSampleText(String(display))) {
    return String(display);
  }

  const rawText = formatSampleValue(field.sampleValue);
  if (!rawText) return '';

  const options = field.options || [];
  if (options.length) {
    const matched = options.find(opt => String(opt.id) === rawText);
    if (matched?.name) return matched.name;
  }

  return rawText;
};

const mapFieldOptions = (options?: AiSystemFieldItem['options']) => {
  if (!Array.isArray(options)) return [];
  return options
    .map(opt => ({
      id: String(opt?.id ?? ''),
      name: String(opt?.name ?? opt?.id ?? ''),
    }))
    .filter(opt => opt.id);
};

const mapFieldItem = (
  item: AiSystemFieldItem,
  system?: Pick<AiSystemInfo, 'system_id' | 'name'>,
  isExtension = false,
): SystemFieldRow => ({
  rawName: String(item.raw_name || ''),
  keys: Array.isArray(item.keys) ? item.keys.map(String) : [],
  displayName: String(item.display_name || item.raw_name || ''),
  nlName: String(item.nl_name || item.display_name || item.raw_name || ''),
  description: String(item.description || ''),
  allowOperators: Array.isArray(item.allow_operators) ? item.allow_operators.map(String) : ['eq'],
  fieldType: item.field_type ? String(item.field_type) : undefined,
  options: mapFieldOptions(item.options),
  isExtension,
  sampleValue: item.sample_value,
  sampleValueDisplay: item.sample_value_display ?? null,
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

const pickCandidateSystems = (message: AiMessage): SelectedSystem[] => {
  const candidates = message.output_data?.error?.candidates;
  if (!Array.isArray(candidates)) return [];
  return candidates
    .map((item: any) => ({
      id: String(item?.system_id ?? item?.id ?? ''),
      name: String(item?.name ?? item?.system_name ?? item?.system_id ?? item?.id ?? ''),
    }))
    .filter((item: SelectedSystem) => item.id);
};

const pickSystemFields = (output?: Record<string, any> | null) => {
  const systemList = output?.systems;
  const systems = Array.isArray(systemList) ? systemList as AiSystemInfo[] : [];
  const standardFields: SystemFieldRow[] = [];
  const extensionFields: SystemFieldRow[] = [];

  systems.forEach((system) => {
    (system.standard_fields || []).forEach((field) => {
      standardFields.push(mapFieldItem(field, system, false));
    });
    (system.extension_fields || []).forEach((field) => {
      extensionFields.push(mapFieldItem(field, system, true));
    });
  });

  return { standardFields, extensionFields };
};

const formatFilterValue = (filters: any[]): string => {
  if (!Array.isArray(filters) || !filters.length) return '';
  return filters.map(item => formatSampleValue(item)).filter(Boolean)
    .join('，');
};

/** 常见父字段中文名兜底（目录无空 keys 父项时） */
const KNOWN_PARENT_FIELD_LABELS: Record<string, string> = {
  extend_data: '拓展数据',
  instance_data: '实例当前内容',
  snapshot_instance_data: '实例信息快照',
};

/** 解析下钻父字段中文名：优先目录空 keys 项，其次已知兜底，最后 rawName */
export const resolveParentFieldLabel = (
  rawName: string,
  fieldCatalog: SystemFieldRow[] = [],
): string => {
  if (!rawName) return '';
  const parent = fieldCatalog.find(field => field.rawName === rawName && !(field.keys?.length));
  if (parent) {
    return parent.displayName || parent.nlName || rawName;
  }
  return KNOWN_PARENT_FIELD_LABELS[rawName] || rawName;
};

/**
 * 下钻字段展示：父中文名 + 点路径
 * 例：拓展数据.request_data.audit_status_in
 */
export const resolveNestedPathLabel = (
  rawName: string,
  keys: string[],
  parentLabel?: string,
): string => {
  if (!keys.length) return parentLabel || rawName || '条件';
  const parent = parentLabel || rawName || '条件';
  return `${parent}.${keys.join('.')}`;
};

/** SystemFieldRow → 引导卡 / 条件 tag 展示名（有 keys 时：父中文名 + 点路径） */
export const resolveSystemFieldDisplayLabel = (
  field: Pick<SystemFieldRow, 'rawName' | 'keys' | 'displayName' | 'nlName'>,
  fieldCatalog: SystemFieldRow[] = [],
): string => {
  const keys = field.keys || [];
  if (keys.length) {
    return resolveNestedPathLabel(
      field.rawName,
      keys,
      resolveParentFieldLabel(field.rawName, fieldCatalog),
    );
  }
  return field.displayName || field.nlName || field.rawName || '条件';
};

/** 用 SYSTEM_SELECTION 字段表把 raw_name[+keys] 映射为展示名 */
export const resolveConditionFieldLabel = (
  rawName: string,
  keys: string[] = [],
  fieldCatalog: SystemFieldRow[] = [],
): string => {
  if (!rawName) return keys.length ? keys.join('.') : '条件';

  if (keys.length) {
    return resolveNestedPathLabel(
      rawName,
      keys,
      resolveParentFieldLabel(rawName, fieldCatalog),
    );
  }

  if (!fieldCatalog.length) return rawName;

  const byRaw = fieldCatalog.find(field => field.rawName === rawName && !field.keys?.length)
    || fieldCatalog.find(field => field.rawName === rawName);
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
    if (sample?.result_content !== undefined && sample?.result_content !== null && sample?.result_content !== '') {
      row.result_content = sample.result_content;
    }
    return row;
  });

  const totalHit = Number(output.total ?? 0);
  const previewCount = rows.length;
  const condition = (
    message.input_data?.condition || undefined
  ) as AiSearchCondition | undefined;
  const conditionTags = mapConditionToFilterTags(condition, fieldCatalog);
  const isNaturalLanguage = output.query_summary?.source === 'natural_language';
  // 仅自然语言（大模型）检索展示「思考了 X 秒」；条件/字段检索不走模型，不展示
  const durationSeconds = message.duration_seconds;
  const thinkSeconds = !isNaturalLanguage
    || durationSeconds === null
    || durationSeconds === undefined
    || Number.isNaN(Number(durationSeconds))
    ? null
    : Math.max(0, Math.round(Number(durationSeconds)));

  return {
    conditions: conditionTags,
    rawCondition: condition || undefined,
    toolCount: isNaturalLanguage ? 3 : 2,
    thinkSeconds,
    title: '日志检索结果',
    totalHit,
    previewCount,
    showPreviewHint: totalHit > previewCount,
    columns,
    rows,
  };
};

/** 仅条件就绪、表格未到：撑起结果卡壳，正文 tablePending loading */
export const mapConditionPendingResult = (
  condition?: AiSearchCondition | null,
  fieldCatalog: SystemFieldRow[] = [],
  options?: { toolCount?: number },
): RetrievalResultPayload | undefined => {
  if (!condition || typeof condition !== 'object') return undefined;
  return {
    conditions: mapConditionToFilterTags(condition, fieldCatalog),
    rawCondition: condition,
    toolCount: options?.toolCount ?? 3,
    thinkSeconds: null,
    title: '日志检索结果',
    totalHit: 0,
    previewCount: 0,
    showPreviewHint: false,
    columns: [],
    rows: [],
    tablePending: true,
  };
};

/** LOG_SEARCH FAILED：用 input 条件撑起结果卡，正文展示失败态（对齐条件检索失败） */
export const mapLogSearchFailedToResult = (
  message: AiMessage,
  fieldCatalog: SystemFieldRow[] = [],
): RetrievalResultPayload => {
  const condition = (message.input_data?.condition || undefined) as AiSearchCondition | undefined;
  return {
    conditions: mapConditionToFilterTags(condition, fieldCatalog),
    rawCondition: condition || undefined,
    toolCount: 2,
    thinkSeconds: null,
    title: '日志检索结果',
    totalHit: 0,
    previewCount: 0,
    showPreviewHint: false,
    columns: [],
    rows: [],
  };
};

export interface MapAiMessageOptions {
  /** 来自 SYSTEM_SELECTION 的字段表，用于条件标签中文映射 */
  fieldCatalog?: SystemFieldRow[];
  /**
   * 后端尚未下发 visible 时，用内存标记强制隐藏卡片。
   * 有协议字段时以协议为准。
   */
  hiddenCardMessageIds?: Set<string>;
}

/** 解析消息卡片是否可见（读顶层 visible，缺省 true） */
export const resolveMessageVisible = (
  message: AiMessage,
  hiddenCardMessageIds?: Set<string>,
): boolean => {
  if (typeof message.visible === 'boolean') return message.visible;
  if (hiddenCardMessageIds?.has(message.uid)) return false;
  return true;
};

/** NL 消息在 SUCCESS 时若 output_data.error 非空，表示识别失败（非任务 FAILED） */
export const getNlRecognitionError = (message: AiMessage): AiNlRecognitionError | null => {
  if (message.message_type !== 'NATURAL_LANGUAGE_SEARCH' && message.message_type !== 'USER_INTENT') return null;
  const error = message.output_data?.error;
  if (!error || typeof error !== 'object') return null;
  const errorCode = String(error.error_code || '').trim();
  if (!errorCode) return null;
  return {
    error_code: errorCode,
    error_message: String(error.error_message || '').trim(),
    candidates: Array.isArray(error.candidates) ? error.candidates as AiSystemInfo[] : null,
  };
};

/**
 * 从 USER_INTENT output 解析派生消息名单。
 * 优先 derived_messages；否则回退 selection_message_uid / log_search_message_uid。
 */
export const resolveDerivedMessageRefs = (output?: AiUserIntentOutput | null): AiDerivedMessageRef[] => {
  if (!output) return [];
  const derived = Array.isArray(output.derived_messages)
    ? output.derived_messages.filter(item => Boolean(item?.message_uid))
    : [];
  if (derived.length) return derived;

  const refs: AiDerivedMessageRef[] = [];
  const selectionUid = String(output.selection_message_uid || '').trim();
  if (selectionUid) {
    refs.push({
      message_uid: selectionUid,
      message_type: 'SYSTEM_SELECTION',
    });
  }
  const logSearchUid = String(output.log_search_message_uid || '').trim();
  if (logSearchUid) {
    refs.push({
      message_uid: logSearchUid,
      message_type: 'LOG_SEARCH',
    });
  }
  return refs;
};

/** 意图是否已声明派生消息（含兼容 uid） */
export const hasIntentDerivedMessages = (message: AiMessage): boolean => {
  if (message.message_type !== 'USER_INTENT' && message.message_type !== 'NATURAL_LANGUAGE_SEARCH') {
    return false;
  }
  return resolveDerivedMessageRefs((message.output_data || {}) as AiUserIntentOutput).length > 0;
};

/**
 * 纯切系统：intent=select_system 且已解析 system_id，无检索条件 / 识别错误。
 * 此类消息不会续链 LOG_SEARCH，不应进入检索 loading。
 */
export const isPureSystemSwitchIntent = (message: AiMessage): boolean => {
  if (message.message_type !== 'USER_INTENT' || message.status !== 'SUCCESS') return false;
  if (getNlRecognitionError(message)) return false;
  const output = (message.output_data || {}) as AiUserIntentOutput;
  // 若派生名单里已有 LOG_SEARCH，说明同时还要检索，不算纯切系统
  const derived = resolveDerivedMessageRefs(output);
  if (derived.some(item => item.message_type === 'LOG_SEARCH')) return false;
  return (
    output.intent === 'select_system'
    && Boolean(String(output.system_id || '').trim())
    && !output.condition
  );
};

/**
 * 将后端消息映射为当前 UI 卡片模型。
 */
export const mapAiMessageToChatMessage = (
  message: AiMessage,
  options: MapAiMessageOptions = {},
): ChatMessage => {
  const fieldCatalog = options.fieldCatalog || [];
  const hiddenCardMessageIds = options.hiddenCardMessageIds || new Set<string>();
  const outputSystems = pickSystems(message.output_data);
  const systems = outputSystems.length ? outputSystems : pickSystems(message.input_data);
  const systemIds = systems.map(item => item.id);
  const visible = resolveMessageVisible(message, hiddenCardMessageIds);
  const baseMeta = {
    apiStatus: message.status,
    messageType: message.message_type,
    errorCode: message.error_code || undefined,
    errorMessage: message.error_message || undefined,
    parentMessageUid: message.parent_message_uid,
    visible,
  };

  if (message.message_type === 'SYSTEM_SELECTION') {
    // PROCESSING：已选系统可先出壳；建议/字段等 SUCCESS 再填
    if (message.status === 'PROCESSING' && systems.length) {
      return {
        id: message.uid,
        role: 'assistant',
        type: 'retrieval-guide',
        systems,
        systemIds,
        commonOperations: [],
        historicalOperations: [],
        standardFields: [],
        extensionFields: [],
        ...baseMeta,
      };
    }
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
    const candidateSystems = pickCandidateSystems(message);
    // 协议：SYSTEM_REQUIRED 有 candidates 时引导选系统
    // SYSTEM_UNAVAILABLE（无权限系统）：走权限错误卡，不引导选系统
    const shouldPromptSystemSelection = (
      recognitionError?.error_code === 'SYSTEM_REQUIRED' && candidateSystems.length > 0
    );
    if (shouldPromptSystemSelection) {
      return {
        id: message.uid,
        role: 'assistant',
        type: 'select-system',
        status: 'pending',
        selectionReason: 'disambiguate',
        systems: candidateSystems,
        systemIds: candidateSystems.map(item => item.id),
        candidateSystems,
        content: queryText,
        aiMessage: recognitionError?.error_message || undefined,
        ...baseMeta,
        errorCode: recognitionError?.error_code || baseMeta.errorCode,
      };
    }
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
        errorCode: recognitionError.error_code || baseMeta.errorCode,
      };
    }
    // 识别成功：条件先出壳；表格等子 LOG_SEARCH（有子卡后本卡不再渲染结果）
    const nlCondition = message.status === 'SUCCESS'
      ? (message.output_data?.condition as AiSearchCondition | null | undefined)
      : undefined;
    return {
      id: message.uid,
      role: 'assistant',
      type: 'retrieval-result',
      content: queryText,
      result: mapConditionPendingResult(nlCondition, fieldCatalog),
      ...baseMeta,
    };
  }

  if (message.message_type === 'USER_INTENT') {
    const queryText = String(message.input_data?.query_text ?? '');
    const output = ((message.output_data || {}) as AiUserIntentOutput);
    const recognitionError = getNlRecognitionError(message);
    const candidateSystems = pickCandidateSystems(message);
    const resolvedSystemId = String(output.system_id || '').trim();
    const hasDerived = hasIntentDerivedMessages(message);
    const shouldPromptSystemSelection = (
      (recognitionError?.error_code === 'SYSTEM_REQUIRED' && candidateSystems.length > 0)
      || (output.intent === 'select_system' && !resolvedSystemId)
    );

    if (shouldPromptSystemSelection) {
      let systemPromptTip: string | undefined;
      if (recognitionError?.error_code === 'SYSTEM_REQUIRED') {
        systemPromptTip = recognitionError?.error_message || undefined;
      } else if (output.message) {
        systemPromptTip = String(output.message);
      }
      return {
        id: message.uid,
        role: 'assistant',
        type: 'select-system',
        status: 'pending',
        selectionReason: 'disambiguate',
        systems: candidateSystems,
        systemIds: candidateSystems.map(item => item.id),
        candidateSystems,
        content: queryText,
        aiMessage: systemPromptTip,
        intent: output.intent,
        hasDerivedMessages: hasDerived,
        ...baseMeta,
        errorCode: recognitionError?.error_code || baseMeta.errorCode,
      };
    }

    if (recognitionError) {
      return {
        id: message.uid,
        role: 'assistant',
        type: 'retrieval-result',
        content: queryText,
        result: undefined,
        aiMessage: output.message ? String(output.message) : undefined,
        intent: output.intent,
        candidateSystems,
        hasDerivedMessages: hasDerived,
        recognitionError: {
          code: recognitionError.error_code,
          message: recognitionError.error_message,
        },
        ...baseMeta,
        errorCode: recognitionError.error_code || baseMeta.errorCode,
      };
    }

    // 纯切系统：不渲染确认气泡；检索引导由 selection / derived SYSTEM_SELECTION 承接
    if (isPureSystemSwitchIntent(message)) {
      return {
        id: message.uid,
        role: 'assistant',
        type: 'text',
        content: '',
        intent: output.intent,
        hasDerivedMessages: hasDerived,
        ...baseMeta,
      };
    }

    // 意图成功且已识别条件：先出条件区，表格等派生 LOG_SEARCH
    const pendingResult = message.status === 'SUCCESS'
      ? mapConditionPendingResult(output.condition, fieldCatalog)
      : undefined;

    return {
      id: message.uid,
      role: 'assistant',
      type: 'retrieval-result',
      content: queryText,
      result: pendingResult,
      aiMessage: output.message ? String(output.message) : undefined,
      intent: output.intent,
      candidateSystems,
      hasDerivedMessages: hasDerived,
      ...baseMeta,
    };
  }

  if (message.message_type === 'LOG_SEARCH') {
    let result: RetrievalResultPayload | undefined;
    if (message.status === 'SUCCESS') {
      result = mapLogSearchOutputToResult(message, fieldCatalog);
    } else if (message.status === 'PROCESSING') {
      result = mapConditionPendingResult(
        message.input_data?.condition as AiSearchCondition | undefined,
        fieldCatalog,
        { toolCount: 2 },
      );
    } else if (message.status === 'FAILED') {
      result = mapLogSearchFailedToResult(message, fieldCatalog);
    }
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
