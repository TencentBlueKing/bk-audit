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
    <!-- ECharts 图表区域 - 独立 loading -->
    <div
      v-if="showChart && (chartLoading || chartRows.length > 0 || (!chartLoading && chartRows.length === 0))"
      class="chart-section-wrapper">
      <!-- 分布总览标题（可点击收起/展开） -->
      <div
        v-if="chartTitle"
        class="chart-overview-header"
        @click="isChartCollapsed = !isChartCollapsed">
        <audit-icon
          class="collapse-icon"
          :type="isChartCollapsed ? 'angle-fill-rignt' : 'angle-fill-down'" />
        <span class="chart-overview-title">{{ chartTitle }}</span>
      </div>
      <div v-show="!isChartCollapsed">
        <bk-loading
          class="chart-loading-wrapper"
          :loading="chartLoading"
          size="small">
          <div
            v-if="chartLoading"
            class="chart-loading-placeholder" />
          <template v-else>
            <!-- 图表有数据 -->
            <div
              v-if="chartRows.length > 0"
              :class="chartsContentClass">
              <div
                v-for="(row, rowIndex) in chartRows"
                :key="rowIndex"
                class="charts-section">
                <record-pie-chart
                  v-for="(chart, chartIndex) in row"
                  :key="chartIndex"
                  :active-name="chartActiveNames[chart.title] || ''"
                  :center-label="chart.centerLabel"
                  :col-count="row.length"
                  :data="chart.data"
                  :title="chart.title"
                  :tooltip-name-map="chart.tooltipNameMap"
                  :total="chart.total"
                  @legend-click="handleLegendClick" />
              </div>
            </div>
            <!-- 图表无数据 -->
            <div
              v-else
              class="chart-empty">
              <bk-exception
                scene="part"
                type="empty">
                <div class="chart-empty-text">
                  {{ t('暂无图表数据') }}
                </div>
              </bk-exception>
            </div>
          </template>
        </bk-loading>
      </div>
    </div>

    <!-- 表格明细区域 - 独立 loading，始终保留筛选框 -->
    <bk-loading
      class="table-loading-wrapper"
      :loading="tableLoading"
      size="small">
      <div
        v-show="tableLoading"
        class="table-loading-placeholder" />
      <!-- 始终渲染 record-detail-table，表格为空时由 bk-table 自身显示空状态 -->
      <record-detail-table
        v-show="!tableLoading"
        :columns="tableColumns"
        :data="tableData"
        :external-conditions="externalConditions"
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
    </bk-loading>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { ChartConfig } from './game-chart-builder';
  import type { SearchFieldItem } from './game-search-fields';
  import RecordDetailTable from './record-detail-table.vue';
  import RecordPieChart from './record-pie-chart.vue';

  interface Props {
    chartRows?: ChartConfig[][];                      // 图表行配置，每个子数组代表一行
    chartTitle?: string;                              // 图表区域总览标题（如“赠送分布总览”）
    chartColumns?: number;                            // 图表每行列数（3=固定三列，默认为响应式2/4列）
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
    chartLoading?: boolean;                           // 图表区域 loading
    tableLoading?: boolean;                           // 表格区域 loading
    showChart?: boolean;                              // 是否显示图表区域
    externalConditions?: any[];                       // 外部注入的搜索条件（用于图表联动）
    chartActiveNames?: Record<string, string>;        // 各饼图当前激活项（key=图表title，value=激活的图例名）
  }
  const props = withDefaults(defineProps<Props>(), {
    chartRows: () => [],
    chartTitle: '',
    chartColumns: 0,
    showDatePicker: true,
    searchFields: () => [],
    chartLoading: false,
    tableLoading: false,
    showChart: true,
    externalConditions: () => [],
    chartActiveNames: () => ({}),
  });

  const emit = defineEmits<{
    'page-change': [page: number];
    'page-limit-change': [limit: number];
    'search': [keyword: string];
    'date-change': [range: [string, string]];
    'search-condition-change': [conditions: any[]];
    'legend-click': [payload: { title: string; name: string; selected: boolean }];
  }>();

  // 根据 chartColumns 生成图表容器的 CSS 类名
  const chartsContentClass = computed(() => {
    if (props.chartColumns === 3) return 'charts-content charts-content--fixed-3';
    return 'charts-content';
  });

  const { t } = useI18n();

  // 图表收起状态（默认展开）
  const isChartCollapsed = ref(false);

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

  // 饼图图例点击：透传给父组件，由父组件转换成表格搜索条件
  const handleLegendClick = (payload: { title: string; name: string; selected: boolean }) => {
    emit('legend-click', payload);
  };
