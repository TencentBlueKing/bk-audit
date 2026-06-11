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
import Quill from 'quill';

const BlockEmbed = Quill.import('blots/block/embed') as any;

const TABLE_SANITIZE_OPTIONS = {
  ALLOWED_TAGS: ['table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'strong', 'em', 'br', 'span', 'code'],
  ALLOWED_ATTR: ['class', 'colspan', 'rowspan'],
};

const sanitizeTableHtml = (html: string) => DOMPurify.sanitize(html, TABLE_SANITIZE_OPTIONS);

export const hasTableContent = (html: string) => /<table\b/i.test(html);

export const buildReportTableHtml = (rowCount: number, colCount: number) => {
  const rows = Math.max(2, Math.min(rowCount, 20));
  const cols = Math.max(1, Math.min(colCount, 10));
  const headerCells = Array.from({ length: cols }, (_, index) => `<th>列${index + 1}</th>`).join('');
  const bodyRows = Array.from({ length: rows - 1 }, () => (
    `<tr>${Array.from({ length: cols }, () => '<td><br></td>').join('')}</tr>`
  )).join('');
  return `<table class="report-table"><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}</tbody></table>`;
};

const enableTableCellEditing = (root: HTMLElement) => {
  root.querySelectorAll('td, th').forEach((cell) => {
    cell.setAttribute('contenteditable', 'true');
  });
};

class ReportTableBlot extends BlockEmbed {
  static create(value: string) {
    const node = super.create() as HTMLElement;
    node.setAttribute('contenteditable', 'false');
    const tableHtml = sanitizeTableHtml(value);
    node.innerHTML = tableHtml.includes('<table')
      ? tableHtml
      : `<table class="report-table">${tableHtml}</table>`;
    const table = node.querySelector('table');
    table?.classList.add('report-table');
    enableTableCellEditing(node);
    return node;
  }

  static value(node: HTMLElement) {
    const table = node.querySelector('table');
    return table ? table.outerHTML : node.innerHTML;
  }
}

ReportTableBlot.blotName = 'reportTable';
ReportTableBlot.tagName = 'div';
ReportTableBlot.className = 'ql-report-table';

Quill.register(ReportTableBlot);

interface ReportQuillInstance {
  getSelection: (focus?: boolean) => { index: number; length: number } | null;
  getLength: () => number;
  insertEmbed: (index: number, type: string, value: string, source?: string) => void;
  insertText: (index: number, text: string, source?: string) => void;
  setSelection: (index: number, length?: number, source?: string) => void;
}

export const insertReportTable = (
  quill: ReportQuillInstance,
  rowCount: number,
  colCount: number,
) => {
  const range = quill.getSelection(true);
  const index = range ? range.index : quill.getLength();
  const html = buildReportTableHtml(rowCount, colCount);
  quill.insertEmbed(index, 'reportTable', html, 'user');
  quill.insertText(index + 1, '\n', 'user');
  quill.setSelection(index + 2, 0, 'user');
};

interface ReportTableMatcherQuill {
  clipboard: {
    addMatcher: (selector: string, matcher: (node: Node) => any) => void;
  };
}

export const registerReportTableMatcher = (quill: ReportTableMatcherQuill) => {
  const Delta = Quill.import('delta') as any;

  quill.clipboard.addMatcher('TABLE', (node: Node) => {
    const table = node as HTMLTableElement;
    table.classList.add('report-table');
    return new Delta().insert({ reportTable: table.outerHTML });
  });

  quill.clipboard.addMatcher('div.ql-report-table', (node: Node) => {
    const element = node as HTMLElement;
    const table = element.querySelector('table');
    if (!table) {
      return new Delta();
    }
    table.classList.add('report-table');
    return new Delta().insert({ reportTable: table.outerHTML });
  });
};

export default ReportTableBlot;
