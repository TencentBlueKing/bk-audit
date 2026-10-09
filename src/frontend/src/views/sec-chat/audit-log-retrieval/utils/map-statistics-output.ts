/*
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
*/
import dayjs from 'dayjs';
import type { EChartsOption } from 'echarts';

import type {
  AiFieldStatisticsOutput,
  AiStatisticsDistributionGroup,
  AiStatisticsNumericSummary,
} from '@model/ai-assistant/types';

import {
  type ChartSanitizeErrorCode,
  clampChartHeight,
} from './sanitize-chart-option';

const PALETTE = [
  '#3A84FF',
  '#66C0DA',
  '#94D6C4',
  '#F6D96D',
  '#F8B551',
  '#F06A6A',
  '#FF6A8A',
  '#D968FF',
  '#A3D8F0',
  '#C4B5FD',
];

/** 合成组固定色：其他偏灰、缺失更浅，不与真实类别抢色板 */
const OTHER_COLOR = '#979BA5';
const MISSING_COLOR = '#DCDEE5';

const MAX_CHARTS = 8;
const DEFAULT_CARD_HEIGHT = 280;
const EMPTY_TEXT = '—';

export const TREND_CARD_TITLE = '时序趋势';
export const RATIO_CARD_TITLE = '维度占比';

export const isStatisticsAttachmentType = (type?: string) => (
  type === 'AI_STATISTICS' || type === 'FIELD_STATISTICS'
);

export const isFieldStatisticsType = (type?: string) => type === 'FIELD_STATISTICS';

/**
 * 比例协议为 0～1。页面保留两位；null 显示「—」，计数为 0 显示 0.00%。
 * 舍入后变成 0 的正比例用 count/total 重算，仍小于 0.01% 时显示 <0.01%。
 */
export const formatStatisticsRatio = (
  ratio?: number | null,
  count?: number | null,
  total?: number | null,
) => {
  let value = ratio;
  const roundedAway = typeof value !== 'number' || !Number.isFinite(value) || value === 0;
  if (
    roundedAway
    && typeof count === 'number'
    && count > 0
    && typeof total === 'number'
    && total > 0
  ) {
    value = count / total;
  }
  if (typeof value !== 'number' || !Number.isFinite(value)) return EMPTY_TEXT;
  if (value === 0) return '0.00%';
  const percent = value * 100;
  if (percent > 0 && percent < 0.01) return '<0.01%';
  return `${percent.toFixed(2)}%`;
};

export const formatStatisticsCount = (count?: number | null) => {
  if (typeof count !== 'number' || !Number.isFinite(count)) return EMPTY_TEXT;
  return count.toLocaleString('en-US');
};

/** 数值摘要沿用后端已收到的四位小数，不再按有效数字重排 */
export const formatNumericValue = (value?: number | null) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return EMPTY_TEXT;
  if (Number.isInteger(value)) return value.toLocaleString('en-US');
  return String(value);
};

export const formatNumericValueFull = (value?: number | null) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return EMPTY_TEXT;
  return String(value);
};

/** 合成组与空字符串的固定文案由调用方注入，映射层不依赖 i18n */
export interface StatisticsLabelDict {
  other: string;
  missing: string;
  emptyString: string;
}

const DEFAULT_LABELS: StatisticsLabelDict = {
  other: '其他',
  missing: '缺失',
  emptyString: '空字符串',
};

/**
 * 类别标签：OTHER / MISSING 文案固定，VALUE 保留原始标量。
 * 合成组的 value 同为 null，只能按 kind 区分，不能按文案合并。
 */
const resolveGroupLabel = (group: AiStatisticsDistributionGroup, labels: StatisticsLabelDict) => {
  if (group.kind === 'OTHER') return labels.other;
  if (group.kind === 'MISSING') return labels.missing;
  const { value } = group;
  if (value === null || value === undefined) return EMPTY_TEXT;
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  const text = String(value);
  return text === '' ? labels.emptyString : text;
};

const VALUE_TYPE_SUFFIX: Record<string, string> = {
  number: '数字',
  string: '字符串',
  boolean: '布尔',
};

/**
 * 图例按名称区分类别。真实值撞上「其他 / 缺失」时标成原始值；
 * 同一文案同时有数字和字符串时再标类型，避免饼图按名称合并。
 */
