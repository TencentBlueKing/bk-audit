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
    ref="rootRef"
    class="select-field-value"
    :class="{
      'is-errored': isError,
      'is-background-errored-tip': theme === 'background'
    }">
    <bk-select
      v-model="modelValue"
      filterable
      :placeholder="t('请选择')"
      @change="attrs.onChange"
      @update:model-value="onUpdate">
      <template #prefix>
        <slot name="prefix" />
      </template>
      <bk-option
        v-for="(item, key) in rtFields"
        :key="key"
        :label="item.label"
        :value="item.value" />
    </bk-select>
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
    ref,
    useAttrs,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    rtFields: Array<{
      label: string;
      value: string;
      field_type: string;
    }>;
    theme?: 'background' | '',
  }

  interface Expose {
    getValue: () => void,
    clearFields: () => void
  }
  withDefaults(defineProps<Props>(), {
    theme: '',
  });

  const { t } = useI18n();
  const attrs = useAttrs();

  const isError = ref(false);
  const modelValue = defineModel({
    default: '',
  });

  const onUpdate = (val: string) => {
    if (val) {
      isError.value = false;
    }
  };

  defineExpose<Expose>({
    getValue() {
      if (!modelValue.value) {
        isError.value = true;
        return Promise.reject(new Error('必填'));
      }
      isError.value = false;
      return Promise.resolve();
    },
    clearFields() {
      isError.value = false;
      modelValue.value = '';
    },
  });
</script>
<style lang="postcss">
.select-field-value {
  position: relative;

  .err-tip {
    position: absolute;
    top: 27%;
    right: 30px;
    font-size: 16px;
    line-height: 1;
    color: #ea3636;
  }
}

.is-errored.is-background-errored-tip .bk-input {
  input {
    background-color: #fee !important;
  }
}
</style>
