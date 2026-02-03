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
export const sanitizeEditorHtml = (content: string) => {
  if (!content) return content;
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div>${content}</div>`, 'text/html');
  const container = doc.body.firstElementChild as HTMLElement | null;
  if (!container) {
    return content
      .replace(/\\n/g, '</p><p>')
      .replace(/\r?\n/g, '</p><p>');
  }

  const tables = Array.from(container.querySelectorAll('table')) as HTMLTableElement[];
  tables.forEach((table) => {
    const rows = Array.from(table.querySelectorAll('tr'));
    const fragment = doc.createDocumentFragment();
    rows.forEach((row) => {
      const cells = Array.from(row.querySelectorAll('th,td')) as HTMLElement[];
      if (!cells.length) return;
      const line = cells
        .map(cell => (cell.textContent || '').trim())
        .filter(Boolean)
        .join(' | ');
      if (!line) return;
      const paragraph = doc.createElement('p');
      paragraph.textContent = line;
      fragment.appendChild(paragraph);
    });
    table.parentNode?.insertBefore(fragment, table);
    table.parentNode?.removeChild(table);
  });

  const walker = doc.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    const nextNode = walker.nextNode();
    const textValue = node.nodeValue || '';
    if (textValue && (/[\r\n]/.test(textValue) || textValue.includes('\\n'))) {
      const parentElement = node.parentNode as HTMLElement | null;
      const inParagraph = parentElement?.closest('p');
      if (inParagraph) {
        const normalizedText = textValue.replace(/\\n/g, '\n');
        if (normalizedText.trim() === '') {
          node.nodeValue = normalizedText.replace(/\r?\n/g, '');
        } else {
          const parts = normalizedText.split(/\r?\n+/);
          if (parts.length <= 1) {
            node.nodeValue = normalizedText;
          } else {
            const parent = inParagraph.parentNode;
            if (!parent) {
              node.nodeValue = normalizedText.replace(/\r?\n/g, '');
            } else {
              const fragment = doc.createDocumentFragment();
              parts.forEach((part, index) => {
                const targetParagraph = index === 0
                  ? inParagraph
                  : doc.createElement('p');
                if (index > 0) {
                  fragment.appendChild(targetParagraph);
                }
                if (part) {
                  targetParagraph.appendChild(doc.createTextNode(part));
                }
              });
              node.nodeValue = '';
              parent.insertBefore(fragment, inParagraph.nextSibling);
            }
          }
        }
      } else {
        node.nodeValue = textValue.replace(/\\n/g, '').replace(/\r?\n/g, '');
      }
    }
    node = nextNode;
  }

  const blockSelector = 'p,div,section,article,header,footer,aside,nav,h1,h2,h3,h4,h5,h6,pre,blockquote';
  const listItems = Array.from(container.querySelectorAll('li')) as HTMLElement[];
  listItems.forEach((li) => {
    // 扁平化 li 内的嵌套列表，避免 Quill 渲染丢失
    const nestedLists = Array.from(li.children)
      .filter(child => child.tagName === 'UL' || child.tagName === 'OL') as HTMLElement[];
    nestedLists.forEach((list) => {
      const nestedItems = Array.from(list.children)
        .filter(child => child.tagName === 'LI') as HTMLElement[];
      if (!nestedItems.length) {
        list.parentNode?.removeChild(list);
        return;
      }
      const fragment = doc.createDocumentFragment();
      nestedItems.forEach((item, index) => {
        const text = (item.textContent || '').trim();
        if (!text) return;
        const span = doc.createElement('span');
        span.textContent = `• ${text}`;
        fragment.appendChild(span);
        if (index < nestedItems.length - 1) {
          fragment.appendChild(doc.createElement('br'));
        }
      });
      li.insertBefore(fragment, list);
      list.parentNode?.removeChild(list);
    });

    const blocks = Array.from(li.querySelectorAll(blockSelector)) as HTMLElement[];
    blocks.forEach((block) => {
      while (block.firstChild) {
        li.insertBefore(block.firstChild, block);
      }
      block.parentNode?.removeChild(block);
    });
  });

  return container.innerHTML;
};
