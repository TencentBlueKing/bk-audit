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
  <div
    ref="wrapperRef"
    class="condition-tag-item nl-tag-input-item"
    :class="{ 'is-editing': isEditing }">
    <!-- 查看态 -->
    <template v-if="!isEditing">
      <div
        class="tag-view-content"
        @click="handleStartEdit">
        <span class="tag-label">{{ t(tag.label) }}：</span>
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
    <!-- 编辑态：行内撑宽 + 原位向下撑高 -->
    <template v-else>
      <span class="tag-label">{{ t(tag.label) }}：</span>
      <div class="nl-tag-input-edit-zone">
        <textarea
          ref="inputRef"
          v-model="localValue"
          class="nl-tag-inline-textarea"
          :placeholder="t(`请输入${tag.label}`)"
          rows="1"
          @input="handleAutoResize"
          @keydown.enter.exact.prevent="handleConfirm" />
        <!-- 隐藏的测量元素，用于计算文本宽度 -->
        <span
          ref="measureRef"
          class="nl-tag-measure-span">
          {{ localValue || t(`请输入${tag.label}`) }}
        </span>
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
    nextTick,
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

  // 标签值查看态最大展示字符数
  const tagValueMaxDisplayLength = 20;
  // 标签输入框自动撑宽范围
  const tagInputMinWidth = 120;
  const tagInputMaxWidth = 400;

  const localValue = ref('');
  const inputRef = ref();
  const measureRef = ref<HTMLSpanElement>();
  const wrapperRef = ref<HTMLElement>();

  const fullDisplayValue = computed(() => {
    const { value } = props.tag;
    if (!value && value !== 0) {
      return '--';
    }
    return String(value);
  });

  const displayValue = computed(() => {
    const text = fullDisplayValue.value;
    if (text.length > tagValueMaxDisplayLength) {
      return `${text.slice(0, tagValueMaxDisplayLength)}...`;
    }
    return text;
  });

  const isOverflow = computed(() => String(props.tag.value).length > tagValueMaxDisplayLength);

  const handleStartEdit = () => {
    emit('startEdit', props.tag.fieldName);
  };

  const handleConfirm = () => {
    emit('update', props.tag.fieldName, localValue.value);
    emit('finishEdit');
  };

  // textarea 自动调整宽度和高度
  // 先根据内容撑宽（最大 400px），宽度到上限后原位向下撑高
  const handleAutoResize = () => {
    const el = inputRef.value;
    const measure = measureRef.value;
    if (!el || !measure) {
      return;
    }

    // 1. 根据隐藏 span 测量的文本宽度来设置 textarea 宽度
    const textWidth = measure.scrollWidth + 4; // 加一点余量
    const newWidth = Math.max(tagInputMinWidth, Math.min(textWidth, tagInputMaxWidth));
    el.style.width = `${newWidth}px`;

    // 2. 自动调整高度（当宽度达到上限后，内容换行原位向下撑高）
    el.style.height = 'auto';
    const scrollH = el.scrollHeight;
    el.style.height = `${scrollH}px`;
  };

  // 点击外部区域关闭编辑态
  const handleDocumentClick = (e: MouseEvent) => {
    if (props.isEditing) {
      const target = e.target as HTMLElement;
      if (!wrapperRef.value?.contains(target)) {
        handleConfirm();
      }
    }
  };

  // 进入编辑态时自动聚焦
  watch(() => props.isEditing, async (val) => {
    if (val) {
      localValue.value = _.cloneDeep(props.tag.value) || '';
      await nextTick();
      const el = inputRef.value;
      if (el) {
        el.focus?.();
        handleAutoResize();
      }
      setTimeout(() => {
        document.addEventListener('click', handleDocumentClick);
      });
    } else {
      document.removeEventListener('click', handleDocumentClick);
    }
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick);
  });
</script>
<style lang="postcss" scoped>
  .nl-tag-input-item {
    /* 编辑态：允许标签高度随内容撑高 */
    &.is-editing {
      height: auto;
      min-height: 26px;
      align-items: flex-start;
    }
  }

  .nl-tag-input-edit-zone {
    position: relative;
    display: inline-flex;
    min-width: 120px;
  }

  .nl-tag-inline-textarea {
    width: 120px;
    max-width: 400px;
    max-height: 200px;
    min-width: 120px;
    min-height: 20px;
    padding: 0 4px;
    overflow-y: auto;
    font-family: inherit;
    font-size: 12px;
    line-height: 18px;
    color: #63656e;
    word-break: break-all;
    background: #fff;
    border: 1px solid #3a84ff;
    border-radius: 2px;
    outline: none;
    box-sizing: border-box;
    resize: none;

    &::placeholder {
      color: #c4c6cc;
    }

    /* 窄灰色滚动条 */
    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: #c4c6cc;
      border-radius: 2px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }
  }

  /* 隐藏的测量 span，与 textarea 保持相同字体样式 */
  .nl-tag-measure-span {
    position: absolute;
    top: 0;
    left: 0;
    height: 0;
    padding: 0 4px;
    overflow: hidden;
    font-family: inherit;
    font-size: 12px;
    line-height: 18px;
    white-space: pre;
    pointer-events: none;
    visibility: hidden;
  }
</style>
