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
  <div class="render-type-tab">
    <div
      class="render-item"
      :class="{ active: modelValue === 'table' }"
      @click="handleChange('table')">
      <audit-icon type="table" />
      结果列表
    </div>
    <div
      class="render-item"
      :class="{ active: modelValue === 'chart' }"
      @click="handleChange('chart')">
      <audit-icon type="chart" />
      分析视图
    </div>
  </div>
</template>
<script setup lang="ts">
  interface Props {
    modelValue: 'table' | 'chart'
  }
  interface Emits {
    (e: 'change', value:  Props['modelValue']): void,
    (e: 'update:modelValue', value:  Props['modelValue']): void,
  }
  const props = withDefaults(defineProps<Props>(), {
    modelValue: 'table',
  });

  const emit = defineEmits<Emits>();
  const handleChange = (value: Props['modelValue']) => {
    if (value === props.modelValue) {
      return true;
    }
    emit('update:modelValue', value);
    emit('change', value);
  };
</script>
<style lang="postcss">
  .render-type-tab {
    display: flex;
    padding: 3px;
    margin-left: auto;
    background: #eaebf0;
    border-radius: 2px;

    .render-item {
      width: 100px;
      font-size: 14px;
      line-height: 26px;
      color: #63656e;
      text-align: center;
      cursor: pointer;
      border-radius: 2px;

      &.active {
        cursor: default;
        background: #fff;
      }
    }
  }
</style>
