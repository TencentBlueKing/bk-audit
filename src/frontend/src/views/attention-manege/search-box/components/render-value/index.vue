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
  <div class="render-form-serach-value">
    <audit-icon
      class="filter-flag mr8"
      style="color: #c4c6cc;"
      type="filter" />
    <value-tag
      v-for="(value, name) in modelValue"
      :key="name"
      ref="valueTagRef"
      :model="modelValue"
      :name="name"
      :value="value"
      @change="handleChange"
      @remove="handleRemove" />
    <div
      v-if="isShowClearBtn"
      v-bk-tooltips="t('清空搜索条件')"
      class="search-value-clear-btn"
      @click="handleValueClear">
      <audit-icon type="delete-fill" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ValueTag from './value-tag.vue';

  interface Props {
    modelValue: Record<string, any>
  }

  interface Emits {
    (e: 'update:modelValue', value: Record<string, any>): void;
    (e: 'submit'): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const valueTagRef = ref();
  const isShowClearBtn = computed(() => Object.keys(props.modelValue).length > 1);

  const handleChange = (fieldName: string, fieldValue: any) => {
    const result = { ...props.modelValue };
    result[fieldName] = fieldValue;
    const getValues = valueTagRef.value.map((item: any) => item.getValue(fieldValue));
    Promise.all(getValues).then(() => {
      emits('update:modelValue', result);
      emits('submit');
      valueTagRef.value.forEach((item: any) => item.handleCancel());
    });
  };

  // 移除单个筛选
  const handleRemove = (fieldName: string) => {
    const result = { ...props.modelValue };
    delete result[fieldName];
    emits('update:modelValue', result);
    emits('submit');
  };

  // 移除所有
  const handleValueClear = () => {
    const result = { };
    emits('update:modelValue', result);
    emits('submit');
  };
</script>
<style lang="postcss">
  .render-form-serach-value {
    display: flex;
    padding: 24px 16px 16px;
    font-size: 12px;
    align-items: center;
    flex-wrap: wrap;

    .filter-flag {
      margin-top: 4px;
      font-size: 16px;
      align-self: flex-start;
    }

    .search-value-clear-btn {
      display: flex;
      height: 22px;
      margin-bottom: 8px;
      color: #c4c6cc;
      cursor: pointer;
      align-items: center;
      justify-content: center;
      transition: all .15s;

      &:hover {
        color: #dcdee5;
      }
    }
  }
</style>
