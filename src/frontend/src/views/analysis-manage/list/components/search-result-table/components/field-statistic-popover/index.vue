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
  <bk-popover
    ext-cls="field-statistic-popover"
    placement="bottom"
    theme="light"
    trigger="click"
    @after-hidden="statisticActive = false"
    @after-show="statisticActive = true">
    <template #default>
      <audit-icon
        v-bk-tooltips="{
          content: t('查看该字段数据统计'),
        }"
        class="field-statistic-icon"
        :class="{ 'is-active': statisticActive }"
        type="shujutongji"
        @click="handleClick" />
    </template>
    <template #content>
      <bk-loading :loading="loading">
        <div
          v-if="statisticData.results"
          class="statistic-content">
          <div class="statistic-overview">
            <span class="overview-item">
              <span class="overview-label">{{ t('总行数') }}:</span>
              <span class="overview-value">{{ totalRows }}</span>
            </span>
            <span class="overview-item">
              <span class="overview-label">{{ t('出现行数') }}:</span>
              <span class="overview-value">{{ nonEmptyRows }}</span>
            </span>
            <span class="overview-item">
              <span class="overview-label">{{ t('日志占比') }}:</span>
              <span class="overview-value">{{ logRatio }}</span>
            </span>
          </div>
          <template v-if="numberStats.length">
            <div class="statistic-divider" />
            <div class="values-container">
              <div
                v-for="item in numberStats"
                :key="item.label"
                class="item">
                {{ item.label }} <span class="item-count">{{ item.value }}</span>
              </div>
            </div>
          </template>
          <template v-if="chartSeries.length">
            <div class="statistic-divider" />
            <p class="statistic-chart-title">
              {{ t('TOP5时序图') }}
            </p>
            <div
              ref="chartRef"
              class="statistic-chart" />
            <ul class="statistic-legend">
              <li
                v-for="(item, index) in chartSeries"
                :key="item.name"
                class="legend-item">
                <span
                  class="legend-mark"
                  :style="{ background: chartColors[index % chartColors.length] }" />
                <span>{{ item.name }}</span>
              </li>
            </ul>
          </template>
          <template v-if="sortedValues.length">
            <div class="statistic-divider" />
            <div class="statistic-field">
              <div class="title">
                {{ t('去重后字段统计') }}
                <span class="values-number">{{ sortedValues.length }}</span>
              </div>
              <ul class="field-list">
                <li
                  v-for="(item, index) in sortedValues"
                  :key="index"
                  class="field-list-item">
                  <div class="field-row">
                    <span class="field-name">{{ item[props.fieldName] }}</span>
                    <span class="field-count">{{ item.count }}{{ t('条') }} {{ valuePercent(item.count) }}</span>
                  </div>
                  <div class="field-bar">
                    <div
                      class="field-bar-fill"
                      :style="{ width: valuePercent(item.count) }" />
                  </div>
                </li>
              </ul>
            </div>
          </template>
        </div>
        <bk-exception
          v-else
          class="exception-part"
          scene="part"
          type="search-empty">
          {{ t('暂无数据') }}
        </bk-exception>
      </bk-loading>
    </template>
  </bk-popover>
</template>

