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
      append-to-body
      clearable
      style="width: 100%"
      type="datetime"
      @change="handleTimeChange" />

    <bk-select
      v-if="dataConfig.field_category === 'multiselect'"
      v-model="enumValue"
      class="bk-select"
      filterable
      :input-search="false"
      multiple
      :search-placeholder="t('请输入关键字')"
      @change="handleEnumChange">
      <bk-option
        v-for="(selectItem, selectIndex) in dataConfig.choices"
        :key="selectIndex"
        :label="selectItem.name"
        :value="selectItem.key" />
    </bk-select>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  interface SearchItem {
    // value: string;
    raw_name: string;
    required: boolean;
    description: string;
    display_name: string;
    field_category: string;
    choices:Array<{
      key: string,
      name: string
    }>;
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
    setData: (val: any) => void,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const inputData = ref<string>('');
  const numberInputData = ref<number>(NaN);
  const pickerRangeValue = ref();
  const pickerValue = ref<string>('');
  const user = ref<Array<string>>([]);
  const enumValue = ref<Array<string>>([]);

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

  const handleInputDataChange = (value: string) => {
    inputData.value = value;
    emits('change', value || null);
  };
  const handleNumberInputDataChange = (value: number) => {
    numberInputData.value = value;
    emits('change', value || null);
  };
  const handleUserChange = (value: Array<string>) => {
    user.value = value;
    emits('change', value || []);
  };
  const handleRangeChange = (value: any) => {
    pickerRangeValue.value = value;
    emits('change', value || []);
  };
  const handleTimeChange = (value: string) => {
    pickerValue.value = value;
    emits('change', value || null);
  };
  const handleEnumChange = (value: Array<string>) => {
    enumValue.value = value;
    emits('change', value || []);
  };

  const change = (val: any) => {
    const type: keyof typeof handlers = props.dataConfig.field_category as keyof typeof handlers;

    const handlers = {
      input: () => {
        const value =  val;
        handleInputDataChange(value);
      },
      number_input: () => {
        const value = val;
        handleNumberInputDataChange(value);
      },
      person_select: () => {
        const value = val;
        handleUserChange(value);
      },
      time_range_select: () => {
        const value = val;
        handleRangeChange(value);
      },
      time_select: () => {
        // 如果已经是正确的格式字符串，直接使用
        if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(val)) {
          handleTimeChange(val);
          return;
        }
        const timestamp = Number(val);
        if (!isNaN(timestamp) && timestamp > 0) {
          const date = new Date(timestamp);
          const formattedDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`;
          handleTimeChange(formattedDate);
        }
      },
      multiselect: () => {
        const value = val || [];
        handleEnumChange(value);
      },
    };

    if (handlers[type]) handlers[type]();
  };

  onMounted(() => {
    fetchGlobalChoices();
  });

  defineExpose<Exposes>({
    resetValue() {
      inputData.value = '';
      numberInputData.value = NaN;
      pickerRangeValue.value = [];
      pickerValue.value = '';
      user.value = [];
    },
    setData(val: any) {
      change(val);
    },
  });
</script>
