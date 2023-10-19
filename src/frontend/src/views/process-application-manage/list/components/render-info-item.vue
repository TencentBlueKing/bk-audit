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
  <div class="render-info-item">
    <span
      class="info-label"
      :style="labelStyle">{{ label }}: </span>
    <span class="info-value">
      <slot />
    </span>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
  } from 'vue';

  interface Props{
    label: string,
    labelWidth?: number,
  }

  const props = defineProps<Props>();
  const labelStyle = computed(() => ({
    'min-width': `${props.labelWidth || 80}px`,
    flex: `0 0 ${props.labelWidth || 80}px`,
  }));
</script>
<style lang="postcss" scoped>
  .render-info-item {
    display: flex;

    .info-label {
      min-width: 60px;
      color: #979ba5;
      text-align: right;
      flex: 0 0 60px;
    }

    .info-value {
      padding-left: 12px;
      color: #313238;
      flex: 1;
    }
  }
</style>
