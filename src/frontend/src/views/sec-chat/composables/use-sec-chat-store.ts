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
import { computed, ref } from 'vue';

import { buildMockRetrievalResult } from '../audit-log-retrieval/utils/build-mock-result';
import type {
  Conversation,
  Group,
  SelectedSystem,
} from '../types';

const createEmptyConversation = (partial: Omit<Conversation, 'systemIds' | 'systems' | 'messages'> & Partial<Conversation>): Conversation => ({
  systemIds: [],
  systems: [],
  messages: [],
  ...partial,
});

const sidebarCollapsed = ref(false);
const activeConversationId = ref<string | null>(null);

const groups = ref<Group[]>([
  { id: 'g1', name: '审计日志检索' },
  { id: 'g2', name: '风险分析' },
  { id: 'g3', name: '风险解读' },
  { id: 'g4', name: '报告解读' },
]);

const conversations = ref<Conversation[]>([
  createEmptyConversation({
    id: '1',
    title: '安全态势总结',
    pinned: false,
    createdAt: Date.now() - 86400000,
  }),
  createEmptyConversation({
    id: '2',
    title: 'Q2季度主机分析报告',
    pinned: false,
    createdAt: Date.now() - 172800000,
  }),
  createEmptyConversation({
    id: '3',
    title: '总结本月安全事件',
    pinned: false,
    createdAt: Date.now() - 259200000,
  }),
  createEmptyConversation({
    id: '4',
    title: '主机历史行为分析',
    pinned: false,
    groupName: '审计日志检索',
    sceneType: 'log',
    createdAt: Date.now() - 345600000,
  }),
  createEmptyConversation({
    id: '5',
    title: '主机历史行为',
    pinned: false,
    groupName: '审计日志检索',
    sceneType: 'log',
    createdAt: Date.now() - 432000000,
  }),
  createEmptyConversation({
    id: '6',
    title: '本周风险趋势分析',
    pinned: false,
    groupName: '风险分析',
    createdAt: Date.now() - 518400000,
  }),
  createEmptyConversation({
    id: '7',
    title: '高危风险分布统计',
    pinned: false,
    groupName: '风险分析',
    createdAt: Date.now() - 604800000,
  }),
  createEmptyConversation({
    id: '8',
    title: '风险处置优先级建议',
    pinned: false,
    groupName: '风险分析',
    createdAt: Date.now() - 691200000,
  }),
  createEmptyConversation({
    id: '9',
    title: '主机安全检查',
    pinned: false,
    groupName: '报告解读',
    createdAt: Date.now() - 777600000,
  }),
]);

const activeConversation = computed(() => (
  conversations.value.find(c => c.id === activeConversationId.value) || null
));

const ensureLogConversationMessages = (conversationId: string) => {
  const conv = conversations.value.find(c => c.id === conversationId);
  if (!conv || conv.sceneType !== 'log' || conv.messages.length > 0) return;
  conv.messages = [
    {
      id: `${conv.id}-user`,
      role: 'user',
      type: 'text',
      content: '审计日志检索',
    },
    {
      id: `${conv.id}-select-system`,
      role: 'assistant',
      type: 'select-system',
      status: 'pending',
      systemIds: [],
      systems: [],
    },
  ];
};

const createLogConversation = (prompt: string) => {
  const id = `log-${Date.now()}`;
  const displayText = prompt === '请帮我检索审计日志' ? '审计日志检索' : prompt;
  const title = displayText.length > 20 ? `${displayText.slice(0, 20)}...` : displayText;
  const conversation: Conversation = {
    id,
    title,
    pinned: false,
    groupName: '审计日志检索',
    sceneType: 'log',
    systemIds: [],
    systems: [],
    messages: [
      {
        id: `${id}-user`,
        role: 'user',
        type: 'text',
        content: displayText,
      },
      {
        id: `${id}-select-system`,
        role: 'assistant',
        type: 'select-system',
        status: 'pending',
        systemIds: [],
        systems: [],
      },
    ],
    createdAt: Date.now(),
  };
  conversations.value.unshift(conversation);
  activeConversationId.value = id;
  return conversation;
};

