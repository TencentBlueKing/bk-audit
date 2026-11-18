<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <div
    v-if="hasDefaultSlot"
    :class="containerClass">
    <slot />
  </div>
  <div
    v-else
    :class="itemClass"
    :style="itemStyle" />
</template>
<script lang="ts">
  export type SkeletonShape = 'circle' | 'default' | 'round';
  export type SkeletonVariant = 'dark' | 'light';
</script>
<script setup lang="ts">
  import {
    computed,
    useSlots,
  } from 'vue';

  import './skeleton.css';

  interface Props {
    width?: number | string;
    height?: number | string;
    variant?: SkeletonVariant;
    shape?: SkeletonShape;
    customClass?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    width: '100%',
    height: '20px',
    variant: 'light',
    shape: 'default',
    customClass: '',
  });

  const slots = useSlots();
  const hasDefaultSlot = computed(() => Boolean(slots.default));

  const toCssSize = (value: number | string) => {
    if (typeof value === 'number') {
      return `${value}px`;
    }
    if (/^\d+(\.\d+)?$/.test(value)) {
      return `${value}px`;
    }
    return value;
  };

  const itemStyle = computed(() => ({
    width: props.width ? toCssSize(props.width) : undefined,
    height: props.height ? toCssSize(props.height) : undefined,
  }));

  const containerClass = computed(() => [
    'audit-skeleton-container',
    props.variant === 'dark' ? 'is-dark' : '',
    props.customClass,
  ]);

  const itemClass = computed(() => [
    'audit-skeleton',
    props.variant === 'dark' ? 'is-dark' : '',
    props.shape === 'circle' ? 'is-circle' : '',
    props.shape === 'round' ? 'is-round' : '',
    props.customClass,
  ]);
</script>
