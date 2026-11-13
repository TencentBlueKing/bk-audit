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

import type { BksecTicketPreviewRow } from '@model/bksec/ticket-preview';

export interface PreviewField {
  id: string;
  name: string;
}

export interface LocalPreviewInput {
  fieldValues: Record<string, string>;
  fields: PreviewField[];
  riskTypeId?: string | null;
  riskTypeName?: string;
}

export interface RemotePreviewInput {
  riskTypeId?: string | null;
  riskTypeName?: string;
  fields: PreviewField[];
  response: Record<string, any>;
}

const LEVEL_LABEL: Record<string, string> = {
  HIGH: '高',
  MIDDLE: '中',
  MEDIUM: '中',
  LOW: '低',
};

const dash = (value: unknown) => {
  if (Array.isArray(value)) {
    const text = value.map(item => String(item ?? '').trim()).filter(Boolean)
      .join(', ');
    return text || '--';
  }
  const text = value === undefined || value === null ? '' : String(value).trim();
  return text || '--';
};

const variableToken = /\{\{\s*[^}]+\s*\}\}/g;

/** 新建没有风险数据，变量替换为空；去掉变量后整段为空则显示 --。 */
export const renderLocalField = (template?: string) => {
  if (!template || !String(template).trim()) return '--';
  return dash(String(template).replace(variableToken, ''));
};

const levelLabel = (value: unknown) => {
  const text = String(value || '').trim();
  return LEVEL_LABEL[text] || text || '--';
};

const typeLabel = (name?: string, id?: string | null) => {
  if (!id && !name) return '--';
  if (name && id) return `${name}(${id})`;
  return name || String(id);
};

const extensionRows = (
  fields: PreviewField[],
  resolve: (fieldId: string) => string,
): BksecTicketPreviewRow[] => fields
  .filter(field => field.id && field.id !== 'operator')
  .map(field => ({
    key: field.id,
    label: field.name || field.id,
    value: dash(resolve(field.id)),
  }));

/** 新建没有风险数据。固定信息为空，已填工单字段按原文展示，变量替换为空。 */
export const buildLocalPreview = (input: LocalPreviewInput): BksecTicketPreviewRow[] => {
  const values = input.fieldValues || {};
  const rows: BksecTicketPreviewRow[] = [
    { key: 'ticket_id', label: '工单ID', value: '--' },
    { key: 'title', label: '工单标题', value: '--' },
    { key: 'deadline', label: '处理截止时间', value: '--' },
    { key: 'submitted_at', label: '提单时间', value: '--' },
    { key: 'status', label: '工单状态', value: '--', kind: 'status' },
    { key: 'level', label: '风险等级', value: '--', kind: 'level' },
    { key: 'risk_type', label: '风险类型', value: typeLabel(input.riskTypeName, input.riskTypeId) },
    { key: 'notice_users', label: '关注人', value: '--' },
    { key: 'event_time', label: '风险发现时间', value: '--' },
    { key: 'channel', label: '风险发现途径', value: '--' },
    { key: 'current_operator', label: '当前责任人', value: '--' },
    { key: 'operator', label: '初始责任人', value: renderLocalField(values.operator) },
    { key: 'org', label: '当前责任人所属组织', value: '--' },
    { key: 'description', label: '风险描述', value: '--', kind: 'multiline' },
    { key: 'guidance', label: '处理指引', value: '--', kind: 'multiline' },
  ];
  rows.push(...extensionRows(input.fields || [], fieldId => renderLocalField(values[fieldId])));
  return rows;
};

interface RemoteTicketField {
  key: string;
  name: string;
  value: unknown;
}

interface PreviewSlot {
  rowKey: string;
  fieldKey: string;
  label: string;
  value: string;
  kind?: BksecTicketPreviewRow['kind'];
}

/** 接口把人员等数组存成 JSON 字符串，展示前还原成列表再交给 dash。 */
const parseJsonArray = (value: unknown) => {
  if (typeof value !== 'string') return value;
  const text = value.trim();
  if (!text.startsWith('[')) return value;
  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? parsed : value;
  } catch {
    return value;
  }
};

const normalizeTicketFields = (value: unknown): RemoteTicketField[] | null => {
  if (!Array.isArray(value)) return null;
  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return [];
    const record = item as Record<string, unknown>;
    const key = String(record.key ?? '').trim();
    if (!key) return [];
    return [{
      key,
      name: String(record.name ?? '').trim(),
      value: record.value,
    }];
  });
};

const emptySlot = (
  rowKey: string,
  label: string,
  kind?: BksecTicketPreviewRow['kind'],
): PreviewSlot => ({
  rowKey,
  fieldKey: rowKey,
  label,
  value: '--',
  kind,
});

const fieldSlot = (
  fields: Map<string, RemoteTicketField>,
  used: Set<string>,
  fieldKey: string,
  rowKey: string,
  fallbackLabel: string,
  kind?: BksecTicketPreviewRow['kind'],
  format: (value: unknown) => string = value => dash(parseJsonArray(value)),
): PreviewSlot => {
  const field = fields.get(fieldKey);
  if (!field) return emptySlot(rowKey, fallbackLabel, kind);
  used.add(fieldKey);
  return {
    rowKey,
    fieldKey,
    label: field.name || fallbackLabel,
    value: format(field.value),
    kind,
  };
};

