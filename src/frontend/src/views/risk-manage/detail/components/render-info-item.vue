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
    <div
      class="info-label"
      :style="labelStyle">
      <span
        v-bk-tooltips="{
          disabled: !description,
          content: description
        }"
        :class="[description ? 'tips' : '']">
        {{ label }}
      </span>
    </div>
    <span class="info-colon">
      :
    </span>
    <div class="info-value">
      <slot />
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
  } from 'vue';

  interface Props{
    label: string,
    labelWidth?: number,
    labelWidthPercent?: number,
    description?: string,
  }

  const props = defineProps<Props>();
  const labelStyle = computed(() => {
    const fixedWidth = props.labelWidth || 80;
    if (props.labelWidthPercent) {
      const percentWidth = `${props.labelWidthPercent}%`;
      return {
        width: percentWidth,
        minWidth: `${fixedWidth}px`,
        maxWidth: percentWidth,
        flex: `0 0 ${percentWidth}`,
      };
    }
    return {
      width: `${fixedWidth}px`,
      minWidth: `${fixedWidth}px`,
      maxWidth: `${fixedWidth}px`,
      flex: `0 0 ${fixedWidth}px`,
    };
  });
</script>
<style lang="postcss" scoped>
.render-info-item {
  display: flex;
  font-size: 12px;
  align-items: center;

  .info-label {
    min-width: 60px;
    color: #63656e;
    text-align: right;
    flex: 0 0 60px;
    word-break: break-all;
    word-wrap: break-word;
  }

  .info-colon {
    flex-shrink: 0;
    color: #63656e;
  }

  .info-value {
    min-width: 0;
    padding-left: 14px;
    color: #313238;
    flex: 1;
    word-break: break-all;
    word-wrap: break-word;
  }
}
</style>
<style lang="postcss">
.info-field-rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.info-field-row {
  display: flex;
  flex-flow: row nowrap;
  gap: 24px;
  align-items: flex-start;
  width: 100%;
}

.info-field-row .render-info-item {
  width: calc(50% - 12px);
  max-width: calc(50% - 12px);
  min-width: 0;
  box-sizing: border-box;
  flex: 0 0 calc(50% - 12px);
  align-items: flex-start;
}

.info-field-row.is-full-row .render-info-item {
  flex: 0 0 100%;
  width: 100%;
  max-width: 100%;
}

.fields-section-divider {
  height: 1px;
  margin: 4px 0;
  background: #dcdee5;
}
</style>
