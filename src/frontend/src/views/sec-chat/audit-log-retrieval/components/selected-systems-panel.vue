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
    <div class="systems-header">
      <div class="systems-title">
        <span class="title-text">
          <span class="title-label">{{ title }}</span>
          <template v-if="selectedSystemLabel">
            <span>：</span>
            <span
              class="system-name"
              :title="selectedSystemLabel">{{ selectedSystemLabel }}</span>
          </template>
        </span>
      </div>
      <button
        v-if="actionText"
        class="reselect-link"
        :disabled="actionDisabled"
        type="button"
        @click.stop="$emit('action')">
        <audit-icon
          class="reselect-icon"
          type="refresh" />
        <span>{{ actionText }}</span>
      </button>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue';

  import type { SelectedSystem } from '../../types';

  const props = withDefaults(defineProps<{
    systems: SelectedSystem[];
    title?: string;
    actionText?: string;
    actionDisabled?: boolean;
  }>(), {
    title: '已选系统',
    actionText: '',
    actionDisabled: false,
  });

  defineEmits<{
    action: [];
  }>();

  const selectedSystemLabel = computed(() => {
    const system = props.systems[0];
    if (!system) return '';
    const { name, id } = system;
    if (name && id && name !== id) return `${name}(${id})`;
    return name || id || '';
  });
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
  }

  .systems-title {
    display: flex;
    min-width: 0;
    align-items: center;
    font-size: 14px;
    font-weight: 500;
    line-height: 22px;
    color: #313238;
  }

  .title-text {
    display: flex;
    min-width: 0;
    align-items: center;
  }

  .title-label {
    flex-shrink: 0;
  }

  .system-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .reselect-link {
    display: inline-flex;
    flex-shrink: 0;
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

    &:disabled {
      color: #c4c6cc;
      cursor: not-allowed;
      opacity: 1;
    }

    .reselect-icon {
      font-size: 14px;
    }
  }
</style>
