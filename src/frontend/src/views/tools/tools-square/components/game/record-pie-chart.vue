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
    <div class="chart-header">
      <div class="chart-title">
        {{ title }} Top10
      </div>
      <div
        v-if="hasOther"
        class="other-switch">
        <span class="switch-label">其他</span>
        <bk-switcher
          v-model="showOther"
          size="small"
          theme="primary"
          @change="handleOtherSwitch" />
      </div>
    </div>
    <!-- "其他"开关已移至标题行右侧 -->
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
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

  const props = withDefaults(defineProps<Props>(), {
    activeName: '',
    tooltipNameMap: () => ({}),
    colCount: 2,
  });

  // 定义事件：图例点击时触发，用于与下方表格搜索联动
  const emit = defineEmits<{
    'legend-click': [payload: { title: string; name: string; selected: boolean }];
  }>();

  // "其他"开关状态，默认展示
  const showOther = ref(true);

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
    dim_type: string;                       // 维度类型，如"发放人"、"需求来源"等
    metric_type: string;                    // 指标类型，如"发放金额（元）"、"总数量"等
    dim_value: string;                      // 维度值，如"yimohe"、"福利来源（IEOP）"等
    metric_value: number;                   // 指标值
    rn: string;                             // 排名，"其他"分类时rn为"99999"
  }

  interface Props {
    title: string;                          // 图表标题
    data: ChartDataItem[];                  // 饼图数据
    total: number;                          // 总数
    centerLabel: string;                    // 中心文字，如"登录总数"、"总额（元）"
    activeName?: string;                    // 当前激活项的 name；为空表示全部显示（默认）
    tooltipNameMap?: Record<string, string>; // 图例名称 → hover 展示名称 映射
    colCount?: number;                      // 每行图表个数，用于响应式调整饼图中心位置
  }

  const chartRef = ref<HTMLElement>();
  let chartInstance: echarts.ECharts | null = null;

  // 判断数据中是否包含"其他"分类（rn === '99999'）
  const hasOther = computed(() => props.data.some(item => item.rn === '99999'));

  // 监听 hasOther 变化：当"其他"分类从消失变为出现时，重置开关为开启状态
  watch(hasOther, (newVal, oldVal) => {
    if (newVal && !oldVal) {
      showOther.value = true;
    }
  });

  // 根据 showOther 开关过滤后的数据
  const filteredData = computed(() => {
    if (showOther.value) return props.data;
    return props.data.filter(item => item.rn !== '99999');
  });

  // 根据 showOther 开关计算总数
  const filteredTotal = computed(() => {
    if (showOther.value) return props.total;
    return filteredData.value.reduce((sum, item) => sum + item.metric_value, 0);
  });

  // 图表颜色（按设计稿色序：蓝-青-浅绿-黄-橙-红-粉-紫）
  const chartColors = ['#3A84FF', '#66C0DA', '#94D6C4', '#F6D96D', '#F8B551', '#F06A6A', '#FF6A8A', '#D968FF', '#A3D8F0', '#C4B5FD'];
  // "其他"分类的固定灰色
  const OTHER_COLOR = '#C4C6CC';

  // 格式化数字，添加千分位分隔符
  const formatNumber = (num: number) => num.toLocaleString();

  // hover 高亮时扇区向外放大的尺寸（与 series.emphasis.scaleSize 保持一致）
  const HOVER_SCALE_SIZE = 6;

  // 将原始数据转换为 echarts 饼图所需的 { name, value } 格式
  // "其他"分类（rn === '99999'）排在最后
  const getChartData = () => {
    const normalItems = filteredData.value.filter(item => item.rn !== '99999');
    const otherItems = filteredData.value.filter(item => item.rn === '99999');
    return [
      ...normalItems.map(item => ({ name: item.dim_value, value: item.metric_value })),
      ...otherItems.map(item => ({ name: item.dim_value, value: item.metric_value })),
    ];
  };

  // 生成颜色列表，"其他"分类使用固定灰色
  const getChartColorList = () => {
    const normalItems = filteredData.value.filter(item => item.rn !== '99999');
    const otherItems = filteredData.value.filter(item => item.rn === '99999');
    const colors: string[] = [];
    normalItems.forEach((_, index) => {
      colors.push(chartColors[index % chartColors.length]);
    });
    otherItems.forEach(() => {
      colors.push(OTHER_COLOR);
    });
    return colors;
  };

  // 根据 activeName 生成 legend.selected 配置
  // - activeName 为空：全部选中（默认显示全部）
  // - activeName 非空：仅 activeName 选中
  const buildLegendSelected = () => {
    const selected: Record<string, boolean> = {};
    const chartData = getChartData();
    chartData.forEach((item) => {
      selected[item.name] = props.activeName ? item.name === props.activeName : true;
    });
    return selected;
  };

  // 图例始终单列展示，不再换列
  const LEGEND_MAX_PER_COLUMN = 999;

  // 根据容器实际像素尺寸动态计算布局参数
  const getLayoutParams = () => {
    const containerWidth = chartRef.value?.clientWidth || 400;
    const containerHeight = chartRef.value?.clientHeight || 200;

    // 为 hover 放大预留安全间距，避免超出容器被裁切
    const safePadding = HOVER_SCALE_SIZE + 2;
    // 饼图最大直径不超过容器高度（预留 hover 放大空间）
    const pieMaxDiameter = containerHeight - safePadding * 2;
    // 饼图区域宽度 = min(饼图直径 + 留白, 容器宽度的 40%)
    const pieAreaWidth = Math.min(pieMaxDiameter + 20, containerWidth * 0.4);
    // 饼图中心 X 坐标（像素）
    let pieCenterX = pieAreaWidth * 0.5;

    // 饼图内外半径（像素），确保 hover 放大后也不超出容器
    const outerRadius = Math.min(pieMaxDiameter / 2, pieAreaWidth / 2 - safePadding);

    // 当一行图表数 >= 3 时（容器较宽），饼图中心相对容器偏左，需向右偏移改善视觉居中
    if (props.colCount >= 3) {
      const extraSpace = containerWidth - pieAreaWidth;
      pieCenterX += Math.min(extraSpace * 0.18, 60);
    }

    // 边界保护：确保饼图不超出容器且图例至少有 100px 的展示空间
    const minLegendWidth = 100;
    const maxPieCenterX = containerWidth - outerRadius - safePadding - 24 - minLegendWidth;
    pieCenterX = Math.min(pieCenterX, maxPieCenterX);
    const minPieCenterX = outerRadius + safePadding;
    pieCenterX = Math.max(pieCenterX, minPieCenterX);

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

    // 计算图例列数和每列宽度
    const chartData = getChartData();
    const legendCount = chartData.length;
    const legendColumns = Math.ceil(legendCount / LEGEND_MAX_PER_COLUMN);
    // 图例可用总宽度
    const legendTotalWidth = containerWidth - legendLeftPx - 8;
    // 每列文字宽度（减去图标和间距）
    const legendTextWidth = legendColumns > 1
      ? Math.floor(legendTotalWidth / legendColumns) - 20
      : Math.min(360, legendTotalWidth - 20);

    return {
      pieCenterX,
      pieCenterY: containerHeight / 2,
      innerRadius,
      outerRadius,
      legendLeftPx,
      legendRight: 8,
      legendWidth: legendTotalWidth,
      legendColumns,
      legendTextWidth,
      centerFontSize,
      centerCountSize,
    };
  };

  // 构建多列 legend 配置（每列最多 LEGEND_MAX_PER_COLUMN 个）
  const buildLegendList = (layout: ReturnType<typeof getLayoutParams>) => {
    const chartData = getChartData();
    const selected = buildLegendSelected();
    const { legendColumns } = layout;
    // 每列宽度
    const columnWidth = legendColumns > 1
      ? Math.floor(layout.legendWidth / legendColumns)
      : layout.legendWidth;

    const legends: any[] = [];
    for (let col = 0; col < legendColumns; col++) {
      const startIdx = col * LEGEND_MAX_PER_COLUMN;
      const endIdx = Math.min(startIdx + LEGEND_MAX_PER_COLUMN, chartData.length);
      const columnData = chartData.slice(startIdx, endIdx).map(d => d.name);

      legends.push({
        orient: 'vertical' as const,
        left: layout.legendLeftPx + col * columnWidth,
        top: 'middle',
        selectedMode: 'multiple' as const,
        selected,
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 6,
        icon: 'circle',
        data: columnData,
        textStyle: {
          fontSize: 12,
          color: '#63656e',
          lineHeight: 18,
          width: columnWidth - 24,
          overflow: 'truncate' as const,
          ellipsis: '...',
        },
        tooltip: {
          show: true,
          position: 'right' as const,
          formatter: (params: any) => {
            const item = chartData.find(d => d.name === params.name);
            if (!item) return params.name;
            const total = filteredTotal.value;
            const percent = total > 0 ? ((item.value / total) * 100).toFixed(2) : '0';
            const displayName = props.tooltipNameMap?.[params.name] || params.name;
            return `${displayName}：${formatNumber(item.value)}（${percent}%）`;
          },
        },
        formatter: (name: string) => {
          const item = chartData.find(d => d.name === name);
          if (!item) return name;
          const total = filteredTotal.value;
          const percent = total > 0 ? ((item.value / total) * 100).toFixed(2) : '0';
          return `${name}：${formatNumber(item.value)}（${percent}%）`;
        },
      });
    }
    return legends;
  };

  // 创建环形图配置
  const createPieOption = () => {
    const layout = getLayoutParams();

    return {
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          const displayName = props.tooltipNameMap?.[params.name] || params.name;
          return `${displayName}：${formatNumber(params.value)}（${params.percent}%）`;
        },
        appendToBody: true,
        position: 'right' as const,
      },
      legend: buildLegendList(layout),
      color: getChartColorList(),
      series: [
        {
          type: 'pie',
          radius: [layout.innerRadius, layout.outerRadius],
          center: [layout.pieCenterX, layout.pieCenterY],
          avoidLabelOverlap: false,
          label: {
            show: true,
            position: 'center',
            formatter: () => {
              // 选中单个图例时，中心显示该图例的名称和数值
              if (props.activeName) {
                const activeItem = filteredData.value.find(item => item.dim_value === props.activeName);
                if (activeItem) {
                  return `{total|${props.centerLabel}}\n{count|${formatNumber(activeItem.metric_value)}}`;
                }
              }
              return `{total|${props.centerLabel}}\n{count|${formatNumber(filteredTotal.value)}}`;
            },
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
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 2,
          },
          emphasis: {
            scaleSize: HOVER_SCALE_SIZE,
            label: {
              show: true,
            },
          },
          labelLine: {
            show: false,
          },
          data: getChartData(),
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
      bindChartEvents();
    }
    chartInstance.setOption(createPieOption());
  };

  // 绑定图表事件
  const bindChartEvents = () => {
    if (!chartInstance) return;
    // 图例点击逻辑：
    // - 当前为"全部显示"(activeName 为空)：点击 X → 切换为只显示 X
    // - 当前为"仅显示 X"：点击 X → 复位为全部显示；点击 Y → 切换为只显示 Y
    // 注意：echarts 默认会"切换被点击项的 selected 状态"，这与我们需要的"单选切换"语义不一致，
    // 所以这里立刻用 setOption 把 legend.selected 强制修正回受控状态（由 activeName 决定），
    // 真正的切换通过 emit 给父组件、父组件更新 activeName 后再下发 prop 完成。
    chartInstance.on('legendselectchanged', (params: any) => {
      const clickedName = params?.name as string;
      if (!clickedName) return;
      handlePieItemClick(clickedName);
    });

    // 饼图扇区点击：与图例点击触发相同的筛选效果
    chartInstance.on('click', 'series.pie', (params: any) => {
      const clickedName = params?.name as string;
      if (!clickedName) return;
      handlePieItemClick(clickedName);
    });
  };

  // 统一处理点击逻辑（图例点击 / 扇区点击）
  const handlePieItemClick = (clickedName: string) => {
    // "其他"分类（rn === '99999'）为聚合项，不触发搜索联动
    const clickedItem = filteredData.value.find(item => item.dim_value === clickedName);
    if (clickedItem && clickedItem.rn === '99999') {
      // 立即用受控状态覆盖 echarts 默认行为，避免视图状态变化
      chartInstance?.setOption({
        legend: { selected: buildLegendSelected() },
      });
      return;
    }

    // 计算"用户点击后期望的 activeName"
    let nextActiveName = '';
    if (!props.activeName) {
      // 当前全部显示 → 点击则切换到仅显示该项
      nextActiveName = clickedName;
    } else if (props.activeName === clickedName) {
      // 当前仅显示该项 → 再次点击复位
      nextActiveName = '';
    } else {
      // 当前显示其它项 → 切换到刚点击的项
      nextActiveName = clickedName;
    }

    // 立即用受控状态覆盖 echarts 默认行为，避免视图与父组件不同步
    chartInstance?.setOption({
      legend: { selected: buildLegendSelected() },
    });

    emit('legend-click', {
      title: props.title,
      name: nextActiveName,
      // 是否处于"仅显示某项"状态：nextActiveName 非空时为 true
      selected: !!nextActiveName,
    });
  };

  // 更新图表
  const updateChart = () => {
    if (chartInstance) {
      chartInstance.setOption(createPieOption());
    }
  };

  // "其他"开关切换处理
  const handleOtherSwitch = () => {
    updateChart();
  };

  // 监听数据变化，更新图表
  watch(() => [props.data, props.total, props.centerLabel, props.activeName], () => {
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
            bindChartEvents();
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
  padding: 5px 12px;
  background: #fff;
  border-radius: 2px;

  .chart-header {
    display: flex;
    align-items: center;
    margin-bottom: 4px;
    gap: 16px;
  }

  .chart-title {
    font-size: 12px;
    font-weight: 700;
    line-height: 20px;
    color: #313238;
  }

  .other-switch {
    display: flex;
    align-items: center;
    gap: 6px;

    .switch-label {
      font-size: 12px;
      color: #63656e;
    }
  }

  .chart-container {
    width: 100%;
    height: 270px;
    overflow: hidden;
  }
}
</style>
