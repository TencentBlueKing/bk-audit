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
    class="condition-tag-item"
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
    <!-- 编辑态 -->
    <template v-else>
      <span class="tag-label">{{ t(tag.label) }}：</span>
      <bk-input
        ref="inputRef"
        v-model="localValue"
        class="nl-tag-inline-input"
        :placeholder="t(`请输入${tag.label}`)"
        size="small"
        @blur="handleConfirm"
        @enter="handleConfirm" />
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

  const MAX_SINGLE_LEN = 20;

  const localValue = ref('');
  const inputRef = ref();

  const fullDisplayValue = computed(() => {
    const { value } = props.tag;
    if (!value && value !== 0) return '--';
    return String(value);
  });

  const displayValue = computed(() => {
    const text = fullDisplayValue.value;
    if (text.length > MAX_SINGLE_LEN) {
      return `${text.slice(0, MAX_SINGLE_LEN)}...`;
    }
    return text;
  });

  const isOverflow = computed(() => String(props.tag.value).length > MAX_SINGLE_LEN);

  const handleStartEdit = () => {
    emit('startEdit', props.tag.fieldName);
  };

  const handleConfirm = () => {
    emit('update', props.tag.fieldName, localValue.value);
    emit('finishEdit');
  };

  // 进入编辑态时自动聚焦
  watch(() => props.isEditing, async (val) => {
    if (val) {
      localValue.value = _.cloneDeep(props.tag.value) || '';
      await nextTick();
      inputRef.value?.focus?.();
    }
  });
</script>
<style lang="postcss" scoped>
  .nl-tag-inline-input {
    width: 120px;

    :deep(.bk-input--text) {
      height: 20px;
      font-size: 12px;
      background: transparent;
      border: none;
    }
  }
</style>
