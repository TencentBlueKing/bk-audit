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

/** 转义 HTML，避免 JSON 注入 */
const escapeHtml = (text: string) => text
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

/** 尝试解析为非空 plain object（不含数组） */
export const tryParseJsonObject = (value: unknown): Record<string, unknown> | null => {
  if (value === undefined || value === null) return null;

  if (typeof value === 'object') {
    if (Array.isArray(value)) return null;
    const keys = Object.keys(value as Record<string, unknown>);
    if (!keys.length) return null;
    return value as Record<string, unknown>;
  }

  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) return null;
  try {
    const parsed = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
    if (!Object.keys(parsed).length) return null;
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
};

/**
 * 表格预览：仅保留第一个 key:value。
 * 嵌套 object/array 不展开完整内容，避免超长串撑破列宽 / tip 定位。
 * 最终仍由单元格 CSS ellipsis 按列宽裁剪。
 */
export const getJsonFirstPairPreview = (obj: Record<string, unknown>): string => {
  const key = Object.keys(obj)[0];
  if (key === undefined) return '';
  const value = obj[key];
  try {
    if (value !== null && typeof value === 'object') {
      return Array.isArray(value) ? `{"${key}":[...]}` : `{"${key}":{...}}`;
    }
    return JSON.stringify({ [key]: value });
  } catch {
    return `{"${key}":...}`;
  }
};

/** 格式化完整 JSON 文本（复制 / 纯文本兜底） */
export const getJsonPrettyText = (value: unknown): string => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const renderJsonValueHtml = (value: unknown, indent: number): string => {
  const pad = '  '.repeat(indent);
  const nextPad = '  '.repeat(indent + 1);

  if (value === null) {
    return '<span class="json-literal">null</span>';
  }
  if (typeof value === 'boolean' || typeof value === 'number') {
    return `<span class="json-literal">${escapeHtml(String(value))}</span>`;
  }
  if (typeof value === 'string') {
    return `<span class="json-string">"${escapeHtml(value)}"</span>`;
  }
  if (Array.isArray(value)) {
    if (!value.length) return '[]';
    const items = value
      .map(item => `${nextPad}${renderJsonValueHtml(item, indent + 1)}`)
      .join(',\n');
    return `[\n${items}\n${pad}]`;
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length) return '{}';
    const lines = entries.map(([key, child], index) => {
      const comma = index < entries.length - 1 ? ',' : '';
      return `${nextPad}<span class="json-key">"${escapeHtml(key)}"</span>: ${renderJsonValueHtml(child, indent + 1)}${comma}`;
    });
    return `{\n${lines.join('\n')}\n${pad}}`;
  }
  return `<span class="json-string">"${escapeHtml(String(value))}"</span>`;
};

/** 生成带简单语法高亮的 JSON HTML（key 蓝色） */
export const getJsonHighlightHtml = (value: unknown): string => renderJsonValueHtml(value, 0);
