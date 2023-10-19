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
  <div style="padding: 20px 0;">
    <content-loader
      :height="716"
      :width="maxWidth"
      v-bind="attrs">
      <!-- eslint-disable vue/max-attributes-per-line -->
      <rect height="48" rx="5" width="48" x="0" y="0" />
      <rect height="16" rx="1" width="120" x="60" y="6" />
      <rect height="14" rx="1" width="258" x="60" y="32" />
      <rect height="14" rx="1" width="56" x="24" y="155" />
      <rect height="14" rx="1" width="56" x="520" y="155" />
      <rect height="14" rx="1" width="56" x="24" y="302" />
      <rect height="14" rx="1" width="56" x="400" y="302" />
      <rect height="56" rx="2" width="432" x="24" y="188" />
      <rect height="56" rx="2" width="432" x="24" y="335" />
      <rect height="56" rx="2" width="432" x="24" y="399" />
      <rect height="56" rx="2" width="432" x="24" y="463" />
      <rect height="14" rx="1" width="36" x="86" y="155" />
      <rect height="14" rx="1" width="36" x="86" y="302" />
      <rect height="14" rx="1" width="56" x="114" y="78" />
      <rect height="14" rx="1" width="123" x="380" y="32" />
      <rect height="14" rx="1" width="246" x="519" y="32" />
      <rect height="14" rx="1" width="456" x="781" y="32" />
      <rect height="14" rx="1" width="46" x="380" y="8" />
      <rect height="14" rx="1" width="46" x="519" y="8" />
      <rect height="14" rx="1" width="46" x="781" y="8" />
      <rect height="40" rx="2" width="714" x="520" y="188" />
      <rect height="40" rx="2" width="714" x="520" y="260" />
      <rect height="40" rx="2" width="714" x="520" y="332" />
      <rect height="40" rx="2" width="714" x="520" y="404" />
      <rect height="40" rx="2" width="714" x="520" y="476" />
    </content-loader>
  </div>
</template>
<script setup lang="ts">
  import { useAttrs } from 'vue';
  import { ContentLoader } from 'vue-content-loader';

  import { attrsOnlyProp } from '@utils/assist';

  interface Props {
    maxWidth?: number;
  }
  defineProps<Props>();

  const attrs = attrsOnlyProp(useAttrs());
</script>

