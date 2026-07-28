<!--
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
-->
<template>
  <div class="sec-chat-page">
    <!-- 左侧侧边栏 -->
    <chat-sidebar
      :active-id="activeConversationId"
      :collapsed="sidebarCollapsed"
      :conversations="conversations"
      :groups="groups"
      @delete="handleDeleteConversation"
      @delete-group="handleDeleteGroup"
      @new-chat="handleNewChat"
      @pin="handlePinConversation"
      @select="handleSelectConversation"
      @toggle="toggleSidebar"
      @update-conv-title="handleUpdateConvTitle"
      @update-group="handleUpdateConversationGroup"
      @update-groups="handleUpdateGroups" />

    <!-- 右侧主区域：仅入口页 -->
    <div class="sec-chat-main">
      <chat-welcome
        @select-prompt="handleSelectPrompt" />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';
  import ChatSidebar from './components/chat-sidebar.vue';
  import ChatWelcome from './components/chat-welcome.vue';

  interface Conversation {
    id: string;
    title: string;
    pinned: boolean;
    groupName?: string;
    messages: any[];
    createdAt: number;
  }

  interface Group {
    id: string;
    name: string;
  }

  const sidebarCollapsed = ref(false);
  const activeConversationId = ref<string | null>(null);

  const groups = ref<Group[]>([
    { id: 'g1', name: '审计日志检索' },
    { id: 'g2', name: '风险分析' },
    { id: 'g3', name: '风险解读' },
    { id: 'g4', name: '报告解读' },
  ]);

  const conversations = ref<Conversation[]>([
    {
      id: '1',
      title: '安全态势总结',
      pinned: false,
      messages: [],
      createdAt: Date.now() - 86400000,
    },
    {
      id: '2',
      title: 'Q2季度主机分析报告',
      pinned: false,
      messages: [],
      createdAt: Date.now() - 172800000,
    },
    {
      id: '3',
      title: '总结本月安全事件',
      pinned: false,
      messages: [],
      createdAt: Date.now() - 259200000,
    },
    {
      id: '4',
      title: '主机历史行为分析',
      pinned: false,
      groupName: '审计日志检索',
      messages: [],
      createdAt: Date.now() - 345600000,
    },
    {
      id: '5',
      title: '主机历史行为',
      pinned: false,
      groupName: '审计日志检索',
      messages: [],
      createdAt: Date.now() - 432000000,
    },
    {
      id: '6',
      title: '本周风险趋势分析',
      pinned: false,
      groupName: '风险分析',
      messages: [],
      createdAt: Date.now() - 518400000,
    },
    {
      id: '7',
      title: '高危风险分布统计',
      pinned: false,
      groupName: '风险分析',
      messages: [],
      createdAt: Date.now() - 604800000,
    },
    {
      id: '8',
      title: '风险处置优先级建议',
      pinned: false,
      groupName: '风险分析',
      messages: [],
      createdAt: Date.now() - 691200000,
    },
    {
      id: '9',
      title: '主机安全检查',
      pinned: false,
      groupName: '报告解读',
      messages: [],
      createdAt: Date.now() - 777600000,
    },
  ]);

  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  };

  const handleNewChat = () => {
    activeConversationId.value = null;
  };

  const handleSelectConversation = (id: string) => {
    activeConversationId.value = id;
  };

  const handleDeleteConversation = (id: string) => {
    const idx = conversations.value.findIndex(c => c.id === id);
    if (idx !== -1) {
      conversations.value.splice(idx, 1);
      if (activeConversationId.value === id) {
        activeConversationId.value = null;
      }
    }
  };

  const handlePinConversation = (id: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv) {
      conv.pinned = !conv.pinned;
    }
  };

  const handleUpdateConversationGroup = (id: string, groupName?: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv) {
      conv.groupName = groupName;
    }
  };

  const handleUpdateConvTitle = (id: string, title: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv) {
      conv.title = title;
    }
  };

  const handleUpdateGroups = (newGroups: Group[]) => {
    groups.value = newGroups;
  };

  const handleDeleteGroup = (groupName: string, keepConversations: boolean) => {
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

  // 入口页提示词 / 输入：后续再接对话流程
  const handleSelectPrompt = () => {
    // TODO: 接入新对话流程
  };
</script>

<style lang="postcss" scoped>
  .sec-chat-page {
    display: flex;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background-color: #f5f7fa;

    .sec-chat-main {
      display: flex;
      min-width: 0;
      overflow: hidden;
      background-color: #f5f7fa;
      flex: 1;
      flex-direction: column;
    }
  }
</style>
