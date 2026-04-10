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
        :popover-width="320"
        :width="240"
        @change="handleSceneChange" />
    </div>
    <skeleton-loading
      fullscreen
      :loading="isLoading"
      name="analysisList"
      style="width: 98%; margin-top: 20px;margin-left: 1%;">
      <div>
        <div class="search-box">
          <search-box
            ref="searchBoxRef"
            @change="handleSearchChange" />
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
          v-if="false"
          style="height: 52px; margin-top: 24px;">
          <search-page-footer />
        </div>
      </div>
    </skeleton-loading>
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
  const selectedScene = ref<SceneItem | null>({
    id: '100001',
    name: '主机安全审计',
    type: 'scene',
  });

  const searchModel = ref<Record<string, any>>({});
  const searchResultCom = computed(() => comMap[renderType.value]);
  const isLoading = computed(() => (resultRef.value ? resultRef.value.loading : true));
  const tableSearchModel = computed(() => (resultRef.value ? resultRef.value.tableSearchModel : {}));

  const total = ref<number>(0);
  provide('total', total);
  provide('tableSearchModel', tableSearchModel);

  // 场景切换
  const handleSceneChange = (value: SceneItem | null) => {
    console.log('场景切换:', value);
    // TODO: 根据选择的场景/系统重新加载数据
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

  watch(() => isDoris.value, (data) => {
    if (data.enabled) {
      dataSource.value = EsQueryService.fetchCollectorSearchList;
    }
    isInit.value = true;
  });
</script>
<style lang="postcss">
.analysis-manage-page {
  min-height: 100vh;
  background-color: #f5f7fa;

  .page-header {
    display: flex;
    align-items: center;
    height: 52px;
    padding: 0 24px;
    background-color: #fff;
    box-shadow: 0 2px 4px 0 rgb(0 0 0 / 5%);

    .header-title {
      margin-right: 16px;
      font-size: 16px;
      font-weight: 700;
      color: #313238;
    }
  }

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
