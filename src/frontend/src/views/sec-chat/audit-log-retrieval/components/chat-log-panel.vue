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
    <div
      ref="panelBodyRef"
      class="panel-body">
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

            <!-- 查询后的结构化结果卡片 -->
            <retrieval-result-card
              v-else-if="msg.type === 'retrieval-result' && msg.result"
              :result="msg.result"
              @regenerate="handleRegenerate(msg.content || '')" />
          </div>
        </div>
      </div>
    </div>

    <div class="panel-footer">
      <div class="chat-surface">
        <chat-input
          ref="chatInputRef"
          hide-shortcuts
          @attach="$emit('attach')"
          @send="$emit('send', $event)" />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { nextTick, ref, watch } from 'vue';

  import ChatInput from '@views/sec-chat/components/chat-input.vue';

  import RetrievalGuideCard from './retrieval-guide-card.vue';
  import RetrievalResultCard from './retrieval-result-card.vue';
  import SelectSystemCard from './select-system-card.vue';
  import type { ChatMessage, SelectedSystem } from '../../types';

  const props = defineProps<{
    messages: ChatMessage[];
  }>();

  const emit = defineEmits<{
    'confirm-system': [messageId: string, systemIds: string[], systems: SelectedSystem[]];
    'close-select-system': [messageId: string];
    'reselect-system': [];
    send: [content: string];
    attach: [];
  }>();

  const chatInputRef = ref<{ setInputValue:(text: string) => void } | null>(null);
  const panelBodyRef = ref<HTMLElement | null>(null);

  const handleSelectSuggestion = (text: string) => {
    chatInputRef.value?.setInputValue(text);
  };

  const handleRegenerate = (text: string) => {
    if (text) emit('send', text);
  };

  const scrollToBottom = async () => {
    await nextTick();
    requestAnimationFrame(() => {
      const el = panelBodyRef.value;
      if (!el) return;
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    });
  };

  watch(() => props.messages.length, () => {
    scrollToBottom();
  });
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
      margin-bottom: 8px;
      overflow: visible;
    }
  }

  .message-list {
    display: flex;
    width: 100%;
    overflow: visible;
    flex-direction: column;
    gap: 24px;
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
    max-width: 640px;
    padding: 12px 24px;
    font-size: 14px;
    line-height: 22px;
    color: #313238;
    letter-spacing: 0;
    word-break: break-word;
    background: #CDDFFE;
    border-radius: 16px 0px 16px 16px;
    box-sizing: border-box;
  }

  .panel-footer {
    flex-shrink: 0;
    width: 100%;
    padding: 0 24px 20px;
    box-sizing: border-box;
  }
</style>
