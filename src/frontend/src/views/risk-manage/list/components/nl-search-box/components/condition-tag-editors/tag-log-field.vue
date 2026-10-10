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
    class="condition-tag-item condition-tag-log-item"
    :class="{ 'is-editing': isEditingValue }">
    <span class="tag-label">{{ t(tag.label) }}</span>
    <bk-popover
      :arrow="false"
      ext-cls="nl-tag-log-operator-popover-wrap"
      :is-show="isOperatorShow"
      placement="bottom-start"
      theme="light nl-tag-popover"
      trigger="manual"
      @after-hidden="isOperatorShow = false">
      <span
        class="tag-operator-badge"
        :class="{ 'is-active': isOperatorShow }"
        @click.stop="handleToggleOperator">
        {{ operatorBadgeName }}
      </span>
      <template #content>
        <div
          class="nl-tag-operator-popover nl-tag-log-operator-popover"
          @click.stop
          @mousedown.stop>
          <div
            v-for="op in operatorList"
            :key="op.id"
            class="nl-tag-operator-item"
            :class="{ 'is-selected': currentOperator === op.id }"
            @click="handleSelectOperator(op.id)">
            <span>{{ op.label }}</span>
          </div>
        </div>
      </template>
    </bk-popover>
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
      <div class="nl-tag-log-edit-zone">
        <textarea
          ref="inputRef"
          v-model="localValue"
          class="nl-tag-log-inline-textarea"
          :placeholder="t('请输入')"
          rows="1"
          @input="handleAutoResize"
          @keydown.enter.exact.prevent="handleConfirmValue" />
        <span
          ref="measureRef"
          class="nl-tag-log-measure-span">
          {{ localValue || t('请输入') }}
        </span>
      </div>
    </template>
    <audit-icon
      class="tag-remove-btn"
      type="close"
      @click.stop="$emit('remove', tag.fieldName)" />
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

  import type { IConditionTag } from '../../types';

  const props = withDefaults(defineProps<Props>(), {
    isEditing: false,
  });

  const emit = defineEmits<Emits>();

  /** 下拉列表：符号 + 描述（对齐风险 NL 事件字段） */
  const LOG_OPERATOR_LABEL_MAP: Record<string, string> = {
    eq: '=  等于',
    neq: '!=  不等于',
    include: '包含',
    exclude: '不包含',
    like: '模糊匹配',
    not_like: '不匹配',
    gt: '>  大于',
    lt: '<  小于',
    gte: '>=  大于等于',
    lte: '<=  小于等于',
    isnull: '为空',
    notnull: '不为空',
    match_any: '匹配任一',
    match_all: '匹配全部',
    '=': '=  等于',
    '!=': '!=  不等于',
  };

  /** 徽章展示：紧凑符号 + 描述 */
  const LOG_OPERATOR_BADGE_MAP: Record<string, string> = {
    eq: '= 等于',
    neq: '!= 不等于',
    include: '包含',
    exclude: '不包含',
    like: '模糊匹配',
    not_like: '不匹配',
    gt: '> 大于',
    lt: '< 小于',
    gte: '>= 大于等于',
    lte: '<= 小于等于',
    isnull: '为空',
    notnull: '不为空',
    match_any: '匹配任一',
    match_all: '匹配全部',
    '=': '= 等于',
    '!=': '!= 不等于',
  };

  interface Props {
    tag: IConditionTag;
    isEditing?: boolean;
  }
  interface Emits {
    (e: 'remove', fieldName: string): void;
    (e: 'update', fieldName: string, value: { operator: string; value: string }): void;
    (e: 'startEdit', fieldName: string): void;
    (e: 'finishEdit'): void;
  }

  const { t } = useI18n();

  const wrapperRef = ref<HTMLElement>();
  const tagValueRef = ref<HTMLElement>();
  const inputRef = ref<HTMLTextAreaElement>();
  const measureRef = ref<HTMLSpanElement>();
  const isOperatorShow = ref(false);
  const isEditingValue = ref(false);
  const localValue = ref('');
  const isOverflow = ref(false);

  const textareaMinWidth = 56;
  const textareaMaxWidth = 400;

  const fieldValue = computed(() => {
    const raw = props.tag.value;
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      return raw as { operator?: string; value?: string };
    }
    return { operator: '', value: '' };
  });

  const allowOperators = computed(() => {
    const config = props.tag.config as { allowOperators?: string[]; defaultOperator?: string };
    return config.allowOperators?.length
      ? config.allowOperators
      : [config.defaultOperator || 'eq'];
  });

  const currentOperator = computed(() => (
    fieldValue.value.operator || allowOperators.value[0] || 'eq'
  ));

  const resolveOperatorLabel = (id: string) => LOG_OPERATOR_LABEL_MAP[id] || id;
  const resolveOperatorBadge = (id: string) => LOG_OPERATOR_BADGE_MAP[id] || resolveOperatorLabel(id);

  const operatorList = computed(() => allowOperators.value.map(id => ({
    id,
    label: resolveOperatorLabel(id),
  })));

  const operatorBadgeName = computed(() => resolveOperatorBadge(currentOperator.value));

  const fullDisplayValue = computed(() => {
    const text = fieldValue.value.value;
    if (text === undefined || text === null || text === '') return '--';
    return String(text);
  });

  const handleAutoResize = () => {
    const el = inputRef.value;
    const measure = measureRef.value;
    if (!el || !measure) return;
    const textWidth = measure.scrollWidth + 4;
    const newWidth = Math.max(textareaMinWidth, Math.min(textWidth, textareaMaxWidth));
    Object.assign(el.style, { width: `${newWidth}px`, height: 'auto' });
    Object.assign(el.style, { height: `${el.scrollHeight}px` });
  };

  const checkOverflow = () => {
    if (tagValueRef.value) {
      isOverflow.value = tagValueRef.value.scrollWidth > tagValueRef.value.clientWidth;
    }
  };

  const emitUpdate = (patch: Partial<{ operator: string; value: string }>) => {
    emit('update', props.tag.fieldName, {
      operator: patch.operator ?? currentOperator.value,
      value: patch.value ?? fieldValue.value.value ?? '',
    });
  };

  const handleToggleOperator = () => {
    isOperatorShow.value = !isOperatorShow.value;
    if (isOperatorShow.value) {
      emit('startEdit', props.tag.fieldName);
    }
  };

  const handleSelectOperator = (operator: string) => {
    emitUpdate({ operator });
    isOperatorShow.value = false;
  };

  const handleStartEditValue = () => {
    emit('startEdit', props.tag.fieldName);
    localValue.value = fieldValue.value.value || '';
    isEditingValue.value = true;
    nextTick(() => {
      inputRef.value?.focus();
      handleAutoResize();
    });
  };

  const handleConfirmValue = () => {
    emitUpdate({ value: localValue.value });
    isEditingValue.value = false;
    emit('finishEdit');
  };

  const handleDocumentClick = (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (wrapperRef.value?.contains(target)) return;
    if (isOperatorShow.value) {
      const closestTippy = target.closest?.('.tippy-box[data-theme~="nl-tag-popover"]');
      if (!closestTippy) {
        isOperatorShow.value = false;
      }
    }
    if (isEditingValue.value) {
      handleConfirmValue();
    }
  };

  watch(isEditingValue, (val) => {
    if (val) {
      setTimeout(() => document.addEventListener('click', handleDocumentClick));
    } else {
      document.removeEventListener('click', handleDocumentClick);
    }
  });

  watch(isOperatorShow, (val) => {
    if (val && !isEditingValue.value) {
      setTimeout(() => document.addEventListener('click', handleDocumentClick));
    } else if (!val && !isEditingValue.value) {
      document.removeEventListener('click', handleDocumentClick);
    }
  });

  watch(() => props.isEditing, (val) => {
    if (val && !isEditingValue.value) {
      handleStartEditValue();
    }
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick);
  });
</script>
<style lang="postcss" scoped>
  .condition-tag-log-item {
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
      white-space: nowrap;

      &:hover,
      &.is-active {
        background: #fdeed8;
      }
    }
  }

  .nl-tag-log-edit-zone {
    position: relative;
    display: inline-flex;
    min-width: 56px;
  }

  .nl-tag-log-inline-textarea {
    width: 56px;
    max-width: 400px;
    max-height: 200px;
    min-width: 56px;
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
  }

  .nl-tag-log-measure-span {
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
<style lang="postcss">
  .nl-tag-log-operator-popover-wrap.bk-popover.bk-pop2-content,
  .tippy-box[data-theme~='nl-tag-popover'] .nl-tag-log-operator-popover-wrap {
    padding: 0 !important;
  }

  .nl-tag-log-operator-popover.nl-tag-operator-popover {
    min-width: unset;
    width: max-content;
    padding: 2px 0;

    .nl-tag-operator-item {
      height: 28px;
      padding: 0 10px;
      white-space: nowrap;
    }
  }
</style>
