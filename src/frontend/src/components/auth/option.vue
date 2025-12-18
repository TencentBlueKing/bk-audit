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
  <bk-option
    v-if="isShowRaw"
    v-bind="attrs">
    <template v-if="slots.default">
      <slot />
    </template>
    <template v-else>
      {{ attrs.label }}
    </template>
  </bk-option>
  <bk-option
    v-else
    v-cursor
    class="auth-option-disabled"
    v-bind="attrs">
    <div
      class="auth-option-label"
      @click.stop="handleRequestPermission">
      <template v-if="slots.default">
        <slot />
      </template>
      <template v-else>
        {{ attrs.label }}
      </template>
    </div>
  </bk-option>
</template>
<script lang="ts">
  export default {
    inheritAttrs: false,
  };
</script>
<script setup lang="ts">
  import {
    useAttrs,
    useSlots,
  } from 'vue';

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
  const slots = useSlots();

  const {
    isShowRaw,
    handleRequestPermission,
  } = useBase(props);

</script>
<style lang="postcss" scoped>
  .auth-option-disabled {
    color: #c4c6cc !important;

    & > * {
      pointer-events: none;
    }

    .auth-option-label {
      width: 100%;
      pointer-events: all !important;
    }
  }
</style>