const disambiguateGroupLabels = (
  groups: AiStatisticsDistributionGroup[],
  labels: StatisticsLabelDict,
) => {
  const bases = groups.map((group) => {
    const name = resolveGroupLabel(group, labels);
    const collided = group.kind === 'VALUE' && (name === labels.other || name === labels.missing);
    return {
      group,
      name: collided ? `${name}（原始值）` : name,
      valueType: group.kind === 'VALUE' ? String(group.value_type || '') : '',
    };
  });
  const typesByName = new Map<string, Set<string>>();
  bases.forEach((item) => {
    if (item.group.kind !== 'VALUE' || !item.valueType) return;
    const types = typesByName.get(item.name) || new Set<string>();
    types.add(item.valueType);
    typesByName.set(item.name, types);
  });
  return bases.map((item) => {
    const types = typesByName.get(item.name);
    if (!types || types.size < 2) return item.name;
    const suffix = VALUE_TYPE_SUFFIX[item.valueType];
    return suffix ? `${item.name}（${suffix}）` : item.name;
  });
};

const resolveGroupColor = (group: AiStatisticsDistributionGroup, valueIndex: number) => {
  if (group.kind === 'OTHER') return OTHER_COLOR;
  if (group.kind === 'MISSING') return MISSING_COLOR;
  return PALETTE[valueIndex % PALETTE.length];
};

/**
 * 时间桶标签直接取 ISO 字符串的日期时间片段。
 * bucket_starts 已是服务端有效时区的表示，转本地时区会让刻度与 timezone 声明不一致。
 */
const formatBucketLabel = (bucketStart: string, interval: string) => {
  const matched = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(String(bucketStart || ''));
  if (!matched) return String(bucketStart || '');
  const [, , month, day, hour, minute] = matched;
  if (interval === 'DAY') return `${month}-${day}`;
  return `${month}-${day} ${hour}:${minute}`;
};

export interface StatisticsRatioItem {
  groupId: string;
  kind: string;
  name: string;
  value: number;
  valueText: string;
  percent: string;
  color: string;
}

export interface StatisticsTrendSeries {
  groupId: string;
  name: string;
  color: string;
  data: Array<number | null>;
}

export interface StatisticsTrendView {
  xAxis: string[];
  series: StatisticsTrendSeries[];
  /** 实际时间桶粒度，原样展示不重分桶 */
  effectiveInterval: string;
  timezone: string;
}

export interface StatisticsChartCard {
  key: string;
  title: string;
  kind: 'trend' | 'ratio' | 'echarts';
  height: number;
  errorCode?: ChartSanitizeErrorCode | null;
  trend?: StatisticsTrendView;
  ratio?: StatisticsRatioItem[];
  option?: EChartsOption;
}

export interface StatisticsOverviewView {
  totalCount: number;
  totalText: string;
  presentText: string;
  missingText: string;
  presentRatioText: string;
}

/** SUCCESS 但没有可画的数据，两种原因要分开提示 */
export type StatisticsEmptyKind = 'no-logs' | 'field-missing' | null;

export interface FieldStatisticsView {
  fieldLabel: string;
  isNumeric: boolean;
  overview: StatisticsOverviewView;
  numericSummary: AiStatisticsNumericSummary | null;
  emptyKind: StatisticsEmptyKind;
  /** 实际统计范围，来自 query_summary，不是附件创建时间 */
  scopeText: string;
  effectiveInterval: string;
  timezone: string;
  cards: StatisticsChartCard[];
}

const isRecord = (value: unknown): value is Record<string, any> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

const mapRatioItems = (
  output: AiFieldStatisticsOutput,
  labels: StatisticsLabelDict,
): StatisticsRatioItem[] => {
  const groups = Array.isArray(output.distribution?.groups) ? output.distribution.groups : [];
  const names = disambiguateGroupLabels(groups, labels);
  const total = output.overview?.total_count;
  let valueIndex = 0;
  return groups.map((group, index) => {
    const color = resolveGroupColor(group, valueIndex);
    if (group.kind !== 'OTHER' && group.kind !== 'MISSING') valueIndex += 1;
    const count = Number(group.count ?? 0);
    return {
      groupId: String(group.group_id ?? ''),
      kind: String(group.kind ?? ''),
      name: names[index],
      value: count,
      valueText: formatStatisticsCount(count),
      percent: formatStatisticsRatio(group.ratio, count, total),
      color,
    };
  });
};