<script setup lang="ts">
  // import { ref } from 'vue';
  import { LineChart } from 'echarts/charts';
  import {
    GridComponent,
    TooltipComponent } from 'echarts/components';
  import * as echarts from 'echarts/core';
  import { UniversalTransition } from 'echarts/features';
  import { CanvasRenderer } from 'echarts/renderers';
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EsQueryService from '@service/es-query';

  import SearchStatisticModel from '@model/es-query/search_statistic';

  import useRequest from '@hooks/use-request';

  interface Props {
    fieldName: string;
    params: Record<string, any>;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const statisticActive = ref(false);
  const chartRef = ref<HTMLDivElement>();
  let chartInstance: echarts.ECharts | null = null;

  echarts.use([
    TooltipComponent,
    GridComponent,
    LineChart,
    CanvasRenderer,
    UniversalTransition,
  ]);

  const readToken = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const chartColors = [
    readToken('--bk-theme-color-brand-2'),
    readToken('--bk-theme-color-success-2'),
    readToken('--bk-theme-color-warn-2'),
    readToken('--bk-theme-color-danger-2'),
    readToken('--bk-theme-color-brand-3'),
  ];

  // 获取统计数据
  const {
    data: statisticData,
    run: fetchSearchStatistic,
    loading,
  } = useRequest(EsQueryService.fetchSearchStatistic, {
    defaultValue: new SearchStatisticModel(),
    onSuccess: () => {
      nextTick(() => {
        setChart();
      });
    },
  });

  const totalRows = computed(() => statisticData.value.results?.total_rows?.[0]?.total_rows ?? 0);
  const nonEmptyRows = computed(() => statisticData.value.results?.non_empty_rows?.[0]?.non_empty_rows ?? 0);
  const logRatio = computed(() => {
    if (!totalRows.value) return '--';
    return `${((nonEmptyRows.value / totalRows.value) * 100).toFixed(2)}%`;
  });
  const chartSeries = computed(() => statisticData.value.results?.top_5_echarts_time_series?.series || []);
  const sortedValues = computed(() => {
    const values = statisticData.value.results?.top_5_values || [];
    return [...values].sort((prev, next) => Number(next.count) - Number(prev.count));
  });
  const numberStats = computed(() => {
    const results = statisticData.value.results;
    if (!results?.max_value) return [];
    return [
      { label: t('最大值'), value: results.max_value[0]?.max_value },
      { label: t('最小值'), value: results.min_value?.[0]?.min_value },
      { label: t('平均值'), value: results.avg_value?.[0]?.avg_value },
      { label: t('中位数'), value: results.median_value?.[0]?.median_value },
    ];
  });

  const valuePercent = (count: number) => {
    if (!totalRows.value) return '0.00%';
    return `${((count / totalRows.value) * 100).toFixed(2)}%`;
  };

  const setChart = () => {
    const series = chartSeries.value;
    if (!chartRef.value || !series.length) return;
    const textColor = readToken('--bk-theme-text-weak');
    const lineColor = readToken('--bk-theme-border-weak');
    const times = statisticData.value.results.top_5_echarts_time_series.times || [];
    if (!chartInstance) {
      chartInstance = echarts.init(chartRef.value);
    }
    chartInstance.setOption({
      tooltip: { trigger: 'axis' },
      grid: {
        left: 8,
        right: 8,
        top: 8,
        bottom: 8,
        containLabel: true,
      },
      color: chartColors,
      xAxis: {
        type: 'category',
        boundaryGap: false,
        axisLine: { lineStyle: { color: lineColor } },
        axisLabel: { color: textColor, fontSize: 12 },
        data: times.map((timestamp) => {
          const date = new Date(timestamp);
          return `${date.getHours().toString()
            .padStart(2, '0')}:${date.getMinutes().toString()
            .padStart(2, '0')}`;
        }),
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: textColor, fontSize: 12 },
        splitLine: { lineStyle: { color: lineColor } },
      },
      series: series.map(value => ({
        name: value.name,
        type: 'line',
        showSymbol: false,
        data: value.data,
      })),
    });
  };

  // 处理点击事件
  const handleClick = () => {
    const params = {
      ...props.params,
      field_name: props.fieldName,
    };
    fetchSearchStatistic(params);
  };

  onBeforeUnmount(() => {
    chartInstance?.dispose();
  });
</script>

<style lang="postcss">
.bk-popover.bk-pop2-content.field-statistic-popover[data-theme^='light'] {
  padding: 0;
  background: var(--bk-theme-surface-default);
  border-radius: var(--bk-theme-overlay-radius);
  box-shadow: var(--bk-theme-card-shadow);
}

.bk-popover.bk-pop2-content.field-statistic-popover[data-theme^='light'] .bk-pop2-arrow {
  background: var(--bk-theme-surface-default);
}
</style>
<style lang="postcss" scoped>
.field-statistic-icon {
  padding-left: var(--bk-theme-space-4);
  color: var(--bk-theme-text-weak);
  cursor: pointer;

  &:hover,
  &.is-active {
    color: var(--bk-theme-color-brand-2);
  }
}

