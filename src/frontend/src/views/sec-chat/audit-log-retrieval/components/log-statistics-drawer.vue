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
    :width="800"
    @update:is-show="handleUpdateShow">
    <template #header>
      <div class="stats-header">
        <span class="stats-title">{{ headerTitle }}</span>
        <span class="stats-divider" />
        <span class="stats-time">{{ t('统计时间') }}：{{ createdAtText }}</span>
      </div>
    </template>

    <div class="stats-body">
      <div
        v-if="isLoading"
        class="stats-placeholder"
        data-testid="statistics-loading">
        <audit-icon
          class="placeholder-loading"
          type="loading" />
        {{ t('数据统计中') }}
      </div>

      <div
        v-else-if="isFailed"
        class="stats-placeholder"
        data-testid="statistics-failed">
        <span>{{ errorMessage || t('统计失败') }}</span>
        <bk-button
          :loading="regenerating"
          size="small"
          theme="primary"
          @click="handleRegenerate">
          {{ t('重新统计') }}
        </bk-button>
      </div>

      <template v-else>
        <div
          v-if="fieldView"
          class="stats-card"
          data-testid="statistics-overview">
          <div class="card-head">
            <span class="card-title">{{ t('统计概览') }}</span>
            <span
              v-if="fieldView.scopeText"
              class="card-extra">{{ fieldView.scopeText }}</span>
          </div>
          <div class="overview-grid">
            <div class="overview-item">
              <span class="overview-label">{{ t('日志总数') }}</span>
              <span class="overview-value">{{ fieldView.overview.totalText }}</span>
            </div>
            <div class="overview-item">
              <span class="overview-label">{{ t('有值条数') }}</span>
              <span class="overview-value">{{ fieldView.overview.presentText }}</span>
            </div>
            <div class="overview-item">
              <span class="overview-label">{{ t('缺失条数') }}</span>
              <span class="overview-value">{{ fieldView.overview.missingText }}</span>
            </div>
            <div class="overview-item">
              <span class="overview-label">{{ t('有值占比') }}</span>
              <span class="overview-value">{{ fieldView.overview.presentRatioText }}</span>
            </div>
          </div>
        </div>

        <div
          v-if="rawContent"
          class="stats-card"
          data-testid="statistics-raw-content">
          <div class="card-head">
            <span class="card-title">{{ t('统计结果') }}</span>
            <bk-button
              :loading="regenerating"
              outline
              size="small"
              @click="handleRegenerate">
              {{ t('重新统计') }}
            </bk-button>
          </div>
          <p class="raw-tip">
            {{ contentFailureText }}
          </p>
          <pre class="raw-content">{{ rawContent }}</pre>
        </div>

        <div
          v-for="card in viewCards"
          :key="card.key"
          class="stats-card"
          data-testid="statistics-chart-card">
          <div class="card-head">
            <span class="card-title">{{ cardTitleText(card.title) }}</span>
            <bk-button
              v-if="isFieldStatistics && !isCardBroken(card)"
              class="export-btn"
              outline
              size="small"
              @click="handleExport(card.key)">
              <audit-icon
                class="export-icon"
                type="download" />
              {{ t('导出') }}
            </bk-button>
          </div>
          <div
            v-if="isCardBroken(card)"
            class="chart-error"
            data-testid="statistics-chart-error">
            {{ cardErrorText(card) }}
          </div>
          <div
            v-else-if="card.kind === 'ratio'"
            class="ratio-wrap">
            <div
              :ref="el => setChartRef(card.key, el)"
              class="chart-box is-ratio"
              :style="{ height: `${card.height}px`, width: `${card.height}px` }" />
            <div
              class="ratio-legend"
              @mouseleave="hideLegendTip">
              <div
                v-for="item in card.ratio || []"
                :key="item.groupId"
                class="legend-item"
                :class="{ 'is-off': !isLegendItemOn(card.key, item.name) }"
                @click="toggleChartLegend(card.key, item.name)"
                @mouseenter="showLegendTip(item, $event)">
                <span
                  class="legend-dot"
                  :style="{ background: isLegendItemOn(card.key, item.name) ? item.color : 'var(--audit-neutral-text-04)' }" />
                <span class="legend-label">
                  <span class="legend-name">{{ item.name }}</span>
                  <span class="legend-meta">：{{ item.valueText }} ( {{ item.percent }} )</span>
                </span>
              </div>
            </div>
          </div>
          <template v-else>
            <div
              :ref="el => setChartRef(card.key, el)"
              class="chart-box"
              :style="{ height: `${chartBoxHeight(card)}px` }" />
            <div
              v-if="card.legendItems.length"
              class="chart-legend-block"
              data-testid="statistics-chart-legend"
              @mouseleave="hideLegendTip">
              <div
                :ref="el => setLegendListRef(card.key, el)"
                class="chart-legend"
                :class="{
                  'is-measuring': !legendPageSpans[card.key],
                  'is-paged': legendPageCount(card.key) > 1,
                }">
                <div
                  v-for="item in visibleLegendItems(card)"
                  :key="item.key"
                  class="chart-legend-item"
                  :class="{ 'is-off': !isLegendItemOn(card.key, item.name) }"
                  @click="toggleChartLegend(card.key, item.name)"
                  @mouseenter="showChartLegendTip(item.name, $event)">
                  <span
                    class="legend-dot"
                    :style="{ background: isLegendItemOn(card.key, item.name) ? item.color : 'var(--audit-neutral-text-04)' }" />
                  <span class="chart-legend-name">{{ truncateLegendLabel(item.name) }}</span>
                </div>
              </div>
              <div
                :ref="el => setLegendMeasureRef(card.key, el)"
                class="chart-legend-measure"
                aria-hidden="true">
                <div
                  v-for="(item, index) in card.legendItems"
                  :key="`${item.name}-${index}`"
                  class="chart-legend-item">
                  <span
                    class="legend-dot"
                    :style="{ background: item.color }" />
                  <span class="chart-legend-name">{{ truncateLegendLabel(item.name) }}</span>
                </div>
              </div>
              <div
                v-if="legendPageCount(card.key) > 1"
                class="chart-legend-pager"
                data-testid="statistics-chart-legend-pager">
                <button
                  class="legend-page-btn"
                  :disabled="legendPageNumber(card.key) <= 1"
                  type="button"
                  @click="stepLegendPage(card.key, -1)">
                  <audit-icon
                    class="is-prev"
                    type="angle-fill-rignt" />
                </button>
                <span class="legend-page-index">{{ legendPageLabel(card.key) }}</span>
                <button
                  class="legend-page-btn"
                  :disabled="legendPageNumber(card.key) >= legendPageCount(card.key)"
                  type="button"
                  @click="stepLegendPage(card.key, 1)">
                  <audit-icon type="angle-fill-rignt" />
                </button>
              </div>
            </div>
            <p
              v-if="card.kind === 'trend' && trendHint"
              class="card-hint">
              {{ trendHint }}
            </p>
          </template>
        </div>

        <div
          v-if="numericSummary"
          class="stats-card"
          data-testid="statistics-numeric-summary">
          <div class="card-head">
            <span class="card-title">{{ t('数值摘要') }}</span>
          </div>
          <div class="overview-grid">
            <div
              v-for="item in numericSummaryItems"
              :key="item.label"
              class="overview-item">
              <span class="overview-label">{{ item.label }}</span>
              <span
                class="overview-value"
                :title="item.title">{{ item.value }}</span>
            </div>
          </div>
        </div>

        <div
          v-if="isEmptyResult"
          class="stats-placeholder"
          data-testid="statistics-empty">
          <span>{{ emptyText }}</span>
          <bk-button
            v-if="!isFieldStatistics"
            :loading="regenerating"
            size="small"
            theme="primary"
            @click="handleRegenerate">
            {{ t('重新统计') }}
          </bk-button>
        </div>
      </template>
    </div>
    <bk-popover
      ref="legendPopoverRef"
      ext-cls="statistics-legend-popover"
      :is-show="legendTipShow"
      :max-width="360"
      placement="top"
      :popover-delay="0"
      :reference="legendTipAnchor"
      theme="light"
      trigger="manual">
      <span class="legend-tip-anchor" />
      <template #content>
        <div class="statistics-legend-full">
          {{ legendTipText }}
        </div>
      </template>
    </bk-popover>
  </audit-sideslider>
