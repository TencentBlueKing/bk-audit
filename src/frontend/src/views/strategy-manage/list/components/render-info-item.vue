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
    <span class="info-label">{{ label }}: </span>
    <span
      v-bk-tooltips="{
        content,
        disabled: hasToolTips,
        extCls: 'info-label-tooltips',
      }"
      class="info-value"
      @mouseenter="enter">
      <slot />
    </span>
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';

  defineProps({
    label: {
      type: String,
      default: () => '',
    },
  });

  let hasToolTips = false;
  const content = ref('');

  const enter = (e: MouseEvent) => {
    const { target } = e;
    const { offsetWidth, scrollWidth } = target as HTMLElement;
    hasToolTips = offsetWidth >= scrollWidth;
    content.value = (e.target as HTMLElement).innerText;
  };
</script>
<style lang="postcss" scoped>
  .render-info-item {
    display: flex;

    .info-label {
      min-width: 80px;
      color: #979ba5;
      text-align: right;
      flex: 0 0 80px;
    }

    .info-value {
      padding-left: 14px;
      overflow: hidden;
      color: #63656e;
      text-overflow: ellipsis;
      flex: 1;
    }
  }
</style>
<style>
  .info-label-tooltips {
    max-width: 816px;
    word-break: break-all;
  }
</style>
