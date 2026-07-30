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
  <div class="chat-log-panel">
    <div class="panel-body">
      <div class="chat-surface">
        <div class="message-list">
          <div
            v-for="msg in messages"
            :key="msg.id"
            class="message-row"
            :class="`is-${msg.role}`">
            <!-- 用户气泡 -->
            <div
              v-if="msg.role === 'user' && msg.type === 'text'"
              class="user-bubble">
              {{ msg.content }}
            </div>

            <!-- 内联选择系统卡片 -->
            <select-system-card
              v-else-if="msg.type === 'select-system' && msg.status === 'pending'"
              :model-value="msg.systemIds || []"
              @close="$emit('close-select-system', msg.id)"
              @confirm="(ids, systems) => $emit('confirm-system', msg.id, ids, systems)" />

            <!-- 确认选择后的检索引导卡片 -->
            <retrieval-guide-card
              v-else-if="msg.type === 'retrieval-guide'"
              :systems="msg.systems || []"
              @reselect="$emit('reselect-system')"
              @select-suggestion="handleSelectSuggestion" />
          </div>
        </div>
      </div>
    </div>

    <div class="panel-footer">
      <div class="chat-surface">
        <chat-input
          ref="chatInputRef"
          @attach="$emit('attach')"
          @send="$emit('send', $event)" />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';

  import ChatInput from '@views/sec-chat/components/chat-input.vue';

  import RetrievalGuideCard from './retrieval-guide-card.vue';
  import SelectSystemCard from './select-system-card.vue';
  import type { ChatMessage, SelectedSystem } from '../../types';

  defineProps<{
    messages: ChatMessage[];
  }>();

  defineEmits<{
    'confirm-system': [messageId: string, systemIds: string[], systems: SelectedSystem[]];
    'close-select-system': [messageId: string];
    'reselect-system': [];
    send: [content: string];
    attach: [];
  }>();

  const chatInputRef = ref<{ setInputValue:(text: string) => void } | null>(null);

  const handleSelectSuggestion = (text: string) => {
    chatInputRef.value?.setInputValue(text);
  };
</script>

<style lang="postcss" scoped>
  .chat-log-panel {
    display: flex;
    width: 100%;
    height: 100%;
    overflow: visible;
    background-color: #f5f7fa;
    flex-direction: column;
  }

  /* 消息区与输入区共用内容面，卡片按设计稿 900 居中 */
  .chat-surface {
    width: 100%;
    max-width: 900px;
    margin: 0 auto;
  }

  .panel-body {
    display: flex;
    flex: 1;
    min-height: 0;
    padding: 24px 24px 24px;
    overflow: auto;
    flex-direction: column;
    scrollbar-width: thin;
    scrollbar-color: #dcdee5 transparent;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: #dcdee5;
      border-radius: 2px;
    }

    &::-webkit-scrollbar-thumb:hover {
      background: #c4c6cc;
    }

    .chat-surface {
      /* 内容少时贴底，但与输入区留出间距，避免卡片底部被挡住 */
      margin-top: auto;
      margin-bottom: 8px;
      overflow: visible;
    }
  }

  .message-list {
    display: flex;
    width: 100%;
    overflow: visible;
    flex-direction: column;
    gap: 16px;
  }

  .message-row {
    display: flex;
    width: 100%;
    overflow: visible;

    &.is-user {
      justify-content: flex-end;
    }

    &.is-assistant {
      justify-content: center;
      overflow: visible;

      > * {
        width: 900px;
        max-width: 100%;
      }
    }
  }

  .user-bubble {
    max-width: 70%;
    padding: 10px 16px;
    font-size: 14px;
    line-height: 22px;
    color: #fff;
    letter-spacing: 0;
    word-break: break-word;
    background: #3a84ff;
    border-radius: 8px 2px 8px 8px;
  }

  .panel-footer {
    flex-shrink: 0;
    width: 100%;
    padding: 0 24px 20px;
    box-sizing: border-box;
  }
</style>
