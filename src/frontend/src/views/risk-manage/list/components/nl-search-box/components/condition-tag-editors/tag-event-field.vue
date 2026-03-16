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
    class="condition-tag-item condition-tag-event-item"
    :class="{ 'is-editing': isEditingValue }">
    <span class="tag-label">{{ item.display_name }}：</span>
    <!-- 操作符区域 -->
    <bk-popover
      ref="operatorPopoverRef"
      :arrow="false"
      :is-show="isOperatorShow"
      placement="bottom-start"
      theme="light nl-tag-popover"
      trigger="manual"
      @after-hidden="isOperatorShow = false">
      <span
        class="tag-operator-badge"
        :class="{ 'is-active': isOperatorShow }"
        @click.stop="handleToggleOperator">
        {{ item.operator }}
      </span>
      <template #content>
        <div
          class="nl-tag-operator-popover"
          @click.stop
          @mousedown.stop>
          <div
            v-for="op in operatorList"
            :key="op.id"
            class="nl-tag-operator-item"
            :class="{ 'is-selected': item.operator === op.id }"
            @click="handleSelectOperator(op.id)">
            <span>{{ op.name }}</span>
          </div>
        </div>
      </template>
    </bk-popover>
    <!-- 值区域 -->
    <template v-if="!isEditingValue">
      <span
        v-bk-tooltips="{
          content: fullDisplayValue,
          disabled: !isOverflow,
          extCls: 'nl-tag-tooltip-wrap',
        }"
        class="tag-value-wrapper"
        @click.stop="handleStartEditValue"
        @mouseenter="checkOverflow">
        <span
          ref="tagValueRef"
          class="tag-value">{{ fullDisplayValue }}</span>
      </span>
    </template>
    <template v-else>
      <div class="nl-tag-event-edit-zone">
        <!-- IN/NOT IN 模式：简单的 tag-input 风格 -->
        <template v-if="isMultiValueMode">
          <div class="nl-tag-event-input-wrap">
            <textarea
              ref="multiInputRef"
              v-model="multiInputText"
              class="nl-tag-event-inline-textarea"
              :placeholder="t('输入后按回车')"
              rows="1"
              @input="handleAutoResize($event.target as HTMLTextAreaElement)"
              @keydown.enter.exact.prevent="handleAddMultiValue" />
            <span
              ref="multiMeasureRef"
              class="nl-tag-event-measure-span">
              {{ multiInputText || t('输入后按回车') }}
            </span>
          </div>
          <div
            v-if="localMultiValue.length > 0"
            class="nl-tag-event-multi-tags">
            <span
              v-for="(val, idx) in localMultiValue"
              :key="idx"
              class="nl-tag-event-multi-tag">
              {{ val }}
              <audit-icon
                class="multi-tag-close"
                type="close"
                @click.stop="handleRemoveMultiValue(idx)" />
            </span>
          </div>
        </template>
        <!-- 单值模式 -->
        <template v-else>
          <div class="nl-tag-event-input-wrap">
            <textarea
              ref="singleInputRef"
              v-model="localSingleValue"
              class="nl-tag-event-inline-textarea"
              :placeholder="t('请输入')"
              rows="1"
              @input="handleAutoResize($event.target as HTMLTextAreaElement)"
              @keydown.enter.exact.prevent="handleConfirmValue" />
            <span
              ref="singleMeasureRef"
              class="nl-tag-event-measure-span">
              {{ localSingleValue || t('请输入') }}
            </span>
          </div>
        </template>
      </div>
    </template>
    <audit-icon
      class="tag-remove-btn"
      type="close"
      @click.stop="$emit('remove', item.id)" />
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    item: Record<string, any>;
    conditionList: Array<{ id: string; name: string }>;
  }
  interface Emits {
    (e: 'remove', id: string): void;
    (e: 'updateOperator', id: string, operator: string): void;
    (e: 'updateValue', id: string, value: any): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();

  const wrapperRef = ref<HTMLElement>();
  const tagValueRef = ref<HTMLElement>();
  const isOperatorShow = ref(false);
  const isEditingValue = ref(false);
  const multiInputRef = ref<HTMLTextAreaElement>();
  const singleInputRef = ref<HTMLTextAreaElement>();
  const multiMeasureRef = ref<HTMLSpanElement>();
  const singleMeasureRef = ref<HTMLSpanElement>();

  // textarea 自动撑宽范围（与条件标签 tag-input 保持一致）
  const textareaMinWidth = 120;
  const textareaMaxWidth = 400;

  // 单值模式的本地值
  const localSingleValue = ref('');
  // 多值模式的本地值
  const localMultiValue = ref<string[]>([]);
  const multiInputText = ref('');

  // textarea 自动调整宽度和高度
  // 先根据内容撑宽（最大 400px），宽度到上限后原位向下撑高
  const handleAutoResize = (el?: HTMLTextAreaElement) => {
    if (!el) return;
    // 找到对应的测量 span
    const measure = el === multiInputRef.value ? multiMeasureRef.value : singleMeasureRef.value;
    if (!measure) return;

    // 1. 根据隐藏 span 测量的文本宽度来设置 textarea 宽度
    const textWidth = measure.scrollWidth + 4;
    const newWidth = Math.max(textareaMinWidth, Math.min(textWidth, textareaMaxWidth));
    Object.assign(el.style, { width: `${newWidth}px` });

    // 2. 自动调整高度（当宽度达到上限后，内容换行原位向下撑高）
    Object.assign(el.style, { height: 'auto' });
    const scrollH = el.scrollHeight;
    Object.assign(el.style, { height: `${scrollH}px` });
  };

  // 操作符列表（与接口 event_filters 操作符枚举保持一致）
  const operatorList = computed(() => props.conditionList || [
    { id: '=', name: '=' },
    { id: '!=', name: '!=' },
    { id: 'CONTAINS', name: '包含' },
    { id: 'NOT CONTAINS', name: '不包含' },
    { id: 'IN', name: 'IN' },
    { id: 'NOT IN', name: 'NOT IN' },
    { id: '>=', name: '>=' },
    { id: '<=', name: '<=' },
    { id: '>', name: '>' },
    { id: '<', name: '<' },
  ]);

  // 是否为多值模式（IN / NOT IN）
  const isMultiValueMode = computed(() => props.item.operator === 'IN' || props.item.operator === 'NOT IN');

  // 完整显示值
  const fullDisplayValue = computed(() => {
    const { value } = props.item;
    if (!value && value !== 0) return '--';
    if (Array.isArray(value)) {
      return value.length > 0 ? value.join('，') : '--';
    }
    return String(value) || '--';
  });

  // 通过 DOM 检测文本是否溢出，与条件标签保持一致
  const isOverflow = ref(false);

  const checkOverflow = () => {
    if (tagValueRef.value) {
      isOverflow.value = tagValueRef.value.scrollWidth > tagValueRef.value.clientWidth;
    }
  };

  // 操作符下拉切换
  const handleToggleOperator = () => {
    isOperatorShow.value = !isOperatorShow.value;
  };

  // 选择操作符
  const handleSelectOperator = (operator: string) => {
    emit('updateOperator', props.item.id, operator);
    isOperatorShow.value = false;
  };

  // 开始编辑值
  const handleStartEditValue = () => {
    if (isMultiValueMode.value) {
      localMultiValue.value = Array.isArray(props.item.value) ? [...props.item.value] : [];
      multiInputText.value = '';
    } else {
      localSingleValue.value = props.item.value || '';
    }
    isEditingValue.value = true;
    nextTick(() => {
      if (isMultiValueMode.value) {
        multiInputRef.value?.focus();
        handleAutoResize(multiInputRef.value || undefined);
      } else {
        singleInputRef.value?.focus();
        handleAutoResize(singleInputRef.value || undefined);
      }
    });
  };

  // 单值模式确认
  const handleConfirmValue = () => {
    emit('updateValue', props.item.id, localSingleValue.value);
    isEditingValue.value = false;
  };

  // 多值模式添加
  const handleAddMultiValue = () => {
    const text = multiInputText.value.trim();
    if (!text) return;
    // 支持逗号分隔批量输入
    const values = text.split(',').map(s => s.trim())
      .filter(s => s);
    const newValues = [...new Set([...localMultiValue.value, ...values])];
    localMultiValue.value = newValues;
    multiInputText.value = '';
    emit('updateValue', props.item.id, newValues);
  };

  // 多值模式删除
  const handleRemoveMultiValue = (index: number) => {
    localMultiValue.value.splice(index, 1);
    emit('updateValue', props.item.id, [...localMultiValue.value]);
  };

  // 点击外部关闭编辑态
  const handleDocumentClick = (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (wrapperRef.value?.contains(target)) return;
    // 关闭操作符下拉
    if (isOperatorShow.value) {
      const closestTippy = (target as Element)?.closest?.('.tippy-box[data-theme~="nl-tag-popover"]');
      if (!closestTippy) {
        isOperatorShow.value = false;
      }
    }
    // 关闭值编辑态
    if (isEditingValue.value) {
      if (isMultiValueMode.value) {
        // 多值模式：如有未提交的文本，先添加
        if (multiInputText.value.trim()) {
          handleAddMultiValue();
        }
      } else {
        handleConfirmValue();
      }
      isEditingValue.value = false;
    }
  };

  watch(isEditingValue, (val) => {
    if (val) {
      setTimeout(() => {
        document.addEventListener('click', handleDocumentClick);
      });
    } else {
      document.removeEventListener('click', handleDocumentClick);
    }
  });

  watch(isOperatorShow, (val) => {
    if (val && !isEditingValue.value) {
      setTimeout(() => {
        document.addEventListener('click', handleDocumentClick);
      });
    } else if (!val && !isEditingValue.value) {
      document.removeEventListener('click', handleDocumentClick);
    }
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick);
  });
