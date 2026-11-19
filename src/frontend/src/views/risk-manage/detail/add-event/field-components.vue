<!-- eslint-disable vue/v-on-event-hyphenation -->
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
  <div class="add-event-com">
    <bk-input
      v-if="type === 'textarea'"
      v-model="textareaValue"
      :resize="false"
      type="textarea"
      @update:modelValue="handleChange('textarea')" />
    <bk-input
      v-if="type === 'number-input'"
      v-model="numberValue"
      :precision="999"
      type="number"
      @update:modelValue="handleChange('number-input')" />
    <bk-input
      v-if="type === 'input'"
      v-model="inputValue"
      type="input"
      @update:modelValue="handleChange('input')" />
    <audit-user-selector-tenant
      v-if="type === 'user-selector'"
      v-model="userValue"
      allow-create
      :auto-focus="false"
      class="add-event-com-user-selector"
      @update:modelValue="handleChange('user-selector')" />
    <bk-date-picker
      v-if="type === 'date-picker'"
      v-model="timeValue"
      append-to-body
      class="add-event-com-date-picker"
      clearable
      type="datetime"
      @update:modelValue="handleChange('date-picker')" />
  </div>
</template>


<script setup lang='ts'>
  import { ref } from 'vue';

  import { convertGMTTimeToStandard } from '@/utils/assist/timestamp-conversion';

  interface Props {
    type: string;
  }

  interface Emits{
    (e: 'update', value: string | number | string[]): void;
  }
  defineProps<Props>();

  const emits = defineEmits<Emits>();
  const inputValue = ref('');
  const textareaValue = ref('');
  const numberValue = ref();
  const userValue = ref([]);
  const timeValue = ref('');

  const handleChange = (type: string) => {
    if (type === 'textarea') {
      emits('update', textareaValue.value);
    }
    if (type === 'number-input') {
      emits('update', numberValue.value);
    }
    if (type === 'user-selector') {
      emits('update', userValue.value);
    }
    if (type === 'date-picker') {
      emits('update', convertGMTTimeToStandard(timeValue.value));
    }
    if (type === 'input') {
      emits('update', inputValue.value);
    }
  };
</script>

<style lang="postcss" scoped>
.user-selector {
  width: 250px;
  height: 40px;

  :deep(.bk-input) {
    border: none !important;
  }

}

.add-event-com {
  width: 100%;
  height: 100%;

  :deep(.bk-input),
  :deep(.bk-textarea),
  :deep(.bk-date-picker),
  :deep(.bk-date-picker-rel) {
    width: 100%;
    height: 100%;
  }

  :deep(.bk-input),
  :deep(.bk-textarea) {
    border: none !important;
    border-radius: 0;
  }

  :deep(.bk-input--text),
  :deep(.bk-textarea > textarea) {
    height: 100% !important;
    min-height: 0 !important;
    padding: 0 var(--bk-theme-space-12);
    overflow: hidden;
    line-height: 40px;
  }
}

.add-event-com-date-picker {
  :deep(.bk-date-picker-rel .bk-date-picker-editor) {
    height: 100%;
    border: none !important;
  }
}
</style>
<style lang="postcss">
.add-event-com-user-selector {
  width: 100%;
  height: 100%;

  .bk-select-trigger,
  .bk-select-tag {
    height: 100% !important;
    border: none !important;
  }
}
</style>
