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
  <div class="audit-menu">
    <slot />
  </div>
</template>
<script setup lang="ts">
  import {
    provide,
    ref,
  } from 'vue';

  import {
    menuKey,
  } from './common';

  interface Props {
    floded: boolean // eslint-disable-line vue/no-unused-properties
  }
  interface Emits {
    (e: 'change', index: string): void
  }
  const props = withDefaults(defineProps<Props>(), {
    floded: false,
  });
  const emit = defineEmits<Emits>();
  const activeIndex = ref('');

  const change = (index: string) => {
    emit('change', index);
  };


  provide(menuKey, {
    props,
    activeIndex,
    change,
  });
</script>

<style lang='postcss'>
  .audit-menu {
    font-size: var(--bk-theme-font-size-base);
    white-space: nowrap;
  }

  .audit-menu-item-group {
    .audit-menu-group-title {
      height: 40px;
      padding-left: var(--bk-theme-space-16);
      font-size: var(--bk-theme-font-size-sm);
      line-height: 40px;
      color: var(--bk-theme-nav-side-text);
    }

    &:nth-child(n+2) {
      margin-top: var(--bk-theme-space-16);
    }
  }

  .audit-menu-item {
    height: 40px;
    padding-left: var(--bk-theme-space-12);
    margin: 0 var(--bk-theme-space-12) var(--bk-theme-nav-side-item-gap);
    line-height: 40px;
    color: var(--bk-theme-nav-side-text);
    cursor: pointer;
    border-radius: var(--bk-theme-nav-side-active-radius);

    &:hover {
      color: var(--bk-theme-nav-side-text);
      background: var(--bk-theme-surface-subtle);
    }

    &.active {
      color: var(--bk-theme-nav-side-text-active);
      background: var(--bk-theme-nav-side-active-bg);

      .menu-item-icon,
      .audit-icon {
        color: var(--bk-theme-nav-side-text-active);
      }
    }

    &.active-weak {
      color: var(--bk-theme-nav-side-text);
      background: var(--bk-theme-color-brand-7);

      .menu-item-icon {
        color: var(--bk-theme-nav-side-text);
      }
    }

    .audit-icon {
      margin-right: var(--bk-theme-space-8);
      font-size: var(--bk-theme-font-size-lg);
      color: var(--bk-theme-nav-side-text);
    }
  }
</style>
