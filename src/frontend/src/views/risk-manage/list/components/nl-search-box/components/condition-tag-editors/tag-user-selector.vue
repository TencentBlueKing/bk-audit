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
    ref="wrapperRef"
    class="condition-tag-item nl-tag-user-selector-item"
    :class="{ 'is-editing': isEditing }">
    <template v-if="!isEditing">
      <div
        class="tag-view-content"
        @click="handleStartEdit">
        <span class="tag-label">{{ t(tag.label) }}:</span>
        <span
          v-bk-tooltips="{
            content: fullDisplayValue,
            disabled: !isOverflow,
            extCls: 'nl-tag-tooltip-wrap',
          }"
          class="tag-value-wrapper">
          <span class="tag-value">{{ displayValue }}</span>
        </span>
      </div>
      <audit-icon
        class="tag-remove-btn"
        type="close"
        @click.stop="$emit('remove', tag.fieldName)" />
    </template>

    <template v-else>
      <span class="tag-label">{{ t(tag.label) }}:</span>
      <div class="nl-tag-user-selector-edit-zone">
        <audit-user-selector-tenant
          v-model="localValue"
          allow-create
          auto-focus
          class="nl-tag-user-selector"
          :placeholder="t('请输入人员')"
          @update:model-value="handleValueChange" />
      </div>
      <audit-icon
        class="tag-remove-btn"
        type="close"
        @click.stop="$emit('remove', tag.fieldName)" />
    </template>
  </div>
</template>

<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { IConditionTag } from '../../types';

  interface Props {
    tag: IConditionTag;
    isEditing: boolean;
  }

  interface Emits {
    (e: 'startEdit', fieldName: string): void;
    (e: 'update', fieldName: string, value: any): void;
    (e: 'remove', fieldName: string): void;
    (e: 'finishEdit'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const maxMultiLen = 10;

  const localValue = ref<string[]>([]);
  const wrapperRef = ref<HTMLElement>();

  const formatUsers = (value: unknown) => {
    if (!Array.isArray(value) || value.length === 0) {
      return [];
    }
    return value.map(item => String(item)).filter(Boolean);
  };

  const fullDisplayValue = computed(() => {
    const users = formatUsers(props.tag.value);
    return users.length ? users.join(', ') : '--';
  });

  const displayValue = computed(() => {
    const users = formatUsers(props.tag.value);
    if (users.length === 0) {
      return '--';
    }
    let displayText = '';
    let visibleCount = 0;
    for (const user of users) {
      const nextText = visibleCount === 0 ? user : `${displayText}, ${user}`;
      if (nextText.length > maxMultiLen && visibleCount > 0) {
        break;
      }
      displayText = nextText;
      visibleCount += 1;
    }
    const remaining = users.length - visibleCount;
    return remaining > 0 ? `${displayText}, +${remaining}` : displayText;
  });

  const isOverflow = computed(() => fullDisplayValue.value.length > maxMultiLen);

  const isInSelectPopover = (target: Node) => {
    const el = target as HTMLElement;
    if (!el?.closest) {
      return false;
    }
    return !!el.closest('.bk-select-popover, .bk-select-content, .bk-popover2, .bk-popover, .bk-pop2-content');
  };

  const handleStartEdit = () => {
    emit('startEdit', props.tag.fieldName);
  };

  const handleValueChange = (value: string[] | string) => {
    let nextValue: string[] = [];
    if (Array.isArray(value)) {
      nextValue = value;
    } else if (value) {
      nextValue = [value];
    }
    localValue.value = nextValue;
    emit('update', props.tag.fieldName, [...nextValue]);
  };

  const handleDocumentClick = (e: MouseEvent) => {
    if (!props.isEditing) {
      return;
    }
    const target = e.target as Node;
    if (wrapperRef.value?.contains(target as HTMLElement)) {
      return;
    }
    if (isInSelectPopover(target)) {
      return;
    }
    emit('finishEdit');
  };

  watch(() => props.isEditing, (val) => {
    if (val) {
      localValue.value = _.cloneDeep(formatUsers(props.tag.value));
      document.body.classList.add('nl-tag-user-selector-editing');
      setTimeout(() => {
        document.addEventListener('mousedown', handleDocumentClick, true);
      });
      return;
    }
    document.body.classList.remove('nl-tag-user-selector-editing');
    document.removeEventListener('mousedown', handleDocumentClick, true);
  });

  onBeforeUnmount(() => {
    document.body.classList.remove('nl-tag-user-selector-editing');
    document.removeEventListener('mousedown', handleDocumentClick, true);
  });
</script>

<style lang="postcss" scoped>
  .nl-tag-user-selector-item {
    min-height: 26px;

    &.is-editing {
      height: auto;
      min-height: 26px;
    }
  }

  .nl-tag-user-selector-edit-zone {
    position: relative;
    display: inline-flex;
    max-width: min(400px, calc(100vw - 260px));
    min-width: 120px;
  }

  .nl-tag-user-selector {
    width: 100%;
  }
</style>

<style lang="postcss">
  body.nl-tag-user-selector-editing {
    .nl-tag-user-selector.bk-user-selector {
      width: auto !important;
      height: auto !important;
      max-width: min(400px, calc(100vw - 260px)) !important;
      min-width: 120px !important;
      font-size: 12px;
    }

    .nl-tag-user-selector.bk-user-selector .tags-container {
      height: auto !important;
      min-height: 20px !important;
      padding: 0 4px !important;
      overflow-y: visible !important;
      background: #fff !important;
      border: 1px solid #3a84ff !important;
      border-radius: 2px !important;
      box-shadow: none !important;
      box-sizing: border-box !important;
      transition: none !important;
    }

    .nl-tag-user-selector.bk-user-selector .tags-container.focused {
      border-color: #3a84ff !important;
      box-shadow: none !important;
    }

    .nl-tag-user-selector.bk-user-selector .tag-list {
      height: auto !important;
      min-height: 18px !important;
      flex-wrap: wrap !important;
      align-items: flex-start !important;
    }

    .nl-tag-user-selector.bk-user-selector .tag-wrapper {
      max-width: 100%;
      margin-top: 1px !important;
      margin-bottom: 1px !important;
    }

    .nl-tag-user-selector.bk-user-selector .search-input,
    .nl-tag-user-selector.bk-user-selector .search-input.input-inline,
    .nl-tag-user-selector.bk-user-selector .search-input.input-last,
    .nl-tag-user-selector.bk-user-selector .search-input.search-input-collapsed {
      height: 18px !important;
      min-width: 40px !important;
      padding: 0 !important;
      font-size: 12px !important;
      line-height: 18px !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag,
    .nl-tag-user-selector.bk-user-selector .user-tag {
      height: 18px !important;
      padding: 0 4px 0 6px !important;
      color: #1768ef !important;
      background: #e1ecff !important;
      border: none !important;
      border-radius: 2px !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag:hover,
    .nl-tag-user-selector.bk-user-selector .user-tag:hover {
      background: #cddffe !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag-text,
    .nl-tag-user-selector.bk-user-selector .custom-tag {
      font-size: 12px !important;
      line-height: 18px !important;
      color: #1768ef !important;
      background: transparent !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag-close {
      margin-left: 4px !important;
      color: #1768ef !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag-close:hover {
      color: #0f5bd8 !important;
    }

    .bk-user-selector-popover.bk-popover.bk-pop2-content[data-theme^='light'] {
      width: 460px !important;
      max-width: calc(100vw - 120px);
    }
  }
</style>
