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
      <bk-loading
        v-if="showMessageLoading"
        class="message-area-loading"
        color="transparent"
        loading
        :opacity="0"
        size="small"
        title="加载消息…">
        <div class="message-area-loading-box" />
      </bk-loading>
      <div
        v-else-if="!messageLoading"
        class="chat-surface">
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
          <template
            v-for="msg in messages"
            :key="msg.id">
            <div
              v-if="isMessageRowVisible(msg)"
              class="message-row"
              :class="`is-${msg.role}`">
              <!-- 用户气泡 -->
              <div
                v-if="msg.role === 'user' && msg.type === 'text'"
                class="user-bubble">
                {{ msg.content }}
              </div>

              <!-- 系统确认/引导异步处理中：整条骨架占位，避免终态卡片突然撑开 -->
              <retrieval-card-skeleton
                v-else-if="msg.messageType === 'SYSTEM_SELECTION'
                  && msg.apiStatus === 'PROCESSING'"
                :status-text="msg.showGuide === false ? '正在理解检索意图…' : '正在加载检索引导…'" />

              <!-- 内联选择系统卡片 -->
              <select-system-card
                v-else-if="msg.type === 'select-system' && msg.status === 'pending' && msg.showGuide !== false"
                :candidate-systems="msg.candidateSystems || []"
                :confirming="confirmingSystemMessageId === msg.id"
                :model-value="msg.systemIds || []"
                :selection-reason="msg.selectionReason || 'initial'"
                :tip-message="msg.aiMessage || ''"
                @close="$emit('close-select-system', msg.id)"
                @confirm="(ids, systems) => $emit('confirm-system', msg.id, ids, systems)" />

              <!-- 显式选系统后的检索引导卡片 -->
              <retrieval-guide-card
                v-else-if="msg.type === 'retrieval-guide' && msg.showGuide !== false"
                :common-operations="msg.commonOperations || []"
                :confirming-system="confirmingSystemMessageId === msg.id"
                :extension-fields="msg.extensionFields || []"
                :historical-operations="msg.historicalOperations || []"
                :standard-fields="msg.standardFields || []"
                :systems="msg.systems || []"
                @append-nl-field="handleAppendNlField"
                @confirm-system="(ids, systems) => $emit('confirm-system', msg.id, ids, systems)"
                @open-condition-filter="handleOpenConditionFilter"
                @select-suggestion="handleSelectSuggestion" />

              <!-- NL 处理中：整条骨架占位，避免终态卡片突然撑开 -->
              <retrieval-card-skeleton
                v-else-if="shouldShowRetrievalLoading(msg)"
                :status-text="getRetrievalLoadingText(msg)" />

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
                    {{
                      msg.recognitionError.message
                        || msg.aiMessage
                        || getRecognitionFallback(msg.recognitionError.code)
                    }}
                  </div>
                  <bk-button
                    v-if="showRecognitionResend(msg.recognitionError.code) && msg.content"
                    class="recognition-resend-btn"
                    size="small"
                    theme="primary"
                    @click="handleEditAndResend(msg.content || '')">
                    编辑后重发
                  </bk-button>
                </div>
                <div
                  v-if="showRecognitionSuggestions(msg.recognitionError.code)
                    && recognitionSuggestions.length"
                  class="suggest-section">
                  <div class="suggest-label">
                    试试这样说：
                  </div>
                  <button
                    v-for="(item, index) in recognitionSuggestions"
                    :key="`nl-suggest-${index}`"
                    class="suggest-item"
                    type="button"
                    @click="handleSelectSuggestion(item)">
                    {{ item }}
                  </button>
                </div>
              </div>

              <!-- 查询后的结构化结果卡片（含 LOG_SEARCH FAILED：条件区 + 卡内失败态） -->
              <retrieval-result-card
                v-else-if="msg.type === 'retrieval-result' && msg.result"
                :api-status="msg.apiStatus"
                :error-message="msg.errorMessage || msg.aiMessage || ''"
                :extension-fields="extensionFields"
                :message-uid="msg.id"
                :result="msg.result"
                :standard-fields="standardFields"
                :systems="systems"
                @regenerate="handleRegenerate(msg.content || '')"
                @reselect-system="handleReselectSystem" />

              <!-- NL / 无条件任务失败：对齐条件检索失败态（居中图标 + 文案） -->
              <div
                v-else-if="msg.type === 'retrieval-result' && msg.apiStatus === 'FAILED'"
                class="result-status-card is-failed">
                <img
                  alt=""
                  class="failed-icon"
                  :src="errorSearchIcon">
                <div class="status-title">
                  检索失败
                </div>
                <div class="status-desc">
                  {{ msg.aiMessage || msg.errorMessage || '请检查网络是否通畅或联系管理员' }}
                </div>
                <bk-button
                  v-if="msg.messageType === 'NATURAL_LANGUAGE_SEARCH' || msg.messageType === 'USER_INTENT'"
                  class="failed-retry-btn"
                  size="small"
                  theme="primary"
                  @click="$emit('retry-message', msg.id)">
                  重试
                </bk-button>
              </div>
            </div>
          </template>

          <!-- 条件检索卡：未检索时覆盖草稿；已检索后再点则新建，固定在会话底部 -->
          <div
            v-for="card in conditionFilterCards"
            :id="`condition-filter-${card.id}`"
            :key="card.id"
            class="message-row is-assistant condition-filter-row">
            <condition-filter-card
              :extension-fields="extensionFields"
              :initial-field-name="card.fieldName"
              :initial-sample="card.sample"
              :standard-fields="standardFields"
              :systems="systems"
              @reselect-system="handleReselectSystem"
              @searched="(success) => handleConditionSearched(card.id, success)" />
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
  import {
    computed,
    nextTick,
    onActivated,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';

  import ChatInput from '@views/sec-chat/components/chat-input.vue';

  import errorSearchIcon from '@images/error-search.svg';

  import RetrievalGuideCard from './retrieval-guide-card.vue';
  import RetrievalCardSkeleton from './retrieval-card-skeleton.vue';
  import ConditionFilterCard from './condition-filter-card.vue';
  import RetrievalResultCard from './retrieval-result-card.vue';
  import SelectSystemCard from './select-system-card.vue';
  import type { ChatMessage, SelectedSystem, SystemFieldRow } from '../../types';

  const props = withDefaults(defineProps<{
    conversationId?: string;
    messages: ChatMessage[];
    hasBeforeMessages?: boolean;
    loadingOlderMessages?: boolean;
    messageLoading?: boolean;
    commonOperations?: string[];
    standardFields?: SystemFieldRow[];
    extensionFields?: SystemFieldRow[];
    systems?: SelectedSystem[];
    /** 正在确认系统选择的消息 ID，用于禁用确认按钮 */
    confirmingSystemMessageId?: string | null;
  }>(), {
    conversationId: undefined,
    hasBeforeMessages: false,
    loadingOlderMessages: false,
    messageLoading: false,
    commonOperations: () => [],
    standardFields: () => [],
    extensionFields: () => [],
    systems: () => [],
    confirmingSystemMessageId: null,
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

  const chatInputRef = ref<{
    setInputValue:(text: string) => void
    appendInputValue:(text: string, separator?: string) => void
  } | null>(null);
  const panelBodyRef = ref<HTMLElement | null>(null);
  /** 引导卡条件筛选：未检索最多 1 张草稿（再点覆盖）；检索成功收起后再点则新建 */
  const conditionFilterCards = ref<Array<{
    id: string
    fieldName: string
    sample?: string
  }>>([]);
  /** prepend 历史消息后用于恢复滚动位置 */
  const scrollAnchor = ref<{ height: number; top: number } | null>(null);
  /** 避免 scroll 事件在 loading 状态生效前重复触发 */
  const olderLoadTriggered = ref(false);
  /** 首次滚到底完成前禁止触发上滑加载，避免 scrollTop=0 误触 BEFORE 请求 */
  const allowLoadOlder = ref(false);
  /** 延迟展示消息区 loading，避免接口很快返回时闪一下 */
  const showMessageLoading = ref(false);
  let messageLoadingDelayTimer: ReturnType<typeof setTimeout> | null = null;

  const SCROLL_LOAD_THRESHOLD = 80;
  const CONDITION_FILTER_SCROLL_MS = 400;
  const MESSAGE_LOADING_DELAY_MS = 160;

  const clearMessageLoadingDelay = () => {
    if (!messageLoadingDelayTimer) return;
    clearTimeout(messageLoadingDelayTimer);
    messageLoadingDelayTimer = null;
  };

  const NL_RECOGNITION_TITLES: Record<string, string> = {
    SYSTEM_REQUIRED: '需要补充系统信息',
    UNRECOGNIZED_INTENT: '未能理解当前意图',
    QUERY_NOT_RECOGNIZED: '未能理解检索需求',
    AI_OUTPUT_PARSE_FAILED: '检索条件解析失败',
    AI_OUTPUT_INVALID: '检索条件无效',
    AI_SERVICE_ERROR: 'AI 服务暂不可用',
    AI_TIMEOUT: 'AI 服务响应超时',
    PERMISSION_DENIED: '无日志检索权限',
  };

  const NL_RECOGNITION_FALLBACKS: Record<string, string> = {
    SYSTEM_REQUIRED: '请选择目标系统后继续检索',
    UNRECOGNIZED_INTENT: '请换一种描述方式重新发送',
    QUERY_NOT_RECOGNIZED: '请换一种描述或补充关键信息',
    AI_OUTPUT_PARSE_FAILED: '请重新描述检索需求',
    AI_OUTPUT_INVALID: '请修改描述后重试',
    AI_SERVICE_ERROR: '请稍后重试',
    AI_TIMEOUT: '请稍后重试',
    PERMISSION_DENIED: '请联系管理员申请目标系统的日志检索权限',
  };

  const SUGGESTION_LIMIT = 4;

  /** 「试试这样说」：复用会话里 SYSTEM_SELECTION 的常用操作 */
  const recognitionSuggestions = computed(() => (
    props.commonOperations.slice(0, SUGGESTION_LIMIT)
  ));

  const getRecognitionTitle = (code: string) => (
    NL_RECOGNITION_TITLES[code] || '未能完成检索'
  );

  const getRecognitionFallback = (code: string) => (
    NL_RECOGNITION_FALLBACKS[code] || '请修改描述后重新发送'
  );

  /** 意图不明 / 条件未识别 / 条件无效：展示固定「试试这样说」 */
  const showRecognitionSuggestions = (code: string) => (
    code === 'UNRECOGNIZED_INTENT'
    || code === 'QUERY_NOT_RECOGNIZED'
    || code === 'AI_OUTPUT_INVALID'
  );

  /** AI 瞬时失败：回填原句到输入框，由用户编辑后重发（不走 RetryMessage） */
  const showRecognitionResend = (code: string) => (
    code === 'AI_TIMEOUT'
    || code === 'AI_SERVICE_ERROR'
    || code === 'AI_OUTPUT_PARSE_FAILED'
  );

  const getProcessingText = (messageType?: string) => {
    if (messageType === 'LOG_SEARCH') return '正在检索日志…';
    return '正在理解检索意图…';
  };

  const hasChildRetrievalMessage = (messageId: string) => (
    props.messages.some(item => item.parentMessageUid === messageId && item.type === 'retrieval-result')
  );

  /** 无结果卡时才展示全局检索 loading；已有结果卡则由卡内 loading 承接二次检索 */
  const shouldShowRetrievalLoading = (msg: ChatMessage) => {
    if (msg.type !== 'retrieval-result' || msg.recognitionError || msg.result) return false;
    if (msg.apiStatus === 'PROCESSING') return true;
    if (msg.apiStatus !== 'SUCCESS') return false;
    return (
      (msg.messageType === 'USER_INTENT' || msg.messageType === 'NATURAL_LANGUAGE_SEARCH')
      && !hasChildRetrievalMessage(msg.id)
    );
  };

  const getRetrievalLoadingText = (msg: ChatMessage) => {
    if (
      msg.apiStatus === 'SUCCESS'
      && (msg.messageType === 'USER_INTENT' || msg.messageType === 'NATURAL_LANGUAGE_SEARCH')
    ) {
      return '正在检索日志…';
    }
    return getProcessingText(msg.messageType);
  };

  /** 与模板渲染条件对齐；隐藏空行避免 flex gap 把上下间距撑成双倍 */
  const isMessageRowVisible = (msg: ChatMessage) => {
    if (msg.role === 'user' && msg.type === 'text') return true;
    if (msg.messageType === 'SYSTEM_SELECTION' && msg.apiStatus === 'PROCESSING') return true;
    if (msg.type === 'select-system' && msg.status === 'pending' && msg.showGuide !== false) return true;
    if (msg.type === 'retrieval-guide' && msg.showGuide !== false) return true;
    if (shouldShowRetrievalLoading(msg)) return true;
    if (msg.type === 'retrieval-result' && msg.recognitionError) return true;
    if (msg.type === 'retrieval-result' && msg.result) return true;
    if (msg.type === 'retrieval-result' && msg.apiStatus === 'FAILED') return true;
    return false;
  };

  const visibleMessageSignature = computed(() => props.messages.map((msg) => {
    const visibleKind = (() => {
      if (msg.role === 'user' && msg.type === 'text') return 'user-text';
      if (msg.messageType === 'SYSTEM_SELECTION' && msg.apiStatus === 'PROCESSING') return 'system-selection-loading';
      if (msg.type === 'select-system' && msg.status === 'pending' && msg.showGuide !== false) return 'select-system-card';
      if (msg.type === 'retrieval-guide' && msg.showGuide !== false) return 'retrieval-guide-card';
      if (shouldShowRetrievalLoading(msg)) return 'retrieval-loading';
      if (msg.type === 'retrieval-result' && msg.recognitionError) return `recognition-error:${msg.recognitionError.code || ''}`;
      if (msg.type === 'retrieval-result' && msg.result) {
        return msg.apiStatus === 'FAILED' ? 'retrieval-result-failed' : 'retrieval-result-card';
      }
      if (msg.type === 'retrieval-result' && msg.apiStatus === 'FAILED') return `retrieval-failed:${msg.messageType || ''}`;
      return 'hidden';
    })();

    return [
      msg.id,
      visibleKind,
      msg.status || '',
      msg.apiStatus || '',
      msg.showGuide === false ? 'hidden-guide' : 'show-guide',
      msg.systems?.map(item => item.id).join(',') || '',
    ].join(':');
  }).join('|'));

  const handleSelectSuggestion = (text: string) => {
    chatInputRef.value?.setInputValue(text);
  };

  /** AI 瞬时失败：把原查询填回输入框，便于用户修改后重发 */
  const handleEditAndResend = (text: string) => {
    if (!text) return;
    chatInputRef.value?.setInputValue(text);
  };

  /** 自然语言字段检索：多选向输入框末尾追加，逗号区隔 */
  const handleAppendNlField = (text: string) => {
    chatInputRef.value?.appendInputValue(text);
  };

  const handleRegenerate = (text: string) => {
    if (text) emit('send', text);
  };

  const createConditionFilterCardId = () => (
    `cf-${Date.now()}-${Math.random().toString(36)
      .slice(2, 8)}`
  );

  const handleOpenConditionFilter = async (payload: { fieldName: string; sample?: string }) => {
    const cardId = createConditionFilterCardId();
    // 未检索：用新 id 覆盖当前草稿（强制重挂载重置条件）；已检索后列表为空则视为新建
    conditionFilterCards.value = [{
      id: cardId,
      fieldName: payload.fieldName,
      sample: payload.sample,
    }];
    await scrollConditionFilterIntoView(cardId, true);
  };

  const handleConditionSearched = (cardId: string, success: boolean) => {
    if (success) {
      // 检索成功后收起该条件卡；二次检索改在结果卡上操作
      conditionFilterCards.value = conditionFilterCards.value.filter(item => item.id !== cardId);
    }
    void scrollToBottom(true);
  };

  const handleReselectSystem = () => {
    conditionFilterCards.value = [];
    emit('reselect-system');
  };

  const resetConditionFilterPanel = () => {
    conditionFilterCards.value = [];
  };

  /** 平滑滚动到指定条件检索卡，锚定卡片而非瞬间跳到底 */
  const scrollConditionFilterIntoView = async (cardId: string, smooth = true): Promise<void> => {
    allowLoadOlder.value = false;
    await nextTick();
    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        const row = document.getElementById(`condition-filter-${cardId}`);
        if (!row) {
          allowLoadOlder.value = true;
          resolve();
          return;
        }
        requestAnimationFrame(() => {
          row.scrollIntoView({
            behavior: smooth ? 'smooth' : 'auto',
            block: 'end',
          });
          const enableLoadOlder = () => {
            allowLoadOlder.value = true;
            resolve();
          };
          if (smooth) {
            window.setTimeout(enableLoadOlder, CONDITION_FILTER_SCROLL_MS);
          } else {
            enableLoadOlder();
          }
        });
      });
    });
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

  watch(visibleMessageSignature, async (next, prev) => {
    if (!prev || next === prev || scrollAnchor.value) return;
    await scrollToBottom(true);
  });

  watch(() => props.conversationId, () => {
    scrollAnchor.value = null;
    olderLoadTriggered.value = false;
    allowLoadOlder.value = false;
    resetConditionFilterPanel();
    void scrollToBottom(false);
  });

  watch(() => props.messageLoading, (loading, wasLoading) => {
    clearMessageLoadingDelay();
    if (!loading) {
      showMessageLoading.value = false;
      if (wasLoading) {
        void scrollToBottom(false);
      }
      return;
    }
    messageLoadingDelayTimer = setTimeout(() => {
      messageLoadingDelayTimer = null;
      if (props.messageLoading) {
        showMessageLoading.value = true;
      }
    }, MESSAGE_LOADING_DELAY_MS);
  }, { immediate: true });

  onActivated(() => {
    allowLoadOlder.value = false;
    void scrollToBottom(false);
  });

  onBeforeUnmount(() => {
    clearMessageLoadingDelay();
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

  .message-area-loading {
    flex: 1;
    min-height: 160px;
  }

  .message-area-loading-box {
    min-height: 160px;
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

    &.condition-filter-row {
      overflow: visible;
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

      .recognition-resend-btn {
        margin-top: 4px;
      }
    }

    &.is-failed {
      align-items: center;
      justify-content: center;
      min-height: 200px;
      gap: 8px;
      text-align: center;

      .failed-icon {
        display: block;
        width: 48px;
        height: 48px;
      }

      .status-title,
      .status-desc {
        text-align: center;
      }

      .failed-retry-btn {
        margin-top: 4px;
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
      color: #4d4f56;
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
