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

import aiIconUrl from '@images/ai.svg';

const Embed = Quill.import('blots/embed') as any;

// AI智能体数据接口
interface AIAgentData {
  prompt: string;
  id: string;
  name?: string;
  result?: string;
}

// 自定义AI智能体块 - 使用Embed blot以便insertEmbed可以工作
class AIAgentBlot extends Embed {
  static create(value: string | AIAgentData): HTMLElement {
    const node = super.create() as HTMLElement;

    // 处理value参数，确保是对象格式
    const data: AIAgentData = typeof value === 'object'
      ? value
      : { prompt: value || '', id: Date.now().toString() };

    node.setAttribute('data-type', 'ai-agent');
    node.setAttribute('data-prompt', data.prompt || '');
    node.setAttribute('data-id', data.id || Date.now().toString());
    if (data.name) {
      node.setAttribute('data-name', data.name);
    }
    if (data.result) {
      node.setAttribute('data-result', data.result);
    }
    node.setAttribute('contenteditable', 'false');

    // 转义HTML以防止XSS
    const escapeHtml = (text: string): string => DOMPurify.sanitize(text, { ALLOWED_TAGS: [] });

    // 创建块内容
    node.innerHTML = `
      <div class="ai-agent-block">
        <img class="ai-agent-ai" src="${aiIconUrl}" width="24" height="17" />
        <div class="ai-agent-content">
          <div class="ai-agent-prompt">${escapeHtml(data.prompt || '')}</div>
        </div>
      </div>
    `;

    return node;
  }

  static value(node: HTMLElement): AIAgentData {
    return {
      id: node.getAttribute('data-id') || '',
      prompt: node.getAttribute('data-prompt') || '',
      name: node.getAttribute('data-name') || undefined,
      result: node.getAttribute('data-result') || undefined,
    };
  }
}

AIAgentBlot.blotName = 'aiAgent';
AIAgentBlot.tagName = 'span';
AIAgentBlot.className = 'ql-ai-agent';

Quill.register(AIAgentBlot);

export default AIAgentBlot;

