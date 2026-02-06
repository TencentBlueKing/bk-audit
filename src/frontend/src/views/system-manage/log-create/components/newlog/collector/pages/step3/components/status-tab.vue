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
  <div class="status-tab">
    <div
      class="status-tab-item"
      :class="{active: modelValue === 'all'}"
      @click="handleStatusChange('all')">
      {{ t('全部') }} ({{ data.allList.length }})
    </div>
    <div
      class="status-tab-item"
      :class="{
        active: modelValue === 'successed'
      }"
      @click="handleStatusChange('successed')">
      <audit-icon
        svg
        type="success" />
      {{ t('成功') }} ({{ data.successList.length }})
    </div>
    <div
      class="status-tab-item"
      :class="{
        active: modelValue === 'failed'
      }"
      @click="handleStatusChange('failed')">
      <audit-icon
        svg
        type="failed" />
      {{ t('失败') }} ({{ data.failedList.length }})
    </div>
    <div
      class="status-tab-item"
      :class="{
        active: modelValue === 'running'
      }"
      @click="handleStatusChange('running')">
      <audit-icon
        :class="{
          'rotate-loading': data.runningList.length>0
        }"
        style="color: #3a84ff;"
        svg
        type="loading" />
      {{ t('执行中') }} ({{ data.runningList.length }})
    </div>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import type CollectorTaskStatusModel from '@model/collector/task-status';

  defineProps<Props>();

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  interface Props {
    modelValue: string,
    data: CollectorTaskStatusModel
  }
  interface Emits {
    (e: 'update:modelValue', value: string): void
  }
  const handleStatusChange = (status: string) => {
    emits('update:modelValue', status);
  };
</script>
