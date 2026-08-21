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
  <div class="condition-filter-card">
    <div class="card-title-row">
      <audit-icon
        class="title-icon"
        type="search1" />
      <span class="card-title">请添加条件进行检索</span>
    </div>

    <div class="condition-area">
      <condition-tags
        ref="conditionTagsRef"
        compact-select-popover
        :condition-list="[]"
        :event-field-items="[]"
        :field-config="fieldConfig"
        :search-model="searchModel"
        @clear-all="handleClear"
        @remove="handleRemoveCondition"
        @update="handleUpdateCondition">
        <add-condition
          accent
          :event-fields="[]"
          :field-config="fieldConfig"
          :primary-field-names="commonFieldKeys"
          primary-tab-label="通用字段"
          :secondary-field-names="extendFieldKeys"
          secondary-source="config"
          secondary-tab-label="拓展字段"
          :selected-event-field-ids="[]"
          :selected-fields="selectedFieldNames"
          @add-field="handleAddField" />
      </condition-tags>
    </div>

    <div
      v-if="searchState !== 'done'"
      class="card-actions">
      <bk-button
        v-if="searchState !== 'loading'"
        class="search-btn"
        theme="primary"
        @click="handleSearch">
        开始检索
      </bk-button>
      <div
        v-else
        aria-label="检索中"
        class="search-btn is-loading">
        <span class="loading-dot" />
        <span class="loading-dot" />
        <span class="loading-dot" />
        <span class="loading-dot" />
      </div>
    </div>

    <div
      v-if="searchState === 'empty'"
      class="status-panel is-empty">
      <img
        alt=""
        class="empty-icon"
        :src="emptySearchIcon">
      <div class="status-title">
        检索结果为空
      </div>
      <div class="status-desc">
        可以尝试修改或减少检索条件
      </div>
    </div>

    <div
      v-else-if="searchState === 'failed'"
      class="status-panel is-failed">
      <img
        alt=""
        class="failed-icon"
        :src="errorSearchIcon">
      <div class="status-title">
        检索失败
      </div>
      <div class="status-desc">
        {{ searchError || '请检查网络是否通畅或联系管理员' }}
      </div>
    </div>

    <div
      v-if="inlineResult && searchState === 'done'"
      class="inline-result">
      <retrieval-result-card
        embedded
        :result="inlineResult"
        @regenerate="handleSearch" />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import dayjs from 'dayjs';
  import { computed, nextTick, ref } from 'vue';

  import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

  import AddCondition from '@views/risk-manage/list/components/nl-search-box/components/add-condition.vue';
  import ConditionTags from '@views/risk-manage/list/components/nl-search-box/components/condition-tags.vue';

  import emptySearchIcon from '@images/empty-search.svg';
  import errorSearchIcon from '@images/error-search.svg';

  import RetrievalResultCard from './retrieval-result-card.vue';
  import type { RetrievalResultPayload, SelectedSystem } from '../../types';
  import { buildMockRetrievalResult } from '../utils/build-mock-result';
  import {
    COMMON_FIELD_KEYS,
    createConditionFieldConfig,
    createDefaultDatetime,
    createDefaultDatetimeOrigin,
    DATETIME_SHORTCUT_LABEL_MAP,
    EXTEND_FIELD_KEYS,
    FIELD_LABEL_TO_KEY,
  } from '../config/condition-fields';

  const props = withDefaults(defineProps<{
    systems?: SelectedSystem[];
  }>(), {
    systems: () => [],
  });

  const emit = defineEmits<{
    searched: [];
  }>();

  const commonFieldKeys = COMMON_FIELD_KEYS;
  const extendFieldKeys = EXTEND_FIELD_KEYS;

  const conditionTagsRef = ref<{ startEditField?:(fieldName: string) => void }>();
  const inlineResult = ref<RetrievalResultPayload | null>(null);
  const searchState = ref<'idle' | 'loading' | 'empty' | 'failed' | 'done'>('idle');
  const searchError = ref('');
  const searchAttempt = ref(0);
  const searchModel = ref<Record<string, any>>({
    datetime: createDefaultDatetime(),
    datetime_origin: createDefaultDatetimeOrigin(),
  });

  const fieldConfig = computed(() => createConditionFieldConfig(props.systems));

  const selectedFieldNames = computed(() => Object.keys(searchModel.value)
    .filter(key => key !== 'datetime_origin' && fieldConfig.value[key]));

  const getDefaultValue = (config: IFieldConfig) => {
    if (config.type === 'select' || config.type === 'user-selector') {
      return [];
    }
    if (config.type === 'datetimerange') {
      return createDefaultDatetime();
    }
    return '';
  };

  const resolveFieldKey = (fieldNameOrLabel: string) => (
    FIELD_LABEL_TO_KEY[fieldNameOrLabel] || fieldNameOrLabel
  );

  const sampleToValue = (config: IFieldConfig, sample?: string, fieldName?: string) => {
    if (!sample) {
      return getDefaultValue(config);
    }
    if (config.type === 'user-selector') {
      return [sample];
    }
    if (config.type === 'select') {
      if (fieldName === 'system_id') {
        const matched = props.systems.find(item => item.id === sample || item.name === sample);
        return [matched?.id || sample];
      }
      return [sample];
    }
    return sample;
  };

  const insertFieldAtFront = (fieldName: string, value: any) => {
    const next: Record<string, any> = {
      datetime: searchModel.value.datetime || createDefaultDatetime(),
      datetime_origin: searchModel.value.datetime_origin || createDefaultDatetimeOrigin(),
    };
    if (fieldName !== 'datetime' && fieldName !== 'datetime_origin') {
      next[fieldName] = value;
    }
    Object.keys(searchModel.value).forEach((key) => {
      if (key === 'datetime' || key === 'datetime_origin' || key === fieldName) return;
      next[key] = searchModel.value[key];
    });
    searchModel.value = next;
  };

  const handleAddField = async (fieldName: string, config: IFieldConfig, initialValue?: any) => {
    if (fieldName !== 'datetime' && searchModel.value[fieldName] !== undefined) {
      conditionTagsRef.value?.startEditField?.(fieldName);
      return;
    }
    const value = initialValue !== undefined ? initialValue : getDefaultValue(config);
    insertFieldAtFront(fieldName, value);
    conditionTagsRef.value?.startEditField?.(fieldName);
    await nextTick();
  };

  const handleRemoveCondition = (fieldName: string) => {
    if (fieldName === 'datetime') return;
    const next = { ...searchModel.value };
    delete next[fieldName];
    searchModel.value = next;
  };

  const handleUpdateCondition = (fieldName: string, value: any) => {
    if (fieldName === 'datetime') {
      if (Array.isArray(value) && value.length >= 2) {
        const formatted = value.map((item: any) => (
          typeof item === 'number' || item instanceof Date
            ? dayjs(item).format('YYYY-MM-DD HH:mm:ss')
            : item
        ));
        searchModel.value.datetime = formatted;
        searchModel.value.datetime_origin = formatted;
      }
      return;
    }
    if (fieldName === 'datetime_origin') {
      searchModel.value.datetime_origin = value;
      return;
    }
    searchModel.value[fieldName] = value;
  };

  const handleClear = () => {
    searchModel.value = {
      datetime: createDefaultDatetime(),
      datetime_origin: createDefaultDatetimeOrigin(),
    };
    inlineResult.value = null;
    searchState.value = 'idle';
    searchError.value = '';
  };

  const formatConditionValue = (fieldName: string, config: IFieldConfig, value: any): string => {
    if (config.type === 'datetimerange') {
      const origin = searchModel.value.datetime_origin?.[0];
      if (origin && DATETIME_SHORTCUT_LABEL_MAP[origin]) {
        return DATETIME_SHORTCUT_LABEL_MAP[origin];
      }
      if (Array.isArray(value) && value.length >= 2) {
        return `${value[0]} - ${value[1]}`;
      }
      return '';
    }
    if (Array.isArray(value)) {
      if (fieldName === 'system_id') {
        return value.map((item) => {
          const matched = props.systems.find(system => system.id === item || system.name === item);
          return matched ? `${matched.name}(${matched.id})` : String(item);
        }).filter(Boolean)
          .join('，');
      }
      return value.map(item => String(item)).filter(Boolean)
        .join('，');
    }
    if (value === undefined || value === null || value === '') {
      return '';
    }
    return String(value);
  };

  const hasConditionValue = (value: any) => {
    if (Array.isArray(value)) {
      return value.some(item => item !== undefined && item !== null && item !== '');
    }
    return value !== undefined && value !== null && value !== '';
  };

  const buildConditionSummary = () => {
    const parts: string[] = [];
    const datetimeValue = formatConditionValue('datetime', fieldConfig.value.datetime, searchModel.value.datetime);
    if (datetimeValue) {
      parts.push(`${fieldConfig.value.datetime.label}为${datetimeValue}`);
    }

    Object.keys(searchModel.value).forEach((fieldName) => {
      if (fieldName === 'datetime' || fieldName === 'datetime_origin' || fieldName === 'sort') return;
      const config = fieldConfig.value[fieldName];
      if (!config) return;
      const displayValue = formatConditionValue(fieldName, config, searchModel.value[fieldName]);
      if (!displayValue && !hasConditionValue(searchModel.value[fieldName])) return;
      parts.push(`${config.label}为${displayValue || '空'}`);
    });

    return parts.join('，');
  };

  const handleSearch = async () => {
    const summary = buildConditionSummary();
    if (!summary) return;
    if (searchState.value === 'loading') return;

    // 本阶段：mock 检索过程用来展示“检索中/检索为空/检索失败”样式
    searchAttempt.value += 1;
    searchState.value = 'loading';
    searchError.value = '';
    inlineResult.value = null;

    await new Promise(resolve => setTimeout(resolve, 1200));

    const mod = searchAttempt.value % 3;
    if (mod === 1) {
      searchState.value = 'empty';
      emit('searched');
      return;
    }
    if (mod === 2) {
      searchState.value = 'failed';
      searchError.value = '请检查网络是否畅通或联系管理员';
      emit('searched');
      return;
    }

    inlineResult.value = buildMockRetrievalResult(`条件筛选：${summary}`);
    searchState.value = 'done';
    emit('searched');
  };

  const addOrFocusField = async (fieldNameOrLabel: string, sample?: string) => {
    const fieldName = resolveFieldKey(fieldNameOrLabel);
    const config = fieldConfig.value[fieldName];
    if (!config) return;

    if (fieldName === 'datetime' || searchModel.value[fieldName] !== undefined) {
      conditionTagsRef.value?.startEditField?.(fieldName);
      return;
    }

    await handleAddField(fieldName, config, sampleToValue(config, sample, fieldName));
  };

  defineExpose({
    addOrFocusField,
  });
