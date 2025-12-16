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
  <div>
    <bk-input
      v-if="type === 'textarea'"
      v-model="textareaValue"
      :resize="false"
      style="width: 232px;height: 100%"
      type="textarea"
      @update:modelValue="handleChange('textarea')" />
    <bk-input
      v-if="type === 'number-input'"
      v-model="numberValue"
      :precision="9"
      style="width: 232px;height: 100%"
      type="number"
      @update:modelValue="handleChange('number-input')" />
    <bk-input
      v-if="type === 'input'"
      v-model="inputValue"
      style="width: 232px;height: 42px"
      type="input"
      @update:modelValue="handleChange('input')" />
    <audit-user-selector
      v-if="type === 'user-selector'"
      v-model="userValue"
      allow-create
      :auto-focus="false"
      class="user-selector"
      @update:modelValue="handleChange('user-selector')" />
    <bk-date-picker
      v-if="type === 'date-picker'"
      v-model="timeValue"
      append-to-body
      clearable
      style="width: 232px;height: 100%"
      type="datetime"
      @update:modelValue="handleChange('date-picker')" />
  </div>
</template>


<script setup lang='ts'>
  import { nextTick, onMounted, ref } from 'vue';

  import { convertGMTTimeToStandard } from '@/utils/assist/timestamp-conversion';

  interface Props {
    type: string;
    value: string | number | string[];
  }

  interface Emits{
    (e: 'update', value: string | number | string[]): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const inputValue = ref('');
  const textareaValue = ref('');
  const numberValue = ref();
  const userValue = ref<string[]>([]);
  const timeValue = ref<string>('');

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

  onMounted(() => {
    nextTick(() => {
      if (props.value !== '') {
        if (props.type === 'textarea' && typeof props.value === 'string') {
          textareaValue.value = props.value;
        }
        if (props.type === 'number-input' && typeof props.value === 'number') {
          numberValue.value = props.value;
        }
        if (props.type === 'user-selector' && Array.isArray(props.value)) {
          userValue.value = props.value;
        }
        if (props.type === 'date-picker' && typeof props.value === 'string') {
          timeValue.value = props.value;
        }
        if (props.type === 'input' && typeof props.value === 'string') {
          inputValue.value = props.value;
        }
      }
    });
  });

</script>

<style>
.user-selector {
  width: 232px;
}
</style>
