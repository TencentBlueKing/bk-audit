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
    :class="{ 'is-editing': isEditing, 'has-users': hasUsers }">
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
      <div
        class="nl-tag-user-selector-edit-zone"
        :class="{ 'has-users': hasUsers }">
        <audit-user-selector-tenant
          v-model="localValue"
          allow-create
          auto-focus
          class="nl-tag-user-selector"
          :class="{ 'has-users': hasUsers }"
          :placeholder="t('请输入人员')"
          @blur="handleSelectorBlur"
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

  const tagValueMaxDisplayLength = 24;

  const localValue = ref<string[]>([]);
  const wrapperRef = ref<HTMLElement>();
  let blurTimer: ReturnType<typeof setTimeout> | null = null;
  let ignoreCloseBefore = 0;

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
    const text = fullDisplayValue.value;
    if (text === '--') {
      return text;
    }
    if (text.length > tagValueMaxDisplayLength) {
      return `${text.slice(0, tagValueMaxDisplayLength)}...`;
    }
    return text;
  });

  const isOverflow = computed(() => fullDisplayValue.value.length > tagValueMaxDisplayLength);

  const hasUsers = computed(() => localValue.value.length > 0);

  const isInUserSelectorLayer = (target: Node | null) => {
    const el = target as HTMLElement;
    if (!el?.closest) {
      return false;
    }
    return !!el.closest('.bk-user-selector-popover, .bk-user-selector, .nl-tag-user-selector-edit-zone, .tippy-box');
  };

  const isUserSelectorPopoverVisible = () => {
    const popover = document.querySelector('.bk-user-selector-popover') as HTMLElement | null;
    if (!popover) {
      return false;
    }
    const style = window.getComputedStyle(popover);
    return style.display !== 'none' && style.visibility !== 'hidden' && popover.offsetParent !== null;
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

  const clearBlurTimer = () => {
    if (blurTimer) {
      clearTimeout(blurTimer);
      blurTimer = null;
    }
  };

  const handleConfirm = () => {
    clearBlurTimer();
    emit('update', props.tag.fieldName, [...localValue.value]);
    emit('finishEdit');
  };

  const handleSelectorBlur = () => {
    clearBlurTimer();
    blurTimer = setTimeout(() => {
      if (!props.isEditing) {
        return;
      }
      const activeEl = document.activeElement;
      if (activeEl && isInUserSelectorLayer(activeEl)) {
        return;
      }
      if (isUserSelectorPopoverVisible()) {
        return;
      }
      handleConfirm();
    }, 200);
  };

  const handleDocumentMousedown = (e: MouseEvent) => {
    if (!props.isEditing) {
      return;
    }
    if (Date.now() < ignoreCloseBefore) {
      return;
    }
    const target = e.target as Node;
    if (wrapperRef.value?.contains(target as HTMLElement)) {
      return;
    }
    if (isInUserSelectorLayer(target)) {
      return;
    }
    handleConfirm();
  };

  const handleDocumentKeydown = (e: KeyboardEvent) => {
    if (!props.isEditing || e.key !== 'Enter') {
      return;
    }
    if (isUserSelectorPopoverVisible()) {
      return;
    }
    e.preventDefault();
    handleConfirm();
  };

  const bindDocumentListeners = () => {
    ignoreCloseBefore = Date.now() + 300;
    setTimeout(() => {
      document.addEventListener('mousedown', handleDocumentMousedown, true);
      document.addEventListener('keydown', handleDocumentKeydown, true);
    });
  };

  const unbindDocumentListeners = () => {
    document.removeEventListener('mousedown', handleDocumentMousedown, true);
    document.removeEventListener('keydown', handleDocumentKeydown, true);
  };

  watch(() => props.isEditing, (val) => {
    if (val) {
      localValue.value = _.cloneDeep(formatUsers(props.tag.value));
      document.body.classList.add('nl-tag-user-selector-scope');
      unbindDocumentListeners();
      bindDocumentListeners();
      return;
    }
    clearBlurTimer();
    document.body.classList.remove('nl-tag-user-selector-scope');
    unbindDocumentListeners();
  }, { immediate: true });

  onBeforeUnmount(() => {
    clearBlurTimer();
    document.body.classList.remove('nl-tag-user-selector-scope');
    unbindDocumentListeners();
  });
</script>

<style lang="postcss" scoped>
  .nl-tag-user-selector-item {
    min-height: 26px;

    &:not(.is-editing) .tag-value-wrapper {
      max-width: 280px;
    }

    &:not(.is-editing) .tag-value {
      max-width: 100%;
    }

    &.is-editing {
      overflow: visible;
      align-items: center;

      &:not(.has-users) {
        height: 26px;
        max-height: 26px;
        min-height: 26px;
      }

      &.has-users {
        height: 26px;
        max-height: 26px;
        min-height: 26px;
      }
    }
  }

  .nl-tag-user-selector-edit-zone {
    position: relative;
    display: inline-flex;
    align-items: center;
    height: 20px;
    flex: 0 0 auto;

    &:not(.has-users) {
      width: 120px;
      max-width: 120px;
      min-width: 120px;
    }

    &.has-users {
      width: auto;
      height: 20px;
      max-width: min(480px, calc(100vw - 260px));
      min-width: 120px;
    }
  }

  .nl-tag-user-selector {
    width: 100%;
    height: 20px;

    &.has-users {
      width: auto;
      height: 20px;
    }
  }
</style>

<style lang="postcss">
  /* 样式挂在 .is-editing 上，避免首次添加时 isEditing 初始为 true 但 watch 未触发导致样式缺失 */
  .nl-tag-user-selector-item.is-editing {
    &.condition-tag-item:not(.has-users) {
      height: 26px !important;
      max-height: 26px !important;
      min-height: 26px !important;
      overflow: hidden !important;
      align-items: center !important;
    }

    &.condition-tag-item.has-users {
      height: 26px !important;
      max-height: 26px !important;
      min-height: 26px !important;
      overflow: hidden !important;
      align-items: center !important;
    }

    /* 覆盖 bk-user-selector 默认 32px 高度 */
    .nl-tag-user-selector.bk-user-selector {
      position: relative !important;
      width: 100% !important;
      height: 20px !important;
      max-height: 20px !important;
      min-height: 20px !important;
      font-size: 12px !important;
      line-height: 18px !important;
    }

    .nl-tag-user-selector.bk-user-selector.has-users {
      width: auto !important;
      height: 20px !important;
      max-width: min(480px, calc(100vw - 260px)) !important;
      max-height: 20px !important;
      min-height: 20px !important;
    }

    .nl-tag-user-selector.bk-user-selector.has-users .tags-container {
      width: max-content !important;
      height: 20px !important;
      max-width: min(480px, calc(100vw - 260px)) !important;
      max-height: 20px !important;
      min-height: 20px !important;
      padding: 0 4px !important;
      overflow: hidden !important;
    }

    .nl-tag-user-selector.bk-user-selector.has-users .tag-list {
      height: 18px !important;
      max-height: 18px !important;
      min-height: 18px !important;
      overflow: hidden !important;
    }

    .nl-tag-user-selector.bk-user-selector.has-users .tag-wrapper {
      max-width: none !important;
      flex-shrink: 0 !important;
      min-width: 0;
    }

    .nl-tag-user-selector.bk-user-selector.has-users .bk-user-selector-tag,
    .nl-tag-user-selector.bk-user-selector.has-users .user-tag {
      max-width: none !important;
      flex-shrink: 0 !important;
    }

    .nl-tag-user-selector.bk-user-selector.has-users .bk-user-selector-tag-text,
    .nl-tag-user-selector.bk-user-selector.has-users .custom-tag,
    .nl-tag-user-selector.bk-user-selector.has-users .user-tag .tag-content .user-name {
      max-width: min(420px, calc(100vw - 300px)) !important;
    }

    .nl-tag-user-selector.bk-user-selector.has-users .search-input,
    .nl-tag-user-selector.bk-user-selector.has-users .search-input.input-inline,
    .nl-tag-user-selector.bk-user-selector.has-users .search-input.input-last,
    .nl-tag-user-selector.bk-user-selector.has-users .search-input.search-input-collapsed {
      width: 40px !important;
      max-width: 80px !important;
      min-width: 40px !important;
      flex: 0 0 40px !important;
    }

    .nl-tag-user-selector.bk-user-selector .me-tag {
      display: none !important;
    }

    .nl-tag-user-selector.bk-user-selector .tags-container,
    .nl-tag-user-selector.bk-user-selector .tags-container.tags-container-collapsed {
      width: 100% !important;
      height: 20px !important;
      max-height: 20px !important;
      min-height: 20px !important;
      padding: 0 4px !important;
      overflow: hidden !important;
      background: #fff !important;
      border: 1px solid #3a84ff !important;
      border-radius: 2px !important;
      box-shadow: none !important;
      box-sizing: border-box !important;
      transition: none !important;
      scrollbar-width: none;
    }

    .nl-tag-user-selector.bk-user-selector .tags-container::-webkit-scrollbar {
      display: none;
    }

    .nl-tag-user-selector.bk-user-selector .tags-container.focused {
      border-color: #3a84ff !important;
      box-shadow: none !important;
    }

    .nl-tag-user-selector.bk-user-selector .tag-list {
      display: flex !important;
      height: 18px !important;
      max-height: 18px !important;
      min-height: 18px !important;
      overflow: hidden !important;
      flex-wrap: nowrap !important;
      align-items: center !important;
      row-gap: 0 !important;
    }

    .nl-tag-user-selector.bk-user-selector:not(.has-users) .tag-wrapper {
      display: none !important;
    }

    .nl-tag-user-selector.bk-user-selector .tag-wrapper {
      max-width: calc(100% - 48px);
      min-width: 0;
      margin: 0 !important;
      flex-shrink: 1;
    }

    .nl-tag-user-selector.bk-user-selector .search-input,
    .nl-tag-user-selector.bk-user-selector .search-input.input-inline,
    .nl-tag-user-selector.bk-user-selector .search-input.input-last,
    .nl-tag-user-selector.bk-user-selector .search-input.search-input-collapsed {
      width: 100% !important;
      height: 18px !important;
      max-width: 100% !important;
      min-width: 0 !important;
      padding: 0 !important;
      margin: 0 !important;
      font-size: 12px !important;
      line-height: 18px !important;
      flex: 1 1 auto !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag,
    .nl-tag-user-selector.bk-user-selector .user-tag {
      display: inline-flex !important;
      height: 18px !important;
      max-width: 100%;
      padding: 0 4px 0 6px !important;
      margin: 0 4px 0 0 !important;
      color: #1768ef !important;
      background: #e1ecff !important;
      border: none !important;
      border-radius: 2px !important;
      box-sizing: border-box !important;
      align-items: center !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag:hover,
    .nl-tag-user-selector.bk-user-selector .user-tag:hover {
      background: #cddffe !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag-text,
    .nl-tag-user-selector.bk-user-selector .custom-tag {
      display: inline-flex !important;
      max-width: 160px;
      overflow: hidden;
      font-size: 12px !important;
      line-height: 1 !important;
      color: #1768ef !important;
      text-overflow: ellipsis;
      white-space: nowrap;
      background: transparent !important;
      align-items: center !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag-close {
      display: inline-flex !important;
      margin-left: 4px !important;
      font-size: 12px !important;
      line-height: 1 !important;
      color: #1768ef !important;
      align-items: center !important;
    }

    .nl-tag-user-selector.bk-user-selector .bk-user-selector-tag-close:hover {
      color: #0f5bd8 !important;
    }
  }

  /*
   * 下拉层 teleport 到 body，不能嵌套在 .is-editing 内；
   * tippy 会按触发器宽度（120px）收缩，需单独覆盖。
   */
  body.nl-tag-user-selector-scope {
    .tippy-box:has(.bk-user-selector-popover) {
      width: 460px !important;
      max-width: calc(100vw - 120px) !important;
      min-width: 460px !important;
    }

    .bk-user-selector-popover.bk-popover.bk-pop2-content {
      width: 460px !important;
      max-width: calc(100vw - 120px) !important;
      min-width: 460px !important;
    }

    .bk-user-selector-popover {
      width: 100% !important;
      max-width: 100% !important;
      min-width: 100% !important;
      padding: 0 !important;
      box-sizing: border-box !important;
    }

    .bk-user-selector-popover .dropdown-content {
      width: 100% !important;
      overflow-x: hidden !important;
    }

    .bk-user-selector-popover .dropdown-panel,
    .bk-user-selector-popover .dropdown-panels {
      width: 100% !important;
      min-width: 100% !important;
    }

    .bk-user-selector-popover .user-option {
      height: auto !important;
      min-height: 32px !important;
      white-space: nowrap !important;
    }

    .bk-user-selector-popover .user-name,
    .bk-user-selector-popover .tenant-name,
    .bk-user-selector-popover .user-main {
      overflow: hidden !important;
      text-overflow: ellipsis !important;
      white-space: nowrap !important;
    }
  }
</style>
