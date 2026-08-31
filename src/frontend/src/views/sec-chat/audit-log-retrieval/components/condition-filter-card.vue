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
      <span class="card-title">请输入条件进行检索</span>
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
      v-if="searchState !== 'loading'"
      class="card-actions">
      <bk-button
        class="search-btn"
        theme="primary"
        @click="handleSearch">
        开始检索
      </bk-button>
    </div>
    <div
      v-else
      aria-label="检索中"
      class="card-actions">
      <div class="search-btn is-loading">
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
      v-else-if="inlineResult && searchState === 'done'"
      class="inline-result">
      <retrieval-result-card
        embedded
        :message-uid="resultMessageUid"
        :result="inlineResult" />
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

  import { useSecChatStore } from '../../composables/use-sec-chat-store';
  import type { RetrievalResultPayload, SelectedSystem, SystemFieldRow } from '../../types';
  import {
    buildAiSearchCondition,
    appendSearchModelField,
    createConditionFieldConfigFromSystemFields,
    createDefaultDatetime,
    createDefaultDatetimeOrigin,
    getConditionDefaultValue,
    getPrimaryFieldNames,
    getSecondaryFieldNames,
    sampleToConditionValue,
  } from '../config/condition-fields';

  import RetrievalResultCard from './retrieval-result-card.vue';

  const props = withDefaults(defineProps<{
    systems?: SelectedSystem[];
    standardFields?: SystemFieldRow[];
    extensionFields?: SystemFieldRow[];
  }>(), {
    systems: () => [],
    standardFields: () => [],
    extensionFields: () => [],
  });

  const emit = defineEmits<{
    searched: [];
  }>();

  const { sendConditionSearch } = useSecChatStore();

  const conditionTagsRef = ref<{ startEditField?:(fieldName: string) => void }>();
  const searchState = ref<'idle' | 'loading' | 'empty' | 'failed' | 'done'>('idle');
  const searchError = ref('');
  const inlineResult = ref<RetrievalResultPayload | null>(null);
  const resultMessageUid = ref('');
  const searchModel = ref<Record<string, any>>({
    datetime: createDefaultDatetime(),
    datetime_origin: createDefaultDatetimeOrigin(),
  });

  const fieldConfig = computed(() => createConditionFieldConfigFromSystemFields(
    props.standardFields,
    props.extensionFields,
  ));

  const commonFieldKeys = computed(() => getPrimaryFieldNames(props.standardFields));
  const extendFieldKeys = computed(() => getSecondaryFieldNames(props.extensionFields));

  const selectedFieldNames = computed(() => Object.keys(searchModel.value)
    .filter(key => key !== 'datetime_origin' && fieldConfig.value[key]));

  const getDefaultValue = (config: IFieldConfig) => getConditionDefaultValue(config);

  const sampleToValue = (config: IFieldConfig, sample?: string) => (
    sampleToConditionValue(config, sample)
  );

  const resolveFieldKey = (fieldNameOrLabel: string) => {
    if (fieldConfig.value[fieldNameOrLabel]) return fieldNameOrLabel;
    const matched = Object.entries(fieldConfig.value)
      .find(([, config]) => config.label === fieldNameOrLabel);
    return matched?.[0] || fieldNameOrLabel;
  };

  const appendField = (fieldName: string, value: any) => {
    searchModel.value = appendSearchModelField(
      searchModel.value,
      fieldName,
      value,
      {
        datetime: createDefaultDatetime(),
        datetimeOrigin: createDefaultDatetimeOrigin(),
      },
    );
  };

  const handleAddField = async (fieldName: string, config: IFieldConfig, initialValue?: any) => {
    if (fieldName !== 'datetime' && searchModel.value[fieldName] !== undefined) {
      conditionTagsRef.value?.startEditField?.(fieldName);
      return;
    }
    const value = initialValue !== undefined ? initialValue : getDefaultValue(config);
    appendField(fieldName, value);
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
    searchState.value = 'idle';
    searchError.value = '';
    inlineResult.value = null;
    resultMessageUid.value = '';
  };

  const handleSearch = async () => {
    if (searchState.value === 'loading') return;

    const scopeId = props.systems[0]?.id;
    const condition = buildAiSearchCondition({
      scopeId: scopeId || '',
      searchModel: searchModel.value,
      fieldConfig: fieldConfig.value,
    });
    if (!condition) {
      searchState.value = 'failed';
      searchError.value = scopeId ? '请至少选择时间范围' : '请先选择系统';
      inlineResult.value = null;
      resultMessageUid.value = '';
      return;
    }

    searchState.value = 'loading';
    searchError.value = '';
    inlineResult.value = null;
    resultMessageUid.value = '';

    try {
      const chatMessage = await sendConditionSearch(condition);
      if (chatMessage.apiStatus === 'FAILED') {
        searchState.value = 'failed';
        searchError.value = chatMessage.errorMessage || '检索失败';
        emit('searched');
        return;
      }
      const { result } = chatMessage;
      if (!result || result.totalHit === 0) {
        searchState.value = 'empty';
        emit('searched');
        return;
      }
      // 按设计稿：结果内嵌在当前条件卡，不追加消息列表卡片
      inlineResult.value = result;
      resultMessageUid.value = chatMessage.id;
      searchState.value = 'done';
      emit('searched');
    } catch (error: any) {
      searchState.value = 'failed';
      searchError.value = error?.message || '请检查网络是否通畅或联系管理员';
      emit('searched');
    }
  };

  const addOrFocusField = async (fieldNameOrLabel: string, sample?: string) => {
    const fieldName = resolveFieldKey(fieldNameOrLabel);
    const config = fieldConfig.value[fieldName];
    if (!config) return;

    if (fieldName === 'datetime' || searchModel.value[fieldName] !== undefined) {
      conditionTagsRef.value?.startEditField?.(fieldName);
      return;
    }

    await handleAddField(fieldName, config, sampleToValue(config, sample));
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
    margin-top: 32px;
    margin-bottom: 8px;
    min-height: 200px;
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
    margin-top: 24px;
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
