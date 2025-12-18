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
      <rect height="32" rx="2" width="246" x="24" y="21" />
      <rect height="32" rx="2" width="246" x="24" y="91" />
      <rect height="32" rx="2" width="246" x="286" y="91" />
      <rect height="32" rx="2" width="246" x="548" y="91" />
      <rect height="32" rx="2" width="246" x="286" y="21" />
      <rect height="32" rx="2" width="246" x="548" y="21" />
      <rect height="32" rx="2" width="246" x="810" y="21" />
      <rect height="12" rx="2" width="51" x="24" y="0" />
      <rect height="12" rx="2" width="51" x="24" y="70" />
      <rect height="12" rx="2" width="51" x="24" y="140" />
      <rect height="32" rx="2" width="76" x="24" y="171" />
      <rect height="32" rx="2" width="64" x="0" y="243" />
      <rect height="32" rx="2" width="217" :x="maxWidth - 217" y="243" />
      <rect height="32" rx="2" width="76" x="108" y="171" />
      <rect height="32" rx="2" width="116" x="192" y="171" />
      <rect height="12" rx="2" width="51" x="286" y="70" />
      <rect height="12" rx="2" width="51" x="548" y="70" />
      <rect height="12" rx="2" width="51" x="810" y="101" />
      <rect height="12" rx="2" width="51" x="286" y="0" />
      <rect height="12" rx="2" width="51" x="548" y="0" />
      <rect height="12" rx="2" width="51" x="810" y="0" />
      <rect height="24" rx="2" :width="maxWidth" x="24" y="324" />
      <rect height="24" rx="2" :width="maxWidth" x="24" y="366" />
      <rect height="24" rx="2" :width="maxWidth" x="24" y="408" />
      <rect height="24" rx="2" :width="maxWidth" x="24" y="450" />
      <rect height="24" rx="2" :width="maxWidth" x="24" y="492" />
    </content-loader>
  </div>
</template>
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

