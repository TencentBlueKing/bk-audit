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
    :arrow="false"
    :is-show="isShow"
    placement="bottom-start"
    theme="light nl-tag-popover"
    trigger="manual"
    @after-hidden="handlePopoverHidden">
    <div
      ref="tagRef"
      class="condition-tag-item"
      :class="{ 'is-editing': isShow }"
      @click="handleToggle">
      <span class="tag-label">{{ t(tag.label) }}：</span>
      <span
        v-bk-tooltips="{
          content: fullDisplayValue,
          disabled: !isOverflow,
        }"
        class="tag-value-wrapper">
        <span class="tag-value">{{ displayValue }}</span>
      </span>
      <audit-icon
        class="tag-remove-btn"
        type="close"
        @click.stop="$emit('remove', tag.fieldName)" />
    </div>
    <template #content>
      <div class="nl-tag-editor-popover nl-tag-user-popover">
        <audit-user-selector
          v-model="localValue"
          allow-create
          auto-focus
          multiple
          need-record
          :placeholder="t(`请选择${tag.label}`)"
          @change="handleChange" />
      </div>
    </template>
  </bk-popover>
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
    // eslint-disable-next-line vue/no-unused-properties
    searchModel: Record<string, any>;
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

  const MAX_MULTI_LEN = 10;

  const isShow = ref(props.isEditing);
  const localValue = ref<any[]>([]);
  const tagRef = ref<HTMLElement>();

  const fullDisplayValue = computed(() => {
    const { value } = props.tag;
    if (!Array.isArray(value) || value.length === 0) return '--';
    return value.join('，');
  });

  const displayValue = computed(() => {
    const { value } = props.tag;
    if (!Array.isArray(value) || value.length === 0) return '--';
    let displayText = '';
    let visibleCount = 0;
    for (const item of value) {
      const nextText = visibleCount === 0 ? String(item) : `${displayText}，${item}`;
      if (nextText.length > MAX_MULTI_LEN && visibleCount > 0) break;
      displayText = nextText;
      visibleCount += 1;
    }
    const remaining = value.length - visibleCount;
    return remaining > 0 ? `${displayText}，+${remaining}` : displayText;
  });

  const isOverflow = computed(() => {
    const { value } = props.tag;
    if (!Array.isArray(value)) return false;
    return value.join('，').length > MAX_MULTI_LEN;
  });

  const handleToggle = () => {
    if (isShow.value) {
      emit('finishEdit');
    } else {
      emit('startEdit', props.tag.fieldName);
    }
  };

  // 点击外部区域关闭下拉框
  const handleDocumentClick = (e: MouseEvent) => {
    if (!isShow.value) return;
    const target = e.target as HTMLElement;
    // 点击标签自身内部 → 由 handleToggle 处理
    if (tagRef.value?.contains(target)) return;
    // 点击 popover 弹出层内部 → 不关闭
    const popoverContent = document.querySelector('.tippy-box[data-theme~="nl-tag-popover"]');
    if (popoverContent?.contains(target)) return;
    // 点击人员选择器下拉列表（可能挂载在 body 上）→ 不关闭
    if (target.closest('.user-selector-popover') || target.closest('.bk-select-dropdown')) return;
    // 其他区域 → 关闭
    emit('finishEdit');
  };

  const handleChange = (value: any) => {
    localValue.value = value;
    emit('update', props.tag.fieldName, value);
  };

  const handlePopoverHidden = () => {
    // 不在此处调用 finishEdit，完全由外部点击和 handleToggle 控制关闭
    // 避免选择人员更新 searchModel 时 popover 意外关闭
  };

  watch(() => props.isEditing, (val) => {
    isShow.value = val;
    if (val) {
      localValue.value = _.cloneDeep(props.tag.value) || [];
      document.addEventListener('click', handleDocumentClick, true);
    } else {
      document.removeEventListener('click', handleDocumentClick, true);
    }
  });

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleDocumentClick, true);
  });
</script>
<style lang="postcss" scoped>
  .nl-tag-user-popover {
    width: 280px;
    padding: 8px;
  }
</style>