const disambiguateLabels = (slots: PreviewSlot[]): BksecTicketPreviewRow[] => {
  const counts = new Map<string, number>();
  slots.forEach((slot) => {
    counts.set(slot.label, (counts.get(slot.label) || 0) + 1);
  });
  return slots.map(slot => ({
    key: slot.rowKey,
    label: (counts.get(slot.label) || 0) > 1 ? `${slot.label}（${slot.fieldKey}）` : slot.label,
    value: slot.value,
    ...(slot.kind ? { kind: slot.kind } : {}),
  }));
};

/** 预览接口 warnings。空数组不展示。 */
export const previewWarnings = (response?: Record<string, any>) => {
  const raw = response?.warnings;
  if (!Array.isArray(raw)) return [];
  return raw.map(item => String(item ?? '').trim()).filter(Boolean);
};

const mapFieldListPreview = (
  input: RemotePreviewInput,
  rawFields: RemoteTicketField[],
): BksecTicketPreviewRow[] => {
  const fields = new Map(rawFields.map(field => [field.key, field]));
  const used = new Set<string>();
  const slots: PreviewSlot[] = [
    emptySlot('ticket_id', '工单ID'),
    fieldSlot(fields, used, 'title', 'title', '工单标题'),
    fieldSlot(fields, used, 'deadline_time', 'deadline', '统一处理期限'),
    emptySlot('submitted_at', '提单时间'),
    emptySlot('status', '工单状态', 'status'),
    fieldSlot(fields, used, 'risk_level', 'level', '风险等级', 'level', value => levelLabel(parseJsonArray(value))),
    {
      rowKey: 'risk_type',
      fieldKey: 'risk_type',
      label: '风险类型',
      value: typeLabel(
        input.response?.risk_type_name || input.riskTypeName,
        input.response?.risk_type_id || input.riskTypeId,
      ),
    },
    fieldSlot(fields, used, 'current_followers', 'notice_users', '关注人'),
    fieldSlot(fields, used, 'event_time', 'event_time', '风险发现时间'),
    fieldSlot(fields, used, 'source_type', 'channel', '风险发现途径'),
    fieldSlot(fields, used, 'latest_operator', 'current_operator', '当前责任人'),
    fieldSlot(fields, used, 'operator', 'operator', '初始责任人'),
    fieldSlot(fields, used, 'department', 'org', '当前责任人所属组织'),
    fieldSlot(fields, used, 'risk_desc', 'description', '风险描述', 'multiline'),
    fieldSlot(fields, used, 'risk_guide', 'guidance', '处理指引', 'multiline'),
  ];
  rawFields.forEach((field) => {
    if (used.has(field.key)) return;
    slots.push({
      rowKey: field.key,
      fieldKey: field.key,
      label: field.name || field.key,
      value: dash(parseJsonArray(field.value)),
    });
  });
  return disambiguateLabels(slots);
};

const mapLegacyRemotePreview = (input: RemotePreviewInput): BksecTicketPreviewRow[] => {
  const ticket = input.response?.ticket || {};
  const header = input.response?.ticket_header || {};
  const attribute = ticket.risk_attribute || {};
  const rendered = ticket.fields || {};
  const rows: BksecTicketPreviewRow[] = [
    { key: 'ticket_id', label: '工单ID', value: dash(header.ticket_id) },
    { key: 'title', label: '工单标题', value: dash(header.title || attribute.title) },
    { key: 'deadline', label: '处理截止时间', value: dash(header.deadline) },
    { key: 'submitted_at', label: '提单时间', value: dash(header.submit_time) },
    { key: 'status', label: '工单状态', value: dash(header.status), kind: 'status' },
    { key: 'level', label: '风险等级', value: levelLabel(attribute.risk_level), kind: 'level' },
    {
      key: 'risk_type',
      label: '风险类型',
      value: typeLabel(
        input.response?.risk_type_name || input.riskTypeName,
        input.response?.risk_type_id || input.riskTypeId,
      ),
    },
    { key: 'notice_users', label: '关注人', value: dash(attribute.notice_users) },
    { key: 'event_time', label: '风险发现时间', value: dash(attribute.event_time) },
    { key: 'channel', label: '风险发现途径', value: dash(attribute.event_source) },
    { key: 'current_operator', label: '当前责任人', value: dash(attribute.current_operator) },
    { key: 'operator', label: '初始责任人', value: dash(rendered.operator) },
    { key: 'org', label: '当前责任人所属组织', value: dash(header.current_operator_org) },
    { key: 'description', label: '风险描述', value: dash(attribute.event_content), kind: 'multiline' },
    { key: 'guidance', label: '处理指引', value: dash(attribute.risk_guidance), kind: 'multiline' },
  ];
  rows.push(...extensionRows(input.fields || [], fieldId => rendered[fieldId]));
  return rows;
};

/** 编辑态预览：值只来自接口响应，缺值显示 --。fields 为数组时按 key 取值。 */
export const mapRemotePreview = (input: RemotePreviewInput): BksecTicketPreviewRow[] => {
  const fields = normalizeTicketFields(input.response?.ticket?.fields);
  if (fields) return mapFieldListPreview(input, fields);
  return mapLegacyRemotePreview(input);
};