const findSelectSystemMessage = (conv: Conversation, messageId?: string) => {
  if (messageId) {
    return conv.messages.find(m => m.id === messageId && m.type === 'select-system');
  }
  return [...conv.messages].reverse().find(m => m.type === 'select-system');
};

export function useSecChatStore() {
  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  };

  const setActiveConversation = (id: string | null) => {
    activeConversationId.value = id;
    if (!id) return;
    ensureLogConversationMessages(id);
  };

  const deleteConversation = (id: string) => {
    const idx = conversations.value.findIndex(c => c.id === id);
    if (idx === -1) return;
    conversations.value.splice(idx, 1);
    if (activeConversationId.value === id) {
      activeConversationId.value = null;
    }
  };

  const pinConversation = (id: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv) conv.pinned = !conv.pinned;
  };

  const updateConversationGroup = (id: string, groupName?: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv) conv.groupName = groupName;
  };

  const updateConversationTitle = (id: string, title: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv) conv.title = title;
  };

  const updateGroups = (newGroups: Group[]) => {
    groups.value = newGroups;
  };

  const deleteGroup = (groupName: string, keepConversations: boolean) => {
    groups.value = groups.value.filter(g => g.name !== groupName);
    if (!keepConversations) {
      conversations.value = conversations.value.filter(c => c.groupName !== groupName);
      if (activeConversationId.value && !conversations.value.find(c => c.id === activeConversationId.value)) {
        activeConversationId.value = null;
      }
    } else {
      conversations.value = conversations.value.map(conv => (
        conv.groupName === groupName ? { ...conv, groupName: undefined } : conv
      ));
    }
  };

  const confirmSystem = (
    messageId: string,
    systemIds: string[],
    systems: SelectedSystem[],
  ) => {
    const conv = activeConversation.value;
    if (!conv) return;
    const msg = findSelectSystemMessage(conv, messageId);
    if (!msg) return;
    conv.systemIds = systemIds;
    conv.systems = systems;
    // 移除选择卡片，追加检索引导卡片
    conv.messages = conv.messages.filter(item => item.id !== msg.id);
    conv.messages.push({
      id: `${conv.id}-retrieval-guide`,
      role: 'assistant',
      type: 'retrieval-guide',
      systems: [...systems],
      systemIds: [...systemIds],
    });
  };

  const closeSelectSystem = (messageId: string) => {
    const conv = activeConversation.value;
    if (!conv) return;
    // 关闭后移除选择卡片消息
    conv.messages = conv.messages.filter(item => item.id !== messageId);
  };

  const reselectSystem = () => {
    const conv = activeConversation.value;
    if (!conv) return;
    conv.messages = conv.messages.filter(item => item.type !== 'retrieval-guide' && item.type !== 'select-system');
    conv.messages.push({
      id: `${conv.id}-select-system-${Date.now()}`,
      role: 'assistant',
      type: 'select-system',
      status: 'pending',
      systemIds: [...conv.systemIds],
      systems: [...conv.systems],
    });
  };

  /** 发送检索查询：追加用户气泡 + 结构化结果卡（本阶段 mock） */
  const sendLogQuery = (content: string) => {
    const conv = activeConversation.value;
    if (!conv) return;
    const text = content.trim();
    if (!text) return;

    const stamp = Date.now();
    conv.messages.push({
      id: `${conv.id}-query-${stamp}`,
      role: 'user',
      type: 'text',
      content: text,
    });
    conv.messages.push({
      id: `${conv.id}-result-${stamp}`,
      role: 'assistant',
      type: 'retrieval-result',
      content: text,
      result: buildMockRetrievalResult(text),
    });
  };

  return {
    sidebarCollapsed,
    activeConversationId,
    groups,
    conversations,
    activeConversation,
    toggleSidebar,
    setActiveConversation,
    deleteConversation,
    pinConversation,
    updateConversationGroup,
    updateConversationTitle,
    updateGroups,
    deleteGroup,
    createLogConversation,
    confirmSystem,
    closeSelectSystem,
    reselectSystem,
    sendLogQuery,
  };
}