/**
 * 时序按 group_id 与分布对齐。counts 协议上与 bucket_starts 等长且空桶为 0，
 * 长度或类型不符时缺口补 null——不能补 0，否则脏数据会被画成真实的零点。
 */
const mapTrend = (
  output: AiFieldStatisticsOutput,
  ratioItems: StatisticsRatioItem[],
): StatisticsTrendView | null => {
  const timeSeries = output.time_series;
  const buckets = Array.isArray(timeSeries?.bucket_starts) ? timeSeries.bucket_starts : [];
  const seriesSource = Array.isArray(timeSeries?.series) ? timeSeries.series : [];
  if (!buckets.length || !seriesSource.length) return null;

  const interval = String(timeSeries?.effective_interval || '');
  const groupMap = new Map(ratioItems.map(item => [item.groupId, item]));
  const series = seriesSource.map((item, index) => {
    const groupId = String(item.group_id ?? '');
    const matched = groupMap.get(groupId);
    const counts = Array.isArray(item.counts) ? item.counts : [];
    return {
      groupId,
      name: matched?.name || groupId,
      color: matched?.color || PALETTE[index % PALETTE.length],
      data: buckets.map((_, bucketIndex) => {
        const value = counts[bucketIndex];
        return typeof value === 'number' && Number.isFinite(value) ? value : null;
      }),
    };
  });

  return {
    xAxis: buckets.map(item => formatBucketLabel(item, interval)),
    series,
    effectiveInterval: interval,
    timezone: String(timeSeries?.timezone || ''),
  };
};

const resolveEmptyKind = (output: AiFieldStatisticsOutput): StatisticsEmptyKind => {
  const total = Number(output.overview?.total_count ?? 0);
  const present = Number(output.overview?.present_count ?? 0);
  if (!total) return 'no-logs';
  if (!present) return 'field-missing';
  return null;
};

/** query_summary 的时间是带时区的 ISO 串，按本地时区展示成和其它卡片一致的格式 */
const formatScopeTime = (value?: string) => {
  if (!value) return '';
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm:ss') : value;
};

const resolveScopeText = (output: AiFieldStatisticsOutput) => {
  const summary = output.query_summary;
  if (!summary?.start_time || !summary?.end_time) return '';
  return `${formatScopeTime(summary.start_time)} ~ ${formatScopeTime(summary.end_time)}`;
};

/** FIELD_STATISTICS 固定语义包 → 面板视图模型，只认协议字段 */
export const mapFieldStatisticsOutput = (
  output: AiFieldStatisticsOutput,
  labels: Partial<StatisticsLabelDict> = {},
): FieldStatisticsView => {
  const mergedLabels = { ...DEFAULT_LABELS, ...labels };
  const { overview } = output;
  const ratioItems = mapRatioItems(output, mergedLabels);
  const trend = mapTrend(output, ratioItems);
  const emptyKind = resolveEmptyKind(output);

  const cards: StatisticsChartCard[] = [];
  if (trend) {
    cards.push({
      key: 'trend',
      title: TREND_CARD_TITLE,
      kind: 'trend',
      height: clampChartHeight(DEFAULT_CARD_HEIGHT),
      trend,
    });
  }
  if (ratioItems.some(item => item.value > 0)) {
    cards.push({
      key: 'ratio',
      title: RATIO_CARD_TITLE,
      kind: 'ratio',
      height: clampChartHeight(DEFAULT_CARD_HEIGHT),
      ratio: ratioItems,
    });
  }

  return {
    fieldLabel: output.field?.display_name || output.field?.raw_name || '',
    isNumeric: String(output.statistics_kind || '') === 'NUMERIC',
    overview: {
      totalCount: Number(overview?.total_count ?? 0),
      totalText: formatStatisticsCount(overview?.total_count),
      presentText: formatStatisticsCount(overview?.present_count),
      missingText: formatStatisticsCount(overview?.missing_count),
      presentRatioText: formatStatisticsRatio(
        overview?.present_ratio,
        overview?.present_count,
        overview?.total_count,
      ),
    },
    numericSummary: String(output.statistics_kind || '') === 'NUMERIC'
      ? output.numeric_summary || null
      : null,
    emptyKind,
    scopeText: resolveScopeText(output),
    effectiveInterval: trend?.effectiveInterval || '',
    timezone: trend?.timezone || '',
    cards,
  };
};

