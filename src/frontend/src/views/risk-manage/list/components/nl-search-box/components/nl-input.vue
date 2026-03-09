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
  <div class="nl-search-input">
    <div class="nl-input-wrapper">
      <input
        ref="inputRef"
        v-model="inputValue"
        class="nl-input-inner"
        :placeholder="t('支持自然语言输入，如：张三最近一周的高风险单')"
        type="text"
        @compositionend="isComposing = false"
        @compositionstart="isComposing = true"
        @keydown.enter="handleSubmit">
      <div
        v-if="inputValue"
        class="nl-input-clear"
        @click="handleClear">
        <audit-icon type="close-circle-fill" />
      </div>
      <div
        class="nl-input-send-btn"
        :class="{ 'is-loading': loading, 'is-active': !!inputValue.trim() }"
        @click="handleSubmit">
        <audit-icon
          v-if="loading"
          class="rotate-animation"
          type="loading" />
        <img
          v-else
          class="nl-input-submit-icon"
          :src="inputValue.trim() ? submitBlue : submitGray">
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import submitBlue from '@/images/submit-blue.svg';
  import submitGray from '@/images/submit-gray.svg';

  interface Props {
    loading?: boolean;
  }
  interface Emits {
    (e: 'submit', value: string): void;
  }

  withDefaults(defineProps<Props>(), {
    loading: false,
  });
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const inputRef = ref<HTMLInputElement>();
  const inputValue = ref('');
  const isComposing = ref(false);

  // 提交搜索
  const handleSubmit = () => {
    if (isComposing.value) return;
    const value = inputValue.value.trim();
    if (!value) return;
    emit('submit', value);
  };

  // 清空输入
  const handleClear = () => {
    inputValue.value = '';
    inputRef.value?.focus();
  };

  // 对外暴露
  defineExpose({
    clear() {
      inputValue.value = '';
    },
    focus() {
      inputRef.value?.focus();
    },
  });
</script>
<style lang="postcss">
  @keyframes rotate {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .nl-search-input {
    position: relative;
    z-index: 1;
    padding: 16px 24px 8px;

    .nl-input-wrapper {
      position: relative;
      display: flex;
      align-items: center;
      height: 40px;
      padding: 0 10px;
      background: #fff;
      border: none;
      border-radius: 4px;
      transition: all .2s;

      /* 渐变边框：用伪元素实现，兼容 border-radius */
      &::before {
        position: absolute;
        padding: 1px;
        pointer-events: none;
        background: linear-gradient(90.08deg, #488bff 29.47%, #c43bff 98.92%);
        border-radius: 2px;
        content: '';
        inset: 0;
        mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
        mask-composite: xor;
        mask-composite: exclude;
      }

      &:hover {
        background: #f5f7fa;
      }

      &:focus-within {
        background: #fff;
      }
    }

    .nl-input-icon {
      margin-right: 8px;
      font-size: 16px;
      color: #979ba5;
      flex-shrink: 0;
    }

    .nl-input-inner {
      flex: 1;
      height: 100%;
      font-size: 12px;
      line-height: 36px;
      color: #63656e;
      background: transparent;
      border: none;
      outline: none;

      &::placeholder {
        color: #c4c6cc;
      }
    }

    .nl-input-clear {
      margin-right: 8px;
      font-size: 14px;
      color: #c4c6cc;
      cursor: pointer;
      flex-shrink: 0;
      transition: color .15s;

      &:hover {
        color: #979ba5;
      }
    }

    .nl-input-send-btn {
      display: flex;
      width: 28px;
      height: 28px;
      font-size: 16px;
      color: #c4c6cc;
      cursor: pointer;
      border-radius: 4px;
      transition: all .15s;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;

      .nl-input-submit-icon {
        width: 28px;
        height: 28px;
        object-fit: contain;
      }

      &.is-active {
        cursor: pointer;

        /* &:hover {
          background: #e1ecff;
        } */
      }

      &.is-loading {
        color: #3a84ff;
        cursor: not-allowed;

        .rotate-animation {
          animation: rotate 1s linear infinite;
        }
      }
    }
  }
</style>
