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
  <div class="content-tab-box">
    <div
      v-if="isShowAccessModel"
      class="tab-item"
      :class="{
        active: modelValue === 'accessModel'
      }"
      @click="handleChange('accessModel')">
      {{ t('接入模型') }}
    </div>
    <div
      v-if="isShowDataReport"
      class="tab-item"
      :class="{
        active: modelValue === 'dataReport'
      }"
      @click="handleChange('dataReport')">
      {{ t('数据上报') }}
    </div>
    <div
      v-if="isShowSystemDiagnosis"
      class="tab-item"
      :class="{
        active: modelValue === 'systemDiagnosis'
      }"
      @click="handleChange('systemDiagnosis')">
      {{ t('系统诊断') }}
    </div>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import useUrlSearch from '@hooks/use-url-search';

  interface Props {
    modelValue: 'accessModel' | 'dataReport' | 'systemDiagnosis',
    isShowAccessModel: boolean,
    isShowDataReport: boolean,
    isShowSystemDiagnosis: boolean,
  }
  interface Emits {
    (e: 'update:modelValue', value: Props['modelValue']): void
  }
  withDefaults(defineProps<Props>(), {
    modelValue: 'accessModel',
    isShowAccessModel: true,
    isShowDataReport: true,
    isShowSystemDiagnosis: true,
  });

  const emit = defineEmits<Emits>();

  const { appendSearchParams } = useUrlSearch();
  const { t } = useI18n();

  const handleChange = (value:Props['modelValue']) => {
    appendSearchParams({
      contentType: value,
    });
    emit('update:modelValue', value);
  };
</script>
<style lang="postcss">
  .content-tab-box {
    display: flex;
    padding-left: 24px;
    font-size: 14px;
    line-height: 22px;
    background: #fff;

    .tab-item {
      position: relative;
      padding-bottom: 16px;
      color: #63656e;
      cursor: pointer;

      &.active {
        color: #3a84ff;

        &::after {
          position: absolute;
          right: 0;
          bottom: 0;
          left: 0;
          height: 2px;
          background: #3a84ff;
          content: '';
        }
      }

      &:nth-child(n+2) {
        margin-left: 60px;
      }
    }
  }
</style>
