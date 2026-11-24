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
  <bk-popover
    ref="popoverRef"
    :arrow="false"
    :disabled="disabled"
    ext-cls="match-scope-field-select-popover"
    :is-show="isShow"
    placement="bottom-start"
    theme="light"
    trigger="manual"
    @after-hidden="handleAfterHidden">
    <button
      ref="triggerRef"
      class="match-scope-field-trigger"
      :class="{ 'is-disabled': disabled, 'is-open': isShow }"
      :disabled="disabled"
      type="button"
      @click.stop="handleTogglePopover"
      @mousedown.stop>
      <span
        v-bk-tooltips="{
          content: displayLabel,
          disabled: !labelOverflow,
        }"
        class="match-scope-field-trigger__text"
        @mouseenter="checkTriggerOverflow">
        {{ displayLabel }}
      </span>
      <audit-icon
        class="match-scope-field-trigger__arrow"
        type="angle-line-down" />
    </button>
    <template #content>
      <div
        class="match-scope-field-panel"
        @click.stop
        @mousedown.stop>
        <div class="panel-tabs">
          <span
            class="panel-tab-item"
            :class="{ active: activeTab === 'risk' }"
            @click="activeTab = 'risk'">
            {{ t('风险字段') }}
          </span>
          <span
            class="panel-tab-item"
            :class="{ active: activeTab === 'event' }"
            @click="activeTab = 'event'">
            {{ t('事件字段') }}
          </span>
        </div>
        <div class="panel-search">
          <audit-icon
            class="panel-search-icon"
            type="search1" />
          <bk-input
            v-model="searchKeyword"
            clearable
            :placeholder="t('搜索字段名称')"
            size="small" />
        </div>
        <div
          v-bkloading="{ loading: activeTab === 'event' && eventLoading, opacity: 1 }"
          class="panel-field-list"
          :class="{ 'is-loading': activeTab === 'event' && eventLoading }">
          <template v-if="activeTab === 'risk'">
            <div
              v-for="item in filteredRiskFields"
              :key="item.field"
              class="field-item"
              :class="{ 'is-selected': item.field === modelValue }"
              @click="handleSelectRisk(item)">
              <span
                v-bk-tooltips="{
                  content: item.label,
                  disabled: !overflowFlags[`risk_${item.field}`],
                }"
                class="field-item-label"
                @mouseenter="(e: MouseEvent) => checkOverflow(`risk_${item.field}`, e)">
                {{ item.label }}
              </span>
            </div>
          </template>
          <template v-else-if="!strategyId">
            <div class="field-list-empty">
              {{ t('请先选择命中策略') }}
            </div>
          </template>
          <template v-else>
            <template
              v-for="group in eventFieldGroups"
              :key="group.label">
              <div
                class="field-group-header"
                @click="toggleGroup(group.label)">
                <audit-icon
                  class="field-group-arrow"
                  :class="{ 'is-collapsed': collapsedGroups[group.label] }"
                  type="angle-fill-down" />
                <span class="field-group-label">{{ group.label }} ({{ group.items.length }})</span>
              </div>
              <template v-if="!collapsedGroups[group.label]">
                <div
                  v-for="item in group.items"
                  :key="item.id"
                  class="field-item field-item-indent"
                  :class="{ 'is-selected': item.field_name === modelValue }"
                  @click="handleSelectEvent(item)">
                  <span
                    v-bk-tooltips="{
                      content: `${item.display_name}[${item.field_name}]`,
                      disabled: !overflowFlags[`event_${item.id}`],
                    }"
                    class="field-item-label"
                    @mouseenter="(e: MouseEvent) => checkOverflow(`event_${item.id}`, e)">
                    {{ `${item.display_name}[${item.field_name}]` }}
                  </span>
                </div>
              </template>
            </template>
          </template>
          <div
            v-if="isListEmpty && !(activeTab === 'event' && eventLoading)"
            class="field-list-empty">
            {{ t('暂无匹配字段') }}
          </div>
        </div>
      </div>
    </template>
  </bk-popover>
