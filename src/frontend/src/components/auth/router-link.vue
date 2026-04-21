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
  <router-link
    v-if="isShowRaw"
    v-bind="(attrs as unknown as any)">
    <slot />
  </router-link>
  <span
    v-else
    :id="(attrs.id as string)"
    v-cursor
    class="auth-router-link-disabled"
    :class="attrs.class"
    :loading="loading"
    :style="(attrs.style as StyleValue)"
    @click.stop="handleRequestPermission">
    <slot />
  </span>
</template>
<script lang="ts">
  export default {
    inheritAttrs: false,
  };
</script>
<script setup lang="ts">
  import {
    type StyleValue,
    toRef,
    useAttrs,
  } from 'vue';

  import useBase from './use-base';

  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  /* eslint-disable vue/no-unused-properties */
  interface Props {
    permission?: boolean | string,
    actionId: string,
    resource?: string | number,
    resourceIsScene?: boolean,

  }

  const props = withDefaults(defineProps<Props>(), {
    permission: 'normal',
    resource: '',
  });

  const attrs = useAttrs();
  const {
    loading,
    isShowRaw,
    handleRequestPermission,
  } = useBase({
    actionId: props.actionId,
    resource: props.resourceIsScene ? getSceneSystemParams().scope_id : props.resource,
    permission: toRef(props, 'permission'),
  });
</script>
<style lang="postcss" scoped>
  .auth-router-link-disabled {
    color: #c4c6cc !important;
    user-select: none !important;
  }
</style>
