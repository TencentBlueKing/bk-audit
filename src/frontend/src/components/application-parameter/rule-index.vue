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
  <bk-date-picker
    v-if="config.custom_type === 'datetime'"
    v-model="localValue"
    clearable
    :placeholder="t('请选择日期')"
    type="datetime"
    @change="handleChange" />

  <bk-select
    v-if="config.custom_type === 'select'"
    v-model="localValue"
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
            <div>{{ item.value }}</div>
          </div>
        </template>
      </bk-popover>
    </bk-option>
  </bk-select>

  <div v-else>
    <div v-if="config.custom_type === 'datetime' && config.type === 'self'">
      <bk-date-picker
        v-if="config.custom_type === 'datetime' && config.type === 'self'"
        v-model="localValue"
        clearable
        :placeholder="t('请选择日期')"
        type="datetime"
        @change="handleChange" />
    </div>
    <div v-else>
      <bk-select
        v-if="config.type === 'field' || config.type === 'self'"
        v-model="localValue"
        class="bk-select"
        filterable
        :placeholder="t('请选择已有选项')"
        @change="handlerFieldChange">
        <bk-option
          v-for="(item, index) in riskFieldList"
          :id="item.id"
          :key="index"
          :name="item.name">
          {{ item.name }} {{ item.id }}
        </bk-option>
      </bk-select>
      <bk-input
        v-else
        v-model="localValue"
        clearable
        @change="handlerInputChange" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    riskFieldList: Array<{
      id: string,
      name: string,
    }>
    config?: any,

  }

  defineProps<Props>();
  const { t } = useI18n();
  const localValue = ref('');  // 仅仅用于select绑定，真正传给父组件的是：根据input，select类型赋值给modelValue.value，modelValue.field

  const modelValue = defineModel<{field: string, value: string}>({
    default: () => ({
      field: '',
      value: '',
    }),
  });
  // 日期选择
  const handleChange = (val: string) => {
    modelValue.value = {
      field: '',
      value: val,
    };
  };
  // 选择
  const handlerSelectChange = (val: string) => {
    modelValue.value = {
      field: '',
      value: val,
    };
  };

  const handlerFieldChange = (val: string) => {
    modelValue.value = {
      field: val,
      value: '',
    };
  };
  const handlerInputChange = (val: string) => {
    modelValue.value = {
      field: '',
      value: val,
    };
  };
  localValue.value = modelValue.value.value || modelValue.value.field;
</script>