</template>

<script lang="ts" setup>
  import * as echarts from 'echarts';
  import * as XLSX from 'xlsx';
  import {
    computed,
    markRaw,
    nextTick,
    onBeforeUnmount,
    onDeactivated,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import {
    asFieldStatisticsOutput,
    attachmentStatisticsContent,
  } from '@model/ai-assistant/attachment';
  import type { AiAttachmentOutputData } from '@model/ai-assistant/types';

  import useMessage from '@hooks/use-message';

  import {
    buildBarOption,
    buildRatioOption,
    buildTrendOption,
    formatNumericValue,
    formatNumericValueFull,
    formatStatisticsCount,
    formatStatisticsExportTime,
    isFieldStatisticsType,
    mapFieldStatisticsOutput,
    type StatisticsChartCard,
    type StatisticsContentFailure,
    type StatisticsRatioItem,
    parseStatisticsCharts,
    RATIO_CARD_TITLE,
    statisticsBarChartHeight,
    statisticsIntervalTextKey,
    TREND_CARD_TITLE,
    visibleStatisticsRatio,
  } from '../utils/map-statistics-output';
  import {
    type ChartSanitizeErrorCode,
    sanitizeChartOption,
  } from '../utils/sanitize-chart-option';

  const props = withDefaults(defineProps<{
    isShow?: boolean;
    /** FIELD_STATISTICS | AI_STATISTICS，决定 output_data 的解读方式 */
    attachmentType?: string;
    status?: string;
    createdAt?: string;
    outputData?: AiAttachmentOutputData;
    errorMessage?: string;
    regenerating?: boolean;
  }>(), {
    isShow: false,
    attachmentType: '',
    status: '',
    createdAt: '',
    outputData: null,
    errorMessage: '',
    regenerating: false,
  });

  const emit = defineEmits<{
    'update:isShow': [value: boolean];
    regenerate: [];
  }>();

  const { t } = useI18n();
  const { messageError, messageSuccess, messageWarn } = useMessage();

  const BUILTIN_CARD_TITLES = new Set([TREND_CARD_TITLE, RATIO_CARD_TITLE, '统计图表']);

  const LEGEND_LABEL_MAX = 20;
  const ECHARTS_PALETTE = [
    '#5470c6',
    '#91cc75',
    '#fac858',
    '#ee6666',
    '#73c0de',
    '#3ba272',
    '#fc8452',
    '#9a60b4',
    '#ea7ccc',
  ];

  interface ChartLegendItem {
    name: string;
    color: string;
  }

  interface ChartCardView extends StatisticsChartCard {
    legendItems: ChartLegendItem[];
  }

  const LEGEND_PAGE_ROWS = 4;

  const chartEls = new Map<string, HTMLElement>();
  const chartInstances = new Map<string, echarts.ECharts>();
  /** 入场动画结束前不做 resize，避免把正在生长的图重置成终态 */
  const entranceTimers = new Map<string, ReturnType<typeof setTimeout>>();
  interface LegendPopoverExpose {
    updatePopover?(el: HTMLElement | null): void;
  }

  const legendTipShow = ref(false);
  const legendTipText = ref('');
  const legendTipAnchor = ref<HTMLElement | null>(null);
  const legendPopoverRef = ref<LegendPopoverExpose | null>(null);

  /** 整列图例共用一个提示。每项各挂一个时，快速划过会留下还没关掉的提示 */
  const openLegendTip = (anchor: HTMLElement, text: string) => {
    legendTipAnchor.value = anchor;
    legendTipText.value = text;
    legendTipShow.value = true;
    nextTick(() => {
      legendPopoverRef.value?.updatePopover?.(anchor);
    });
  };

  const showLegendTip = (item: StatisticsRatioItem, event: MouseEvent) => {
    const anchor = event.currentTarget as HTMLElement | null;
    if (!anchor) return;
    openLegendTip(anchor, `${item.name}：${item.valueText} ( ${item.percent} )`);
  };

  const showChartLegendTip = (name: string, event: MouseEvent) => {
    if (name.length <= LEGEND_LABEL_MAX) return;
    const anchor = event.currentTarget as HTMLElement | null;
    if (!anchor) return;
    openLegendTip(anchor, name);
  };

  const hideLegendTip = () => {
    legendTipShow.value = false;
  };

  const legendListEls = new Map<string, HTMLElement>();
  const legendMeasureEls = new Map<string, HTMLElement>();
  const legendPageIndex = ref<Record<string, number>>({});
  /** 与 ECharts 图例一致：false 表示该系列已隐藏 */
  const legendSelected = ref<Record<string, Record<string, boolean>>>({});
  /** 每页是图例下标。按实际换行量出 4 行一页，不按固定个数切 */
  const legendPageSpans = ref<Record<string, number[][]>>({});
  let legendResizeObserver: ResizeObserver | null = null;
  let legendMeasureFrame = 0;

  const legendPageCount = (key: string) => legendPageSpans.value[key]?.length || 1;

  const legendPageNumber = (key: string) => {
    const count = legendPageCount(key);
    return Math.min((legendPageIndex.value[key] || 0) + 1, count);
  };

  const legendPageLabel = (key: string) => `${legendPageNumber(key)}/${legendPageCount(key)}`;

  const visibleLegendItems = (card: ChartCardView) => {
    const spans = legendPageSpans.value[card.key];
    const items = card.legendItems;
    const indexes = spans?.[legendPageNumber(card.key) - 1] || items.map((_, index) => index);
    return indexes.map(index => {
      const item = items[index];
      if (!item) return null;
      return { ...item, key: `${item.name}-${index}` };
    }).filter((item): item is ChartLegendItem & { key: string } => Boolean(item));
  };

  const setLegendPage = (key: string, page: number) => {
    const count = legendPageCount(key);
    const next = Math.min(Math.max(page, 0), count - 1);
    if ((legendPageIndex.value[key] || 0) === next) return;
    legendPageIndex.value = { ...legendPageIndex.value, [key]: next };
  };

  const stepLegendPage = (key: string, delta: number) => {
    setLegendPage(key, (legendPageIndex.value[key] || 0) + delta);
  };

  const isLegendItemOn = (cardKey: string, name: string) => (
    legendSelected.value[cardKey]?.[name] !== false
  );

  const chartBoxHeight = (card: ChartCardView) => {
    if (card.kind !== 'bar' || !card.ratio?.length) return card.height;
    const visible = visibleStatisticsRatio(card.ratio, legendSelected.value[card.key]);
    return statisticsBarChartHeight(visible.length);
  };

  /**
   * 柱状图是单系列，图例选中态不会按类别隐柱。
   * 按仍打开的图例重写纵轴和柱子，高度随可见类别变化后再 resize。
   */
  const applyBarCategoryFilter = (cardKey: string) => {
    const card = viewCards.value.find(item => item.key === cardKey);
    const chart = chartInstances.get(cardKey);
    if (!card || card.kind !== 'bar' || !card.ratio || !chart) return;
    const visible = visibleStatisticsRatio(card.ratio, legendSelected.value[cardKey]);
    chart.setOption({
      yAxis: { data: visible.map(item => item.name) },
      series: [{
        data: visible.map(item => ({
          value: item.value,
          itemStyle: { color: item.color },
        })),
      }],
    });
    nextTick(() => {
      chart.resize();
    });
  };

  /** 画布里的图例已关掉，点击这里补上 ECharts 的显隐 */
  const toggleChartLegend = (cardKey: string, name: string) => {
    const chart = chartInstances.get(cardKey);
    if (!chart || !name) return;
    hideLegendTip();
    const prev = legendSelected.value[cardKey] || {};
    const selected = {
      ...prev,
      [name]: prev[name] === false,
    };
    legendSelected.value = {
      ...legendSelected.value,
      [cardKey]: selected,
    };
    const card = viewCards.value.find(item => item.key === cardKey);
    if (card?.kind === 'bar') {
      applyBarCategoryFilter(cardKey);
      return;
    }
    chart.setOption({
      legend: {
        show: false,
        selected,
      },
    });
  };

  const measureLegendPages = (key: string) => {
    const list = legendListEls.get(key);
    const measure = legendMeasureEls.get(key);
    if (!list || !measure) return;
    const width = list.clientWidth;
    if (width < 40) return;
    measure.style.width = `${width}px`;
    const children = Array.from(measure.children) as HTMLElement[];
    const rows: number[][] = [];
    let rowTop = -1;
    children.forEach((child, index) => {
      const top = child.offsetTop;
      if (!rows.length || top - rowTop > 8) {
        rows.push([index]);
        rowTop = top;
      } else {
        rows[rows.length - 1].push(index);
      }
    });
    const pages: number[][] = [];
    for (let index = 0; index < rows.length; index += LEGEND_PAGE_ROWS) {
      pages.push(rows.slice(index, index + LEGEND_PAGE_ROWS).flat());
    }
    const prev = legendPageSpans.value[key];
    const same = Boolean(prev)
      && prev.length === pages.length
      && prev.every((page, pageIndex) => (
        page.length === pages[pageIndex].length
        && page.every((itemIndex, itemPos) => itemIndex === pages[pageIndex][itemPos])
      ));
    if (!same) {
      legendPageSpans.value = {
        ...legendPageSpans.value,
        [key]: pages.length ? pages : [[]],
      };
    }
    const current = legendPageIndex.value[key] || 0;
    if (current > pages.length - 1) {
      legendPageIndex.value = { ...legendPageIndex.value, [key]: 0 };
    }
  };

  const measureAllLegends = () => {
    legendListEls.forEach((_, key) => measureLegendPages(key));
  };

  const scheduleLegendMeasure = () => {
    if (legendMeasureFrame) cancelAnimationFrame(legendMeasureFrame);
    legendMeasureFrame = requestAnimationFrame(() => {
      legendMeasureFrame = 0;
      measureAllLegends();
      // 翻页控件出现后图例变窄，再量一次行数
      nextTick(() => measureAllLegends());
    });
  };

  const ensureLegendResizeObserver = () => {
    if (legendResizeObserver) return;
    legendResizeObserver = new ResizeObserver(() => {
      scheduleLegendMeasure();
    });
  };

  const setLegendListRef = (key: string, el: unknown) => {
    const node = el as HTMLElement | null;
    const prev = legendListEls.get(key);
    if (prev && prev !== node) legendResizeObserver?.unobserve(prev);
    if (!node) {
      legendListEls.delete(key);
      return;
    }
    legendListEls.set(key, node);
    ensureLegendResizeObserver();
    legendResizeObserver?.observe(node);
    scheduleLegendMeasure();
  };

  const setLegendMeasureRef = (key: string, el: unknown) => {
    const node = el as HTMLElement | null;
    if (node) legendMeasureEls.set(key, node);
    else legendMeasureEls.delete(key);
    if (node) scheduleLegendMeasure();
  };
  let resizeObserver: ResizeObserver | null = null;
  let renderTimer: ReturnType<typeof setTimeout> | null = null;
  let renderFrame = 0;
  let renderToken = 0;

  /** 折线从左长出、环图从中心展开，时长盖过「空白卡片直接出终态」的跳变 */
  const CHART_ENTRANCE_MS = 880;

  const isFieldStatistics = computed(() => isFieldStatisticsType(props.attachmentType));
  const isLoading = computed(() => props.status === 'PROCESSING');
  const isFailed = computed(() => props.status === 'FAILED');

  const fieldView = computed(() => {
    if (!isFieldStatistics.value) return null;
    const output = asFieldStatisticsOutput(props.outputData);
    if (!output) return null;
    return mapFieldStatisticsOutput(output, {
      other: t('其他'),
      missing: t('缺失'),
      emptyString: t('空字符串'),
    });
  });

  const headerTitle = computed(() => (
    isFieldStatistics.value && fieldView.value?.fieldLabel
      ? `${t('数据统计')}：${fieldView.value.fieldLabel}`
      : t('数据统计')
  ));

  /** AI 统计只认标签内原文解析出的图表数组，整份不可用时降级展示原文 */
  const aiResult = computed(() => {
    if (isFieldStatistics.value) return null;
    return parseStatisticsCharts(attachmentStatisticsContent(props.outputData));
  });

  const rawContent = computed(() => {
    if (!aiResult.value?.failure) return '';
    return attachmentStatisticsContent(props.outputData);
  });

  const CONTENT_FAILURE_TEXT: Record<StatisticsContentFailure, string> = {
    NOT_JSON: '图表配置不合法',
    NOT_ARRAY: '图表配置不合法',
    EMPTY: '本次未生成图表',
    INVALID_ITEM: '图表配置不合法',
  };

  const contentFailureText = computed(() => {
    const failure = aiResult.value?.failure;
    return failure ? t(CONTENT_FAILURE_TEXT[failure]) : '';
  });

  const numericSummary = computed(() => fieldView.value?.numericSummary || null);

  const numericSummaryItems = computed(() => {
    const summary = numericSummary.value;
    if (!summary) return [];
    return [
      { label: t('最小值'), value: formatNumericValue(summary.min), title: formatNumericValueFull(summary.min) },
      { label: t('最大值'), value: formatNumericValue(summary.max), title: formatNumericValueFull(summary.max) },
      { label: t('平均值'), value: formatNumericValue(summary.avg), title: formatNumericValueFull(summary.avg) },
      // 后端明确中位数为近似值，不做精确排名
      {
        label: t('中位数（近似）'),
        value: formatNumericValue(summary.median),
        title: formatNumericValueFull(summary.median),
      },
      {
        label: t('有效值条数'),
        value: formatStatisticsCount(summary.valid_count),
        title: formatStatisticsCount(summary.valid_count),
      },
      {
        label: t('转换失败条数'),
        value: formatStatisticsCount(summary.conversion_failed_count),
        title: formatStatisticsCount(summary.conversion_failed_count),
      },
    ];
  });

  const trendHint = computed(() => {
    const view = fieldView.value;
    if (!view?.effectiveInterval && !view?.timezone) return '';
    const intervalKey = statisticsIntervalTextKey(view?.effectiveInterval);
    return [
      intervalKey ? `${t('时间粒度')}：${t(intervalKey)}` : '',
      view?.timezone || '',
    ].filter(Boolean).join(' · ');
  });

  const cardTitleText = (title?: string) => {
    if (!title) return t('数据统计');
    return BUILTIN_CARD_TITLES.has(title) ? t(title) : title;
  };

  const errorText = (_errorCode: ChartSanitizeErrorCode) => t('图表配置不合法');

  /** echarts 自身抛错的卡片，key 记在这里，和配置层的 errorCode 分开 */
  const mountFailedKeys = ref<Set<string>>(new Set());

  const isCardBroken = (card: StatisticsChartCard) => (
    Boolean(card.errorCode) || mountFailedKeys.value.has(card.key)
  );

  const cardErrorText = (card: StatisticsChartCard) => (
    card.errorCode ? errorText(card.errorCode) : t('图表渲染失败')
  );

  const markMountFailed = (key: string) => {
    if (mountFailedKeys.value.has(key)) return;
    const next = new Set(mountFailedKeys.value);
    next.add(key);
    mountFailedKeys.value = next;
  };

  const TOOLTIP_WRAP_STYLE = [
    'max-width:360px',
    'max-height:240px',
    'overflow:auto',
    'white-space:normal',
    'word-break:break-all',
    'overflow-wrap:anywhere',
    'line-height:20px',
  ].join(';');

  const truncateLegendLabel = (name: string) => (
    name.length > LEGEND_LABEL_MAX ? `${name.slice(0, LEGEND_LABEL_MAX)}…` : name
  );

  /**
   * 消毒会丢掉函数和 extraCssText，超长类别名要在消毒之后再挂上。
   * 图例文案截断；悬停图例时 echarts 再弹一层 tooltip 展示全文，并限制宽度换行。
   */
  const decorateLongLabels = (option: Record<string, any>) => {
    const { legend } = option;
    if (legend && typeof legend === 'object' && !Array.isArray(legend)) {
      legend.formatter = (name: string) => truncateLegendLabel(String(name ?? ''));
      const legendTooltip = legend.tooltip && typeof legend.tooltip === 'object' ? legend.tooltip : {};
      legend.tooltip = {
        ...legendTooltip,
        show: true,
        appendToBody: true,
        confine: true,
        enterable: true,
        extraCssText: TOOLTIP_WRAP_STYLE,
      };
    }
    const { tooltip } = option;
    if (tooltip && typeof tooltip === 'object' && !Array.isArray(tooltip)) {
      // 挂到 body 避免被侧栏裁切；confine 把它限制在图表区域内，超高则在提示内滚动
      tooltip.appendToBody = true;
      tooltip.confine = true;
      tooltip.enterable = true;
      tooltip.extraCssText = [tooltip.extraCssText, TOOLTIP_WRAP_STYLE].filter(Boolean).join(';');
    }
    return option;
  };

  const toSeriesList = (series: unknown) => {
    if (Array.isArray(series)) return series;
    if (series) return [series];
    return [];
  };

  /**
   * 消毒之后再写。LLM 和字段统计都走这里，保证屏上是长出来的，导出路径仍关掉动画。
   */
  const applyEntranceMotion = (option: Record<string, any>): echarts.EChartsOption => ({
    ...option,
    animation: true,
    animationDuration: CHART_ENTRANCE_MS,
    animationEasing: 'cubicOut',
    animationDurationUpdate: 280,
    animationEasingUpdate: 'cubicOut',
    series: toSeriesList(option.series).map((series: Record<string, any>, index: number) => {
      if (!series || typeof series !== 'object') return series;
      const pieMotion = series.type === 'pie' ? { animationType: 'scale' as const } : {};
      return {
        ...series,
        ...pieMotion,
        animation: true,
        animationDuration: CHART_ENTRANCE_MS,
        animationEasing: 'cubicOut',
        animationDurationUpdate: 280,
        animationDelay: Math.min(index, 6) * 40,
      };
    }),
  });

  const isPlainRecord = (value: unknown): value is Record<string, any> => (
    Boolean(value) && typeof value === 'object' && !Array.isArray(value)
  );

  const pickColor = (value: unknown) => (
    typeof value === 'string' && value.trim() ? value : ''
  );

  const legendHost = (legend: unknown) => {
    if (Array.isArray(legend)) return legend.find(isPlainRecord) || null;
    return isPlainRecord(legend) ? legend : null;
  };

  /**
   * 图例留在画布里时，多行会叠在坐标轴上。抽到画布外单独排，图表高度保持不变。
   */
  const collectLegendItems = (option: Record<string, any>): ChartLegendItem[] => {
    const legend = legendHost(option.legend);

    const seriesList = (Array.isArray(option.series) ? option.series : option.series ? [option.series] : [])
      .filter(isPlainRecord);
    const palette = (Array.isArray(option.color) ? option.color : ECHARTS_PALETTE)
      .map(pickColor)
      .filter(Boolean);
    const colors = palette.length ? palette : ECHARTS_PALETTE;
    const colorByName = new Map<string, string>();
    let paletteIndex = 0;
    const nextColor = () => {
      const color = colors[paletteIndex % colors.length];
      paletteIndex += 1;
      return color;
    };

    seriesList.forEach((series) => {
      const seriesColor = pickColor(series.color)
        || pickColor(series.itemStyle?.color)
        || pickColor(series.lineStyle?.color);
      const namedData = (Array.isArray(series.data) ? series.data : [])
        .filter(item => isPlainRecord(item) && typeof item.name === 'string' && item.name);
      if (namedData.length && (series.type === 'pie' || !series.name)) {
        namedData.forEach((item) => {
          const name = String(item.name);
          if (colorByName.has(name)) return;
          colorByName.set(name, pickColor(item.itemStyle?.color) || seriesColor || nextColor());
        });
        return;
      }
      if (typeof series.name === 'string' && series.name && !colorByName.has(series.name)) {
        colorByName.set(series.name, seriesColor || nextColor());
      }
    });

    const rawData = legend && Array.isArray(legend.data) ? legend.data : [];
    const names = rawData.length
      ? rawData.map((item) => {
        if (typeof item === 'string') return item;
        if (isPlainRecord(item) && item.name) return String(item.name);
        return '';
      }).filter(Boolean)
      : [...colorByName.keys()];

    rawData.forEach((item) => {
      if (!isPlainRecord(item) || !item.name) return;
      const explicit = pickColor(item.itemStyle?.color) || pickColor(item.color);
      if (explicit) colorByName.set(String(item.name), explicit);
    });

    return names.map((name, index) => ({
      name,
      color: colorByName.get(name) || colors[index % colors.length],
    }));
  };

  const liftChartLegend = (option: Record<string, any>) => {
    const items = collectLegendItems(option);
    if (!items.length) return { items };
    const grid = isPlainRecord(option.grid) ? option.grid : null;
    option.legend = { show: false };
    if (grid && grid.containLabel === true && typeof grid.bottom === 'number' && grid.bottom > 24) {
      grid.bottom = 12;
    }
    return { items };
  };

  const resolveRawOption = (card: StatisticsChartCard) => {
    if (card.errorCode) return null;
    if (card.option) return card.option;
    if (card.kind === 'trend' && card.trend) return buildTrendOption(card.trend);
    if (card.kind === 'bar' && card.ratio?.length) return buildBarOption(card.ratio);
    if (card.kind === 'ratio' && card.ratio?.length) return buildRatioOption(card.ratio);
    return null;
  };

  const viewCards = computed(() => {
    const cards = fieldView.value?.cards || aiResult.value?.charts || [];
    return cards.map((card): ChartCardView => {
      const emptyLegend = {
        legendItems: [] as ChartLegendItem[],
      };
      if (card.errorCode) return { ...card, ...emptyLegend };
      // 构造与消毒都在渲染期执行，任何意外都收敛成错误卡，不让整个抽屉挂掉
      try {
        const rawOption = resolveRawOption(card);
        if (!rawOption) {
          return {
            ...card,
            ...emptyLegend,
            errorCode: 'INVALID_STRUCTURE' as const,
            option: undefined,
          };
        }
        const { option, errorCode } = sanitizeChartOption(rawOption);
        const barLegend = card.kind === 'bar' && card.ratio?.length
          ? card.ratio.map(item => ({ name: item.name, color: item.color }))
          : null;
        const lifted = barLegend
          ? { items: barLegend }
          : (option ? liftChartLegend(option) : { items: [] as ChartLegendItem[] });
        const displayOption = option ? applyEntranceMotion(decorateLongLabels(option)) : null;
        return {
          ...card,
          legendItems: lifted.items,
          option: displayOption ? markRaw(displayOption) : undefined,
          errorCode,
        };
      } catch {
        return {
          ...card,
          ...emptyLegend,
          errorCode: 'INVALID_STRUCTURE' as const,
          option: undefined,
        };
      }
    });
  });

  /** SUCCESS 但无图：区分「时间范围内没有日志」和「该字段全部缺失」 */
  const isEmptyResult = computed(() => {
    if (viewCards.value.length || rawContent.value) return false;
    return true;
  });

  const emptyText = computed(() => {
    const emptyKind = fieldView.value?.emptyKind;
    if (emptyKind === 'no-logs') return t('所选时间范围内没有日志');
    if (emptyKind === 'field-missing') return t('该字段在所选日志中全部缺失');
    return t('暂无统计数据');
  });

  const createdAtText = computed(() => props.createdAt || '--');

  const handleUpdateShow = (val: boolean) => {
    if (!val) hideLegendTip();
    emit('update:isShow', val);
  };

  const handleRegenerate = () => {
    if (props.regenerating) return;
    emit('regenerate');
  };

  onDeactivated(() => {
    emit('update:isShow', false);
  });

  const setChartRef = (key: string, el: unknown) => {
    const node = el as HTMLElement | null;
    if (node) chartEls.set(key, node);
    else chartEls.delete(key);
  };

  const resizeCharts = () => {
    chartInstances.forEach((chart, key) => {
      if (entranceTimers.has(key)) return;
      try {
        chart.resize({ animation: { duration: 0 } });
      } catch {
        // 抽屉收起时容器已销毁，resize 失败无需打断其它图表
      }
    });
  };

  const clearEntranceTimers = () => {
    entranceTimers.forEach(timer => clearTimeout(timer));
    entranceTimers.clear();
  };

  const holdResizeUntilEntranceEnds = (key: string) => {
    const prev = entranceTimers.get(key);
    if (prev) clearTimeout(prev);
    const timer = setTimeout(() => {
      entranceTimers.delete(key);
      const chart = chartInstances.get(key);
      if (!chart) return;
      try {
        chart.resize({ animation: { duration: 0 } });
      } catch {
        // 入场结束时抽屉可能已经关掉
      }
    }, CHART_ENTRANCE_MS + 6 * 40 + 40);
    entranceTimers.set(key, timer);
  };

  const mountChart = (card: StatisticsChartCard) => {
    if (isCardBroken(card) || !card.option) return true;
    if (chartInstances.has(card.key)) return true;
    const el = chartEls.get(card.key);
    if (!el || el.clientWidth < 80) return false;
    // 消毒只保证结构安全，echarts 仍可能因语义不合法抛错；单卡降级，不连累其它卡片
    try {
      const chart = echarts.init(el);
      chartInstances.set(card.key, chart);
      chart.setOption(card.option, true);
      holdResizeUntilEntranceEnds(card.key);
    } catch {
      chartInstances.get(card.key)?.dispose();
      chartInstances.delete(card.key);
      markMountFailed(card.key);
    }
    return true;
  };

  /** 逐张尝试挂载，返回是否还有卡片因宽度未就绪而挂不上；不能用 some，否则第一张失败后面全被短路 */
  const mountPendingCharts = () => {
    let pending = false;
    viewCards.value.forEach((card) => {
      if (!mountChart(card)) pending = true;
    });
    return pending;
  };

  const bindResizeObserver = () => {
    resizeObserver?.disconnect();
    resizeObserver = new ResizeObserver(() => {
      mountPendingCharts();
      resizeCharts();
    });
    chartEls.forEach((el) => {
      resizeObserver?.observe(el);
    });
  };

  const retryMount = (token: number, left: number) => {
    if (left <= 0 || token !== renderToken) return;
    requestAnimationFrame(() => {
      if (token !== renderToken) return;
      const pending = mountPendingCharts();
      resizeCharts();
      if (pending) retryMount(token, left - 1);
    });
  };

  const cancelScheduledRender = () => {
    if (renderTimer) {
      clearTimeout(renderTimer);
      renderTimer = null;
    }
    if (renderFrame) {
      cancelAnimationFrame(renderFrame);
      renderFrame = 0;
    }
  };

  const disposeCharts = () => {
    renderToken += 1;
    cancelScheduledRender();
    clearEntranceTimers();
    resizeObserver?.disconnect();
    resizeObserver = null;
    chartInstances.forEach(chart => chart.dispose());
    chartInstances.clear();
    if (Object.keys(legendSelected.value).length) legendSelected.value = {};
    if (mountFailedKeys.value.size) mountFailedKeys.value = new Set();
  };

  const chartHostWidth = () => {
    let width = 0;
    chartEls.forEach((el) => {
      width = Math.max(width, el.clientWidth);
    });
    return width;
  };

  /**
   * 侧栏还在滑动时宽度每帧都变，这时 init 再 resize 会把入场动画打断成终态。
   * 等宽度连续两帧不变再挂载，图从空画布长出来。
   */
  const renderCharts = async () => {
    const token = renderToken;
    await nextTick();
    if (token !== renderToken) return;
    cancelScheduledRender();
    let lastWidth = -1;
    let stableFrames = 0;
    let frames = 0;
    const tick = () => {
      if (token !== renderToken) return;
      const width = chartHostWidth();
      if (width >= 80 && width === lastWidth) stableFrames += 1;
      else stableFrames = 0;
      lastWidth = width;
      frames += 1;
      if (stableFrames >= 2 || frames >= 45) {
        renderFrame = 0;
        const pending = mountPendingCharts();
        bindResizeObserver();
        if (pending) retryMount(token, 6);
        return;
      }
      renderFrame = requestAnimationFrame(tick);
    };
    renderFrame = requestAnimationFrame(tick);
  };

  watch(
    () => [props.isShow, props.status, props.outputData] as const,
    ([show]) => {
      disposeCharts();
      if (show) void renderCharts();
    },
    { immediate: true },
  );

  /** YYYY-MM-DD HH:mm:ss 共 19 个字符，多留 1 位避免贴边被挡住 */
  const EXPORT_DATE_COLUMN_WIDTH = 20;

  /**
   * 字段统计导出 Excel。类别列与图例共用 value_label 规则。
   * 时序：YYYY-MM-DD HH:mm:ss、字段名、count。分布：字段名、count。
   */
  const buildFieldExportSheet = (card: ChartCardView) => {
    const dimension = fieldView.value?.fieldLabel || t('字段');
    if (card.kind === 'trend' && card.trend) {
      const rows: Array<Array<string | number>> = [[t('日期'), dimension, 'count']];
      const { bucketStarts, xAxis, series } = card.trend;
      const times = bucketStarts?.length ? bucketStarts : xAxis;
      times.forEach((date, index) => {
        const exportedAt = formatStatisticsExportTime(date);
        series.forEach((item) => {
          const value = item.data[index];
          rows.push([exportedAt, item.name, typeof value === 'number' ? value : 0]);
        });
      });
      return rows.length > 1 ? rows : null;
    }
    if ((card.kind === 'ratio' || card.kind === 'bar') && card.ratio?.length) {
      const rows: Array<Array<string | number>> = [[dimension, 'count']];
      card.ratio.forEach((item) => {
        rows.push([item.name, item.value]);
      });
      return rows;
    }
    return null;
  };

  const exportFileName = (card: ChartCardView) => {
    const field = fieldView.value?.fieldLabel || '';
    const title = cardTitleText(card.title);
    return [field, title].filter(Boolean).join('-').replace(/[\\/:*?"<>|]/g, '_');
  };

  const handleExport = (key: string) => {
    const card = viewCards.value.find(item => item.key === key);
    if (!card || !isFieldStatistics.value) {
      messageWarn(t('暂无图表可导出'));
      return;
    }
    const rows = buildFieldExportSheet(card);
    if (!rows) {
      messageWarn(t('暂无图表可导出'));
      return;
    }
    try {
      const sheet = XLSX.utils.aoa_to_sheet(rows);
      const columnCount = rows[0]?.length || 0;
      sheet['!cols'] = Array.from({ length: columnCount }, () => ({ wch: EXPORT_DATE_COLUMN_WIDTH }));
      const book = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(book, sheet, 'Sheet1');
      XLSX.writeFile(book, `${exportFileName(card)}.xlsx`);
      messageSuccess(t('已导出Excel'));
    } catch {
      messageError(t('导出失败'));
    }
  };

  onBeforeUnmount(() => {
    if (legendMeasureFrame) cancelAnimationFrame(legendMeasureFrame);
    legendResizeObserver?.disconnect();
    legendResizeObserver = null;
    disposeCharts();
  });
</script>

<style lang="postcss" scoped>
  .stats-header {
    display: flex;
    height: 52px;
    align-items: center;
    gap: var(--audit-space-8);
  }

  .stats-title {
    font-size: var(--audit-font-size-lg);
    font-weight: var(--audit-font-weight-regular);
    line-height: var(--audit-line-height-lg);
    color: var(--audit-neutral-text-01);
  }

  .stats-divider {
    width: 1px;
    height: 12px;
    background: var(--audit-neutral-border-01);
    flex-shrink: 0;
  }

  .stats-time {
    font-size: var(--audit-font-size-base);
    line-height: var(--audit-line-height-base);
    color: var(--audit-neutral-text-03);
    white-space: nowrap;
  }

  .stats-body {
    display: flex;
    width: 100%;
    height: calc(100vh - 52px);
    min-height: 0;
    padding: var(--audit-space-24);
    overflow-y: auto;
    background: var(--audit-neutral-bg-03);
    flex-direction: column;
    gap: var(--audit-space-16);
    box-sizing: border-box;
  }

  .stats-placeholder,
  .chart-error {
    display: flex;
    padding: var(--audit-space-40) 0;
    font-size: var(--audit-font-size-sm);
    color: var(--audit-neutral-text-03);
    align-items: center;
    justify-content: center;
    gap: var(--audit-space-12);

    .placeholder-loading {
      animation: statistics-drawer-rotate 1s linear infinite;
    }
  }

  @keyframes statistics-drawer-rotate {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }

  .stats-card {
    width: 100%;
    padding: var(--audit-space-16) var(--audit-space-24);
    background: var(--audit-neutral-bg-04);
    border-radius: var(--audit-radius-control);
    box-shadow: var(--audit-shadow-card);
    box-sizing: border-box;
  }

  .card-head {
    display: flex;
    margin-bottom: var(--audit-space-8);
    align-items: center;
    justify-content: space-between;
  }

  .card-title {
    font-size: var(--audit-font-size-base);
    font-weight: var(--audit-font-weight-bold);
    line-height: var(--audit-line-height-base);
    color: var(--audit-neutral-text-01);
  }

  .card-extra {
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-03);
  }

  .card-hint {
    margin: var(--audit-space-8) 0 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-04);
    text-align: right;
  }

  .overview-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--audit-space-16);
  }

  .overview-item {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: var(--audit-space-4);
  }

  .overview-label {
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-03);
  }

  .overview-value {
    overflow: hidden;
    font-size: var(--audit-font-size-lg);
    line-height: var(--audit-line-height-lg);
    color: var(--audit-neutral-text-01);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .raw-tip {
    margin: 0 0 var(--audit-space-8);
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-03);
  }

  .raw-content {
    max-height: 420px;
    padding: var(--audit-space-12);
    margin: 0;
    overflow: auto;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    word-break: break-all;
    white-space: pre-wrap;
    background: var(--audit-neutral-bg-03);
    border-radius: var(--audit-radius-control);
  }

  .export-btn {
    color: var(--audit-neutral-text-02);

    .export-icon {
      margin-right: var(--audit-space-4);
      font-size: var(--audit-font-size-base);
    }
  }

  .chart-box {
    width: 100%;
    min-width: 0;
    flex-shrink: 0;

    &.is-ratio {
      flex-shrink: 0;
    }
  }

  /* 图例在画布外。一页最多 4 行，翻页在图例下方，不跟图表一起动 */
  .chart-legend-block {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--audit-space-8);
    margin-top: var(--audit-space-8);
    overflow: hidden;
  }

  .chart-legend {
    display: flex;
    flex: none;
    flex-wrap: wrap;
    align-content: flex-start;
    gap: 4px 16px;
    width: 100%;
    min-width: 0;

    &.is-measuring {
      max-height: 96px;
      overflow: hidden;
    }

    /* 4 行 = 20px * 4 + 行间距 4px * 3。flex-basis 锁住，避免被内容撑高或缩短 */
    &.is-paged {
      flex: 0 0 92px;
      height: 92px;
      min-height: 92px;
      max-height: 92px;
      overflow: hidden;
    }
  }

  .chart-legend-measure {
    position: absolute;
    top: 0;
    left: 0;
    visibility: hidden;
    pointer-events: none;
    display: flex;
    flex-wrap: wrap;
    align-content: flex-start;
    gap: 4px 16px;

    * {
      pointer-events: none;
    }
  }

  .chart-legend-pager {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: flex-end;
    gap: 2px;
  }

  .legend-page-btn {
    display: inline-flex;
    width: 20px;
    height: 20px;
    padding: 0;
    font-size: var(--audit-font-size-lg);
    color: var(--audit-neutral-text-02);
    cursor: pointer;
    background: transparent;
    border: none;
    align-items: center;
    justify-content: center;

    &:disabled {
      color: var(--audit-neutral-text-04);
      cursor: not-allowed;
    }

    .is-prev {
      transform: rotate(180deg);
    }
  }

  .legend-page-index {
    min-width: 28px;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-03);
    text-align: center;
  }

  .chart-legend-item {
    display: flex;
    max-width: 220px;
    height: 20px;
    min-width: 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    cursor: pointer;
    user-select: none;
    align-items: center;
    gap: var(--audit-space-8);

    &.is-off {
      color: var(--audit-neutral-text-04);
    }
  }

  .chart-legend-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ratio-wrap {
    display: flex;
    width: 100%;
    min-width: 0;
    min-height: 280px;
    align-items: center;
    justify-content: center;
    gap: 48px;
  }

  .ratio-legend {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    gap: var(--audit-space-12);
  }

  .legend-item {
    display: flex;
    max-width: 280px;
    min-width: 0;
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    cursor: pointer;
    user-select: none;
    align-items: center;
    gap: var(--audit-space-8);

    &.is-off {
      color: var(--audit-neutral-text-04);
    }
  }

  .legend-label {
    display: flex;
    min-width: 0;
    align-items: center;
  }

  .legend-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .legend-meta {
    flex-shrink: 0;
  }

  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .legend-tip-anchor {
    display: none;
  }
</style>

<style lang="postcss">
  .statistics-legend-popover .statistics-legend-full {
    max-width: 360px;
    line-height: 20px;
    word-break: break-all;
    white-space: normal;
    overflow-wrap: anywhere;
  }

  .bk-sideslider .bk-modal-content:has(.stats-body),
  .bk-sideslider .bk-sideslider-content:has(.stats-body) {
    height: 100%;
    min-height: calc(100vh - 52px);
    background: var(--audit-neutral-bg-03) !important;
  }
</style>
