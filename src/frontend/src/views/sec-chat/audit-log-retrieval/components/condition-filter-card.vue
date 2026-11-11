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
    <selected-systems-panel
      v-if="systems.length"
      action-text="重新选择"
      class="filter-systems-section"
      :systems="systems"
      @action="$emit('reselectSystem')" />

    <div class="card-title-row">
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
        <template #before-all>
          <readonly-system-tag
            v-if="showSystemTag"
            :systems="systems" />
        </template>
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
      v-if="!isSearching"
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
      v-if="searchState === 'failed'"
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
  </div>
</template>

<script lang="ts" setup>
  import dayjs from 'dayjs';
  import { computed, nextTick, onMounted, ref } from 'vue';

  import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

  import AddCondition from '@views/risk-manage/list/components/nl-search-box/components/add-condition.vue';
  import ConditionTags from '@views/risk-manage/list/components/nl-search-box/components/condition-tags.vue';

  import errorSearchIcon from '@images/error-search.svg';

  import { useSecChatStore } from '../../composables/use-sec-chat-store';
  import type { SelectedSystem, SystemFieldRow } from '../../types';
  import {
    appendSearchModelField,
    buildAiSearchCondition,
    createConditionFieldConfigFromSystemFields,
    createDefaultDatetime,
    createDefaultDatetimeOrigin,
    getConditionDefaultValue,
    getPrimaryFieldNames,
    getSecondaryFieldNames,
    sampleToConditionValue,
  } from '../config/condition-fields';
  import ReadonlySystemTag from './readonly-system-tag.vue';
  import SelectedSystemsPanel from './selected-systems-panel.vue';

  import { isRelativeDatetimeOrigin, syncDatetimeFromOrigin } from '@/utils/sync-datetime-from-url';

  const props = withDefaults(defineProps<{
    systems?: SelectedSystem[];
    standardFields?: SystemFieldRow[];
    extensionFields?: SystemFieldRow[];
    /** 引导卡点条件筛选时预填的字段 */
    initialFieldName?: string;
    initialSample?: string;
    /** 来源引导卡的 SYSTEM_SELECTION uid，作为 LOG_SEARCH 直接父消息 */
    selectionMessageUid?: string;
  }>(), {
    systems: () => [],
    standardFields: () => [],
    extensionFields: () => [],
    initialFieldName: '',
    initialSample: undefined,
    selectionMessageUid: '',
  });

  const emit = defineEmits<{
    searched: [success: boolean];
    reselectSystem: [];
  }>();

  const SYSTEM_FIELD_KEYS = new Set(['system_id', '来源系统']);

  const { sendConditionSearch } = useSecChatStore();

  const conditionTagsRef = ref<{ startEditField?:(fieldName: string) => void }>();
  const showSystemTag = ref(false);
  const searchState = ref<'idle' | 'loading' | 'failed'>('idle');
  const searchError = ref('');
  const searchModel = ref<Record<string, any>>({
    datetime: createDefaultDatetime(),
    datetime_origin: createDefaultDatetimeOrigin(),
  });

  const isSearching = computed(() => searchState.value === 'loading');

  /** 与结果卡一致：系统改选只走「重新选择」，不在条件 tag 中编辑来源系统 */
  const fieldConfig = computed(() => {
    const nextConfig = createConditionFieldConfigFromSystemFields(
      props.standardFields,
      props.extensionFields,
    );
    delete nextConfig.system_id;
    return nextConfig;
  });

  const commonFieldKeys = computed(() => (
    getPrimaryFieldNames(props.standardFields).filter(key => key !== 'system_id')
  ));
  const extendFieldKeys = computed(() => getSecondaryFieldNames(props.extensionFields));

  const selectedFieldNames = computed(() => Object.keys(searchModel.value)
    .filter(key => key !== 'datetime_origin' && key !== 'system_id' && fieldConfig.value[key]));

  const isSystemFieldName = (fieldName: string) => SYSTEM_FIELD_KEYS.has(fieldName);

  const getDefaultValue = (config: IFieldConfig) => getConditionDefaultValue(config);

  const sampleToValue = (config: IFieldConfig, sample?: string) => (
    sampleToConditionValue(config, sample)
  );

  const resolveFieldKey = (fieldNameOrLabel: string) => {
    if (isSystemFieldName(fieldNameOrLabel)) return 'system_id';
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
    if (fieldName === 'datetime' || fieldName === 'system_id') return;
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
        // 只更新绝对时间；datetime_origin 由后续 emit 决定（快捷或手选）
        searchModel.value.datetime = formatted;
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
  };

  const handleSearch = async () => {
    if (isSearching.value) return;

    if (isRelativeDatetimeOrigin(searchModel.value.datetime_origin)) {
      searchModel.value.datetime = syncDatetimeFromOrigin(searchModel.value.datetime_origin);
    }

    const scopeId = props.systems[0]?.id;
    const condition = buildAiSearchCondition({
      scopeId: scopeId || '',
      searchModel: searchModel.value,
      fieldConfig: fieldConfig.value,
    });
    if (!condition) {
      searchState.value = 'failed';
      searchError.value = scopeId ? '请至少选择时间范围' : '请先选择系统';
      return;
    }

    searchState.value = 'loading';
    searchError.value = '';

    try {
      const chatMessage = await sendConditionSearch(condition, {
        datetimeOrigin: searchModel.value.datetime_origin,
        parentMessageUid: props.selectionMessageUid || undefined,
      });

      if (chatMessage.apiStatus === 'FAILED') {
        searchState.value = 'failed';
        searchError.value = chatMessage.errorMessage || '请检查网络是否通畅或联系管理员';
        // 关闭条件草稿卡，由消息流中的结果卡承接失败态（条件区 + 居中失败）
        emit('searched', true);
        return;
      }

      searchState.value = 'idle';
      emit('searched', true);
    } catch (error: any) {
      searchState.value = 'failed';
      searchError.value = error?.message || '请检查网络是否通畅或联系管理员';
      emit('searched', false);
    }
  };

  const addOrFocusField = async (fieldNameOrLabel: string, sample?: string) => {
    const fieldName = resolveFieldKey(fieldNameOrLabel);
    // 来源系统：点选后才展示只读标签（排最前），不可编辑
    if (fieldName === 'system_id' || isSystemFieldName(fieldNameOrLabel)) {
      showSystemTag.value = true;
      return;
    }

    const config = fieldConfig.value[fieldName];
    if (!config) return;

    if (fieldName === 'datetime' || searchModel.value[fieldName] !== undefined) {
      conditionTagsRef.value?.startEditField?.(fieldName);
      return;
    }

    await handleAddField(fieldName, config, sampleToValue(config, sample));
  };

  onMounted(async () => {
    if (!props.initialFieldName) return;
    await nextTick();
    await addOrFocusField(props.initialFieldName, props.initialSample);
  });

  defineExpose({
    addOrFocusField,
  });
