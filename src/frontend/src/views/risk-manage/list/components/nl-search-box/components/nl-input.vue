<!--
  TencentBlueKing is pleased to support the open source community by making
  BlueKing - Audit Center available.
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
  <div
    ref="rootRef"
    class="nl-search-input">
    <div
      class="nl-input-wrapper"
      :class="{ 'is-disabled': loading }"
      @click="handleWrapperClick">
      <input
        ref="inputRef"
        v-model="inputValue"
        class="nl-input-inner"
        :disabled="loading"
        :placeholder="t('支持自然语言输入，如：张三最近一周的高风险单，或直接在下方添加搜索条件')"
        type="text"
        @compositionend="isComposing = false"
        @compositionstart="isComposing = true"
        @focus="handleFocus"
        @keydown.enter="handleSubmit">
      <div
        v-if="inputValue && !loading"
        class="nl-input-clear"
        @click.stop="handleClear">
        <audit-icon type="close-circle-fill" />
      </div>
      <span
        v-if="loading"
        class="nl-input-loading-text">
        {{ t('AI 正在解析中，请稍候…') }}
      </span>
      <div
        class="nl-input-send-btn"
        :class="{ 'is-loading': loading, 'is-active': !!inputValue.trim() }"
        @click.stop="handleSubmit">
        <audit-icon
          v-if="loading"
          class="rotate-animation"
          type="loading" />
        <img
          v-else
          class="nl-input-submit-icon"
          :src="inputValue.trim() ? submitBlue : submitGray">
      </div>
    </div>
    <div
      v-if="isPanelVisible"
      class="nl-input-panel">
      <div class="nl-input-panel-columns">
        <div class="nl-input-panel-column">
          <div class="nl-input-panel-title">
            {{ t('推荐示例') }}
          </div>
          <div
            v-for="(item, index) in recommendationList"
            :key="item"
            :ref="(el) => setPanelItemRef(getPanelItemKey('recommendation', index), el as HTMLElement | null)"
            v-bk-tooltips="{
              content: item,
              disabled: !panelItemOverflowMap[getPanelItemKey('recommendation', index)],
              extCls: 'nl-tag-tooltip-wrap',
            }"
            class="nl-input-panel-item"
            @mousedown.prevent="handleSelectPanelItem(item)">
            {{ item }}
          </div>
        </div>
        <div class="nl-input-panel-divider" />
        <div class="nl-input-panel-column">
          <div class="nl-input-panel-title">
            {{ t('搜索记录') }}
          </div>
          <template v-if="historyList.length">
            <div
              v-for="(item, index) in historyList"
              :key="item.id"
              :ref="(el) => setPanelItemRef(getPanelItemKey('history', index), el as HTMLElement | null)"
              v-bk-tooltips="{
                content: item.query,
                disabled: !panelItemOverflowMap[getPanelItemKey('history', index)],
                extCls: 'nl-tag-tooltip-wrap',
              }"
              class="nl-input-panel-item is-history"
              @mousedown.prevent="handleSelectPanelItem(item.query)">
              {{ item.query }}
            </div>
          </template>
          <div
            v-else
            class="nl-input-panel-empty">
            {{ t('暂无搜索记录') }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';
  import useRequest from '@hooks/use-request';

  import submitBlue from '@/images/submit-blue.svg';
  import submitGray from '@/images/submit-gray.svg';
  import type { INL2RiskFilterLogItem } from '../types';

  interface Props {
    historyRefreshKey?: number;
    loading?: boolean;
    riskViewType?: string;
  }

  interface Emits {
    (e: 'submit', value: string): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    historyRefreshKey: 0,
    loading: false,
    riskViewType: 'all',
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const rootRef = ref<HTMLElement>();
  const inputRef = ref<HTMLInputElement>();
  const inputValue = ref('');
  const isComposing = ref(false);
  const isPanelVisible = ref(false);
  const hasLoadedHistory = ref(false);
  const historyList = ref<INL2RiskFilterLogItem[]>([]);
  const panelItemRefs = ref<Record<string, HTMLElement | null>>({});
  const panelItemOverflowMap = ref<Record<string, boolean>>({});
  let resizeObserver: ResizeObserver | null = null;

  const recommendationList = computed(() => ([
    t('责任人为「替换为实际责任人」的风险单'),
    t('风险等级为「替换为实际风险等级」的风险单'),
    t('风险命中策略为「替换为实际策略名称」的风险单'),
    t('风险ID为「替换为实际风险ID」的风险单'),
    t('风险标题包含「替换为实际风险标题」的风险单'),
    t('事件字段云区域ID为「替换为实际云区域ID」的风险单'),
  ]));

  const {
    run: fetchNl2RiskFilterLog,
  } = useRequest(RiskManageService.fetchNl2RiskFilterLog, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 0,
    },
    // 本项目 useRequest：manual=true 会在 onMounted 用 defaultParams 自动请求
    manual: true,
    defaultParams: {
      page: 1,
      page_size: 6,
      status: 'success',
      risk_view_type: props.riskViewType || 'all',
    },
    onSuccess(data) {
      historyList.value = (data?.results || []).slice(0, 6);
      hasLoadedHistory.value = true;
    },
  });

  const loadHistory = () => fetchNl2RiskFilterLog({
    page: 1,
    page_size: 6,
    status: 'success',
    risk_view_type: props.riskViewType || 'all',
  });

  const getPanelItemKey = (type: 'recommendation' | 'history', index: number) => `${type}-${index}`;

  const setPanelItemRef = (key: string, el: HTMLElement | null) => {
    if (el) {
      panelItemRefs.value[key] = el;
      return;
    }
    delete panelItemRefs.value[key];
  };

  const checkPanelItemOverflow = () => {
    const result: Record<string, boolean> = {};
    Object.entries(panelItemRefs.value).forEach(([key, el]) => {
      if (el) {
        result[key] = el.scrollWidth > el.clientWidth;
      }
    });
    panelItemOverflowMap.value = result;
  };

  const openPanel = () => {
    if (props.loading) {
      return;
    }
    isPanelVisible.value = true;
    if (!hasLoadedHistory.value) {
      loadHistory();
    }
  };

  const closePanel = () => {
    isPanelVisible.value = false;
  };

  const handleFocus = () => {
    openPanel();
  };

  const handleWrapperClick = () => {
    if (props.loading) return;
    inputRef.value?.focus();
    openPanel();
  };

  const handleSelectPanelItem = (value: string) => {
    inputValue.value = value;
    inputRef.value?.focus();
  };

  const handleSubmit = () => {
    if (isComposing.value || props.loading) return;
    const value = inputValue.value.trim();
    if (!value) return;
    closePanel();
    emit('submit', value);
  };

  const handleClear = () => {
    inputValue.value = '';
    inputRef.value?.focus();
    openPanel();
  };

  const handleDocumentClick = (event: MouseEvent) => {
    const target = event.target as Node;
    if (rootRef.value && !rootRef.value.contains(target)) {
      closePanel();
    }
  };

  watch(() => props.historyRefreshKey, () => {
    loadHistory();
  });

  watch(() => props.riskViewType, () => {
    hasLoadedHistory.value = false;
    if (isPanelVisible.value) {
      loadHistory();
    }
  });

  // 列表/智能搜索 loading 时关闭示例框，避免被表格 loading 遮罩盖住
  watch(() => props.loading, (loading) => {
    if (loading) {
      closePanel();
    }
  });

  watch(historyList, () => {
    nextTick(() => {
      checkPanelItemOverflow();
    });
  });

  watch(recommendationList, () => {
    nextTick(() => {
      checkPanelItemOverflow();
    });
  });

  watch(isPanelVisible, (visible) => {
    if (!visible) {
      return;
    }
    nextTick(() => {
      checkPanelItemOverflow();
    });
  });

  onMounted(() => {
    resizeObserver = new ResizeObserver(() => {
      checkPanelItemOverflow();
    });
    if (rootRef.value) {
      resizeObserver.observe(rootRef.value);
    }
    document.addEventListener('click', handleDocumentClick);
  });

  onBeforeUnmount(() => {
    resizeObserver?.disconnect();
    document.removeEventListener('click', handleDocumentClick);
  });

  defineExpose({
    clear() {
      inputValue.value = '';
      closePanel();
    },
    focus() {
      inputRef.value?.focus();
    },
    refreshHistory() {
      loadHistory();
    },
  });
