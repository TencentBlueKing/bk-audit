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
  strategyName?: string;
  openedAt: string;
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
  const text = value === undefined || value === null ? '' : String(value).trim();
  return text || '--';
};

const pad = (value: number) => String(value).padStart(2, '0');

const formatDate = (date: Date) => (
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
);

export const renderLocalTemplate = (template?: string) => {
  if (!template || !String(template).trim()) return '--';
  const rendered = String(template).replace(/\{\{\s*[^}]+\s*\}\}/g, '--').trim();
  return rendered || '--';
};

const addDays = (value: string, days: number) => {
  const date = new Date(value.replace(/-/g, '/'));
  if (Number.isNaN(date.getTime())) return '--';
  date.setDate(date.getDate() + days);
  return formatDate(date);
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

/** 新建策略没有 risk_id，本地生成固定项。变量替换为 --。 */
export const buildLocalPreview = (input: LocalPreviewInput): BksecTicketPreviewRow[] => {
  const stamp = (input.openedAt || '').replace(/\D/g, '') || String(Date.now());
  const values = input.fieldValues || {};
  const rows: BksecTicketPreviewRow[] = [
    { key: 'ticket_id', label: '工单ID', value: `W${stamp}` },
    { key: 'title', label: '工单标题', value: dash(input.strategyName || input.riskTypeName) },
    { key: 'deadline', label: '处理截止时间', value: addDays(input.openedAt, 3) },
    { key: 'submitted_at', label: '提单时间', value: dash(input.openedAt) },
    { key: 'status', label: '工单状态', value: '待处理', kind: 'status' },
    { key: 'level', label: '风险等级', value: '--', kind: 'level' },
    { key: 'risk_type', label: '风险类型', value: typeLabel(input.riskTypeName, input.riskTypeId) },
    { key: 'notice_users', label: '关注人', value: '--' },
    { key: 'event_time', label: '风险发现时间', value: '--' },
    { key: 'channel', label: '风险发现途径', value: '审计中心' },
    { key: 'current_operator', label: '当前责任人', value: '--' },
    { key: 'operator', label: '初始责任人', value: renderLocalTemplate(values.operator) },
    { key: 'org', label: '当前责任人所属组织', value: '--' },
    { key: 'description', label: '风险描述', value: '--', kind: 'multiline' },
    { key: 'guidance', label: '处理指引', value: '--', kind: 'multiline' },
  ];
  rows.push(...extensionRows(input.fields || [], fieldId => renderLocalTemplate(values[fieldId])));
  return rows;
};

/** 编辑态预览：展示行按需求固定，值来自协议响应，不使用协议里的 mock 说明。 */
export const mapRemotePreview = (input: RemotePreviewInput): BksecTicketPreviewRow[] => {
  const ticket = input.response?.ticket || {};
  const header = input.response?.ticket_header || {};
  const attribute = ticket.risk_attribute || {};
  const rendered = ticket.fields || {};
  const rows: BksecTicketPreviewRow[] = [
    { key: 'ticket_id', label: '工单ID', value: dash(header.ticket_id) },
    { key: 'title', label: '工单标题', value: dash(header.title || attribute.title) },
    { key: 'deadline', label: '处理截止时间', value: dash(header.deadline) },
    { key: 'submitted_at', label: '提单时间', value: dash(header.submit_time) },
    { key: 'status', label: '工单状态', value: '待处理', kind: 'status' },
    { key: 'level', label: '风险等级', value: levelLabel(attribute.risk_level), kind: 'level' },
    {
      key: 'risk_type',
      label: '风险类型',
      value: typeLabel(input.riskTypeName || input.response?.risk_type_name, input.riskTypeId || input.response?.risk_type_id),
    },
    { key: 'notice_users', label: '关注人', value: dash(attribute.notice_users) },
    { key: 'event_time', label: '风险发现时间', value: dash(attribute.event_time) },
    { key: 'channel', label: '风险发现途径', value: dash(attribute.event_source || '审计中心') },
    { key: 'current_operator', label: '当前责任人', value: dash(attribute.current_operator) },
    { key: 'operator', label: '初始责任人', value: dash(rendered.operator) },
    { key: 'org', label: '当前责任人所属组织', value: dash(header.current_operator_org) },
    { key: 'description', label: '风险描述', value: dash(attribute.event_content), kind: 'multiline' },
    { key: 'guidance', label: '处理指引', value: dash(attribute.risk_guidance), kind: 'multiline' },
  ];
  rows.push(...extensionRows(input.fields || [], fieldId => rendered[fieldId]));
  return rows;
};
