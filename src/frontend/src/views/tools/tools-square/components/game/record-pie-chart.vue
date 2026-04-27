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
  <div class="record-pie-chart">
    <div class="chart-title">
      {{ title }}
    </div>
    <div
      ref="chartRef"
      class="chart-container" />
  </div>
</template>

<script setup lang="ts">
  import { PieChart } from 'echarts/charts';
  import {
    LegendComponent,
    TitleComponent,
    TooltipComponent,
  } from 'echarts/components';
  import * as echarts from 'echarts/core';
  import { LabelLayout } from 'echarts/features';
  import { CanvasRenderer } from 'echarts/renderers';
  import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

  const props = defineProps<Props>();

  // 注册 echarts 组件
  echarts.use([
    TitleComponent,
    TooltipComponent,
    LegendComponent,
    PieChart,
    CanvasRenderer,
    LabelLayout,
  ]);

  interface ChartDataItem {
    name: string;
    value: number;
  }

  interface Props {
    title: string;                // 图表标题
    data: ChartDataItem[];        // 饼图数据
    total: number;                // 总数
    centerLabel: string;          // 中心文字，如"登录总数"、"总额（元）"
  }

  const chartRef = ref<HTMLElement>();
  let chartInstance: echarts.ECharts | null = null;

  // 图表颜色（按设计稿色序：蓝-青-浅绿-黄-橙-红-粉-紫）
  const chartColors = ['#3A84FF', '#66C0DA', '#94D6C4', '#F6D96D', '#F8B551', '#F06A6A', '#FF6A8A', '#D968FF', '#A3D8F0', '#C4B5FD'];

  // 格式化数字，添加千分位分隔符
  const formatNumber = (num: number) => num.toLocaleString();

  // 根据容器实际像素尺寸动态计算布局参数
  const getLayoutParams = () => {
    const containerWidth = chartRef.value?.clientWidth || 400;
    const containerHeight = chartRef.value?.clientHeight || 200;

    // 饼图最大直径不超过容器高度的 90%
    const pieMaxDiameter = containerHeight ;
    // 饼图区域宽度 = min(饼图直径 + 留白, 容器宽度的 40%)
    const pieAreaWidth = Math.min(pieMaxDiameter + 20, containerWidth * 0.4);
    // 饼图中心 X 坐标（像素）
    const pieCenterX = pieAreaWidth * 0.7;

    // 饼图内外半径（像素），确保不超出容器
    const outerRadius = Math.min(pieMaxDiameter / 2, pieAreaWidth / 2 - 4);
    // 图例起始位置（像素），以饼图真实右边界为基准再留安全间距
    const legendLeftPx = pieCenterX + outerRadius + 24;
    const innerRadius = outerRadius * 0.6;

    // 根据饼图半径确定中心文字大小
    let centerFontSize = 12;
    let centerCountSize = 22;
    if (outerRadius < 50) {
      centerFontSize = 9;
      centerCountSize = 14;
    } else if (outerRadius < 70) {
      centerFontSize = 10;
      centerCountSize = 16;
    }

    return {
      pieCenterX,
      pieCenterY: containerHeight / 2,
      innerRadius,
      outerRadius,
      legendLeftPx,
      legendRight: 8,
      centerFontSize,
      centerCountSize,
    };
  };

  // 创建环形图配置
  const createPieOption = () => {
    const layout = getLayoutParams();

    return {
      tooltip: {
        trigger: 'item',
        formatter: '{b}：{c}（{d}%）',
        confine: true,
      },
      legend: {
        orient: 'vertical' as const,
        left: layout.legendLeftPx,
        top: 'middle',
        right: layout.legendRight,
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 6,
        icon: 'circle',
        textStyle: {
          fontSize: 12,
          color: '#63656e',
          lineHeight: 18,
        },
        formatter: (name: string) => {
          const item = props.data.find(d => d.name === name);
          if (!item) return name;
          const percent = props.total > 0 ? ((item.value / props.total) * 100).toFixed(2) : '0';
          return `${name}：${formatNumber(item.value)}（${percent}%）`;
        },
      },
      color: chartColors,
      series: [
        {
          type: 'pie',
          radius: [layout.innerRadius, layout.outerRadius],
          center: [layout.pieCenterX, layout.pieCenterY],
          avoidLabelOverlap: false,
          label: {
            show: true,
            position: 'center',
            formatter: () => `{total|${props.centerLabel}}\n{count|${formatNumber(props.total)}}`,
            rich: {
              total: {
                fontSize: layout.centerFontSize,
                color: '#979ba5',
                lineHeight: 20,
              },
              count: {
                fontSize: layout.centerCountSize,
                fontWeight: 700,
                color: '#313238',
                lineHeight: 30,
              },
            },
          },
          emphasis: {
            label: {
              show: true,
            },
          },
          labelLine: {
            show: false,
          },
          data: props.data,
        },
      ],
    };
  };

  let resizeObserver: ResizeObserver | null = null;

  // 窗口 resize 处理函数
  const handleResize = () => {
    if (chartInstance) {
      chartInstance.resize();
      chartInstance.setOption(createPieOption());
    }
  };

  // 初始化图表
  const initChart = () => {
    if (!chartRef.value) return;
    // 如果容器宽度还未正确计算（如在隐藏的 tab 中），跳过初始化，等 ResizeObserver 触发
    const { clientWidth } = chartRef.value;
    if (clientWidth <= 0) return;

    if (!chartInstance) {
      chartInstance = echarts.init(chartRef.value);
    }
    chartInstance.setOption(createPieOption());
  };

  // 更新图表
  const updateChart = () => {
    if (chartInstance) {
      chartInstance.setOption(createPieOption());
    }
  };

  // 监听数据变化，更新图表
  watch(() => [props.data, props.total, props.centerLabel], () => {
    updateChart();
  }, { deep: true });

  onMounted(() => {
    nextTick(() => {
      initChart();

      // 监听窗口变化（双保险：window.resize + ResizeObserver）
      window.addEventListener('resize', handleResize);

      // 使用 ResizeObserver 监听容器尺寸变化
      // 解决 tab 切换时容器从 display:none 变为可见后 ECharts 宽度不正确的问题
      if (chartRef.value) {
        resizeObserver = new ResizeObserver(() => {
          if (!chartRef.value) return;
          const { clientWidth } = chartRef.value;
          if (clientWidth <= 0) return;

          if (!chartInstance) {
            // 容器首次获得正确宽度，初始化图表
            chartInstance = echarts.init(chartRef.value);
            chartInstance.setOption(createPieOption());
          } else {
            // 容器尺寸变化，先 resize 再重新设置布局参数
            chartInstance.resize();
            chartInstance.setOption(createPieOption());
          }
        });
        resizeObserver.observe(chartRef.value);
      }
    });
  });

  onBeforeUnmount(() => {
    window.removeEventListener('resize', handleResize);
    resizeObserver?.disconnect();
    resizeObserver = null;
    chartInstance?.dispose();
    chartInstance = null;
  });
</script>

<style scoped lang="postcss">
.record-pie-chart {
  padding: 16px;
  background: #fff;
  border-radius: 2px;

  .chart-title {
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .chart-container {
    width: 100%;
    height: 200px;
    overflow: hidden;
  }
}
</style>
