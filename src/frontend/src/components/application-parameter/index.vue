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
    v-model="localValue"
    allow-create
    class="bk-select"
    filterable
    placeholder="请选择已有选项或自行输入内容后Enter结束"
    @change="handlerChange">
    <bk-option
      v-for="(item, index) in riskFieldList"
      :id="item.id"
      :key="index"
      :name="item.name">
      {{ item.name }}
    </bk-option>
  </bk-select>
</template>
<script setup lang="ts">
  import {
    onMounted,
    ref,
  } from 'vue';

  interface Props {
    modelValue: {
      field: string,
      value: string,
    }
    riskFieldList: Array<{
      id: string,
      name: string,
    }>
  }

  const props = defineProps<Props>();

  const emit = defineEmits<{
    'update:modelValue': [value: {field: string, value: string}]
  }>();

  const localValue = ref('');  // 仅仅用于select绑定，真正传给父组件的是：根据input，select类型赋值给modelValue.value，modelValue.field

  // 选中或者enter选中，也可能是自定义输入
  const handlerChange = (val: string) => {
    const target = {
      ...props.modelValue,
    };
    // 如果是选中（包含搜索enter选中）
    if (props.riskFieldList.find((item: { id: string; }) => item.id === val)) {
      target.field = val;
      target.value = '';
      emit('update:modelValue', target);
      return;
    }
    // 自定义输入
    target.value = val;
    target.field = '';
    emit('update:modelValue', target);
  };

  onMounted(() => {
    // 编辑、克隆填充
    localValue.value = props.modelValue.value || props.modelValue.field;
  });
</script>
