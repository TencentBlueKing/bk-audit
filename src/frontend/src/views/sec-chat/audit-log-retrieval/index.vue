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
      :messages="panelConversation.messages"
      @attach="handleAttach"
      @close-select-system="handleCloseSelectSystem"
      @confirm-system="handleConfirmSystem"
      @reselect-system="reselectSystem"
      @send="handleConversationSend" />
  </div>
</template>

<script lang="ts" setup>
  import { computed, watch } from 'vue';
  import { useRoute, useRouter } from 'vue-router';

  import { useSecChatStore } from '../composables/use-sec-chat-store';
  import type { SelectedSystem } from '../types';
  import ChatLogPanel from './components/chat-log-panel.vue';

  const route = useRoute();
  const router = useRouter();
  const {
    activeConversation,
    conversations,
    draftConversation,
    setActiveConversation,
    confirmSystem,
    closeSelectSystem,
    reselectSystem,
    sendLogQuery,
  } = useSecChatStore();

  const panelConversation = computed(() => activeConversation.value);

  const syncConversationFromRoute = async () => {
    const conversationId = route.params.conversationId as string | undefined;
    if (!conversationId) {
      router.replace({ name: 'secChatHome' });
      return;
    }

    if (conversationId.startsWith('draft-')) {
      if (draftConversation.value?.id === conversationId) {
        await setActiveConversation(conversationId);
        return;
      }
      router.replace({ name: 'secChatHome' });
      return;
    }

    try {
      await setActiveConversation(conversationId);
      if (!conversations.value.find(c => c.id === conversationId)) {
        router.replace({ name: 'secChatHome' });
      }
    } catch {
      router.replace({ name: 'secChatHome' });
    }
  };

  watch(() => route.params.conversationId, syncConversationFromRoute, { immediate: true });

  const handleConversationSend = (content: string) => {
    sendLogQuery(content);
  };

  const handleConfirmSystem = async (
    messageId: string,
    systemIds: string[],
    systems: SelectedSystem[],
  ) => {
    const wasDraft = Boolean(activeConversation.value?.isDraft);
    try {
      const result = await confirmSystem(messageId, systemIds, systems);
      if (wasDraft && result?.id) {
        await router.replace({
          name: 'secChatAuditLog',
          params: { conversationId: result.id },
        });
      }
    } catch {
      // 创建失败留在选系统页，提示由全局 request 中间件处理
    }
  };

  const handleCloseSelectSystem = (messageId: string) => {
    const wasDraft = Boolean(activeConversation.value?.isDraft);
    closeSelectSystem(messageId);
    if (wasDraft) {
      router.push({ name: 'secChatHome' });
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
