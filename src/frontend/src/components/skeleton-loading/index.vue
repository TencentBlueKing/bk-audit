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
  <div
    ref="rootRef"
    class="audit-skeleton-loading">
    <component
      :is="renderCom"
      v-if="realLoading && maxWidth"
      class="skeleton-loading-mask"
      :class="{
        fullscreen
      }"
      :max-width="maxWidth"
      primary-color="#EBECF3"
      secondary-color="#F6F7FB"
      :speed="2" />
    <div :class="{ 'skeleton-loading-hidden': realLoading }">
      <slot />
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    onMounted,
    ref,
    watch,
  } from 'vue';

  import AnalysisList from './components/analysis-list.vue';
  import ChartTableList from './components/chart-table-list.vue';
  import CreateCollectorStep2 from './components/create-collector-step2.vue';
  import CreateNoticeGroup from './components/create-notice-group.vue';
  import CreateStrategy from './components/create-strategy.vue';
  import CreateTools from './components/create-tools.vue';
  import EventList from './components/event-list.vue';
  import NoticeGroup from './components/notice-group.vue';
  import StorageList from './components/storage-list.vue';
  import StrategyList from './components/strategy-list.vue';
  import SystemDetail from './components/system-detail.vue';
  import SystemDetailApiPush from './components/system-detail-api-push.vue';
  import SystemDetailList from './components/system-detail-list.vue';
  import SystemDetailLogCollector from './components/system-detail-log-collector.vue';
  import SystemDetailRecentData from './components/system-detail-recent-data.vue';
  import SystemList from './components/system-list.vue';

  interface Props {
    name: string;
    loading: boolean;
    once?: boolean;
    fullscreen?:boolean
  }

  const props = withDefaults(defineProps<Props>(), {
    loading: true,
    once: true,
    fullscreen: false,
  });

  const comMap = {
    analysisList: AnalysisList,
    createCollectorStep2: CreateCollectorStep2,
    storageList: StorageList,
    systemList: SystemList,
    systemDetail: SystemDetail,
    systemDetailList: SystemDetailList,
    systemDetailLogCollector: SystemDetailLogCollector,
    systemDetailRecentData: SystemDetailRecentData,
    strategyList: StrategyList,
    noticeGroup: NoticeGroup,
    createNoticeGroup: CreateNoticeGroup,
    eventList: EventList,
    createStrategy: CreateStrategy,
    chartTableList: ChartTableList,
    systemDetailApiPush: SystemDetailApiPush,
    createTools: CreateTools,
  };

  const rootRef = ref();
  const maxWidth = ref(0);
  const realLoading = ref(true);

  const renderCom = comMap[props.name as keyof typeof comMap];

  const unwatch = watch(() => props.loading, (loading: boolean) => {
    if (loading) {
      realLoading.value = loading;
      return;
    }
    setTimeout(() => {
      realLoading.value = loading;
      if (!loading && props.once) {
        unwatch();
      }
    }, 1000);
  }, {
    immediate: true,
  });

  onMounted(() => {
    const { width } = rootRef.value.getBoundingClientRect();
    maxWidth.value = width;
  });
</script>
<style lang="postcss">
  .audit-skeleton-loading {
    position: relative;

    .skeleton-loading-mask {
      position: absolute;
      inset: 0;
      z-index: 1;
      width: 100%;
      overflow: hidden;
      background: #f5f7fa;
      opacity: 100%;
      visibility: visible;

      &.fullscreen {
        min-height: calc(100vh - 92px);
      }
    }

    .skeleton-loading-hidden {
      opacity: 0%;
      visibility: hidden;
    }
  }
</style>
