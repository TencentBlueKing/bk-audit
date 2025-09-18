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
    v-else-if="config.custom_type === 'select'"
    v-model="localValue"
    allow-create
    class="bk-select"
    filterable
    :placeholder="t('请选择已有选项或自行输入内容后Enter结束')"
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

  <bk-select
    v-else
    v-model="localValue"
    allow-create
    class="bk-select"
    filterable
    :placeholder="t('请选择已有选项或自行输入内容后Enter结束')"
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
          placement="left"
          theme="light">
          <div style="width: 100%;height: 100%;">
            {{ item.name }}
          </div>
          <template #content>
            <div>
              <div style="font-size: 12px;font-weight: 700;">
                {{ t('当前值：') }}
              </div>
              <div>{{ item.id }}</div>
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
    </bk-option-group>
  </bk-select>
  <div
    v-if="localValue !== ''"
    class="item-value">
    <div>
      {{ t('当前值：') }}
    </div>
    <tool-tip-text
      :data="formatTooltipData(config.custom_type, localValue)"
      placement="left"
      theme="light" />
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolTipText from '@/components/show-tooltips-text/index.vue';

  interface Props {
    riskFieldList: Array<{
      id: string,
      name: string,
    }>
    config?: any,
    eventDataList?: any,
  }

  const props = defineProps<Props>();
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
  // 选中或者enter选中，也可能是自定义输入
  const handlerChange = (val: string) => {
    // 如果是选中（包含搜索enter选中）
    if (props.riskFieldList.find((item: { id: string; }) => item.id === val)) {
      modelValue.value = {
        field: val,
        value: '',
      };
      return;
    }
    // 自定义输入
    modelValue.value = {
      field: '',
      value: val,
    };
  };
  const formatTooltipData = (type: string, value: string) => {
    if (type === 'datetime') {
      const date = new Date(value);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }
    return value;
  };
  localValue.value = modelValue.value.value || modelValue.value.field;
</script>

<style lang="postcss" scoped>
.item-value {
  width: 100%;
  height: 50px;
  padding: 3px;
  margin-top: 3px;
  font-size: 12px;
  line-height: 16px;
  word-break: break-all;
  background: #fff;
}
</style>