.statistic-content {
  display: flex;
  width: 360px;
  padding: var(--bk-theme-space-24);
  color: var(--bk-theme-text-strong);
  background: var(--bk-theme-surface-default);
  border-radius: var(--bk-theme-overlay-radius);
  box-sizing: border-box;
  flex-direction: column;
  gap: var(--bk-theme-space-16);
}

.statistic-overview {
  display: flex;
  justify-content: space-between;
  font-size: var(--bk-theme-font-size-sm);
  line-height: var(--bk-theme-line-height-sm);
  gap: var(--bk-theme-space-8);
}

.overview-item {
  display: flex;
  gap: var(--bk-theme-space-4);
  white-space: nowrap;
}

.overview-label {
  color: var(--bk-theme-text-weak);
}

.overview-value {
  font-weight: var(--bk-theme-font-weight-bold);
}

.statistic-divider {
  height: 1px;
  background: var(--bk-theme-border-default);
}

.statistic-chart-title {
  margin: 0;
  font-size: var(--bk-theme-font-size-base);
  font-weight: var(--bk-theme-font-weight-bold);
  line-height: var(--bk-theme-line-height-base);
}

.statistic-chart {
  width: 100%;
  height: 160px;
}

.statistic-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--bk-theme-space-16);
  padding: 0;
  margin: 0;
  list-style: none;
}

.legend-item {
  display: flex;
  align-items: center;
  font-size: var(--bk-theme-font-size-sm);
  line-height: var(--bk-theme-line-height-sm);
  gap: var(--bk-theme-space-8);
}

.legend-mark {
  width: 8px;
  height: 8px;
  border-radius: var(--bk-theme-tag-radius);
}

.values-container {
  display: flex;
  flex-wrap: wrap;
  gap: var(--bk-theme-space-8);

  .item {
    height: 32px;
    font-size: var(--bk-theme-font-size-sm);
    line-height: 32px;
    text-align: center;
    background: var(--bk-theme-surface-muted);
    box-sizing: border-box;
    flex: 0 0 calc(50% - 4px);
  }

  .item-count {
    font-weight: var(--bk-theme-font-weight-bold);
  }
}

.statistic-field {
  .title {
    display: flex;
    align-items: center;
    margin-bottom: var(--bk-theme-space-16);
    font-size: var(--bk-theme-font-size-sm);
    font-weight: var(--bk-theme-font-weight-bold);
    line-height: var(--bk-theme-line-height-sm);
    gap: var(--bk-theme-space-8);
  }

  .values-number {
    display: inline-flex;
    height: 18px;
    padding: 0 var(--bk-theme-space-4);
    font-size: var(--bk-theme-font-size-sm);
    font-weight: var(--bk-theme-font-weight-regular);
    line-height: 18px;
    color: var(--bk-theme-text-default);
    background: var(--bk-theme-surface-muted);
    border-radius: var(--bk-theme-tab-pill-radius);
  }
}

.field-list {
  display: flex;
  padding: 0;
  margin: 0;
  list-style: none;
  flex-direction: column;
  gap: var(--bk-theme-space-16);
}

.field-list-item {
  display: flex;
  flex-direction: column;
  gap: var(--bk-theme-space-4);
}

.field-row {
  display: flex;
  justify-content: space-between;
  font-size: var(--bk-theme-font-size-sm);
  line-height: var(--bk-theme-line-height-sm);
  gap: var(--bk-theme-space-8);
}

.field-name {
  color: var(--bk-theme-text-strong);
}

.field-count {
  color: var(--bk-theme-text-default);
  white-space: nowrap;
}

.field-bar {
  height: 6px;
  overflow: hidden;
  background: var(--bk-theme-surface-muted);
  border-radius: var(--bk-theme-tab-pill-radius);
}

.field-bar-fill {
  height: 6px;
  background: var(--bk-theme-color-success-2);
  border-radius: var(--bk-theme-tab-pill-radius);
}
</style>