</template>
<script setup lang="ts">
  import {
    computed,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { ConditionFieldOption } from '@model/risk-whitelist/whitelist';

  import { compareFieldName, sortByBasicEventFieldOrder } from '@/utils/assist';

  export interface EventFieldOption {
    id: string;
    field_name: string;
    display_name: string;
    type?: string;
  }

  export interface FieldSelectPayload {
    field: string;
    field_name: string;
    field_label: string;
    field_group: 'risk' | 'event';
  }

  interface Props {
    modelValue?: string;
    label?: string;
    disabled?: boolean;
    strategyId?: string;
    riskFields?: ConditionFieldOption[];
    eventFields?: EventFieldOption[];
    eventLoading?: boolean;
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: '',
    label: '',
    disabled: false,
    strategyId: '',
    riskFields: () => [],
    eventFields: () => [],
    eventLoading: false,
  });

  const emit = defineEmits<{
    (e: 'change', payload: FieldSelectPayload): void;
  }>();

  const { t } = useI18n();
  const popoverRef = ref<{ hide?:() => void }>();
  const triggerRef = ref<HTMLElement>();
  const isShow = ref(false);
  const activeTab = ref<'risk' | 'event'>('risk');
  const searchKeyword = ref('');
  const labelOverflow = ref(false);
  const overflowFlags = ref<Record<string, boolean>>({});
  const collapsedGroups = ref<Record<string, boolean>>({});
  const pendingSelection = ref<FieldSelectPayload | null>(null);

  const displayLabel = computed(() => props.label || props.modelValue || t('请选择字段'));

  const filteredRiskFields = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    return props.riskFields.filter((item) => {
      if (!keyword) return true;
      return item.label.toLowerCase().includes(keyword)
        || item.name.toLowerCase().includes(keyword)
        || item.field.toLowerCase().includes(keyword);
    });
  });

  const filteredEventFields = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    let list = props.eventFields.filter(item => item.field_name !== 'strategy_id');
    if (keyword) {
      list = list.filter(item => item.display_name.toLowerCase().includes(keyword)
        || item.field_name.toLowerCase().includes(keyword));
    }
    const basicFields = list.filter(item => item.type === 'basic_event_field');
    const detailFields = list.filter(item => item.type !== 'basic_event_field');
    const sortedBasicFields = sortByBasicEventFieldOrder(basicFields);
    const sortedDetailFields = [...detailFields].sort((first, second) => {
      const displayNameCompare = compareFieldName(first.display_name, second.display_name);
      if (displayNameCompare !== 0) return displayNameCompare;
      return compareFieldName(first.field_name, second.field_name);
    });
    return sortedBasicFields.concat(sortedDetailFields);
  });

  const eventFieldGroups = computed(() => {
    const basicFields = sortByBasicEventFieldOrder(filteredEventFields.value
      .filter(item => item.type === 'basic_event_field'));
    const detailFields = filteredEventFields.value
      .filter(item => item.type !== 'basic_event_field');
    const groups: Array<{ label: string; items: EventFieldOption[] }> = [];
    if (basicFields.length > 0) {
      groups.push({ label: t('基本信息'), items: basicFields });
    }
    if (detailFields.length > 0) {
      groups.push({ label: t('事件详情'), items: detailFields });
    }
    return groups;
  });

  const isListEmpty = computed(() => {
    if (activeTab.value === 'risk') {
      return filteredRiskFields.value.length === 0;
    }
    if (!props.strategyId || props.eventLoading) return false;
    return eventFieldGroups.value.length === 0;
  });

  const checkOverflow = (key: string, e: MouseEvent) => {
    const el = e.target as HTMLElement;
    if (el) {
      overflowFlags.value[key] = el.scrollWidth > el.clientWidth;
    }
  };

  const checkTriggerOverflow = (e: MouseEvent) => {
    const el = e.target as HTMLElement;
    labelOverflow.value = Boolean(el && el.scrollWidth > el.clientWidth);
  };

  const toggleGroup = (label: string) => {
    collapsedGroups.value[label] = !collapsedGroups.value[label];
  };

  const closePopover = () => {
    document.removeEventListener('mousedown', handleDocumentClick, true);
    isShow.value = false;
    popoverRef.value?.hide?.();
  };

  const isInPopoverLayer = (target: Node) => {
    const el = target as HTMLElement;
    if (!el?.closest) return false;
    return !!el.closest('.match-scope-field-select-popover, .tippy-box, .bk-popover, .bk-pop2-content, .bk-popover2');
  };

  const handleDocumentClick = (event: MouseEvent) => {
    if (!isShow.value) return;
    const target = event.target as Node | null;
    if (!target) return;
    if (triggerRef.value?.contains(target as HTMLElement)) return;
    if (isInPopoverLayer(target)) return;
    closePopover();
  };

  const handleTogglePopover = () => {
    if (props.disabled) return;
    isShow.value = !isShow.value;
  };

  const handleSelectRisk = (item: ConditionFieldOption) => {
    pendingSelection.value = {
      field: item.field,
      field_name: item.name,
      field_label: item.label,
      field_group: 'risk',
    };
    closePopover();
  };

  const handleSelectEvent = (item: EventFieldOption) => {
    pendingSelection.value = {
      field: item.field_name,
      field_name: item.display_name,
      field_label: `${item.display_name}(${item.field_name})`,
      field_group: 'event',
    };
    closePopover();
  };

  const handleAfterHidden = () => {
    isShow.value = false;
    if (!pendingSelection.value) return;
    emit('change', pendingSelection.value);
    pendingSelection.value = null;
  };

  watch(isShow, (value) => {
    if (value) {
      searchKeyword.value = '';
      const currentIsEvent = props.eventFields.some(item => item.field_name === props.modelValue);
      activeTab.value = currentIsEvent ? 'event' : 'risk';
      setTimeout(() => {
        document.addEventListener('mousedown', handleDocumentClick, true);
      });
      return;
    }
    document.removeEventListener('mousedown', handleDocumentClick, true);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('mousedown', handleDocumentClick, true);
  });
