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
  <div class="analysis-manage-page">
    <div class="page-header">
      <span class="header-title">{{ t('检索') }}</span>
      <scene-system-selector
        v-model="selectedScene"
        :popover-width="400"
        scene-permission="view_scene"
        system-permission="view_system"
        width="208px"
        @change="handleSceneChange" />
    </div>
    <div class="analysis-page-content">
      <div class="search-box">
        <search-box
          ref="searchBoxRef"
          :loading="isLoading"
          @change="handleSearchChange"
          @change-table-height="handleTableHeightChange" />
        <div class="search-result-action">
          <render-type-tab
            v-if="false"
            v-model="renderType" />
        </div>
      </div>
      <component
        :is="searchResultCom"
        v-if="isInit"
        ref="resultRef"
        :data-source="dataSource"
        :filter="searchModel"
        :is-doris="isDoris"
        @clear-search="handleClearSearch"
        @update-total="handleUpdateTotal" />
      <div
        v-else
        class="search-result-list bk-theme-card">
        <table-skeleton :row-count="8" />
      </div>
      <div
        v-if="false"
        style="height: 52px; margin-top: 24px;">
        <search-page-footer />
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    provide,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EsQueryService from '@service/es-query';

  import SceneSystemSelector from '@components/scene-system-selector/index.vue';
  import TableSkeleton from '@components/table-skeleton/index.vue';

  import RenderTypeTab from './components/render-type-tab.vue';
  import SearchBox from './components/search-box/index.vue';
  import SearchPageFooter from './components/search-page-footer.vue';
  import SearchResultChart from './components/search-result-chart/index.vue';
  import SearchResultTable from './components/search-result-table/index.vue';

  import useFeature from '@/hooks/use-feature';
  import type { IRequestResponsePaginationData } from '@/utils/request';

  interface SceneItem {
    id: string;
    name: string;
    type: 'aggregate' | 'scene' | 'system';
  }

  const { t } = useI18n();
  const { feature: isDoris } = useFeature('enable_doris');
  const comMap = {
    table: SearchResultTable,
    chart: SearchResultChart,
  };
  const renderType = ref<'chart'|'table'>('table');
  const searchBoxRef = ref();
  const resultRef = ref();
  const dataSource = ref<(params: any)=> Promise<IRequestResponsePaginationData<any>>>(EsQueryService.fetchSearchList);
  const isInit = ref(false);

  // 场景选择器
  const selectedScene = ref<SceneItem | null>();

  const searchModel = ref<Record<string, any>>({});
  const searchResultCom = computed(() => comMap[renderType.value]);
  const isLoading = computed(() => (resultRef.value ? resultRef.value.loading : true));
  const tableSearchModel = computed(() => (resultRef.value ? resultRef.value.tableSearchModel : {}));

  const total = ref<number>(0);
  provide('total', total);
  provide('tableSearchModel', tableSearchModel);

  // 场景选择器初始化时会触发一次 change，不应清空 URL 带入的搜索条件
  const isSceneInitialized = ref(false);

  // 场景切换
  const handleSceneChange = () => {
    resultRef.value?.handleUpdateField();
    if (!isSceneInitialized.value) {
      isSceneInitialized.value = true;
      return;
    }
    // 清空搜索
    searchBoxRef.value.clearValue();
  };

  // 搜索
  const handleSearchChange = (value: Record<string, any>) => {
    searchModel.value = value;
  };
  // 清空搜索
  const handleClearSearch = () => {
    searchBoxRef.value.clearValue();
  };
  // 获取表格数据
  const handleUpdateTotal = (totalNumber: unknown) => {
    if (typeof totalNumber === 'number') {
      total.value = totalNumber;
    }
  };

  // 搜索区高度变化时重新计算表格高度
  const handleTableHeightChange = () => {
    resultRef.value?.calcTableHeight?.();
  };

  watch(() => isDoris.value, (data) => {
    if (data.enabled) {
      dataSource.value = EsQueryService.fetchCollectorSearchList;
    }
    isInit.value = true;
  });
</script>
<style lang="postcss">
.analysis-manage-page {
  position: absolute;
  inset: 0;
  width: 100vw;
  height: 100%;
  overflow-y: auto;
  background-color: var(--bk-theme-surface-muted);

  .page-header {
    display: flex;
    align-items: center;
    height: var(--bk-theme-page-title-height);
    padding: 0 var(--bk-theme-space-24);
    margin-top: var(--bk-theme-space-16);
    background: transparent;
    box-shadow: none;
    gap: var(--bk-theme-space-16);

    .header-title {
      font-size: var(--bk-theme-page-title-size);
      font-weight: var(--bk-theme-page-title-weight);
      line-height: var(--bk-theme-line-height-xl);
      color: var(--bk-theme-page-title-color);
    }

    .scene-system-selector {
      background: var(--bk-theme-surface-default);
      box-shadow: var(--bk-theme-card-shadow);
    }
  }

  .analysis-page-content {
    width: 98%;
    margin-top: var(--bk-theme-space-16);
    margin-left: 1%;
  }

  .search-result-action {
    display: flex;
    margin-top: var(--bk-theme-space-16);
  }
}
</style>
