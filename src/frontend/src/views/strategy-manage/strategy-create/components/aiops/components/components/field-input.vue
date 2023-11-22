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
    class="field-input"
    :class="{
      'is-errored': isError,
      'is-background-errored-tip': theme === 'background'
    }">
    <bk-input
      v-model="localValue"
      clearable />
    <span
      v-if="isError"
      v-bk-tooltips="{content: t('必填项'), placement: 'top'}"
      class="err-tip">
      <audit-icon
        type="alert" />
    </span>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    modelValue: string;
    required?: boolean;
    theme?: string;
  }

  interface Emits{
    (e: 'update:modelValue', value: string):void
  }

  interface Expose {
    getValue: () => Promise<any>,
    clearFields: () => void
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: '',
    required: false,
    theme: '',
  });
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const isError = ref(false);
  const localValue = computed({
    get() {
      return props.modelValue;
    },
    set(value) {
      const newValue = value.trim();
      if (newValue) {
        isError.value = false;
      }
      emit('update:modelValue', newValue);
    },
  });

  defineExpose<Expose>({
    getValue() {
      if (props.required && !localValue.value) {
        isError.value = true;
        return Promise.reject(new Error('必填'));
      }
      isError.value = false;
      return Promise.resolve();
    },
    clearFields() {
      isError.value = false;
      localValue.value = '';
    },
  });
</script>
<style lang="postcss" scoped>
.field-input {
  display: flex;
  width: 100%;
  justify-content: space-between;
  align-items: center;

  .bk-input {
    height: 42px;

    .is-focused:not(.is-readonly) {
      border: 1px solid #3a84ff !important;
      outline: 0;
      box-shadow: 0 0 3px #a3c5fd;
    }
  }

  .bk-input:not(.is-focused) {
    border: none;
  }

  .err-tip {
    font-size: 16px;
    color: #ea3636;
  }
}

.is-errored {
  background-color: #fee;

  .bk-input {
    border-color: #ea3636 !important;
  }
}
</style>
