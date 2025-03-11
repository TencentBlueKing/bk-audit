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
  <skeleton-loading
    fullscreen
    :loading="isLoading"
    name="analysisList">
    <div class="analysis-manage-page">
      <search-box
        ref="searchBoxRef"
        :is-doris="isDoris"
        @change="handleSearchChange" />
      <div class="search-result-action">
        <!-- <BkButton>导出</BkButton> -->
        <render-type-tab
          v-if="false"
          v-model="renderType" />
      </div>
      <component
        :is="searchResultCom"
        v-if="isInit"
        ref="resultRef"
        :data-source="dataSource"
        :filter="searchModel"
        :is-doris="isDoris"
        @clear-search="handleClearSearch" />
      <div style="height: 52px; margin-top: 24px;">
        <search-page-footer />
      </div>
    </div>
  </skeleton-loading>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';

  import EsQueryService from '@service/es-query';

  import RenderTypeTab from './components/render-type-tab.vue';
  import SearchBox from './components/search-box/index.vue';
  import SearchPageFooter from './components/search-page-footer.vue';
  import SearchResultChart from './components/search-result-chart/index.vue';
  import SearchResultTable from './components/search-result-table/index.vue';

  import useFeature from '@/hooks/use-feature';
  import type { IRequestResponsePaginationData } from '@/utils/request';

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

  const searchModel = ref<Record<string, any>>({});
  const searchResultCom = computed(() => comMap[renderType.value]);
  const isLoading = computed(() => (resultRef.value ? resultRef.value.loading : true));

  watch(() => isDoris.value, (data) => {
    if (data.enabled) {
      dataSource.value = EsQueryService.fetchCollectorSearchList;
    }
    isInit.value = true;
  });

  // 搜索
  const handleSearchChange = (value: Record<string, any>) => {
    searchModel.value = value;
  };
  // 清空搜索
  const handleClearSearch = () => {
    searchBoxRef.value.clearValue();
  };
</script>
<style lang="postcss">
  .analysis-manage-page {
    /* 解决表格悬停超出 */
    .bk-table-fixed .column_fixed {
      bottom: 80px !important;
    }

    .search-result-action {
      display: flex;
      margin-top: 16px;
    }
  }
</style>
