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

    <!-- 右侧主区域 -->
    <div class="sec-chat-main">
      <!-- 欢迎页（无活跃对话时） -->
      <chat-welcome
        v-if="!activeConversationId"
        @select-prompt="handleSelectPrompt" />

      <!-- 聊天区域（有活跃对话时） -->
      <chat-window
        v-else
        :loading="isLoading"
        :messages="currentMessages"
        @refresh-answer="handleRefreshAnswer"
        @send="handleSendMessage"
        @stop="handleStopGenerate" />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref, computed } from 'vue';
  import ChatSidebar from './components/chat-sidebar.vue';
  import ChatWelcome from './components/chat-welcome.vue';
  import ChatWindow from './components/chat-window.vue';

  // 对话类型定义
  interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: number;
    type?: 'case' | 'query';
    thinkingTime?: string;
  }

  interface Conversation {
    id: string;
    title: string;
    pinned: boolean;
    groupName?: string;
    messages: Message[];
    createdAt: number;
  }

  interface Group {
    id: string;
    name: string;
  }

  // 侧边栏折叠状态
  const sidebarCollapsed = ref(false);

  // 当前活跃对话ID
  const activeConversationId = ref<string | null>(null);

  // 加载状态
  const isLoading = ref(false);

  // 分组列表
  const groups = ref<Group[]>([
    { id: 'g1', name: '安全事件' },
    { id: 'g2', name: '主机分析' },
  ]);

  // 对话列表（模拟数据）
  const conversations = ref<Conversation[]>([
    {
      id: '1',
      title: '分析 10.0.1.5 异常行为',
      pinned: true,
      messages: [],
      createdAt: Date.now() - 86400000,
    },
    {
      id: '2',
      title: '高危风险告警解读',
      pinned: true,
      messages: [],
      createdAt: Date.now() - 172800000,
    },
    {
      id: '3',
      title: '当前安全态势',
      pinned: true,
      messages: [],
      createdAt: Date.now() - 259200000,
    },
    {
      id: '4',
      title: 'Q2季度主机分析报告',
      pinned: false,
      messages: [],
      createdAt: Date.now() - 345600000,
    },
    {
      id: '5',
      title: '总结本月安全事件',
      pinned: false,
      groupName: '安全事件',
      messages: [],
      createdAt: Date.now() - 432000000,
    },
    {
      id: '6',
      title: '主机历史行为分析',
      pinned: false,
      groupName: '安全事件',
      messages: [],
      createdAt: Date.now() - 518400000,
    },
    {
      id: '7',
      title: '主机安全基线检查',
      pinned: false,
      groupName: '主机分析',
      messages: [],
      createdAt: Date.now() - 604800000,
    },
    {
      id: '8',
      title: '10.0.2.x 主机异常排查',
      pinned: false,
      groupName: '主机分析',
      messages: [],
      createdAt: Date.now() - 691200000,
    },
    {
      id: '9',
      title: '未分类对话示例',
      pinned: false,
      messages: [],
      createdAt: Date.now() - 777600000,
    },
  ]);

  // 当前对话的消息列表
  const currentMessages = computed<Message[]>(() => {
    const conv = conversations.value.find(c => c.id === activeConversationId.value);
    return conv?.messages ?? [];
  });

  // 切换侧边栏折叠
  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  };

  // 新建对话
  const handleNewChat = () => {
    activeConversationId.value = null;
  };

  // 选择对话
  const handleSelectConversation = (id: string) => {
    activeConversationId.value = id;
  };

  // 删除对话
  const handleDeleteConversation = (id: string) => {
    const idx = conversations.value.findIndex(c => c.id === id);
    if (idx !== -1) {
      conversations.value.splice(idx, 1);
      if (activeConversationId.value === id) {
        activeConversationId.value = null;
      }
    }
  };

  // 置顶/取消置顶对话
  const handlePinConversation = (id: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv) {
      conv.pinned = !conv.pinned;
    }
  };

  // 更新对话分组
  const handleUpdateConversationGroup = (id: string, groupName?: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv) {
      conv.groupName = groupName;
    }
  };

  // 更新对话标题
  const handleUpdateConvTitle = (id: string, title: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv) {
      conv.title = title;
    }
  };

  // 更新分组列表
  const handleUpdateGroups = (newGroups: Group[]) => {
    groups.value = newGroups;
  };

  // 删除分组
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

  // 选择快捷提示词
  const handleSelectPrompt = (prompt: string) => {
    // 创建新对话并发送消息
    const newId = `conv_${Date.now()}`;
    const newConv: Conversation = {
      id: newId,
      title: prompt.slice(0, 20),
      pinned: false,
      messages: [],
      createdAt: Date.now(),
    };
    conversations.value.unshift(newConv);
    activeConversationId.value = newId;
    handleSendMessage(prompt);
  };

  // 发送消息
  const handleSendMessage = async (content: string) => {
    if (!content.trim() || isLoading.value) return;

    let convId = activeConversationId.value;

    // 如果没有活跃对话，创建新对话
    if (!convId) {
      const newId = `conv_${Date.now()}`;
      const newConv: Conversation = {
        id: newId,
        title: content.slice(0, 20),
        pinned: false,
        messages: [],
        createdAt: Date.now(),
      };
      conversations.value.unshift(newConv);
      activeConversationId.value = newId;
      convId = newId;
    }

    const conv = conversations.value.find(c => c.id === convId);
    if (!conv) return;

    // 添加用户消息
    const userMsg: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    conv.messages.push(userMsg);

    // 模拟 AI 回复（根据输入内容判断使用哪种回答格式）
    isLoading.value = true;
    try {
      await new Promise(resolve => setTimeout(resolve, 1500));

      // 判断是否为业务查询类问题（使用普通气泡回答2）
      const isBusinessQuery = /历史行为|分析.*主机|分析.*行为|主机行为分析|异常行为|风险告警|解读风险|解读.*告警|安全事件|基线检查|安全态势|安全健康/.test(content);

      if (isBusinessQuery) {
        // 回答2：交互式查询组件 - 用于具体的业务查询
        const aiMsg: Message = {
          id: `msg_${Date.now() + 1}`,
          role: 'assistant',
          type: 'query',
          content,
          timestamp: Date.now(),
        };
        conv.messages.push(aiMsg);
      } else {
        // 回答1：案例卡片格式 - 用于通用欢迎/功能介绍
        const aiMsg: Message = {
          id: `msg_${Date.now() + 1}`,
          role: 'assistant',
          type: 'case',
          thinkingTime: '0.8秒',
          content: `感谢您的提问。关于【主机安全】，以下是我的分析：

作为 HIDS 安全智能助手，我可以帮助您：
- **分析主机行为**：输入主机的IP，可以识别其异常的异常行为
- **解读风险告警**：帮您解读当前的高风险告警含义
- **调查安全事件**：对安全事件进行深入调查分析
- **安全基线检查**：对指定主机执行全面的安全健康评估
- **查看安全态势**：了解当前整体安全状况
- **HIDS使用帮助**：解答产品使用和配置相关问题

您可以尝试以下提问方式：
- “**分析主机 10.0.1.5 近 24 小时的异常行为**”
- “**帮我解读最新的高风险告警**”
- “**是否有需要我处理的安全事件**”
- “**对生产区 Web 服务器做一次安全健康检查**”`,
          timestamp: Date.now(),
        };
        conv.messages.push(aiMsg);
      }
    } finally {
      isLoading.value = false;
    }
  };

  // 停止生成
  const handleStopGenerate = () => {
    isLoading.value = false;
    // 这里可以处理打断后端请求的逻辑，这里仅做前端状态切换
  };

  // 重新生成回答
  const handleRefreshAnswer = (msgId: string) => {
    const conv = conversations.value.find(c => c.id === activeConversationId.value);
    if (!conv) return;

    // 移除原回答
    const msgIdx = conv.messages.findIndex(m => m.id === msgId);
    if (msgIdx !== -1) {
      conv.messages.splice(msgIdx, 1);
    }

    // 生成新回答
    isLoading.value = true;
    setTimeout(() => {
      const aiMsg: Message = {
        id: `msg_${Date.now()}`,
        role: 'assistant',
        type: 'case',
        thinkingTime: `${(Math.random() * 2 + 0.5).toFixed(1)}秒`,
        content: `【重新生成】感谢您的提问，以下是我的最新分析：

作为 HIDS 安全智能助手，我为您提供以下服务：
- **主机行为分析**：识别异常进程、网络连接和文件操作
- **风险告警解读**：分析告警根因并提供处置建议
- **安全事件调查**：追踪攻击链路并还原事件全貌
- **安全基线检查**：检测配置缺陷和安全漏洞
- **态势总览**：全局安全状况一目了然

建议您可以尝试提问：
- “分析最近一周的主机异常行为”
- “帮我查看当前最紧急的风险告警”`,
        timestamp: Date.now(),
      };
      conv.messages.push(aiMsg);
      isLoading.value = false;
    }, 1200);
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
      flex: 1;
      flex-direction: column;
    }
  }
</style>
