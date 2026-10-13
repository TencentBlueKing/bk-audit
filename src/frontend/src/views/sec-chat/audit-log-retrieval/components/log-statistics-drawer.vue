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
  <audit-sideslider
    :is-show="isShow"
    quick-close
    :show-footer="false"
    show-header-slot
    title=""
    :width="960"
    @update:is-show="handleUpdateShow">
    <template #header>
      <div class="stats-header">
        <span class="stats-title">数据统计</span>
        <span class="stats-divider" />
        <span class="stats-time">统计时间：{{ createdAt }}</span>
      </div>
    </template>

    <div class="stats-body">
      <div class="stats-card">
        <div class="card-head">
          <span class="card-title">时序趋势</span>
          <bk-button
            class="export-btn"
            size="small"
            @click="handleExport('trend')">
            <audit-icon
              class="export-icon"
              type="download" />
            导出
          </bk-button>
        </div>
        <div
          ref="trendChartRef"
          class="chart-box" />
      </div>

      <div class="stats-card">
        <div class="card-head">
          <span class="card-title">维度占比</span>
          <bk-button
            class="export-btn"
            size="small"
            @click="handleExport('ratio')">
            <audit-icon
              class="export-icon"
              type="download" />
            导出
          </bk-button>
        </div>
        <div class="ratio-wrap">
          <div
            ref="ratioChartRef"
            class="chart-box is-ratio" />
          <div class="ratio-legend">
            <div
              v-for="item in ratioLegend"
              :key="item.name"
              class="legend-item">
              <span
                class="legend-dot"
                :style="{ background: item.color }" />
              <span>{{ item.name }}：{{ item.value }}（{{ item.percent }}）</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </audit-sideslider>
</template>

<script lang="ts" setup>
  import * as echarts from 'echarts';
  import {
    nextTick,
    onDeactivated,
    onBeforeUnmount,
    ref,
    watch,
  } from 'vue';

  import useMessage from '@hooks/use-message';

  const props = withDefaults(defineProps<{
    isShow?: boolean;
    createdAt?: string;
    fields?: string[];
  }>(), {
    isShow: false,
    createdAt: '',
    fields: () => [],
  });

  const emit = defineEmits<{
    'update:isShow': [value: boolean];
  }>();

  const { messageSuccess } = useMessage();

  const trendChartRef = ref<HTMLElement | null>(null);
  const ratioChartRef = ref<HTMLElement | null>(null);
  let trendChart: echarts.ECharts | null = null;
  let ratioChart: echarts.ECharts | null = null;
  let resizeObserver: ResizeObserver | null = null;
  let renderTimer: ReturnType<typeof setTimeout> | null = null;

  const ratioLegend = [
    { name: '成功', value: 528, percent: '31.7%', color: '#2dcb56' },
    { name: '失败', value: 308, percent: '24.68%', color: '#ea3636' },
  ];

  const xAxisData = [
    '3-3', '3-5', '3-7', '3-9', '3-11', '3-13', '3-15', '3-17', '3-19', '3-21',
  ];
  const newSeries = [20, 35, 28, 55, 42, 70, 62, 80, 58, 45];
  const handledSeries = [10, 18, 22, 30, 28, 40, 35, 45, 32, 28];

  const handleUpdateShow = (val: boolean) => {
    emit('update:isShow', val);
  };

  // keep-alive 场景下失活时，关闭侧滑避免 teleport/遮罩残留影响其他页点击
  onDeactivated(() => {
    emit('update:isShow', false);
  });

  const resizeCharts = () => {
    trendChart?.resize();
    ratioChart?.resize();
  };

  const renderTrendChart = () => {
    if (!trendChartRef.value) return;
    if (trendChartRef.value.clientWidth < 80) return;
    if (!trendChart) trendChart = echarts.init(trendChartRef.value);
    trendChart.setOption({
      color: ['#ea3636', '#2dcb56'],
      tooltip: { trigger: 'axis' },
      legend: {
        bottom: 0,
        icon: 'diamond',
        data: ['新增', '已处理'],
      },
      grid: {
        left: 48,
        right: 24,
        top: 24,
        bottom: 48,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: xAxisData,
        axisLine: { lineStyle: { color: '#dcdee5' } },
        axisLabel: { color: '#979ba5' },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        splitNumber: 5,
        axisLabel: { color: '#979ba5' },
        splitLine: { lineStyle: { color: '#f0f1f5' } },
      },
      series: [
        {
          name: '新增',
          type: 'line',
          smooth: true,
          symbol: 'none',
          areaStyle: { opacity: 0.2 },
          data: newSeries,
        },
        {
          name: '已处理',
          type: 'line',
          smooth: true,
          symbol: 'none',
          areaStyle: { opacity: 0.2 },
          data: handledSeries,
        },
      ],
    });
  };

  const renderRatioChart = () => {
    if (!ratioChartRef.value) return;
    if (ratioChartRef.value.clientWidth < 80) return;
    if (!ratioChart) ratioChart = echarts.init(ratioChartRef.value);
    ratioChart.setOption({
      color: ['#2dcb56', '#ea3636'],
      tooltip: { trigger: 'item' },
      series: [
        {
          type: 'pie',
          radius: ['48%', '72%'],
          center: ['50%', '50%'],
          avoidLabelOverlap: true,
          label: { show: false },
          labelLine: { show: false },
          data: [
            { name: '成功', value: 528 },
            { name: '失败', value: 308 },
          ],
        },
      ],
    });
  };

  const bindResizeObserver = () => {
    resizeObserver?.disconnect();
    resizeObserver = new ResizeObserver(() => {
      resizeCharts();
    });
    if (trendChartRef.value) resizeObserver.observe(trendChartRef.value);
    if (ratioChartRef.value) resizeObserver.observe(ratioChartRef.value);
  };

  const renderCharts = async () => {
    await nextTick();
    // 等待侧滑动画结束后再初始化，避免容器宽度为 0 导致图表挤压
    if (renderTimer) clearTimeout(renderTimer);
    renderTimer = setTimeout(() => {
      renderTrendChart();
      renderRatioChart();
      resizeCharts();
      bindResizeObserver();
      requestAnimationFrame(() => {
        resizeCharts();
      });
      renderTimer = null;
    }, 320);
  };

  const disposeCharts = () => {
    if (renderTimer) {
      clearTimeout(renderTimer);
      renderTimer = null;
    }
    resizeObserver?.disconnect();
    resizeObserver = null;
    trendChart?.dispose();
    ratioChart?.dispose();
    trendChart = null;
    ratioChart = null;
  };

  watch(() => props.isShow, (val) => {
    if (val) renderCharts();
    else disposeCharts();
  });

  const handleExport = (type: 'trend' | 'ratio') => {
    void props.fields;
    messageSuccess(type === 'trend' ? '已选择导出时序趋势' : '已选择导出维度占比');
  };

  onBeforeUnmount(() => {
    disposeCharts();
  });
