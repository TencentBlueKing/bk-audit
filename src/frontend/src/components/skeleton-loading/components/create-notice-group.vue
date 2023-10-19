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
  <div>
    <content-loader
      :height="716"
      :width="maxWidth"
      v-bind="attrs">
      <!-- eslint-disable vue/max-attributes-per-line -->
      <rect height="32" rx="2" width="100" x="24" y="21" />
      <rect height="32" rx="2" width="480" x="134" y="21" />
      <rect height="32" rx="2" width="100" x="24" y="71" />
      <rect height="32" rx="2" width="800" x="134" y="71" />
      <rect height="32" rx="2" width="800" x="134" y="121" />
      <rect height="32" rx="2" width="100" x="24" y="171" />
      <rect height="100" rx="2" width="800" x="134" y="171" />
      <rect height="32" rx="2" width="100" x="24" y="291" />
      <rect height="70" rx="2" width="800" x="134" y="291" />
      <rect height="32" rx="2" width="88" x="134" y="381" />
      <rect height="32" rx="2" width="54" x="234" y="381" />
    </content-loader>
  </div>
</template>
<script lang="ts">
  export default {
    inheritAttrs: true,
  };
</script>
<script setup lang="ts">
  import { useAttrs } from 'vue';
  import { ContentLoader } from 'vue-content-loader';

  import { attrsOnlyProp } from '@utils/assist';

  interface Props {
    maxWidth: number;
  }
  defineProps<Props>();

  const attrs = attrsOnlyProp(useAttrs());
</script>
