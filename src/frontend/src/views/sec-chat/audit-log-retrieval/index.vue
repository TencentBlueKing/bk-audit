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
    <!-- 临时返回：后续按产品设计替换 -->
    <div class="temp-back-bar">
      <bk-button
        text
        theme="primary"
        @click="handleBack">
        <audit-icon
          class="back-icon"
          type="angle-line-left" />
        返回
      </bk-button>
    </div>
    <chat-log-panel
      v-if="activeConversation"
      :messages="activeConversation.messages"
      @attach="handleAttach"
      @close-select-system="closeSelectSystem"
      @confirm-system="confirmSystem"
      @reselect-system="reselectSystem"
      @send="handleConversationSend" />
  </div>
</template>

<script lang="ts" setup>
  import { watch } from 'vue';
  import { useRoute, useRouter } from 'vue-router';

  import { useSecChatStore } from '../composables/use-sec-chat-store';
  import ChatLogPanel from './components/chat-log-panel.vue';

  const route = useRoute();
  const router = useRouter();
  const {
    activeConversation,
    conversations,
    setActiveConversation,
    confirmSystem,
    closeSelectSystem,
    reselectSystem,
  } = useSecChatStore();

  const syncConversationFromRoute = () => {
    const conversationId = route.params.conversationId as string | undefined;
    if (!conversationId) {
      router.replace({ name: 'secChatHome' });
      return;
    }
    const conv = conversations.value.find(c => c.id === conversationId);
    if (!conv || conv.sceneType !== 'log') {
      router.replace({ name: 'secChatHome' });
      return;
    }
    setActiveConversation(conversationId);
  };

  watch(() => route.params.conversationId, syncConversationFromRoute, { immediate: true });

  const handleBack = () => {
    setActiveConversation(null);
    router.push({ name: 'secChatHome' });
  };

  // 本阶段仅保留输入入口，后续再接 NL 检索
  const handleConversationSend = (_content: string) => {
    void _content;
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

  .temp-back-bar {
    display: flex;
    padding: 12px 16px 0;
    flex-shrink: 0;
    align-items: center;

    .back-icon {
      margin-right: 4px;
      font-size: 16px;
    }
  }
</style>