/** 原文不是约定的图表数组时的降级原因 */
export type StatisticsContentFailure = 'NOT_JSON' | 'NOT_ARRAY' | 'EMPTY' | 'INVALID_ITEM';

export interface StatisticsChartsResult {
  charts: StatisticsChartCard[];
  /** 非空表示整份原文不可用，面板降级展示 content 原文 */
  failure: StatisticsContentFailure | null;
}

const errorCard = (index: number, errorCode: ChartSanitizeErrorCode, title?: string, height?: unknown) => ({
  key: `echarts-${index}`,
  title: title || '统计图表',
  kind: 'echarts' as const,
  height: clampChartHeight(height),
  errorCode,
});

const mapChartItem = (item: unknown, index: number): StatisticsChartCard | null => {
  if (!isRecord(item)) return null;
  const title = typeof item.title === 'string' ? item.title.trim() : '';
  if (!title || !isRecord(item.echarts_option)) return null;
  return {
    key: `echarts-${index}`,
    title,
    kind: 'echarts',
    height: clampChartHeight(typeof item.height === 'number' ? item.height : undefined),
    option: item.echarts_option as EChartsOption,
  };
};

/**
 * AI_STATISTICS 的 output_data.content 是标签内原文，后端不校验 JSON / ECharts。
 * 只接受 [{title, height, echarts_option}]；元素级不合法保留错误卡，
 * 整份不可用时返回 failure，由面板展示原文并提供重新生成。
 */
export const parseStatisticsCharts = (content?: string | null): StatisticsChartsResult => {
  const text = String(content ?? '').trim();
  if (!text) return { charts: [], failure: 'NOT_JSON' };

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { charts: [], failure: 'NOT_JSON' };
  }
  if (!Array.isArray(parsed)) return { charts: [], failure: 'NOT_ARRAY' };
  if (!parsed.length) return { charts: [], failure: 'EMPTY' };

  const mapped = parsed.slice(0, MAX_CHARTS).map((item, index) => mapChartItem(item, index));
  if (mapped.every(item => item === null)) return { charts: [], failure: 'INVALID_ITEM' };

  return {
    charts: mapped.map((item, index) => item || errorCard(index, 'INVALID_STRUCTURE')),
    failure: null,
  };
};

const AXIS_STYLE = {
  color: '#979ba5',
  fontSize: 12,
};

export const buildTrendOption = (trend: StatisticsTrendView): EChartsOption => ({
  color: trend.series.map(item => item.color),
  textStyle: {
    color: '#63656e',
    fontSize: 12,
  },
  tooltip: { trigger: 'axis' },
  legend: {
    // 默认 left:center 会把整组图例居中；铺满宽度后从左侧往下排
    left: 0,
    right: 0,
    bottom: 0,
    icon: 'circle',
    itemWidth: 8,
    itemHeight: 8,
    itemGap: 24,
    textStyle: {
      color: '#4d4f56',
      fontSize: 12,
    },
    data: trend.series.map(item => item.name),
  },
  grid: {
    left: 48,
    right: 24,
    top: 24,
    bottom: trend.series.length > 6 ? 96 : trend.series.length > 1 ? 72 : 48,
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: trend.xAxis,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#dcdee5' } },
    splitLine: { show: false },
    axisLabel: AXIS_STYLE,
  },
  yAxis: {
    type: 'value',
    min: 0,
    axisLine: { lineStyle: { color: '#dcdee5' } },
    axisLabel: AXIS_STYLE,
    splitLine: { lineStyle: { color: '#f0f1f5' } },
  },
  series: trend.series.map(item => ({
    name: item.name,
    type: 'line' as const,
    smooth: true,
    symbol: 'none',
    // 桶数可达后端上限 1440，多类别叠加时按像素抽样，避免逐点绘制
    sampling: 'lttb' as const,
    lineStyle: { width: 2 },
    areaStyle: { opacity: 0.2 },
    data: item.data,
  })) as EChartsOption['series'],
});

export const buildRatioOption = (ratio: StatisticsRatioItem[]): EChartsOption => ({
  color: ratio.map(item => item.color),
  textStyle: {
    color: '#63656e',
    fontSize: 12,
  },
  tooltip: { trigger: 'item' },
  series: [
    {
      type: 'pie',
      radius: ['48%', '72%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      label: { show: false },
      labelLine: { show: false },
      data: ratio.map(item => ({ name: item.name, value: item.value })),
    },
  ],
});
