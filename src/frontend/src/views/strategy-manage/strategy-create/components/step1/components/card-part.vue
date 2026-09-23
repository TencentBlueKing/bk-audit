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
  <div class="strategy-create-card-part">
    <div
      class="card-part-title"
      @click="handleChangeCollapse">
      <slot name="title">
        <span class="card-part-title-default">
          <audit-icon
            v-if="showIcon"
            class="card-part-collapse-icon"
            :class="{ 'is-collapsed': isCollapse }"
            type="angle-line-down" />
          <span class="card-part-title-text">
            {{ title }}
          </span>
        </span>
      </slot>
    </div>

    <div
      v-show="showContent && !isCollapse"
      class="card-part-content">
      <slot name="content" />
    </div>
  </div>
</template>

<script setup lang='ts'>
  import {
    ref,
  } from 'vue';

  interface Props{
    title?: string,
    showContent?:boolean,
    showIcon?:boolean,
  }
  withDefaults(defineProps<Props>(), {
    showContent: true,
    showIcon: true,
    title: '',
  });

  const isCollapse = ref(false);

  const handleChangeCollapse = () => {
    isCollapse.value = !isCollapse.value;
  };
</script>

<style scoped lang="postcss">
.strategy-create-card-part {
  margin-bottom: var(--audit-space-16);
  background: var(--audit-neutral-bg-04);
  border-radius: var(--audit-radius-container);
  box-shadow: var(--audit-shadow-card);

  >.card-part-title {
    display: flex;
    height: auto;
    padding: 12px var(--audit-space-24) var(--audit-space-16);
    font-size: var(--audit-font-size-base);
    font-weight: var(--audit-font-weight-bold);
    line-height: var(--audit-line-height-base);
    color: var(--audit-neutral-text-01);
    cursor: pointer;
    align-items: center;

    .card-part-title-default {
      display: flex;
      align-items: center;
    }

    .card-part-collapse-icon {
      display: inline-block;
      margin-right: var(--audit-space-8);
      font-size: var(--audit-font-size-base);
      color: var(--audit-neutral-text-02);
      transition: transform .2s ease;

      &.is-collapsed {
        transform: rotate(-90deg);
      }
    }

    .card-part-title-text {
      display: inline-flex;
      align-items: center;
    }
  }

  >.card-part-content {
    padding: var(--audit-space-16) var(--audit-space-24) var(--audit-space-24);
    overflow: visible;
    border-top: 1px solid var(--audit-neutral-border-02);
  }
}
</style>
