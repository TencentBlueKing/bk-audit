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
      v-if="dataConfig.field_category === 'input' ||
        dataConfig.field_category === 'inputer' ||
        dataConfig.field_category === 'variable'"
      v-model="inputData"
      v-bk-tooltips="{
        disabled: !dataConfig.disabled,
        content: t('下钻场景中，为确保数据安全，禁止更改查询输入参数'),
        placement: 'top',
      }"
      :disabled="dataConfig.disabled"
      @update:model-value="handleInputDataChange" />

    <bk-input
      v-else-if="dataConfig.field_category === 'number_input'"
      v-model="numberInputData"
      v-bk-tooltips="{
        disabled: !dataConfig.disabled,
        content: t('下钻场景中，为确保数据安全，禁止更改查询输入参数'),
        placement: 'top',
      }"
      :disabled="dataConfig.disabled"
      type="number"
      @update:model-value="handleNumberInputDataChange" />

    <audit-user-selector
      v-else-if="dataConfig.field_category === 'person_select'"
      v-model="user"
      v-bk-tooltips="{
        disabled: !dataConfig.disabled,
        content: t('下钻场景中，为确保数据安全，禁止更改查询输入参数'),
        placement: 'top',
      }"
      :disabled="dataConfig.disabled"
      @change="handleUserChange" />

    <!-- <bk-date-picker
      v-if="dataConfig.field_category === 'time_range_select'"
      append-to-body
      clearable
      :model-value="pickerRangeValue"
      style="width: 100%"
      :time-picker-options="{ allowCrossDay: true }"
      type="datetimerange"
      @change="handleRangeChange" /> -->

    <date-picker
      v-else-if="dataConfig.field_category === 'time_range_select' || dataConfig.field_category === 'time-ranger'"
      v-model="pickerRangeValue"
      v-bk-tooltips="{
        disabled: !dataConfig.disabled,
        content: t('下钻场景中，为确保数据安全，禁止更改查询输入参数'),
        placement: 'top',
      }"
      class="date-picker"
      :disabled="dataConfig.disabled"
      style="width: 100%"
      @update:model-value="handleRangeChange" />

    <bk-date-picker
      v-else-if="dataConfig.field_category === 'time_select' || dataConfig.field_category === 'time-picker'"
      v-model="pickerValue"
      v-bk-tooltips="{
        disabled: !dataConfig.disabled,
        content: t('下钻场景中，为确保数据安全，禁止更改查询输入参数'),
        placement: 'top',
      }"
      append-to-body
      clearable
      :disabled="dataConfig.disabled"
      style="width: 100%"
      type="datetime"
      @change="handleTimeChange" />

    <bk-select
      v-else-if="dataConfig.field_category === 'multiselect'"
      v-model="enumValue"
      v-bk-tooltips="{
        disabled: !dataConfig.disabled,
        content: t('下钻场景中，为确保数据安全，禁止更改查询输入参数'),
        placement: 'top',
      }"
      class="bk-select"
      :disabled="dataConfig.disabled"
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

    <bk-tag-input
      v-else
      v-model="selectorValue"
      v-bk-tooltips="{
        disabled: !dataConfig.disabled,
        content: t('下钻场景中，为确保数据安全，禁止更改查询输入参数'),
        placement: 'top',
      }"
      allow-create
      collapse-tags
      :disabled="dataConfig.disabled"
      has-delete-icon
      :list="[]"
      @change="handleSelectorChange" />
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  import { DateRange } from '@blueking/date-picker';

  interface SearchItem {
    // value: string;
    raw_name: string;
    default_value?: any;
    required: boolean;
    description: string;
    display_name: string;
    field_category: string;
    choices:Array<{
      key: string,
      name: string
    }>;
    disabled?: boolean;
  }
  interface FieldCategoryItem {
    id: string;
    name: string;
  }
  interface Props {
    dataConfig: SearchItem,
    originModel?: boolean,
    targetValue?: any,
  }
  interface Emits {
    (e: 'change', value: any): void
  }
  interface Exposes {
    resetValue: () => void,
    setData: (val: any) => void,
    getData: () => void,
  }

  const props = withDefaults(defineProps<Props>(), {
    targetValue: undefined,
  });
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const inputData = ref<string>('');
  const numberInputData = ref<number>(NaN);
  const pickerRangeValue = ref<Array<string>>();
  const pickerValue = ref<string>('');
  const user = ref<Array<string>>([]);
  const enumValue = ref<Array<string>>([]);
  const selectorValue = ref<Array<string>>([]);
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
  const handleUserChange = (value: Array<string> | string) => {
    if (!Array.isArray(value)) {
      user.value = [value];
    } else {
      user.value = value;
    }
    emits('change', value || []);
  };
  const handleRangeChange = (value: Array<string>) => {
    // 新增工具配置默认值，只用原始值
    if (props.originModel) {
      pickerRangeValue.value = value;
      emits('change', value || []);
      return;
    }
    // 工具使用查询，使用format值
    const date = new DateRange(value, 'YYYY-MM-DD HH:mm:ss', window.timezone);
    pickerRangeValue.value = value;
    emits('change', [date.startDisplayText, date.endDisplayText]);
  };
  const handleTimeChange = (value: string) => {
    pickerValue.value = value;
    emits('change', value || null);
  };
  const handleEnumChange = (value: Array<string>) => {
    enumValue.value = value;
    emits('change', value || []);
  };
  const handleSelectorChange = (value: Array<string>) => {
    selectorValue.value = value;
    emits('change', value || []);
  };

  const setData = (val: any) => {
    const type: keyof typeof handlers = props.dataConfig.field_category as keyof typeof handlers;
    const handlers = {
      inputer: () => {
        handleInputDataChange(val);
      },
      variable: () => {
        handleInputDataChange(val);
      },
      input: () => {
        handleInputDataChange(val);
      },
      number_input: () => {
        handleNumberInputDataChange(val);
      },
      person_select: () => {
        handleUserChange(val);
      },
      time_range_select: () => {
        handleRangeChange(val);
      },
      'time-ranger': () => {
        handleRangeChange(val);
      },
      'time-picker': () => {
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
        handleEnumChange(val);
      },
    };

    if (handlers[type]) {
      handlers[type]();
    } else {
      handleSelectorChange(val);
    }
  };

  watch(() => props.targetValue, (newVal) => {
    if (newVal) {
      setData(newVal);
    }
  }, {
    immediate: true,
  });

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
      enumValue.value = [];
    },
    setData(val: any) {
      setData(val);
    },
    getData() {
      // 工具使用使用now语法， 每次查询获取最新值
      if (props.dataConfig.field_category === 'time_range_select') {
        const date = new DateRange(pickerRangeValue.value, 'YYYY-MM-DD HH:mm:ss', window.timezone);
        emits('change', [date.startDisplayText, date.endDisplayText]);
      }
    },
  });
</script>
<style lang="postcss" scoped>
  :deep(.date-picker) {
    display: flex;
    width: 100%;

    .date-content {
      flex: 1;

      span {
        width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }
</style>
