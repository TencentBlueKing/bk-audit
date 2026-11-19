<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div class="system-detail-skeleton">
    <div class="system-detail-skeleton__header">
      <audit-skeleton
        :height="48"
        :width="48" />
      <div class="system-detail-skeleton__meta">
        <audit-skeleton
          :height="16"
          :width="160" />
        <audit-skeleton
          :height="14"
          :width="240" />
      </div>
    </div>
    <div class="system-detail-skeleton__tabs">
      <audit-skeleton
        v-for="index in 4"
        :key="index"
        custom-class="system-detail-skeleton__tab"
        :height="32"
        :width="96" />
    </div>
    <div class="system-detail-skeleton__panel">
      <audit-skeleton
        :height="16"
        :width="72" />
      <div class="system-detail-skeleton__grid">
        <div
          v-for="index in 4"
          :key="index"
          class="system-detail-skeleton__field">
          <audit-skeleton
            :height="14"
            :width="56" />
          <audit-skeleton
            :height="14"
            :width="120" />
        </div>
      </div>
      <div class="system-detail-skeleton__field">
        <audit-skeleton
          :height="14"
          :width="40" />
        <audit-skeleton
          height="14"
          width="46%" />
      </div>
      <audit-skeleton
        class="system-detail-skeleton__section"
        :height="16"
        :width="72" />
      <div
        v-for="field in callFields"
        :key="field.label"
        class="system-detail-skeleton__field">
        <audit-skeleton
          :height="14"
          :width="field.label" />
        <audit-skeleton
          :height="14"
          :width="field.value" />
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  export default {
    inheritAttrs: false,
  };
</script>
<script setup lang="ts">
  const callFields = [
    { label: 84, value: 220 },
    { label: 108, value: 360 },
    { label: 72, value: 96 },
  ];
</script>
<style lang="postcss">
  .system-detail-skeleton {
    min-height: 100%;
    padding: var(--bk-theme-space-16) var(--bk-theme-space-24) var(--bk-theme-space-24);
    background: var(--bk-theme-surface-page);
  }

  .system-detail-skeleton__header {
    display: flex;
    align-items: flex-start;
    gap: var(--bk-theme-space-12);
    padding: var(--bk-theme-card-padding);
    background: var(--bk-theme-card-bg);
    border-radius: var(--bk-theme-card-radius);
    box-shadow: var(--bk-theme-card-shadow);
  }

  .system-detail-skeleton__meta {
    display: flex;
    flex-direction: column;
    gap: var(--bk-theme-space-8);
    padding-top: var(--bk-theme-space-4);
  }

  .system-detail-skeleton__tabs {
    display: flex;
    gap: var(--bk-theme-space-16);
    margin-top: var(--bk-theme-space-16);
  }

  .system-detail-skeleton__tab {
    border-radius: var(--bk-theme-control-radius);
  }

  .system-detail-skeleton__panel {
    margin-top: var(--bk-theme-space-16);
    padding: var(--bk-theme-card-padding);
    background: var(--bk-theme-card-bg);
    border-radius: var(--bk-theme-card-radius);
    box-shadow: var(--bk-theme-card-shadow);
  }

  .system-detail-skeleton__grid {
    display: flex;
    flex-wrap: wrap;
    gap: var(--bk-theme-space-24) var(--bk-theme-space-32);
    margin-top: var(--bk-theme-space-24);
  }

  .system-detail-skeleton__field {
    display: flex;
    align-items: center;
    gap: var(--bk-theme-space-12);
    margin-top: var(--bk-theme-space-24);
  }

  .system-detail-skeleton__grid .system-detail-skeleton__field {
    margin-top: 0;
  }

  .system-detail-skeleton__section {
    margin-top: var(--bk-theme-space-32);
  }
</style>
