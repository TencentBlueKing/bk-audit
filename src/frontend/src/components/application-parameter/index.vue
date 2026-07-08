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
  <bk-select
    v-if="config.custom_type === 'select'"
    v-model="selectTypeValue"
    :allow-empty-values="[ '0', 0]"
    class="bk-select"
    filterable
    :placeholder="t('请选择已有选项')"
    @change="handlerSelectChange">
    <bk-option
      v-for="(item, index) in JSON.parse(config.value.items_text)"
      :id="item.value"
      :key="index"
      :name="item.text">
      <bk-popover
        placement="left"
        theme="light">
        <div style="width: 100%;height: 100%;">
          {{ item.text }}
        </div>
        <template #content>
          <div>
            <div style="font-size: 12px;font-weight: 700;">
              {{ t('当前值：') }}
            </div>
            <div class="current-value">
              {{ item.value }}
            </div>
          </div>
        </template>
      </bk-popover>
    </bk-option>
  </bk-select>

  <div v-else>
    <div v-if="config.custom_type === 'datetime' && config.type === 'self'">
      <bk-date-picker
        v-if="config.custom_type === 'datetime' && config.type === 'self'"
        v-model="datePickerValue"
        clearable
        :placeholder="t('请选择日期')"
        type="datetime"
        @change="handleChange" />
    </div>
    <div v-else>
      <audit-user-selector-tenant
        v-if="config.custom_type === 'bk_user_selector'"
        v-model="userSelectorValue"
        allow-create
        class="consition-value"
        @change="handlerUserChange" />
      <bk-select
        v-else-if="config.type === 'field' && supportsFieldReference"
        v-model="selectValue"
        class="bk-select"
        filterable
        :input-search="false"
        :placeholder="t('请选择已有选项')"
        :search-placeholder="t('请输入关键字')"
        @change="handlerChange">
        <bk-option-group
          v-if="displayRiskFieldList.length > 0"
          collapsible
          :label="t('风险字段')">
          <bk-option
            v-for="(item, index) in displayRiskFieldList"
            :id="item.id"
            :key="`${item.id}-${index}`"
            :name="item.name" />
        </bk-option-group>

        <bk-option-group
          v-if="eventDataList.length > 0"
          collapsible
          :label="t('事件字段')">
          <bk-option
            v-for="(item, index) in eventDataList"
            :id="item.lable"
            :key="index"
            :name="item.lable" />
        </bk-option-group>
      </bk-select>
      <bk-input
        v-else
        v-model="generalValue"
        clearable
        :resize="false"
        :rows="4"
        show-overflow-tooltips
        show-word-limit
        :type="config.custom_type === 'textarea' ? 'textarea': 'text'"
        @change="handlerChange" />
    </div>
  </div>

  <div
    v-if="localValue && (Array.isArray(localValue) ? localValue.length > 0 : localValue !== '')
      && config.custom_type !== 'select' && isShowtip && isCurrentValue"
    class="item-value">
    <div>
      {{ t('当前值：') }}
    </div>
    <tool-tip-text
      :data="tipText"
      :line="2"
      :max-width="800"
      placement="left"
      theme="light" />
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';

  interface Props {
    riskFieldList: Array<{
      id: string,
      name: string,
    }>
    isCurrentValue?: boolean,
    config?: any,
    eventDataList?: any,
    detailData: any,
  }

  const props = withDefaults(defineProps<Props>(), {
    isCurrentValue: true,
    config: () => ({}),
    eventDataList: () => ([]),
    detailData: () => ({}),
  });
  const { t } = useI18n();
  const tipText = ref('');
  const selectValue = ref();
  // 专门用于 select 类型的下拉框值（支持数字类型如 0, 1）
  const selectTypeValue = ref<string | number>('');

  const supportsFieldReference = computed(() => {
    const customType = props.config?.custom_type;
    return customType === 'datetime'
      || customType === 'textarea'
      || customType === 'input'
      || customType === 'bk_date_picker'
      || customType === '';
  });

  const getRiskFieldName = (fieldId: string) => (
    props.riskFieldList.find(item => item.id === fieldId)?.name || fieldId
  );

  const currentFieldRefId = computed(() => {
    const fieldId = modelValue.value.field || props.config?.default_value || selectValue.value;
    return fieldId ? String(fieldId) : '';
  });

  const displayRiskFieldList = computed(() => {
    const list = [...props.riskFieldList];
    const fieldId = currentFieldRefId.value;
    if (fieldId && !list.some(item => item.id === fieldId)) {
      list.unshift({
        id: fieldId,
        name: getRiskFieldName(fieldId),
      });
    }
    return list;
  });

  const datePickerValue = computed(() => {
    if (props.config.custom_type === 'datetime' && props.config.type === 'self') {
      const value = modelValue.value.value || modelValue.value.field;
      return value ? String(value) : undefined;
    }
    return undefined;
  });

  const userSelectorValue = computed<string | string[]>({
    get() {
      if (props.config.custom_type !== 'bk_user_selector') {
        return [];
      }
      const val = modelValue.value.value;
      if (Array.isArray(val)) {
        return val.map(item => String(item));
      }
      if (val !== undefined && val !== null && val !== '') {
        return String(val);
      }
      return [];
    },
    set(val: string | string[]) {
      modelValue.value = {
        field: '',
        value: val,
      };
    },
  });

  const generalValue = computed<string | number>(() => {
    // 兼容数字类型的值（如 0），不能用 || 因为 0 是 false 值
    const val = modelValue.value.value;
    const value = (val !== undefined && val !== null && val !== '') ? val : modelValue.value.field;
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    if (typeof value === 'number') {
      return value;
    }

    return value ? String(value) : '';
  });

  const localValue = computed(() => {
    if (props.config.custom_type === 'datetime' && props.config.type === 'self') {
      return datePickerValue.value;
    }
    if (props.config.custom_type === 'bk_user_selector') {
      return userSelectorValue.value;
    }
    if (selectValue.value) {
      return selectValue.value;
    }
    return generalValue.value;
  });
  const isShowtip = ref(false);
  const modelValue = defineModel<{field: string | number, value: string | number |string[]}>({
    default: () => ({
      field: '',
      value: '',
    }),
  });
  // 日期选择
  const handleChange = (val: any) => {
    modelValue.value = {
      field: '',
      value: val ? String(val) : '',
    };
  };
  // 选择
  const handlerSelectChange = (val: string | number) => {
    // 兼容数字类型的值（如 0, 1），需要判断 val !== undefined && val !== null
    // 而不是直接用 val，因为 0 是 false 值但是有效的选择
    const isValidValue = val !== undefined && val !== null;
    selectTypeValue.value = isValidValue ? val : '';
    modelValue.value = {
      field: '',
      value: isValidValue ? val : '',
    };
  };

  // 用户选择
  const handlerUserChange = (val: string | string[]) => {
    modelValue.value = {
      field: '',
      value: val,
    };
  };
  // 通用输入
  const handlerChange = (val: string) => {
    // 如果是选中（包含搜索enter选中）
    if (props.riskFieldList.find((item: { id: string; }) => item.id === val)) {
      modelValue.value = {
        field: val,
        value: '',
      };
      isShowtip.value = true;
      return;
    }

    if (props.eventDataList.find((item: { text: string; }) => item.text === val)) {
      isShowtip.value = true;
      // 自定义输入
      modelValue.value = {
        field: '',
        value: props.eventDataList.find((item: { text: string; }) => item.text === val).value,
      };
      return;
    }
    isShowtip.value = false;
    // 自定义输入
    modelValue.value = {
      field: '',
      value: val,
    };
    return;
  };
  const formatTooltipData = (type: string | number, value: string | string[] | number) => {
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    if (typeof value === 'object') {
      return JSON.stringify(value);
    }
    if (type === 'datetime' && props.config.type === 'self') {
      const date = new Date(String(value));
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } if (type === 'datetime' && props.config.type === 'field') {
      return  props.detailData[modelValue.value.field];
    }  if (type === 'select') {
      return value;
    }
    if (modelValue.value.field === '' && modelValue.value.value !== '' && type !== 'datetime' && type !== 'select') {
      return value;
    }
    if (modelValue.value.field !== '' && modelValue.value.value === '' && type !== 'datetime' && type !== 'select') {
      return props.detailData[modelValue.value.field];
    }
    return value;
  };

  const syncFieldSelectValue = () => {
    if (props.config.type !== 'field' || !supportsFieldReference.value) {
      return;
    }
    const fieldId = modelValue.value.field || props.config.default_value || '';
    selectValue.value = fieldId;
  };

  const syncModelFromConfig = () => {
    const { custom_type: customType, type, default_value: defaultValue } = props.config;

    if (customType === 'bk_user_selector') {
      const currentValue = modelValue.value.value;
      const hasValue = Array.isArray(currentValue)
        ? currentValue.length > 0
        : currentValue !== undefined && currentValue !== null && currentValue !== '';
      modelValue.value = {
        field: '',
        value: hasValue ? currentValue : (defaultValue ?? []),
      };
      return;
    }

    if (customType === 'select') {
      const defaultVal = defaultValue;
      selectTypeValue.value = (defaultVal !== undefined && defaultVal !== null) ? defaultVal : '';
      if (modelValue.value.value === '' && selectTypeValue.value !== '') {
        modelValue.value = {
          field: '',
          value: selectTypeValue.value,
        };
      }
      return;
    }

    if (type === 'field' && supportsFieldReference.value) {
      const fieldId = modelValue.value.field || defaultValue || '';
      selectValue.value = fieldId;
      if (fieldId) {
        modelValue.value = {
          field: fieldId,
          value: '',
        };
      }
      return;
    }

    const currentValue = modelValue.value.value;
    const hasValue = currentValue !== undefined && currentValue !== null && currentValue !== '';
    modelValue.value = {
      field: '',
      value: hasValue ? currentValue : (defaultValue ?? ''),
    };
    selectValue.value = undefined;
  };

  watch(() => modelValue.value, (val) => {
    const valueToFormat = val.value || val.field;
    tipText.value = formatTooltipData(props.config.custom_type, valueToFormat);
    syncFieldSelectValue();
  }, {
    deep: true,
  });

  watch(
    () => [props.config.custom_type, props.config.type, props.config.default_value] as const,
    () => {
      syncModelFromConfig();
    },
    {
      immediate: true,
      deep: true,
    },
  );

  watch(
    () => props.riskFieldList,
    () => {
      syncFieldSelectValue();
    },
    { deep: true },
  );

</script>

<style lang="postcss" scoped>
.item-value {
  width: 100%;
  height: auto;
  padding: 3px;
  padding-bottom: 5px;
  margin-top: 3px;
  font-size: 12px;
  line-height: 16px;
  word-break: break-all;
  background: #fff;
}

.current-value {
  height: auto;
  max-width: 50vw;
  max-height: 50vh;
  padding: 3px;
  padding-bottom: 5px;
  margin-top: 3px;
  overflow: auto;
  font-size: 12px;
  line-height: 16px;
  word-break: break-all;
  background: #fff;
}
</style>