</script>
<style lang="postcss" scoped>
  .match-scope-field-trigger {
    display: inline-flex;
    width: 100%;
    height: 32px;
    padding: 0 var(--bk-theme-space-8) 0 var(--bk-theme-space-12);
    font-size: 12px;
    color: var(--bk-theme-text-default);
    cursor: pointer;
    background: var(--bk-theme-surface-default);
    border: 1px solid var(--bk-theme-border-default);
    border-radius: var(--bk-theme-tag-radius);
    align-items: center;
    box-sizing: border-box;

    &:hover:not(.is-disabled) {
      border-color: var(--bk-theme-color-brand-2);
    }

    &.is-open {
      border-color: var(--bk-theme-color-brand-2);
    }

    &.is-disabled {
      color: var(--bk-theme-text-weak);
      cursor: not-allowed;
      background: var(--bk-theme-surface-subtle);
    }
  }

  .match-scope-field-trigger__text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: left;
    flex: 1;
  }

  .match-scope-field-trigger__arrow {
    margin-left: var(--bk-theme-space-4);
    font-size: 12px;
    color: var(--bk-theme-text-weak);
    flex-shrink: 0;
  }
</style>
<style lang="postcss">
  .match-scope-field-panel {
    width: 300px;
    max-width: calc(100vw - 24px);
    min-width: 240px;
    padding: 0;
    box-sizing: border-box;

    .panel-tabs {
      display: flex;
      gap: var(--bk-theme-space-8);
      padding: var(--bk-theme-space-4);
      background-color: var(--bk-theme-surface-muted);

      .panel-tab-item {
        display: inline-flex;
        height: 22px;
        padding: 0 var(--bk-theme-space-32);
        font-size: 12px;
        color: var(--bk-theme-text-default);
        cursor: pointer;
        background: transparent;
        border: 1px solid transparent;
        transition: all .15s;
        align-items: center;
        justify-content: center;
        flex: 1;

        &.active {
          color: var(--bk-theme-color-brand-2);
          background: var(--bk-theme-surface-default);
        }
      }
    }

    .panel-search {
      display: flex;
      padding: var(--bk-theme-space-4) var(--bk-theme-space-12);
      margin-bottom: var(--bk-theme-space-2);
      border-bottom: 1px solid var(--bk-theme-border-default);
      align-items: center;

      .panel-search-icon {
        margin-right: var(--bk-theme-space-6);
        font-size: 15px;
        color: var(--bk-theme-text-weak);
        flex-shrink: 0;
      }

      .bk-input {
        border: none;
        border-radius: 0;
        box-shadow: none;
      }
    }

    .panel-field-list {
      max-height: 260px;
      padding-bottom: var(--bk-theme-space-4);
      overflow: hidden auto;

      &.is-loading {
        min-height: 160px;
      }

      &::-webkit-scrollbar {
        width: 4px;
        height: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: var(--bk-theme-border-strong);
        border-radius: var(--bk-theme-tag-radius);
      }

      &::-webkit-scrollbar-track {
        background: transparent;
      }

      .field-group-header {
        display: flex;
        height: 32px;
        padding: 0 var(--bk-theme-space-12);
        cursor: pointer;
        align-items: center;
        user-select: none;

        &:hover {
          background: var(--bk-theme-surface-subtle);
        }

        .field-group-arrow {
          margin-right: var(--bk-theme-space-6);
          font-size: 12px;
          color: var(--bk-theme-text-weak);
          transition: transform .2s;

          &.is-collapsed {
            transform: rotate(-90deg);
          }
        }

        .field-group-label {
          font-size: 12px;
          color: var(--bk-theme-text-weak);
        }
      }

      .field-item {
        display: flex;
        min-height: 36px;
        padding: var(--bk-theme-space-6) var(--bk-theme-space-16);
        font-size: 12px;
        color: var(--bk-theme-text-default);
        cursor: pointer;
        align-items: center;
        transition: background .15s;

        &:hover {
          background: var(--bk-theme-surface-subtle);
        }

        &.is-selected {
          color: var(--bk-theme-color-brand-2);
        }

        &.field-item-indent {
          padding-left: var(--bk-theme-space-32);
        }

        .field-item-label {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          flex: 1;
        }
      }

      .field-list-empty {
        padding: var(--bk-theme-space-24) 0;
        font-size: 12px;
        color: var(--bk-theme-border-strong);
        text-align: center;
      }
    }
  }

  .match-scope-field-select-popover.bk-popover.bk-pop2-content {
    padding: var(--bk-theme-space-6);
  }
</style>