</script>

<style scoped lang="postcss">
.game-record-tab {
  padding-top: 5px;
}

/* 图表区域容器 */
.chart-section-wrapper {
  position: relative;
  padding: 8px 12px 12px;
  background: #fff;
  border-radius: 2px 2px 0 0;

  /* 与下方明细之间的分割线 */
  &::after {
    position: absolute;
    right: 16px;
    bottom: 0;
    left: 16px;
    height: 1px;
    background: #eaebf0;
    content: '';
  }
}

/* 分布总览标题 */
.chart-overview-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  cursor: pointer;
  user-select: none;

  .collapse-icon {
    margin-right: 6px;
    font-size: 12px;
    color: #63656e;
  }

  .chart-overview-title {
    font-size: 13px;
    font-weight: 700;
    line-height: 20px;
    color: #313238;
  }
}

/* 图表区域 loading */
.chart-loading-wrapper {
  min-height: 100px;
}

.chart-loading-placeholder {
  height: 260px;
}

/* 图表无数据 */
.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 260px;
  padding: 24px;
  background: #fff;
  border-radius: 2px;

  .chart-empty-text {
    margin-top: 4px;
    font-size: 12px;
    color: #979ba5;
  }
}

/* 表格区域 loading */
.table-loading-wrapper {
  min-height: 200px;
  background: #fff;
  border-radius: 0 0 2px 2px;
}

.table-loading-placeholder {
  height: 300px;
}

/* 默认：每行展示 2 个（赠送记录、交易记录） */
.charts-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0;
  margin-bottom: 8px;
  overflow: hidden;
  background: #fff;
  border-radius: 2px;

  &:last-child {
    margin-bottom: 0;
  }

  :deep(.record-pie-chart) {
    min-width: 0;
    padding: 8px 12px 0;
    background: transparent;
    border-right: 1px solid #dcdee5;
    border-radius: 0;
  }

  :deep(.record-pie-chart:last-child) {
    border-right: none;
  }

  /* 每行最后一个（第2个）去掉右边框 */
  :deep(.record-pie-chart:nth-child(2n)) {
    border-right: none;
  }
}

/* 固定 3 列布局（登录记录、代币发放记录） */
.charts-content--fixed-3 {
  .charts-section {
    grid-template-columns: repeat(3, 1fr);

    :deep(.record-pie-chart:nth-child(2n)) {
      border-right: 1px solid #dcdee5;
    }

    :deep(.record-pie-chart:nth-child(3n)) {
      border-right: none;
    }

    :deep(.record-pie-chart:last-child) {
      border-right: none;
    }
  }
}

/* 屏幕宽度超过 2300px 时，响应式布局一行展示 4 个（仅对非固定列数的生效） */

/* 通过 .charts-content 作为 grid 容器，.charts-section 使用 display:contents 打平子元素 */
@media (width >= 2300px) {
  .charts-content:not(.charts-content--fixed-3) {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0;
    overflow: hidden;
    background: #fff;
    border-radius: 2px;

    .charts-section {
      display: contents;

      :deep(.record-pie-chart) {
        min-width: 0;
        padding: 5px 12px 0;
        background: transparent;
        border-right: 1px solid #dcdee5;
        border-radius: 0;
      }

      :deep(.record-pie-chart:nth-child(2n)) {
        border-right: 1px solid #dcdee5;
      }

      :deep(.record-pie-chart:last-child) {
        border-right: 1px solid #dcdee5;
      }
    }

    /* 只有最后一个 section 的最后一个饼图去掉右边框 */
    .charts-section:last-child :deep(.record-pie-chart:last-child) {
      border-right: none;
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

    :deep(.record-pie-chart:nth-child(2n)) {
      border-right: none;
    }

    :deep(.record-pie-chart:last-child) {
      border-bottom: none;
    }
  }

  .charts-content--fixed-3 .charts-section {
    grid-template-columns: 1fr;

    :deep(.record-pie-chart:nth-child(3n)) {
      border-right: none;
    }
  }
}
</style>
