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
import DOMPurify from 'dompurify';
import MarkdownIt from 'markdown-it';

import { sanitizeEditorHtml } from '@views/risk-manage/detail/components/event-report/editor-utils';

export const PREVIEW_HTML_OPTIONS = {
  ADD_ATTR: ['class', 'colspan', 'rowspan'],
};

const markdownRenderer = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
});

/** 是否为 Quill 保存的 HTML 内容 */
export const isQuillHtmlContent = (content: string) => {
  const trimmed = content.trim();
  if (!trimmed) return false;
  return /^<(?:p|h[1-6]|div|ul|ol|blockquote|table|hr)\b/i.test(trimmed)
    || trimmed.includes('ql-report-table');
};

/** 编辑/预览统一：Markdown 或 HTML 转为可渲染 HTML */
export const toReportDisplayHtml = (content: string) => {
  if (!content) return '';
  if (isQuillHtmlContent(content) || /<table\b/i.test(content)) {
    return sanitizeEditorHtml(content);
  }
  const rendered = markdownRenderer.render(content);
  return sanitizeEditorHtml(rendered);
};

export const toPreviewHtml = (content: string) => {
  const html = toReportDisplayHtml(content);
  return DOMPurify.sanitize(html, PREVIEW_HTML_OPTIONS);
};
