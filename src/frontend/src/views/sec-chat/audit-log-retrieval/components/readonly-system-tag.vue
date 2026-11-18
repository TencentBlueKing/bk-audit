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
  <div
    v-if="displayValue"
    v-bk-tooltips="{
      content: SYSTEM_TIP,
      placement: 'top',
    }"
    class="condition-tag-item is-readonly-system">
    <span class="tag-label">来源系统：</span>
    <span class="tag-value-wrapper">
      <span class="tag-value">{{ displayValue }}</span>
    </span>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue';

  import type { SelectedSystem } from '../../types';

  const props = withDefaults(defineProps<{
    systems?: SelectedSystem[];
  }>(), {
    systems: () => [],
  });

  const SYSTEM_TIP = '更换系统请点击上方「重新选择」';

  const displayValue = computed(() => {
    const system = props.systems[0];
    if (!system) return '';
    const { name, id } = system;
    if (name && id && name !== id) return `${name}(${id})`;
    return name || id || '';
  });
</script>

<style lang="postcss" scoped>
  /* 与普通条件标签同色，仅通过无关闭/不可编辑表达只读，避免置灰被误认为无效 */
  .condition-tag-item.is-readonly-system {
    cursor: default;
    user-select: none;
    padding-right: 12px;

    &:hover {
      .tag-value-wrapper {
        background: transparent;
      }
    }
  }
</style>
