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
    font-size: 14px;
    white-space: nowrap;
  }

  .audit-menu-item-group {
    .audit-menu-group-title {
      height: 40px;
      padding-left: 18px;
      font-size: 12px;
      line-height: 40px;
      color: #66748f;
    }

    &:nth-child(n+2) {
      margin-top: 16px;
    }
  }

  .audit-menu-item {
    height: 40px;
    padding-left: 22px;
    line-height: 40px;
    color: #acb9d1;
    cursor: pointer;

    &:hover {
      color: #acb9d1;
      background: #253047;
    }

    &.active {
      color: #fff;
      background: #3a84ff;

      .menu-item-icon {
        color: #fff;
      }
    }

    .audit-icon {
      margin-right: 19px;
      font-size: 16px;
      color: #b0bdd5;
    }
  }
</style>