</script>

<style lang="postcss" scoped>
  .condition-filter-card {
    width: 100%;
    max-width: 100%;
    padding: 20px 24px 24px;
    overflow: visible;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 12px 32px 0 rgb(0 0 0 / 4%);
    box-sizing: border-box;
  }

  .card-title-row {
    display: flex;
    margin-bottom: 12px;
    align-items: center;

    .title-icon {
      margin-right: 8px;
      font-size: 16px;
      color: #979ba5;
      flex-shrink: 0;
    }

    .card-title {
      font-size: 14px;
      line-height: 22px;
      color: #313238;
    }
  }

  .condition-area {
    min-height: 32px;
  }

  .card-actions {
    display: flex;
    margin-top: 16px;
    justify-content: flex-start;

    .search-btn {
      display: inline-flex;
      min-width: 88px;
      height: 32px;
      padding: 0 16px;
      font-size: 14px;
      font-weight: 400;
      line-height: 32px;
      border-radius: 2px;
      align-items: center;
      justify-content: center;
      box-sizing: border-box;

      &.is-loading {
        gap: 4px;
        color: #fff;
        pointer-events: none;
        background: #a3c5fd;
        border: none;
      }
    }
  }

  .loading-dot {
    width: 4px;
    height: 4px;
    background: #fff;
    border-radius: 50%;
    opacity: 40%;
    animation: loading-dot 1s ease-in-out infinite;
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

  .loading-dot:nth-child(4) {
    animation-delay: .45s;
  }

  @keyframes loading-dot {
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

  .status-panel {
    display: flex;
    margin-top: 24px;
    min-height: 180px;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-sizing: border-box;
  }

  .status-panel.is-empty {
    .empty-icon {
      display: block;
      width: 98px;
      height: 88px;
    }

    .status-title {
      margin-top: 8px;
      font-size: 14px;
      line-height: 22px;
      color: #313238;
    }

    .status-desc {
      font-size: 12px;
      line-height: 18px;
      color: #4D4F56;
      text-align: center;
    }
  }

  .status-panel.is-failed {
    .failed-icon {
      display: block;
      width: 48px;
      height: 48px;
    }

    .status-title {
      margin-top: 8px;
      font-size: 14px;
      line-height: 22px;
      color: #313238;
    }

    .status-desc {
      font-size: 12px;
      line-height: 18px;
      color: #4D4F56;
      text-align: center;
    }
  }

  .inline-result {
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid #dcdee5;
  }
</style>
<style lang="postcss">
  /* 仅覆盖 AI 对话条件筛选：标签灰色底 + 32px 高，不影响风险列表条件区 */
  .condition-filter-card {
    .nl-condition-tags-first-row,
    .nl-condition-tags-content {
      align-items: center;
    }

    .condition-tag-item {
      height: 32px;
      padding: 0 8px 0 12px;
      background: #f0f1f5;
      border: 1px solid #dcdee5;
      box-sizing: border-box;

      &:hover {
        .tag-value-wrapper {
          background: transparent;
        }
      }
    }

    .nl-tag-input-item.is-editing {
      height: auto;
      min-height: 32px;
    }

    .nl-add-condition-trigger {
      height: 32px;
      padding: 0 12px;
      box-sizing: border-box;

      &.is-accent {
        background: #f0f5ff;
      }
    }

    .condition-clear-btn {
      height: 32px;
    }

    .nl-tag-user-selector-item.is-editing.condition-tag-item:not(.has-users),
    .nl-tag-user-selector-item.is-editing.condition-tag-item.has-users {
      height: 32px !important;
      max-height: 32px !important;
      min-height: 32px !important;
    }
  }
</style>
