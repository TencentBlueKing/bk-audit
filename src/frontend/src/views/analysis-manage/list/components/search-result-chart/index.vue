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
  <div class="search-result-chart">
    <event-time-ratio />
    <div class="result-row">
      <operator-ratio class="result-col" />
      <app-operation-count class="result-col ml16" />
    </div>
    <div class="result-row">
      <operation-event-ratio class="result-col" />
      <operation-event-name class="result-col ml16" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import AppOperationCount from './components/app-operation-count/index.vue';
  import EventTimeRatio from './components/event-time-ratio/index.vue';
  import OperationEventName from './components/operation-event-name/index.vue';
  import OperationEventRatio from './components/operation-event-ratio/index.vue';
  import OperatorRatio from './components/operator-ratio/index.vue';
</script>
<style lang="postcss">
  .search-result-chart {
    margin-top: 4px;

    .result-row {
      display: flex;
      margin-top: 16px;
    }

    .result-col {
      flex: 1;
    }
  }
</style>
