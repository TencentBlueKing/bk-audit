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
      v-model="localValue"
      class="strategy-create-aiops-select-item"
      filterable
      :multiple="multiple"
      :placeholder="t('请选择')"
      size="large"
      @change="attrs.onChange"
      @update:model-value="onUpdate">
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
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import  type { ResourceFieldType } from './render-field.vue';

  interface Props {
    rtFields: Array<ResourceFieldType>;
    defaultValue: string | string[];
    required?: boolean;
    multiple?: boolean;
    theme?: 'background' | ''
  }

  interface Expose {
    getValue: () => void,
    clearFields: () => void
  }
  const props = withDefaults(defineProps<Props>(), {
    required: false,
    multiple: false,
    theme: '',
  });

  const { t } = useI18n();
  const attrs = useAttrs();

  const isError = ref(false);
  // eslint-disable-next-line vue/no-setup-props-destructure
  const localValue = ref(props.defaultValue);

  const onUpdate = (val: string) => {
    if (val) {
      isError.value = false;
    }
  };
  watch(() => props.defaultValue, (value) => {
    localValue.value = value;
  }, {
    immediate: true,
  });

  defineExpose<Expose>({
    getValue() {
      if (props.required && !localValue.value) {
        isError.value = true;
        return Promise.reject(new Error('必填'));
      }
      isError.value = false;
      return Promise.resolve({
        field_name: localValue.value,
        source_field: localValue.value,
      });
    },
    clearFields() {
      isError.value = false;
      localValue.value = '';
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

.strategy-create-aiops-select-item {
  /* margin: 0 -15px;
  border-bottom: 0; */

  .bk-input,
  .bk-input:hover {
    height: 42px;
    border-color: white;
  }

  .bk-input.is-focused {
    border-color: #3a84ff;
  }

  .bk-input--large {
    font-size: 12px;
  }

  input::placeholder {
    font-size: 12px;
  }
}

.is-errored .bk-input {
  border-color: #ea3636 !important;
}

.is-errored.is-background-errored-tip .bk-input {
  border-color: #fee !important;

  input {
    background-color: #fee !important;
  }
}
</style>
