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
    v-model="generalValue"
    allow-create
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
      <bk-select
        v-if="config.type === 'field'"
        v-model="selectValue"
        class="bk-select"
        filterable
        :placeholder="t('请选择已有选项')"
        @change="handlerChange">
        <bk-option-group
          v-if="riskFieldList.length > 0"
          collapsible
          :label="t('风险字段')">
          <bk-option
            v-for="(item, index) in riskFieldList"
            :id="item.id"
            :key="index"
            :name="item.name">
            <bk-popover
              max-width="800px"
              placement="left"
              theme="light">
              <div style="width: 100%;height: 100%;">
                {{ item.name }}
              </div>
              <template #content>
                <div v-if="isCurrentValue">
                  <div style="font-size: 12px;font-weight: 700;">
                    {{ t('当前值：') }}
                  </div>
                  <div class="current-value">
                    {{ getCurrentValue(item.id) }}
                  </div>
                </div>
              </template>
            </bk-popover>
          </bk-option>
        </bk-option-group>

        <bk-option-group
          v-if="eventDataList.length > 0"
          collapsible
          :label="t('事件字段')">
          <bk-option
            v-for="(item, index) in eventDataList"
            :id="item.lable"
            :key="index"
            :name="item.lable">
            <bk-popover
              placement="left"
              theme="light">
              <div style="width: 100%;height: 100%;">
                {{ item.lable }}
              </div>
              <template #content>
                <div v-if="isCurrentValue">
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
        </bk-option-group>
      </bk-select>
      <div v-else>
        <audit-user-selector-tenant
          v-if="config.custom_type === 'bk_user_selector'"
          v-model="userSelectorValue"
          allow-create
          class="consition-value" />

        <bk-input
          v-else
          v-model="generalValue"
          clearableshow-word-limit
          :resize="false"
          :rows="4"
          show-overflow-tooltips
          :type="config.custom_type === 'textarea' ? 'textarea': 'text'"
          @change="handlerChange" />
      </div>
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

  const datePickerValue = computed(() => {
    if (props.config.custom_type === 'datetime' && props.config.type === 'self') {
      const value = modelValue.value.value || modelValue.value.field;
      return value ? String(value) : undefined;
    }
    return undefined;
  });

  const userSelectorValue = computed<string | string[]>({
    get() {
      if (props.config.custom_type === 'bk_user_selector') {
        const val = modelValue.value.value;
        if (Array.isArray(val)) {
          return val as string[];
        }
        if (typeof val === 'string') {
          return val;
        }
        return [];
      }
      return [];
    },
    set(val: string | string[]) {
      handlerUserChange(val);
    },
  });

  const generalValue = computed<string>(() => {
    const value = modelValue.value.value || modelValue.value.field;
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    if (value === 0) {
      return '0';
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
  const handlerSelectChange = (val: string) => {
    modelValue.value = {
      field: '',
      value: val,
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

  const getCurrentValue = (id: string) => props.detailData[id];

  watch(() => modelValue.value, (val) => {
    const valueToFormat = val.value || val.field;
    // eslint-disable-next-line max-len
    tipText.value = formatTooltipData(props.config.custom_type, valueToFormat);
  }, {
    deep: true,
  });

  watch(() => props.config.custom_type, () => {
    if (props.config.custom_type === 'bk_user_selector') {
      modelValue.value = {
        field: props.config.default_value || [],
        value: props.config.default_value || [],
      };
    } else {
      modelValue.value = {
        field: props.config.default_value || '',
        value: props.config.default_value || '',
      };
    }
  }, {
    immediate: true,
    deep: true,
  });

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