</script>

<style lang="postcss" scoped>
  .stats-header {
    display: flex;
    height: 52px;
    align-items: center;
    gap: 12px;
  }

  .stats-title {
    font-size: 16px;
    font-weight: 700;
    color: #313238;
  }

  .stats-divider {
    width: 1px;
    height: 14px;
    background: #dcdee5;
  }

  .stats-time {
    font-size: 12px;
    color: #979ba5;
  }

  .stats-body {
    display: flex;
    width: 100%;
    min-height: calc(100vh - 52px);
    padding: 16px 20px 24px;
    background: #f5f7fa;
    flex-direction: column;
    gap: 16px;
    box-sizing: border-box;
  }

  .stats-card {
    width: 100%;
    padding: 16px 20px 12px;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px rgb(0 0 0 / 6%);
    box-sizing: border-box;
  }

  .card-head {
    display: flex;
    margin-bottom: 8px;
    align-items: center;
    justify-content: space-between;
  }

  .card-title {
    font-size: 14px;
    font-weight: 700;
    color: #313238;
  }

  .export-btn {
    color: #63656e;

    .export-icon {
      margin-right: 4px;
      font-size: 14px;
    }
  }

  .chart-box {
    width: 100%;
    height: 280px;
    min-width: 0;

    &.is-ratio {
      width: 280px;
      height: 260px;
      flex-shrink: 0;
    }
  }

  .ratio-wrap {
    display: flex;
    width: 100%;
    min-width: 0;
    justify-content: center;
    align-items: center;
    gap: 32px;
  }

  .ratio-legend {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex-shrink: 0;
  }

  .legend-item {
    display: flex;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
    align-items: center;
    gap: 8px;
  }

  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
</style>

<style lang="postcss">
  /* 侧滑内容区背景铺满 */
  .bk-sideslider .bk-modal-content:has(.stats-body),
  .bk-sideslider .bk-sideslider-content:has(.stats-body) {
    height: 100%;
    min-height: calc(100vh - 52px);
    background: #f5f7fa !important;
  }
</style>