</script>

<style lang="postcss" scoped>
  .condition-filter-card {
    width: 100%;
    max-width: 100%;padding: var(--bk-theme-space-16) var(--bk-theme-space-24) var(--bk-theme-space-24);
    overflow: visible;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: var(--bk-theme-text-default);
    letter-spacing: 0;
    background: var(--bk-theme-surface-default);
    border-radius: var(--bk-theme-dialog-radius);
    box-shadow: 0 12px 32px 0 rgb(0 0 0 / 4%);
    box-sizing: border-box;
  }

  .filter-systems-section {
    margin-bottom: var(--bk-theme-space-16);
    padding-bottom: var(--bk-theme-space-16);
    border-bottom: 1px solid var(--bk-theme-border-weak);
  }

  .card-title-row {
    display: flex;
    margin-bottom: var(--bk-theme-space-12);
    align-items: center;

    .card-title {
      font-size: 14px;
      line-height: 22px;
      color: var(--bk-theme-text-strong);
    }
  }

  .condition-area {
    min-height: 32px;
  }

  .card-actions {
    display: flex;
    margin-top: var(--bk-theme-space-16);
    justify-content: flex-start;

    .search-btn {
      display: inline-flex;
      min-width: 88px;
      height: 32px;
      padding: 0 var(--bk-theme-space-16);
      font-size: 14px;
      font-weight: 400;
      line-height: 32px;
      border-radius: var(--bk-theme-tag-radius);
      align-items: center;
      justify-content: center;
      box-sizing: border-box;

      &.is-loading {
        gap: var(--bk-theme-space-4);
        color: var(--bk-theme-surface-default);
        pointer-events: none;
        background: var(--bk-theme-color-brand-4);
        border: none;
      }
    }
  }

  .loading-dot {
    width: 4px;
    height: 4px;
    background: var(--bk-theme-surface-default);
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
    margin-top: var(--bk-theme-space-32);
    margin-bottom: var(--bk-theme-space-8);
    min-height: 200px;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--bk-theme-space-8);
    box-sizing: border-box;
  }

  .status-panel.is-failed {
    .failed-icon {
      display: block;
      width: 48px;
      height: 48px;
    }

    .status-title {
      margin-top: var(--bk-theme-space-8);
      font-size: 14px;
      line-height: 22px;
      color: var(--bk-theme-text-strong);
    }

    .status-desc {
      font-size: 12px;
      line-height: 18px;
      color: var(--bk-theme-text-default);
      text-align: center;
    }
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
      padding: 0 var(--bk-theme-space-8) 0 var(--bk-theme-space-12);
      background: var(--bk-theme-surface-muted);
      border: 1px solid var(--bk-theme-border-default);
      box-sizing: border-box;

      &:hover {
        .tag-value-wrapper {
          background: transparent;
        }
      }

      &.is-readonly-system {
        cursor: default;
        padding-right: var(--bk-theme-space-12);
      }
    }

    .nl-tag-input-item.is-editing {
      height: auto;
      min-height: 32px;
    }

    .nl-add-condition-trigger {
      height: 32px;
      padding: 0 var(--bk-theme-space-12);
      box-sizing: border-box;

      &.is-accent {
        background: var(--bk-theme-select-banner-bg);
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
