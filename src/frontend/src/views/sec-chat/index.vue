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
    <chat-sidebar
      :active-id="activeConversationId"
      :collapsed="sidebarCollapsed"
      :conversations="conversations"
      :groups="groups"
      @delete="handleDeleteConversation"
      @delete-group="handleDeleteGroup"
      @new-chat="handleNewChat"
      @pin="pinConversation"
      @select="handleSelectConversation"
      @toggle="toggleSidebar"
      @update-conv-title="updateConversationTitle"
      @update-group="updateConversationGroup"
      @update-groups="updateGroups" />

    <div class="sec-chat-main">
      <router-view v-slot="{ Component }">
        <component
          :is="Component"
          class="sec-chat-route" />
      </router-view>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { useRouter } from 'vue-router';

  import { useSecChatStore } from './composables/use-sec-chat-store';
  import ChatSidebar from './components/chat-sidebar.vue';

  const router = useRouter();
  const {
    sidebarCollapsed,
    activeConversationId,
    groups,
    conversations,
    toggleSidebar,
    setActiveConversation,
    deleteConversation,
    pinConversation,
    updateConversationGroup,
    updateConversationTitle,
    updateGroups,
    deleteGroup,
  } = useSecChatStore();

  const handleNewChat = () => {
    setActiveConversation(null);
    router.push({ name: 'secChatHome' });
  };

  const handleSelectConversation = (id: string) => {
    const conv = conversations.value.find(c => c.id === id);
    setActiveConversation(id);
    if (conv?.sceneType === 'log') {
      router.push({
        name: 'secChatAuditLog',
        params: { conversationId: id },
      });
      return;
    }
    router.push({ name: 'secChatHome' });
  };

  const handleDeleteConversation = (id: string) => {
    const wasActive = activeConversationId.value === id;
    deleteConversation(id);
    if (wasActive) {
      router.push({ name: 'secChatHome' });
    }
  };

  const handleDeleteGroup = (groupName: string, keepConversations: boolean) => {
    deleteGroup(groupName, keepConversations);
    if (!activeConversationId.value) {
      router.push({ name: 'secChatHome' });
    }
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

      .sec-chat-route {
        display: flex;
        width: 100%;
        height: 100%;
        min-height: 0;
        overflow: hidden;
        flex: 1;
        flex-direction: column;
      }
    }
  }
</style>
