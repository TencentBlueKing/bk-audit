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
              v-if="!isCardBroken(card)"
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
            <div class="ratio-legend">
              <div
                v-for="item in card.ratio || []"
                :key="item.groupId"
                class="legend-item">
                <span
                  class="legend-dot"
                  :style="{ background: item.color }" />
                <span>{{ item.name }}：{{ item.valueText }} ( {{ item.percent }} )</span>
              </div>
            </div>
          </div>
          <template v-else>
            <div
              :ref="el => setChartRef(card.key, el)"
              class="chart-box"
              :style="{ height: `${card.height}px` }" />
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
  </audit-sideslider>
</template>

<script lang="ts" setup>
  import * as echarts from 'echarts';
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
    buildRatioOption,
    buildTrendOption,
    formatNumericValue,
    formatNumericValueFull,
    formatStatisticsCount,
    isFieldStatisticsType,
    mapFieldStatisticsOutput,
    type StatisticsChartCard,
    type StatisticsContentFailure,
    type StatisticsRatioItem,
    parseStatisticsCharts,
    RATIO_CARD_TITLE,
    TREND_CARD_TITLE,
  } from '../utils/map-statistics-output';
  import {
    type ChartSanitizeErrorCode,
    FIELD_STATISTICS_LIMITS,
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

  /** 饼图导出画布宽度：左侧环图 + 右侧竖排图例 */
  const RATIO_EXPORT_WIDTH = 720;

  const chartEls = new Map<string, HTMLElement>();
  const chartInstances = new Map<string, echarts.ECharts>();
  let resizeObserver: ResizeObserver | null = null;
  let renderTimer: ReturnType<typeof setTimeout> | null = null;
  let renderToken = 0;

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
    if (!view?.effectiveInterval) return '';
    return [`${t('时间粒度')}：${view.effectiveInterval}`, view.timezone]
      .filter(Boolean)
      .join(' · ');
  });

  const cardTitleText = (title?: string) => {
    if (!title) return t('数据统计');
    return BUILTIN_CARD_TITLES.has(title) ? t(title) : title;
  };

  const errorText = (errorCode: ChartSanitizeErrorCode) => (
    errorCode === 'TOO_LARGE' ? t('数据量超出渲染上限') : t('图表配置不合法')
  );

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

  const resolveRawOption = (card: StatisticsChartCard) => {
    if (card.errorCode) return null;
    if (card.option) return card.option;
    if (card.kind === 'trend' && card.trend) return buildTrendOption(card.trend);
    if (card.kind === 'ratio' && card.ratio?.length) return buildRatioOption(card.ratio);
    return null;
  };

  const viewCards = computed(() => {
    const cards = fieldView.value?.cards || aiResult.value?.charts || [];
    return cards.map((card) => {
      if (card.errorCode) return card;
      // 构造与消毒都在渲染期执行，任何意外都收敛成错误卡，不让整个抽屉挂掉
      try {
        const rawOption = resolveRawOption(card);
        if (!rawOption) {
          return {
            ...card,
            errorCode: 'INVALID_STRUCTURE' as const,
            option: undefined,
          };
        }
        const { option, errorCode } = sanitizeChartOption(
          rawOption,
          card.kind === 'echarts' ? {} : FIELD_STATISTICS_LIMITS,
        );
        return {
          ...card,
          option: option ? markRaw(option) : undefined,
          errorCode,
        };
      } catch {
        return {
          ...card,
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
    chartInstances.forEach((chart) => {
      try {
        chart.resize();
      } catch {
        // 抽屉收起时容器已销毁，resize 失败无需打断其它图表
      }
    });
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

  const disposeCharts = () => {
    renderToken += 1;
    if (renderTimer) {
      clearTimeout(renderTimer);
      renderTimer = null;
    }
    resizeObserver?.disconnect();
    resizeObserver = null;
    chartInstances.forEach(chart => chart.dispose());
    chartInstances.clear();
    if (mountFailedKeys.value.size) mountFailedKeys.value = new Set();
  };

  const renderCharts = async () => {
    const token = renderToken;
    await nextTick();
    if (token !== renderToken) return;
    if (renderTimer) clearTimeout(renderTimer);
    renderTimer = setTimeout(() => {
      if (token !== renderToken) return;
      const pending = mountPendingCharts();
      resizeCharts();
      bindResizeObserver();
      if (pending) retryMount(token, 3);
      renderTimer = null;
    }, 320);
  };

  watch(
    () => [props.isShow, props.status, props.outputData] as const,
    ([show]) => {
      disposeCharts();
      if (show) void renderCharts();
    },
    { immediate: true },
  );

  /** 屏上饼图关了 label，名称数值都在 DOM 图例里，canvas 截图看不到，导出要补一份 echarts 图例 */
  const buildRatioExportOption = (ratio: StatisticsRatioItem[]) => {
    const option = buildRatioOption(ratio);
    const series = Array.isArray(option.series) ? option.series[0] : undefined;
    return {
      ...option,
      // 导出是同步取像素，留着动画只会截到第 0 帧的空环
      animation: false,
      legend: {
        orient: 'vertical',
        right: 24,
        top: 'center',
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 12,
        textStyle: { color: '#4d4f56', fontSize: 12 },
      },
      series: [{
        ...series,
        center: ['28%', '50%'],
        data: ratio.map(item => ({
          name: `${item.name}：${item.valueText}（${item.percent}）`,
          value: item.value,
        })),
      }],
    };
  };

  /** 离屏渲染，避免改动屏上实例导致饼图重播入场动画 */
  const exportRatioDataUrl = (ratio: StatisticsRatioItem[], height: number) => {
    const host = document.createElement('div');
    host.style.cssText = `position:fixed;left:-99999px;top:0;width:${RATIO_EXPORT_WIDTH}px;height:${height}px;`;
    document.body.appendChild(host);
    const chart = echarts.init(host);
    try {
      chart.setOption(buildRatioExportOption(ratio), true);
      return chart.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#fff',
      });
    } finally {
      chart.dispose();
      host.remove();
    }
  };

  const handleExport = (key: string) => {
    const card = viewCards.value.find(item => item.key === key);
    const chart = chartInstances.get(key);
    if (!card || !chart) {
      messageWarn(t('暂无图表可导出'));
      return;
    }
    try {
      const url = card.kind === 'ratio' && card.ratio?.length
        ? exportRatioDataUrl(card.ratio, card.height)
        : chart.getDataURL({
          type: 'png',
          pixelRatio: 2,
          backgroundColor: '#fff',
        });
      const link = document.createElement('a');
      link.href = url;
      link.download = `${cardTitleText(card.title)}.png`;
      link.click();
      messageSuccess(t('图表已导出'));
    } catch {
      messageError(t('导出失败'));
    }
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
    min-height: calc(100vh - 52px);
    padding: var(--audit-space-24);
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

    &.is-ratio {
      flex-shrink: 0;
    }
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
    font-size: var(--audit-font-size-sm);
    line-height: var(--audit-line-height-sm);
    color: var(--audit-neutral-text-02);
    align-items: center;
    gap: var(--audit-space-8);
  }

  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
</style>

<style lang="postcss">
  .bk-sideslider .bk-modal-content:has(.stats-body),
  .bk-sideslider .bk-sideslider-content:has(.stats-body) {
    height: 100%;
    min-height: calc(100vh - 52px);
    background: var(--audit-neutral-bg-03) !important;
  }
</style>
