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
  <bk-switcher
    v-if="isShowRaw"
    v-bind="attrs" />
  <span
    v-else
    disabled>
    <bk-switcher
      v-cursor
      class="auth-switch-disable"
      v-bind="inheritAttrs"
      :disabled="false"
      :loading="loading"
      @click.stop="handleRequestPermission" />
  </span>
</template>
<script lang="ts">
  export default {
    inheritAttrs: false,
  };
</script>
<script setup lang="ts">
  import {
    useAttrs,
  } from 'vue';

  import { attrsWithoutListener } from '@utils/assist';

  import useBase from './use-base';

  /* eslint-disable vue/no-unused-properties */
  interface Props {
    permission?: boolean | string,
    actionId: string,
    resource?: string | number,
  }

  const props = withDefaults(defineProps<Props>(), {
    permission: 'normal',
    resource: '',
  });

  const attrs = useAttrs();

  const inheritAttrs = attrsWithoutListener(attrs);

  const {
    loading,
    isShowRaw,
    handleRequestPermission,
  } = useBase(props);

</script>
<style lang="postcss" scoped>
  .auth-switch-disable {
    color: #fff !important;
    background-color: #dcdee5 !important;
    border-color: #dcdee5 !important;
    user-select: none !important;

    &.is-text {
      color: #c4c6cc !important;
      background-color: transparent !important;
      border-color: transparent !important;
    }
  }
</style>