</script>
<style lang="postcss" scoped>
  .condition-tag-event-item {
    height: auto;
    min-height: 26px;

    .tag-operator-badge {
      display: inline-flex;
      height: 18px;
      padding: 0 4px;
      margin-right: 4px;
      font-size: 12px;
      font-weight: 700;
      color: #979ba5;
      cursor: pointer;
      background: transparent;
      border-radius: 2px;
      transition: all .15s;
      align-items: center;

      &:hover,
      &.is-active {
        background: #fdeed8;
      }

      /* &.is-active {
        color: #3a84ff;
        background: #e1ecff;
      } */
    }
  }

  .nl-tag-event-edit-zone {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: flex-start;
    max-width: 460px;
  }

  .nl-tag-event-input-wrap {
    position: relative;
    display: inline-flex;
    min-width: 120px;
  }

  .nl-tag-event-inline-textarea {
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
  .nl-tag-event-measure-span {
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

  .nl-tag-event-multi-tags {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 2px;
    align-items: center;
  }

  .nl-tag-event-multi-tag {
    display: inline-flex;
    height: 20px;
    padding: 0 4px;
    font-size: 12px;
    color: #63656e;
    background: #f0f1f5;
    border-radius: 2px;
    align-items: center;
    gap: 2px;

    .multi-tag-close {
      font-size: 12px;
      color: #979ba5;
      cursor: pointer;

      &:hover {
        color: #ea3636;
      }
    }
  }
</style>
<style lang="postcss">
  /* 操作符下拉弹出层样式（非 scoped，因为 popover 内容挂在 body 上） */
  .nl-tag-operator-popover {
    min-width: 80px;
    padding: 4px 0;

    .nl-tag-operator-item {
      display: flex;
      height: 32px;
      padding: 0 12px;
      font-size: 12px;
      color: #63656e;
      cursor: pointer;
      align-items: center;
      transition: background .15s;

      &:hover {
        background: #f5f7fa;
      }

      &.is-selected {
        color: #3a84ff;
        background: #e1ecff;
      }
    }
  }
</style>
