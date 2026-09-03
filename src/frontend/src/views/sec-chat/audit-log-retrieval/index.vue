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
  <div class="audit-log-retrieval-page">
    <chat-log-panel
      v-if="panelConversation"
      :confirming-system-message-id="confirmingSystemMessageId"
      :conversation-id="panelConversation.id"
      :extension-fields="panelConversation.extensionFields || []"
      :has-before-messages="panelConversation.hasBeforeMessages"
      :loading-older-messages="olderMessagesLoading"
      :message-loading="messageLoading"
      :messages="panelConversation.messages"
      :standard-fields="panelConversation.standardFields || []"
      :systems="panelConversation.systems || []"
      @attach="handleAttach"
      @close-select-system="handleCloseSelectSystem"
      @confirm-system="handleConfirmSystem"
      @load-older="handleLoadOlder"
      @reselect-system="reselectSystem"
      @retry-message="retryMessage"
      @send="handleConversationSend" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, onActivated, onDeactivated, ref, watch } from 'vue';
  import { useRoute, useRouter } from 'vue-router';

  import { useSecChatStore } from '../composables/use-sec-chat-store';
  import type { SelectedSystem } from '../types';
  import { preserveSecChatQuery } from '../utils/last-route';
  import ChatLogPanel from './components/chat-log-panel.vue';

  const route = useRoute();
  const router = useRouter();
  const {
    activeConversation,
    conversations,
    draftConversation,
    olderMessagesLoading,
    messageLoading,
    setActiveConversation,
    confirmSystem,
    closeSelectSystem,
    reselectSystem,
    sendLogQuery,
    retryMessage,
    loadOlderMessages,
  } = useSecChatStore();

  /** keep-alive 失活后 route 已是其他页，禁止再 replace 抢导航（否则点工具广场会先被拉回会话首页） */
  const isPageActive = ref(true);
  /** 系统选择确认请求进行中，防止重复点击 */
  const confirmingSystemMessageId = ref<string | null>(null);

  const panelConversation = computed(() => activeConversation.value);

  const withQuery = (to: { name: string; params?: Record<string, string> }) => ({
    ...to,
    query: preserveSecChatQuery(route.query as Record<string, unknown>),
  });

  const syncConversationFromRoute = async () => {
    // 仅在本页激活且当前路由仍是会话详情时同步；切到工具广场等页面时直接忽略
    if (!isPageActive.value || route.name !== 'secChatAuditLog') return;

    const conversationId = route.params.conversationId as string | undefined;
    if (!conversationId) {
      router.replace(withQuery({ name: 'secChatHome' }));
      return;
    }

    if (conversationId.startsWith('draft-')) {
      if (draftConversation.value?.id === conversationId) {
        await setActiveConversation(conversationId);
        return;
      }
      router.replace(withQuery({ name: 'secChatHome' }));
      return;
    }

    try {
      await setActiveConversation(conversationId);
      if (!isPageActive.value || route.name !== 'secChatAuditLog') return;
      if (!conversations.value.find(c => c.id === conversationId)) {
        router.replace(withQuery({ name: 'secChatHome' }));
      }
    } catch {
      if (!isPageActive.value || route.name !== 'secChatAuditLog') return;
      router.replace(withQuery({ name: 'secChatHome' }));
    }
  };

  watch(() => route.params.conversationId, syncConversationFromRoute, { immediate: true });

  onActivated(() => {
    isPageActive.value = true;
    void syncConversationFromRoute();
  });

  onDeactivated(() => {
    isPageActive.value = false;
  });

  const handleConversationSend = (content: string) => {
    void sendLogQuery(content);
  };

  const handleLoadOlder = () => {
    void loadOlderMessages();
  };

  const handleConfirmSystem = async (
    messageId: string,
    systemIds: string[],
    systems: SelectedSystem[],
  ) => {
    if (confirmingSystemMessageId.value) return;
    confirmingSystemMessageId.value = messageId;
    const wasDraft = Boolean(activeConversation.value?.isDraft);
    try {
      const result = await confirmSystem(messageId, systemIds, systems);
      if (wasDraft && result?.id) {
        await router.replace(withQuery({
          name: 'secChatAuditLog',
          params: { conversationId: result.id },
        }));
      }
    } catch {
      // 创建失败留在选系统页，提示由全局 request 中间件处理
    } finally {
      confirmingSystemMessageId.value = null;
    }
  };

  const handleCloseSelectSystem = (messageId: string) => {
    const wasDraft = Boolean(activeConversation.value?.isDraft);
    closeSelectSystem(messageId);
    if (wasDraft) {
      router.push(withQuery({ name: 'secChatHome' }));
    }
  };

  const handleAttach = () => {};
</script>

<style lang="postcss" scoped>
  .audit-log-retrieval-page {
    display: flex;
    width: 100%;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    flex-direction: column;
  }
</style>
