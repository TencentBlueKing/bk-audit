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
  <div class="form-item">
    <bk-input
      v-if="dataConfig.field_category === 'input'"
      v-model="inputData"
      @update:model-value="handleInputDataChange" />
    <bk-input
      v-if="dataConfig.field_category === 'number_input'"
      v-model="numberInputData"
      type="number"
      @update:model-value="handleNumberInputDataChange" />
    <audit-user-selector
      v-if="dataConfig.field_category === 'person_select'"
      v-model="user"
      @change="handleUserChange" />

    <bk-date-picker
      v-if="dataConfig.field_category === 'time_range_select'"
      ref="datePickerRef"
      append-to-body
      clearable
      :model-value="pickerRangeValue"
      style="width: 100%"
      :time-picker-options="{ allowCrossDay: true }"
      type="datetimerange"
      @change="handleRangeChange" />

    <bk-date-picker
      v-if="dataConfig.field_category === 'time_select'"
      v-model="pickerValue"
      clearable
      type="datetime"
      @change="handleChange" />
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue';

  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  interface SearchItem {
    value: string;
    raw_name: string;
    required: boolean;
    description: string;
    display_name: string;
    field_category: string;
  }
  interface FieldCategoryItem {
    id: string;
    name: string;
  }
  interface Props {
    dataConfig: SearchItem,
  }
  interface Emits {
    (e: 'change', value: any): void
  }
  interface Exposes {
    resetValue: () => void,
    change: (isDrillDown: boolean, val?: any) => void,
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const inputData = ref();
  const numberInputData = ref();
  const pickerRangeValue = ref();
  const pickerValue = ref();
  const user = ref();
  const FieldCategory = ref<FieldCategoryItem[]>([]);
  // 获取字段类型
  const { run: fetchGlobalChoices } = useRequest(
    MetaManageService.fetchGlobalChoices,
    {
      defaultValue: {},
      onSuccess(result) {
        FieldCategory.value = result.FieldCategory;
      },
    },
  );

  const handleNumberInputDataChange = (value: any) => {
    numberInputData.value = value;
    emits('change', value);
  };
  const handleInputDataChange = (value: any) => {
    inputData.value = value;
    emits('change', value === '' ?  null : value);
  };
  const handleUserChange = (value: any) => {
    user.value = value;
    emits('change', value);
  };
  const handleRangeChange = (value: any) => {
    pickerRangeValue.value = value;
    emits('change', value);
  };
  const handleChange = (value: any) => {
    pickerValue.value = value;
    emits('change', value);
  };

  const change = (isDrillDown: boolean, val: any) => {
    const newVal = isDrillDown ? props.dataConfig.value : val?.value;
    const type: keyof typeof handlers = isDrillDown ? props.dataConfig.field_category : val.field_category;

    const handlers = {
      input: () => {
        const value = newVal === '' ?  null : newVal;
        if (!isDrillDown) inputData.value = value;
        else handleInputDataChange(value);
      },
      number_input: () => {
        const value = newVal || null;
        if (!isDrillDown) numberInputData.value = value;
        else handleNumberInputDataChange(value);
      },
      person_select: () => {
        const value = newVal || [];
        if (!isDrillDown) user.value = value;
        else handleUserChange(value);
      },
      time_range_select: () => {
        const value = newVal || [];
        if (!isDrillDown) pickerRangeValue.value = value;
        else handleRangeChange(value);
      },
      time_select: () => {
        if (!isDrillDown) {
          pickerValue.value = newVal;
        } else {
          const timestamp = Number(newVal);
          if (!isNaN(timestamp) && timestamp > 0) {
            const date = new Date(timestamp);
            const formattedDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`;
            handleChange(formattedDate);
          } else {
            handleChange(newVal);
          }
        }
      },
    };

    if (handlers[type]) handlers[type]();
  };
  onMounted(() => {
    fetchGlobalChoices();
  });

  defineExpose<Exposes>({
    resetValue() {
      inputData.value = null;
      numberInputData.value = null;
      pickerRangeValue.value = '';
      pickerValue.value = '';
      user.value = '';
    },
    change(isDrillDown: boolean, val?: any) {
      change(isDrillDown, val);
    },
  });
</script>
