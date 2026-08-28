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
      ref="sidebarRef"
      :active-id="activeConversationId"
      :collapsed="sidebarCollapsed"
      :conversations="conversations"
      :groups="groups"
      @add-group="handleAddGroup"
      @clear-all="handleClearAll"
      @delete="handleDeleteConversation"
      @delete-group="handleDeleteGroup"
      @new-chat="handleNewChat"
      @rename-group="handleRenameGroup"
      @reorder-conversation="handleReorderConversation"
      @select="handleSelectConversation"
      @toggle="toggleSidebar"
      @update-conv-title="handleUpdateConvTitle"
      @update-group="handleUpdateGroup"
      @reorder-group="handleReorderGroup" />

    <div class="sec-chat-main">
      <!-- 弹层专用挂载点：禁止 teleport 到含 router-view 的容器，否则 keep-alive 失活时会误卸主内容导致白屏 -->
      <div
        id="sec-chat-overlay-root"
        class="sec-chat-overlay-root" />
      <router-view v-slot="{ Component }">
        <component
          :is="Component"
          class="sec-chat-route" />
      </router-view>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from 'vue';
  import { useRoute, useRouter } from 'vue-router';

  import { useSecChatStore } from './composables/use-sec-chat-store';
  import { preserveSecChatQuery, saveSecChatLastRoute } from './utils/last-route';
  import ChatSidebar from './components/chat-sidebar.vue';

  const route = useRoute();
  const router = useRouter();
  const sidebarRef = ref<InstanceType<typeof ChatSidebar> | null>(null);
  const withQuery = (to: { name: string; params?: Record<string, string> }) => ({
    ...to,
    query: preserveSecChatQuery(route.query as Record<string, unknown>),
  });
  const {
    sidebarCollapsed,
    activeConversationId,
    groups,
    conversations,
    toggleSidebar,
    initSidebar,
    setActiveConversation,
    deleteConversation,
    updateConversationGroup,
    reorderConversation,
    updateConversationTitle,
    createGroup,
    reorderGroup,
    renameGroup,
    deleteGroup,
    clearAllConversations,
    stopAllMessagePolls,
  } = useSecChatStore();

  /** keep-alive 切走时关掉 teleport 到 body 的弹层，避免遮罩残留导致整页无法点击 */
  const closeKeepAliveOverlays = () => {
    sidebarRef.value?.closeKeepAliveOverlays?.();
  };

  watch(
    () => ({
      name: route.name,
      params: route.params,
      query: route.query,
    }),
    (current) => {
      saveSecChatLastRoute(current);
    },
    { deep: true, immediate: true },
  );

  onMounted(() => {
    void initSidebar();
  });

  onActivated(() => {
    closeKeepAliveOverlays();
  });

  onDeactivated(() => {
    closeKeepAliveOverlays();
  });

  onUnmounted(() => {
    stopAllMessagePolls();
  });

  const handleNewChat = () => {
    setActiveConversation(null);
    router.push(withQuery({ name: 'secChatHome' }));
  };

  /** 仅改路由；消息拉取由子页 watch conversationId 单源触发，避免侧栏+路由叠打 */
  const handleSelectConversation = (id: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (conv?.sceneType === 'log' || id.startsWith('draft-')) {
      router.push(withQuery({
        name: 'secChatAuditLog',
        params: { conversationId: id },
      }));
      return;
    }
    router.push(withQuery({ name: 'secChatHome' }));
  };

  const handleDeleteConversation = async (id: string) => {
    const wasActive = activeConversationId.value === id;
    await deleteConversation(id);
    if (wasActive) {
      router.push(withQuery({ name: 'secChatHome' }));
    }
  };

  const handleUpdateConvTitle = (id: string, title: string) => {
    void updateConversationTitle(id, title);
  };

  const handleUpdateGroup = (id: string, groupName?: string) => {
    void updateConversationGroup(id, groupName);
  };

  const handleReorderConversation = (
    id: string,
    payload: { groupName?: string; beforeId?: string; toEnd?: boolean },
  ) => {
    void reorderConversation(id, payload);
  };

  const handleReorderGroup = (
    id: string,
    payload: { beforeId?: string; toEnd?: boolean },
  ) => {
    void reorderGroup(id, payload);
  };

  const handleAddGroup = (name: string) => {
    void createGroup(name);
  };

  const handleRenameGroup = (groupId: string, name: string) => {
    void renameGroup(groupId, name);
  };

  const handleDeleteGroup = async (groupName: string, keepConversations: boolean) => {
    await deleteGroup(groupName, keepConversations);
    if (!activeConversationId.value) {
      router.push(withQuery({ name: 'secChatHome' }));
    }
  };

  const handleClearAll = async () => {
    await clearAllConversations();
    router.push(withQuery({ name: 'secChatHome' }));
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
      position: relative;
      display: flex;
      min-width: 0;
      overflow: hidden;
      background-color: #f5f7fa;
      flex: 1;
      flex-direction: column;

      .sec-chat-overlay-root {
        position: absolute;
        inset: 0;
        z-index: 100;
        pointer-events: none;
      }

      .sec-chat-route {
        display: flex;
        width: 100%;
        height: 100%;
        min-height: 0;
        overflow: hidden;
        flex-direction: column;
      }
    }
  }
</style>
