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
const blockChildTagPattern = /^(H[1-6]|TABLE|BLOCKQUOTE|HR|UL|OL|DIV|PRE|SECTION|ARTICLE)$/i;

export const sanitizeEditorHtml = (content: string) => {
  if (!content) return content;
  const normalizedContent = content
    .replace(/\uFEFF/g, '')
    .replace(/(<hr\s*\/?>)\s*<\/p>/gi, '$1')
    .replace(/([^>])\n(<(?:strong|br|em|code|span)\b)/gi, '$1<br />$2');
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div>${normalizedContent}</div>`, 'text/html');
  const container = doc.body.firstElementChild as HTMLElement | null;
  if (!container) {
    return content
      .replace(/\\n/g, '</p><p>')
      .replace(/\r?\n/g, '</p><p>');
  }

  const tables = Array.from(container.querySelectorAll('table')) as HTMLTableElement[];
  tables.forEach((table) => {
    table.classList.add('report-table');
    table.querySelectorAll('td p, th p').forEach((paragraph) => {
      const cell = paragraph.parentNode;
      if (!cell) return;
      while (paragraph.firstChild) {
        cell.insertBefore(paragraph.firstChild, paragraph);
      }
      cell.removeChild(paragraph);
    });
    if (!table.parentElement?.classList.contains('ql-report-table')) {
      const wrapper = doc.createElement('div');
      wrapper.className = 'ql-report-table';
      table.parentNode?.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    }
  });

  // <p> 内嵌 h2/table/blockquote 等块级标签时，浏览器与 Quill 都会解析异常
  const invalidParagraphs = Array.from(container.querySelectorAll('p')) as HTMLElement[];
  invalidParagraphs.forEach((paragraph) => {
    const hasBlockChild = Array.from(paragraph.children)
      .some(child => blockChildTagPattern.test(child.tagName));
    if (!hasBlockChild) return;
    const parent = paragraph.parentNode;
    if (!parent) return;
    while (paragraph.firstChild) {
      parent.insertBefore(paragraph.firstChild, paragraph);
    }
    parent.removeChild(paragraph);
  });

  const blockquotes = Array.from(container.querySelectorAll('blockquote')) as HTMLElement[];
  blockquotes.forEach((blockquote) => {
    const lines: string[] = [];
    const paragraphs = Array.from(blockquote.querySelectorAll('p'));
    if (paragraphs.length) {
      paragraphs.forEach((paragraph) => {
        const text = (paragraph.textContent || '').trim();
        if (text) lines.push(text);
      });
    } else {
      const text = (blockquote.textContent || '').trim();
      if (text) lines.push(text);
    }
    const replacement = doc.createElement('p');
    replacement.className = 'report-blockquote';
    replacement.textContent = lines.join('\n');
    blockquote.parentNode?.replaceChild(replacement, blockquote);
  });

  const headings = Array.from(container.querySelectorAll('h2, h3')) as HTMLElement[];
  headings.forEach((heading) => {
    const text = (heading.textContent || '').trim();
    const label = heading.querySelector('strong')?.textContent?.trim() || '';
    if (label === '分析' && text.length > 30) {
      const paragraph = doc.createElement('p');
      paragraph.innerHTML = heading.innerHTML;
      heading.parentNode?.replaceChild(paragraph, heading);
    }
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
        node.nodeValue = normalizedText.replace(/\r?\n/g, '');
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
