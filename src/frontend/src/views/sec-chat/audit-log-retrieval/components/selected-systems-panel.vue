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
  <div class="selected-systems-panel">
    <div
      class="systems-header"
      @click="expanded = !expanded">
      <div class="systems-title">
        <img
          alt=""
          class="title-icon"
          :src="wenhaoIcon">
        <span>{{ title }}</span>
      </div>
      <div class="systems-header-right">
        <button
          v-if="actionText && actionPlacement === 'header'"
          class="reselect-link is-header"
          type="button"
          @click.stop="$emit('action')">
          <audit-icon
            class="reselect-icon"
            type="refresh" />
          <span>{{ actionText }}</span>
        </button>
        <audit-icon
          class="expand-icon"
          :class="{ 'is-collapsed': !expanded }"
          type="angle-line-down" />
      </div>
    </div>

    <template v-if="expanded">
      <div class="system-tags">
        <span
          v-for="item in systems"
          :key="item.id"
          class="system-tag">
          {{ item.name }}({{ item.id }})
        </span>
      </div>
      <button
        v-if="actionText && actionPlacement === 'footer'"
        class="reselect-link"
        type="button"
        @click.stop="$emit('action')">
        <audit-icon
          class="reselect-icon"
          type="refresh" />
        <span>{{ actionText }}</span>
      </button>
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';

  import type { SelectedSystem } from '../../types';

  import wenhaoIcon from '@images/wenhao.svg';

  const props = withDefaults(defineProps<{
    systems: SelectedSystem[];
    title: string;
    defaultExpanded?: boolean;
    actionText?: string;
    actionPlacement?: 'header' | 'footer';
  }>(), {
    defaultExpanded: true,
    actionText: '',
    actionPlacement: 'footer',
  });

  defineEmits<{
    action: [];
  }>();

  const expanded = ref(props.defaultExpanded);
</script>

<style lang="postcss" scoped>
  .selected-systems-panel {
    min-width: 0;
  }

  .systems-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    cursor: pointer;
    user-select: none;
  }

  .systems-title {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 500;
    line-height: 22px;
    color: #313238;

    .title-icon {
      display: block;
      width: 18px;
      height: 18px;
      flex-shrink: 0;
    }
  }

  .systems-header-right {
    display: inline-flex;
    flex-shrink: 0;
    align-items: center;
    gap: 8px;
  }

  .expand-icon {
    font-size: 14px;
    color: #979ba5;
    transition: transform .2s;

    &.is-collapsed {
      transform: rotate(-90deg);
    }
  }

  .system-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
    padding: 12px;
    background: #f0f5ff;
    border-radius: 4px;
  }

  .system-tag {
    display: inline-flex;
    max-width: 100%;
    height: 22px;
    padding: 0 8px;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-sizing: border-box;
  }

  .reselect-link {
    display: inline-flex;
    margin-top: 12px;
    padding: 0;
    font-size: 14px;
    line-height: 22px;
    color: #3a84ff;
    cursor: pointer;
    background: transparent;
    border: none;
    align-items: center;
    gap: 4px;

    &:hover {
      opacity: .85;
    }

    &.is-header {
      margin-top: 0;
    }

    .reselect-icon {
      font-size: 14px;
    }
  }
</style>
