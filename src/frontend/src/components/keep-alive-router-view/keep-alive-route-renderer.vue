<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <keep-alive>
    <component
      :is="component"
      v-if="shouldKeepAlive"
      :key="routeName" />
  </keep-alive>
  <component
    :is="component"
    v-if="!shouldKeepAlive"
    :key="routeName" />
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

  defineProps<Props>();

  // RouterView 提供的「当前深度」匹配记录（非合并后的 route.meta）
  const matchedRoute = inject(matchedRouteKey, null);

  const shouldKeepAlive = computed(() => Boolean(unref(matchedRoute)?.meta?.keepAlive));
</script>
