<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <keep-alive>
    <component
      :is="component"
      v-if="shouldKeepAlive"
      :key="renderKey" />
  </keep-alive>
  <component
    :is="component"
    v-if="!shouldKeepAlive"
    :key="renderKey" />
</template>

<script setup lang="ts">
  import {
    computed,
    inject,
    type Component,
    unref,
  } from 'vue';
  import { matchedRouteKey } from 'vue-router';

  interface Props {
    component: Component;
    routeName: string;
  }

  const props = defineProps<Props>();

  // RouterView 提供的「当前深度」匹配记录（非合并后的 route.meta）
  const matchedRoute = inject(matchedRouteKey, null);

  const shouldKeepAlive = computed(() => Boolean(unref(matchedRoute)?.meta?.keepAlive));

  // 按「当前这一层」的路由记录取 key：父级布局（如 notice-group）在子路由间切换时保持同一实例，
  // 否则列表 → 详情会连带重建父级，内层 keep-alive 缓存的列表（含筛选条件）随之丢失
  const renderKey = computed(() => {
    const record = unref(matchedRoute);
    return String(record?.meta?.keepAliveKey || record?.name || record?.path || props.routeName);
  });
</script>
