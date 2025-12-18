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
  <div class="type-tab">
    <div
      class="tab-item"
      :class="{
        active: modelValue === 'dynamicTopo',
        disabled: Boolean(uniquedType) && uniquedType !== 'TOPO'
      }"
      @click="handleChange('dynamicTopo', Boolean(uniquedType) && uniquedType !== 'TOPO')">
      {{ t('动态拓扑') }}
    </div>
    <div
      class="tab-item"
      :class="{
        active: modelValue === 'staticTopo',
        disabled: Boolean(uniquedType) && uniquedType !== 'INSTANCE'
      }"
      @click="handleChange('staticTopo', Boolean(uniquedType) && uniquedType !== 'INSTANCE')">
      {{ t('静态拓扑') }}
    </div>
    <div
      class="tab-item"
      :class="{
        active: modelValue === 'serviceTemplate',
        disabled: Boolean(uniquedType) && uniquedType !== 'SERVICE_TEMPLATE'
      }"
      @click="handleChange('serviceTemplate', Boolean(uniquedType) && uniquedType !== 'SERVICE_TEMPLATE')">
      {{ t('服务模板') }}
    </div>
    <div
      class="tab-item"
      :class="{
        active: modelValue === 'setTemplate',
        disabled: Boolean(uniquedType) && uniquedType !== 'SET_TEMPLATE'
      }"
      @click="handleChange('setTemplate', Boolean(uniquedType) && uniquedType !== 'SET_TEMPLATE')">
      {{ t('集群模板') }}
    </div>
    <div
      class="tab-item"
      :class="{
        active: modelValue === 'customInput',
        disabled: Boolean(uniquedType) && uniquedType !== 'INSTANCE'
      }"
      @click="handleChange('customInput', Boolean(uniquedType) && uniquedType !== 'INSTANCE')">
      {{ t('自定义输入') }}
    </div>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  interface Props {
    modelValue: string,
    uniquedType?: string,
  }
  interface Emits {
    (e: 'change', value: string): void
    (e: 'update:modelValue', value: string): void
  }

  const props = withDefaults(defineProps<Props>(), {
    uniquedType: '',
  });

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const handleChange = (value: string, disabled: boolean) => {
    if (disabled) {
      return;
    }
    if (value === props.modelValue) {
      return;
    }
    emits('change', value);
    emits('update:modelValue', value);
  };
</script>
<style lang="postcss" scoped>
  .type-tab {
    display: flex;
    background: #fafbfd;
    border-bottom: 1px solid #dcdee5;
    user-select: none;

    .tab-item {
      height: 42px;
      min-width: 105px;
      padding: 0 10px;
      line-height: 42px;
      color: #63656e;
      text-align: center;
      cursor: pointer;
      border-right: 1px solid #dcdee5;

      &.active {
        position: relative;
        color: #313238;
        cursor: default;
        background: #fff;

        &::after {
          position: absolute;
          bottom: -2px;
          left: 0;
          width: 100%;
          height: 3px;
          background: #fff;
          content: '';
        }
      }

      &.disabled {
        color: #c4c6cc;
        cursor: not-allowed;
      }
    }
  }
</style>