</script>

<style lang="postcss">
  @keyframes rotate {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  @keyframes nl-border-flow {
    0% { background-position: 0% 50%; }
    100% { background-position: 200% 50%; }
  }
  .nl-search-input {
    position: relative;
    z-index: 510;
    padding: var(--bk-theme-space-16) var(--bk-theme-space-24) var(--bk-theme-space-8);

    .nl-input-wrapper {
      position: relative;
      display: flex;
      align-items: center;
      height: 40px;
      padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
      background: var(--bk-theme-surface-default);
      border: 1px solid var(--bk-theme-search-input-border);
      border-radius: var(--bk-theme-search-card-inner-radius);

      &.is-disabled {
        cursor: default;

        .nl-input-inner {
          color: var(--bk-theme-text-weak);
          cursor: default;
        }
      }
    }

    .nl-input-inner {
      flex: 1;
      height: 100%;
      font-size: var(--bk-theme-font-size-sm);
      line-height: var(--bk-theme-line-height-sm);
      color: var(--bk-theme-text-default);
      background: transparent;
      border: none;
      outline: none;

      &::placeholder {
        color: var(--bk-theme-text-disabled);
      }
    }

    .nl-input-clear {
      margin-right: var(--bk-theme-space-8);
      font-size: var(--bk-theme-font-size-lg);
      color: var(--bk-theme-text-disabled);
      cursor: pointer;
      flex-shrink: 0;
      transition: color .15s;

      &:hover {
        color: var(--bk-theme-text-weak);
      }
    }

    .nl-input-loading-text {
      margin-right: var(--bk-theme-space-8);
      font-size: var(--bk-theme-font-size-sm);
      color: transparent;
      white-space: nowrap;
      background: linear-gradient(90deg, #488bff, #c43bff, #488bff);
      background-clip: text;
      background-size: 200% 100%;
      flex-shrink: 0;
      animation: nl-border-flow 2s linear infinite;
    }

    .nl-input-send-btn {
      display: flex;
      width: 30px;
      height: 30px;
      font-size: var(--bk-theme-font-size-lg);
      color: var(--bk-theme-text-disabled);
      cursor: pointer;
      border-radius: 50%;
      transition: all .15s;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      .nl-input-submit-icon {
        width: 30px;
        height: 30px;
        object-fit: contain;
      }

      &.is-loading {
        color: var(--bk-theme-color-brand-2);
        cursor: not-allowed;

        .rotate-animation {
          animation: rotate 1s linear infinite;
        }
      }
    }

    .nl-input-panel {
      position: absolute;
      top: 68px;
      left: var(--bk-theme-space-24);
      z-index: 520;
      width: min(790px, calc(100% - 48px));
      overflow: hidden;
      background: var(--bk-theme-surface-default);
      border: 1px solid var(--bk-theme-border-weak);
      border-radius: var(--bk-theme-overlay-radius);
      box-shadow: var(--bk-theme-overlay-shadow);
    }

    .nl-input-panel-columns {
      display: flex;
      min-height: 258px;
    }

    .nl-input-panel-column {
      flex: 1;
      min-width: 0;
      padding: var(--bk-theme-space-16) 0 var(--bk-theme-space-12);
    }

    .nl-input-panel-divider {
      width: 1px;
      margin: var(--bk-theme-space-12) 0;
      background: var(--bk-theme-border-default);
      flex-shrink: 0;
    }

    .nl-input-panel-title {
      padding: 0 var(--bk-theme-space-16) var(--bk-theme-space-6);
      font-size: var(--bk-theme-font-size-sm);
      font-weight: var(--bk-theme-font-weight-regular);
      line-height: var(--bk-theme-line-height-sm);
      color: var(--bk-theme-text-weak);
    }

    .nl-input-panel-item {
      padding: 0 var(--bk-theme-space-16);
      overflow: hidden;
      font-size: var(--bk-theme-font-size-sm);
      font-weight: var(--bk-theme-font-weight-regular);
      line-height: 34px;
      color: var(--bk-theme-text-default);
      text-overflow: ellipsis;
      white-space: nowrap;
      cursor: pointer;
      transition: all .15s;

      &:hover {
        color: var(--bk-theme-color-brand-2);
        background: var(--bk-theme-fill-selected);
      }
    }

    .nl-input-panel-item.is-history {
      &:hover {
        color: var(--bk-theme-text-default);
        background: var(--bk-theme-surface-subtle);
      }
    }

    .nl-input-panel-empty {
      padding: 0 var(--bk-theme-space-16);
      font-size: var(--bk-theme-font-size-sm);
      line-height: 40px;
      color: var(--bk-theme-text-disabled);
    }
  }
</style>
