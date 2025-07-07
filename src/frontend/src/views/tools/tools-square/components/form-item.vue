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
  }
  defineProps<Props>();
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
    emits('change', value);
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

  onMounted(() => {
    fetchGlobalChoices();
  });

  defineExpose<Exposes>({
    resetValue() {
      inputData.value = '';
      numberInputData.value = '';
      pickerRangeValue.value = '';
      pickerValue.value = '';
      user.value = '';
    },

  });
</script>
