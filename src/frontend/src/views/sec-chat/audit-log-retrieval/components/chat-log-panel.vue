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
      class="panel-body"
      @scroll="handlePanelScroll">
      <div class="chat-surface">
        <div
          v-if="hasBeforeMessages || loadingOlderMessages"
          class="history-loading-hint">
          <template v-if="loadingOlderMessages">
            <span class="loading-dot" />
            <span class="loading-dot" />
            <span class="loading-dot" />
            <span class="history-loading-text">加载历史消息…</span>
          </template>
        </div>
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
              :common-operations="msg.commonOperations || []"
              :extension-fields="msg.extensionFields || []"
              :historical-operations="msg.historicalOperations || []"
              :standard-fields="msg.standardFields || []"
              :systems="msg.systems || []"
              @reselect="$emit('reselect-system')"
              @select-suggestion="handleSelectSuggestion" />

            <!-- NL 处理中 -->
            <div
              v-else-if="msg.type === 'retrieval-result' && msg.apiStatus === 'PROCESSING'"
              class="result-status-card is-loading">
              <span class="loading-dot" />
              <span class="loading-dot" />
              <span class="loading-dot" />
              <span class="status-text">正在理解检索意图…</span>
            </div>

            <!-- NL 识别失败（SUCCESS + output_data.error，不可 RetryMessage） -->
            <div
              v-else-if="msg.type === 'retrieval-result' && msg.recognitionError"
              class="result-status-card is-recognition-failed">
              <div class="recognition-error-header">
                <img
                  alt=""
                  class="failed-icon"
                  :src="errorSearchIcon">
                <div class="status-title">
                  {{ getRecognitionTitle(msg.recognitionError.code) }}
                </div>
                <div class="status-desc">
                  {{ msg.recognitionError.message || getRecognitionFallback(msg.recognitionError.code) }}
                </div>
              </div>
              <div
                v-if="showRecognitionSuggestions(msg.recognitionError.code)"
                class="suggest-section">
                <div class="suggest-label">
                  试试这样说：
                </div>
                <button
                  v-for="(item, index) in displaySuggestions"
                  :key="`nl-suggest-${index}`"
                  class="suggest-item"
                  type="button"
                  @click="handleSelectSuggestion(item)">
                  {{ item }}
                </button>
              </div>
            </div>

            <!-- NL / LOG 失败（条件检索失败在条件卡内展示） -->
            <div
              v-else-if="msg.type === 'retrieval-result' && msg.apiStatus === 'FAILED' && !isConditionLogResult(msg)"
              class="result-status-card is-failed">
              <div class="status-title">
                检索失败
              </div>
              <div class="status-desc">
                {{ msg.errorMessage || '请稍后重试或改用条件筛选' }}
              </div>
              <bk-button
                v-if="msg.messageType === 'NATURAL_LANGUAGE_SEARCH'"
                size="small"
                theme="primary"
                @click="$emit('retry-message', msg.id)">
                重试
              </bk-button>
            </div>

            <!-- 查询后的结构化结果卡片；条件检索根 LOG 不在此渲染（内嵌于条件卡） -->
            <retrieval-result-card
              v-else-if="msg.type === 'retrieval-result' && msg.result && !isConditionLogResult(msg)"
              :message-uid="msg.id"
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
  import { computed, nextTick, onActivated, ref, watch } from 'vue';

  import ChatInput from '@views/sec-chat/components/chat-input.vue';

  import errorSearchIcon from '@images/error-search.svg';

  import RetrievalGuideCard from './retrieval-guide-card.vue';
  import RetrievalResultCard from './retrieval-result-card.vue';
  import SelectSystemCard from './select-system-card.vue';
  import type { ChatMessage, SelectedSystem } from '../../types';

  const props = withDefaults(defineProps<{
    conversationId?: string;
    messages: ChatMessage[];
    hasBeforeMessages?: boolean;
    loadingOlderMessages?: boolean;
    messageLoading?: boolean;
    /** 识别失败时展示的建议问法（来自 SYSTEM_SELECTION） */
    nlSuggestions?: string[];
  }>(), {
    conversationId: undefined,
    hasBeforeMessages: false,
    loadingOlderMessages: false,
    messageLoading: false,
    nlSuggestions: () => [],
  });

  const emit = defineEmits<{
    'confirm-system': [messageId: string, systemIds: string[], systems: SelectedSystem[]];
    'close-select-system': [messageId: string];
    'reselect-system': [];
    'retry-message': [messageUid: string];
    'load-older': [];
    send: [content: string];
    attach: [];
  }>();

  const chatInputRef = ref<{ setInputValue:(text: string) => void } | null>(null);
  const panelBodyRef = ref<HTMLElement | null>(null);
  /** prepend 历史消息后用于恢复滚动位置 */
  const scrollAnchor = ref<{ height: number; top: number } | null>(null);
  /** 避免 scroll 事件在 loading 状态生效前重复触发 */
  const olderLoadTriggered = ref(false);
  /** 首次滚到底完成前禁止触发上滑加载，避免 scrollTop=0 误触 BEFORE 请求 */
  const allowLoadOlder = ref(false);

  const SCROLL_LOAD_THRESHOLD = 80;

  const NL_RECOGNITION_TITLES: Record<string, string> = {
    QUERY_NOT_RECOGNIZED: '未能理解检索需求',
    AI_OUTPUT_PARSE_FAILED: '检索条件解析失败',
    AI_OUTPUT_INVALID: '检索条件无效',
    AI_SERVICE_ERROR: 'AI 服务暂不可用',
    AI_TIMEOUT: 'AI 服务响应超时',
    PERMISSION_DENIED: '无日志检索权限',
  };

  const NL_RECOGNITION_FALLBACKS: Record<string, string> = {
    QUERY_NOT_RECOGNIZED: '请换一种描述或补充关键信息',
    AI_OUTPUT_PARSE_FAILED: '请重新描述检索需求',
    AI_OUTPUT_INVALID: '请修改描述后重试',
    AI_SERVICE_ERROR: '请稍后重试',
    AI_TIMEOUT: '请稍后重试',
    PERMISSION_DENIED: '请联系管理员申请目标系统的日志检索权限',
  };

  const FALLBACK_SUGGESTIONS = [
    '查询「替换为实际用户」近7天的删除操作',
    '查询「替换为实际安装包」近7天的下载操作',
    '查询「替换为实际安装包」近7天的成功操作',
    '查询「替换为实际用户」近30天的API操作',
  ];

  const displaySuggestions = computed(() => (
    (props.nlSuggestions.length ? props.nlSuggestions : FALLBACK_SUGGESTIONS).slice(0, 4)
  ));

  const getRecognitionTitle = (code: string) => (
    NL_RECOGNITION_TITLES[code] || '未能完成检索'
  );

  const getRecognitionFallback = (code: string) => (
    NL_RECOGNITION_FALLBACKS[code] || '请修改描述后重新发送'
  );

  const showRecognitionSuggestions = (code: string) => code === 'QUERY_NOT_RECOGNIZED';

  /** 条件筛选产生的根 LOG_SEARCH（无 parent），结果在条件卡内嵌展示 */
  const isConditionLogResult = (msg: ChatMessage) => (
    msg.messageType === 'LOG_SEARCH' && !msg.parentMessageUid
  );

  const handleSelectSuggestion = (text: string) => {
    chatInputRef.value?.setInputValue(text);
  };

  const handleRegenerate = (text: string) => {
    if (text) emit('send', text);
  };

  const scrollToBottom = async (smooth = true): Promise<void> => {
    allowLoadOlder.value = false;
    await nextTick();
    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        const el = panelBodyRef.value;
        if (!el) {
          allowLoadOlder.value = true;
          resolve();
          return;
        }
        // keep-alive 恢复后需等布局稳定，再滚到最新消息
        requestAnimationFrame(() => {
          el.scrollTo({
            top: el.scrollHeight,
            behavior: smooth ? 'smooth' : 'auto',
          });
          const enableLoadOlder = () => {
            allowLoadOlder.value = true;
            resolve();
          };
          if (smooth) {
            window.setTimeout(enableLoadOlder, 350);
          } else {
            enableLoadOlder();
          }
        });
      });
    });
  };

  const restoreScrollAnchor = async () => {
    const anchor = scrollAnchor.value;
    if (!anchor) return;
    scrollAnchor.value = null;
    await nextTick();
    requestAnimationFrame(() => {
      const el = panelBodyRef.value;
      if (!el) return;
      el.scrollTop = el.scrollHeight - anchor.height + anchor.top;
    });
  };

  const handlePanelScroll = () => {
    const el = panelBodyRef.value;
    if (!el || !allowLoadOlder.value || props.messageLoading) return;
    if (!props.hasBeforeMessages || props.loadingOlderMessages || olderLoadTriggered.value) return;
    if (el.scrollTop > SCROLL_LOAD_THRESHOLD) return;

    olderLoadTriggered.value = true;
    scrollAnchor.value = { height: el.scrollHeight, top: el.scrollTop };
    emit('load-older');
  };

  watch(() => props.loadingOlderMessages, async (loading, wasLoading) => {
    if (wasLoading && !loading) {
      olderLoadTriggered.value = false;
      // 等 length watch 先完成 scroll 恢复；若仍留有 anchor 说明加载失败或无新消息
      await nextTick();
      if (scrollAnchor.value) {
        scrollAnchor.value = null;
      }
    }
  });

  watch(() => props.messages.length, async (newLen, oldLen) => {
    if (scrollAnchor.value) {
      await restoreScrollAnchor();
      return;
    }
    if (newLen > oldLen) {
      await scrollToBottom(oldLen !== 0);
    }
  });

  watch(() => props.conversationId, () => {
    scrollAnchor.value = null;
    olderLoadTriggered.value = false;
    allowLoadOlder.value = false;
    void scrollToBottom(false);
  });

  watch(() => props.messageLoading, (loading, wasLoading) => {
    if (wasLoading && !loading) {
      void scrollToBottom(false);
    }
  });

  onActivated(() => {
    allowLoadOlder.value = false;
    void scrollToBottom(false);
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
    min-width: 0;
    margin: 0 auto;
    box-sizing: border-box;
  }

  .panel-body {
    display: flex;
    flex: 1;
    min-height: 0;
    padding: 24px 24px 24px;
    overflow: auto;
    flex-direction: column;
    scrollbar-gutter: stable;
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
    min-width: 0;
    overflow: visible;
    flex-direction: column;
    gap: 24px;
  }

  .history-loading-hint {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 32px;
    margin-bottom: 16px;
    gap: 6px;
    color: #979ba5;
  }

  .history-loading-text {
    margin-left: 4px;
    font-size: 12px;
    line-height: 18px;
  }

  .message-row {
    display: flex;
    width: 100%;
    min-width: 0;
    overflow: visible;

    &.is-user {
      justify-content: flex-end;
    }

    &.is-assistant {
      justify-content: center;
      overflow: hidden;

      > * {
        width: 100%;
        max-width: 100%;
        min-width: 0;
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

  .result-status-card {
    display: flex;
    width: 100%;
    max-width: 900px;
    padding: 20px 24px;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 12px 32px 0 rgb(0 0 0 / 4%);
    box-sizing: border-box;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;

    &.is-loading {
      flex-direction: row;
      align-items: center;
      gap: 6px;
      color: #63656e;
    }

    &.is-recognition-failed {
      align-items: stretch;
      gap: 16px;

      .recognition-error-header {
        display: flex;
        width: 100%;
        padding: 16px 0 8px;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 8px;
        text-align: center;
      }

      .failed-icon {
        display: block;
        width: 48px;
        height: 48px;
      }

      .status-title,
      .status-desc {
        text-align: center;
      }
    }

    .suggest-section {
      width: 100%;
      margin-top: 4px;
    }

    .suggest-label {
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 18px;
      color: #979ba5;
    }

    .suggest-item {
      display: block;
      width: 100%;
      margin-bottom: 8px;
      padding: 8px 12px;
      overflow: hidden;
      font-size: 14px;
      line-height: 22px;
      color: #63656e;
      text-align: left;
      cursor: pointer;
      background: #f5f7fa;
      border: 1px solid transparent;
      border-radius: 4px;
      transition: background-color .15s, border-color .15s;
      box-sizing: border-box;

      &:last-child {
        margin-bottom: 0;
      }

      &:hover {
        background: #f0f5ff;
        border-color: #a3c5fd;
      }
    }

    .status-title {
      font-size: 14px;
      font-weight: 500;
      color: #313238;
    }

    .status-desc {
      font-size: 12px;
      line-height: 18px;
      color: #979ba5;
    }

    .status-text {
      margin-left: 4px;
      font-size: 14px;
      color: #63656e;
    }
  }

  .loading-dot {
    width: 6px;
    height: 6px;
    background: #3a84ff;
    border-radius: 50%;
    opacity: 40%;
    animation: chat-loading-dot 1s ease-in-out infinite;
  }

  .loading-dot:nth-child(1) {
    animation-delay: 0s;
  }

  .loading-dot:nth-child(2) {
    animation-delay: .15s;
  }

  .loading-dot:nth-child(3) {
    animation-delay: .3s;
  }

  @keyframes chat-loading-dot {
    0%,
    100% {
      opacity: 40%;
      transform: scale(1);
    }

    50% {
      opacity: 100%;
      transform: scale(1.15);
    }
  }

  .panel-footer {
    flex-shrink: 0;
    width: 100%;
    padding: 0 24px 20px;
    /* 与消息区同样预留滚动条槽，保证输入框与卡片左右对齐、同宽 */
    scrollbar-gutter: stable;
    box-sizing: border-box;
  }
</style>
