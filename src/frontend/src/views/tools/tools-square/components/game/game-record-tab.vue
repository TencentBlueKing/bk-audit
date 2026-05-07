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
  <div class="game-record-tab">
    <!-- ECharts 图表区域 -->
    <template v-if="chartRows.length > 0">
      <div
        v-for="(row, rowIndex) in chartRows"
        :key="rowIndex"
        class="charts-section">
        <record-pie-chart
          v-for="(chart, chartIndex) in row"
          :key="chartIndex"
          :center-label="chart.centerLabel"
          :data="chart.data"
          :title="chart.title"
          :total="chart.total" />
      </div>
    </template>

    <!-- 表格明细区域 -->
    <record-detail-table
      :columns="tableColumns"
      :data="tableData"
      :pagination="tablePagination"
      :search-fields="searchFields"
      :search-placeholder="searchPlaceholder"
      :show-date-picker="showDatePicker"
      :title="tableTitle"
      @date-change="handleDateChange"
      @page-change="handlePageChange"
      @page-limit-change="handlePageLimitChange"
      @search="handleSearch"
      @search-condition-change="handleSearchConditionChange">
      <!-- 透传额外筛选插槽 -->
      <template
        v-if="$slots['extra-filter']"
        #extra-filter>
        <slot name="extra-filter" />
      </template>
    </record-detail-table>
  </div>
</template>

<script setup lang="ts">
  import type { SearchFieldItem } from './game-search-fields';
  import RecordDetailTable from './record-detail-table.vue';
  import RecordPieChart from './record-pie-chart.vue';

  interface ChartConfig {
    title: string;                                    // 图表标题
    data: Array<{ name: string; value: number }>;     // 饼图数据
    total: number;                                    // 总数
    centerLabel: string;                              // 中心文字
  }

  interface Props {
    chartRows?: ChartConfig[][];                      // 图表行配置，每个子数组代表一行
    tableTitle: string;                               // 表格标题
    tableColumns: Array<Record<string, any>>;         // 表格列配置
    tableData: Array<Record<string, any>>;            // 表格数据
    tablePagination: {                                // 分页配置
      count: number;
      current: number;
      limit: number;
    };
    searchPlaceholder: string;                        // 搜索框 placeholder
    showDatePicker?: boolean;                         // 是否显示日期选择器
    searchFields?: SearchFieldItem[];                 // 搜索字段配置
  }

  withDefaults(defineProps<Props>(), {
    chartRows: () => [],
    showDatePicker: true,
    searchFields: () => [],
  });

  const emit = defineEmits<{
    'page-change': [page: number];
    'page-limit-change': [limit: number];
    'search': [keyword: string];
    'date-change': [range: [string, string]];
    'search-condition-change': [conditions: any[]];
  }>();

  const handlePageChange = (page: number) => {
    emit('page-change', page);
  };

  const handlePageLimitChange = (limit: number) => {
    emit('page-limit-change', limit);
  };

  const handleSearch = (keyword: string) => {
    emit('search', keyword);
  };

  const handleDateChange = (range: [string, string]) => {
    emit('date-change', range);
  };

  const handleSearchConditionChange = (conditions: any[]) => {
    emit('search-condition-change', conditions);
  };
</script>

<style scoped lang="postcss">
.game-record-tab {
  padding-top: 16px;
}

.charts-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 0;
  margin-bottom: 16px;
  overflow: hidden;
  background: #fff;
  border-radius: 2px;

  :deep(.record-pie-chart) {
    min-width: 0;
    padding: 16px 20px;
    background: transparent;
    border-right: 1px solid #f0f1f5;
    border-radius: 0;
  }

  :deep(.record-pie-chart:last-child) {
    border-right: none;
  }
}

@media (width <= 1200px) {
  .charts-section {
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));

    :deep(.record-pie-chart) {
      padding: 16px;
    }
  }
}

@media (width <= 768px) {
  .charts-section {
    grid-template-columns: 1fr;

    :deep(.record-pie-chart) {
      border-right: none;
      border-bottom: 1px solid #f0f1f5;
    }

    :deep(.record-pie-chart:last-child) {
      border-bottom: none;
    }
  }
}
</style>
