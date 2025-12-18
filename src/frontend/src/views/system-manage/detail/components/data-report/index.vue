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
  <div class="data-report-box">
    <div class="box-layout-left">
      <api-push
        v-if="showApiPush.enabled"
        ref="apiRef"
        class="mb12"
        @change-checked="handleApiChecked"
        @get-data-enabled="handleGetDataEnabled" />
      <log-collection
        ref="listRef"
        @change-checked="handleChecked" />
    </div>
    <recent-data
      class="box-layout-right ml16"
      :data="collectorData" />
  </div>
</template>
<script setup lang="ts">
  import {
    ref,
  } from 'vue';

  import useFeature from '@hooks/use-feature';

  import ApiPush from './components/api-push.vue';
  import LogCollection from './components/log-collection/index.vue';
  import RecentData from './components/recent-data.vue';

  interface CollectorData {
    id: number|string;
    name: string;
  }
  interface Emits {
    (e: 'dataEnabled', value: boolean): void
  }
  const emit = defineEmits<Emits>();

  const listRef = ref();
  const apiRef = ref();
  const apiRefDataEnabled = ref(false);

  const collectorData = ref < CollectorData >({ id: 0, name: '' });

  const { feature: showApiPush } = useFeature('bklog_otlp');

  const handleChecked = (value: {id: number|string, name: string}) => {
    collectorData.value = value;
    apiRef.value.handleCancelCheck();
  };
  const handleApiChecked = (value: {id: number|string, name: string}) => {
    collectorData.value = value;
    listRef.value.handleCancelCheck();
  };
  const handleGetDataEnabled  = (val: boolean) => {
    apiRefDataEnabled.value = val;
    emit('dataEnabled', val);
  };

</script>
<style lang="postcss">
  .data-report-box {
    display: flex;
    margin-top: 24px;
    overflow: hidden;

    .mt12 {
      margin-top: 12px;
    }

    .box-layout-left {
      flex: 0 0 480px;
      width: 480px;
    }

    .box-layout-right {
      flex: 1;
    }
  }
</style>
