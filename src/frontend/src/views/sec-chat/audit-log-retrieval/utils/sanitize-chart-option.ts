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
import DOMPurify from 'dompurify';

export type ChartSanitizeErrorCode = 'INVALID_STRUCTURE' | 'TOO_LARGE';

export interface SanitizeChartResult {
  option: Record<string, any> | null;
  errorCode: ChartSanitizeErrorCode | null;
}

const TOP_LEVEL_ALLOW = new Set([
  'title',
  'tooltip',
  'legend',
  'grid',
  'xAxis',
  'yAxis',
  'series',
  'color',
  'textStyle',
  'dataZoom',
  'animation',
  'animationDuration',
]);

const DROP_KEYS = new Set([
  'graphic',
  'media',
  'renderItem',
  'extraCssText',
  'className',
  '__proto__',
  'constructor',
  'prototype',
]);

const TITLE_LINK_KEYS = new Set(['link', 'sublink', 'target', 'subtarget']);

const RESOURCE_KEYS = new Set([
  'symbol',
  'symbolPath',
  'image',
  'backgroundColor',
  'borderColor',
  'shadowColor',
  'color',
]);

const SERIES_TYPES = new Set(['line', 'bar', 'pie']);
const FN_WHITELIST = new Set(['datetime', 'percent', 'number', 'bytes', 'truncate']);
const TOOLTIP_TAGS = ['span', 'br', 'b', 'strong', 'div'];

const MAX_DEPTH = 20;
const MAX_SERIES = 10;
const MAX_DATA_POINTS = 2000;
const MAX_SERIALIZED = 200 * 1024;
const MIN_HEIGHT = 160;
const MAX_HEIGHT = 800;
const DEFAULT_HEIGHT = 280;

const DEFAULT_AXIS_TEMPLATE = '{marker}{seriesName}：<b>{value}</b>';
const DEFAULT_ITEM_TEMPLATE = '{marker}{name}：<b>{value}</b>（{percent}%）';

interface WalkCtx {
  depth: number;
  key: string;
  inTooltip: boolean;
  inTitle: boolean;
}

const isRecord = (value: unknown): value is Record<string, any> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

const escapeHtml = (text: string) => text
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

export const clampChartHeight = (height: unknown): number => {
  const num = Number(height);
  if (!Number.isFinite(num)) return DEFAULT_HEIGHT;
  return Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, num));
};

const isFunctionLikeString = (value: string) => {
  const trimmed = value.trim();
  return /^(async\s+)?function\b/.test(trimmed)
    || /^\(?\s*([A-Za-z_$][\w$]*|\(\s*[A-Za-z_$][\w$,\s]*\))\s*\)?\s*=>/.test(trimmed)
    || /^\(\s*\)\s*=>/.test(trimmed);
};

const isDangerousResource = (value: string) => {
  const trimmed = value.trim();
  if (/javascript:/i.test(trimmed)) return true;
  if (/image:\/\//i.test(trimmed)) return true;
  if (/url\s*\(/i.test(trimmed)) return true;
  if (/^https?:\/\//i.test(trimmed)) return true;
  if (/^data:/i.test(trimmed)) return true;
  if (trimmed.startsWith('//')) return true;
  return /[<>"';]/.test(trimmed);
};

const isFnSpec = (value: unknown): value is { __fn: string, options?: Record<string, unknown> } => (
  isRecord(value) && typeof value.__fn === 'string'
);

const emptyObject = (): Record<string, any> => ({});

const formatDisplayValue = (value: unknown): string => {
  if (value == null) return '';
  if (Array.isArray(value)) return value.map(item => formatDisplayValue(item)).join(', ');
  if (typeof value === 'object') {
    if ('value' in (value as Record<string, unknown>)) {
      return formatDisplayValue((value as Record<string, unknown>).value);
    }
    try {
      return JSON.stringify(value);
    } catch {
      return '';
    }
  }
  return String(value);
};

const pickFormatterRaw = (params: unknown): unknown => {
  if (params == null) return '';
  if (typeof params !== 'object') return params;
  const rec = params as Record<string, unknown>;
  if (rec.value != null) return rec.value;
  if (rec.name != null) return rec.name;
  if (rec.data != null) return rec.data;
  return '';
};

const pickFormatterText = (params: unknown): string => formatDisplayValue(pickFormatterRaw(params));

const toFiniteNumber = (raw: unknown): number => {
  if (typeof raw === 'number') return raw;
  if (typeof raw === 'string' && raw.trim()) return Number(raw);
  return Number.NaN;
};

/** 只认 13 位毫秒与 10 位秒时间戳；年份、序号这类数字不是时间，返回 null 交回原样输出 */
const parseEpoch = (num: number): dayjs.Dayjs | null => {
  const digits = String(Math.trunc(Math.abs(num))).length;
  if (digits === 13) return dayjs(num);
  if (digits === 10) return dayjs(num * 1000);
  return null;
};

const parseDatetimeValue = (raw: unknown): dayjs.Dayjs | null => {
  if (typeof raw === 'number') {
    return Number.isFinite(raw) ? parseEpoch(raw) : null;
  }
  if (typeof raw !== 'string') return null;
  const trimmed = raw.trim();
  if (/^-?\d+$/.test(trimmed)) {
    const num = Number(trimmed);
    return Number.isFinite(num) ? parseEpoch(num) : null;
  }
  return dayjs(trimmed);
};

const buildNamedFn = (spec: { __fn: string, options?: Record<string, unknown> }) => {
  if (!FN_WHITELIST.has(spec.__fn)) return null;
  const options = isRecord(spec.options) ? spec.options : {};

  if (spec.__fn === 'datetime') {
    const format = typeof options.format === 'string' && options.format.trim()
      ? options.format
      : 'MM-DD HH:mm';
    return (params: unknown) => {
      const raw = pickFormatterRaw(params);
      const parsed = parseDatetimeValue(raw);
      return parsed && parsed.isValid() ? parsed.format(format) : formatDisplayValue(raw);
    };
  }

  if (spec.__fn === 'percent') {
    const digits = Math.min(4, Math.max(0, Number.isFinite(Number(options.digits)) ? Number(options.digits) : 2));
    return (params: unknown) => {
      const raw = pickFormatterRaw(params);
      const num = toFiniteNumber(raw);
      return Number.isFinite(num) ? `${num.toFixed(digits)}%` : formatDisplayValue(raw);
    };
  }

  if (spec.__fn === 'number') {
    const unit = typeof options.unit === 'string' ? options.unit : '';
    return (params: unknown) => {
      const raw = pickFormatterRaw(params);
      const num = toFiniteNumber(raw);
      if (!Number.isFinite(num)) return formatDisplayValue(raw);
      const formatted = num.toLocaleString('en-US');
      return unit ? `${formatted}${unit}` : formatted;
    };
  }

  if (spec.__fn === 'bytes') {
    return (params: unknown) => {
      const raw = pickFormatterRaw(params);
      const num = toFiniteNumber(raw);
      if (!Number.isFinite(num) || num < 0) return formatDisplayValue(raw);
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      let size = num;
      let index = 0;
      while (size >= 1024 && index < units.length - 1) {
        size /= 1024;
        index += 1;
      }
      return `${size.toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
    };
  }

  const maxLength = Math.min(100, Math.max(1, Number.isFinite(Number(options.maxLength))
    ? Number(options.maxLength)
    : 12));
  return (params: unknown) => {
    const text = pickFormatterText(params);
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
  };
};

const sanitizeValue = (value: unknown, ctx: WalkCtx): unknown => {
  if (ctx.depth > MAX_DEPTH) return undefined;
  if (value == null) return value;
  if (typeof value === 'number') return Number.isFinite(value) ? value : undefined;
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') {
    if (/javascript:/i.test(value)) return undefined;
    if (ctx.key === 'formatter') {
      if (ctx.inTooltip || isFunctionLikeString(value)) return undefined;
      return value;
    }
    if (RESOURCE_KEYS.has(ctx.key) && isDangerousResource(value)) return undefined;
    return value;
  }
  if (typeof value === 'function' || typeof value === 'symbol' || typeof value === 'bigint') {
    return undefined;
  }
  if (Array.isArray(value)) {
    const next: unknown[] = [];
    value.forEach((item) => {
      const sanitized = sanitizeValue(item, {
        ...ctx,
        depth: ctx.depth + 1,
      });
      if (sanitized !== undefined) next.push(sanitized);
    });
    return next;
  }
  if (!isRecord(value)) return undefined;

  if (ctx.key === 'formatter') {
    if (ctx.inTooltip) return undefined;
    if (isFnSpec(value)) {
      const spec = emptyObject();
      spec.__fn = value.__fn;
      if (isRecord(value.options)) {
        const options = sanitizeValue(value.options, {
          depth: ctx.depth + 1,
          key: 'options',
          inTooltip: false,
          inTitle: false,
        });
        if (isRecord(options)) spec.options = options;
      }
      return spec;
    }
    return undefined;
  }

  const next = emptyObject();
  Object.keys(value).forEach((key) => {
    if (DROP_KEYS.has(key)) return;
    if (ctx.inTitle && TITLE_LINK_KEYS.has(key)) return;
    if (ctx.inTooltip && key === 'formatter') return;
    if (key === 'formatter' && (typeof value[key] === 'number' || typeof value[key] === 'boolean')) return;
    const sanitized = sanitizeValue(value[key], {
      depth: ctx.depth + 1,
      key,
      inTooltip: ctx.inTooltip || key === 'tooltip',
      inTitle: ctx.inTitle || key === 'title',
    });
    if (sanitized !== undefined) next[key] = sanitized;
  });
  return next;
};

const asAxisList = (axis: unknown): Record<string, any>[] => {
  if (Array.isArray(axis)) return axis.filter(isRecord);
  return isRecord(axis) ? [axis] : [];
};

const resolveAllowedFormatters = (option: Record<string, any>) => {
  const resolveHost = (candidate: unknown) => {
    if (!isRecord(candidate)) return;
    const host: Record<string, any> = candidate;
    if (!isFnSpec(host.formatter)) return;
    const fn = buildNamedFn(host.formatter);
    if (fn) host.formatter = fn;
    else delete host.formatter;
  };

  resolveHost(option.legend);
  asAxisList(option.xAxis).forEach(axis => resolveHost(axis.axisLabel));
  asAxisList(option.yAxis).forEach(axis => resolveHost(axis.axisLabel));
  (Array.isArray(option.series) ? option.series : []).forEach((series) => {
    if (isRecord(series)) resolveHost(series.label);
  });
};

const stripRemainingFnSpecs = (value: unknown, depth = 0) => {
  if (!value || typeof value !== 'object' || depth > MAX_DEPTH) return;
  if (Array.isArray(value)) {
    value.forEach(item => stripRemainingFnSpecs(item, depth + 1));
    return;
  }
  const rec = value as Record<string, any>;
  if (isFnSpec(rec.formatter)) delete rec.formatter;
  Object.keys(rec).forEach((key) => {
    if (key === 'formatter' && typeof rec[key] === 'function') return;
    stripRemainingFnSpecs(rec[key], depth + 1);
  });
};

const canonTemplate = (value: string) => value
  .replace(/<br\s*\/?>/gi, '<br>')
  .replace(/\s+/g, ' ')
  .trim();

const resolveTooltipTemplate = (raw: unknown, trigger: string) => {
  const fallback = trigger === 'axis' ? DEFAULT_AXIS_TEMPLATE : DEFAULT_ITEM_TEMPLATE;
  if (typeof raw !== 'string' || !raw.trim()) return fallback;
  const sanitized = DOMPurify.sanitize(raw, {
    ALLOWED_TAGS: TOOLTIP_TAGS,
    ALLOWED_ATTR: [],
  });
  if (!sanitized || canonTemplate(raw) !== canonTemplate(sanitized)) return fallback;
  return sanitized;
};

const renderTooltipTemplate = (template: string, param: Record<string, any>) => {
  const marker = typeof param.marker === 'string' ? param.marker : '';
  const seriesName = escapeHtml(String(param.seriesName ?? ''));
  const name = escapeHtml(String(param.name ?? ''));
  const value = escapeHtml(formatDisplayValue(param.value));
  const percent = escapeHtml(String(param.percent ?? ''));
  return template
    .replace(/\{marker\}/g, marker)
    .replace(/\{seriesName\}/g, seriesName)
    .replace(/\{name\}/g, name)
    .replace(/\{value\}/g, value)
    .replace(/\{percent\}/g, percent);
};

export const createTooltipFormatter = (trigger: unknown, templateRaw: unknown) => {
  const resolvedTrigger = trigger === 'axis' ? 'axis' : 'item';
  const template = resolveTooltipTemplate(templateRaw, resolvedTrigger);
  return (params: unknown) => {
    const list = Array.isArray(params) ? params.filter(isRecord) : isRecord(params) ? [params] : [];
    if (!list.length) return '';
    if (resolvedTrigger === 'axis') {
      const title = escapeHtml(String(list[0].axisValueLabel ?? list[0].axisValue ?? ''));
      const lines = list.map(item => renderTooltipTemplate(template, item));
      return [title, ...lines].join('<br/>');
    }
    return renderTooltipTemplate(template, list[0]);
  };
};

const attachTooltipFormatters = (option: Record<string, any>) => {
  const apply = (host: unknown) => {
    if (!isRecord(host) || !isRecord(host.tooltip)) return;
    const tooltip = host.tooltip;
    const template = tooltip.__template;
    delete tooltip.formatter;
    delete tooltip.__template;
    tooltip.formatter = createTooltipFormatter(tooltip.trigger, template);
  };

  apply(option);
  apply(option.legend);
  (Array.isArray(option.series) ? option.series : []).forEach(apply);
};

const countSeriesData = (series: Record<string, any>[]) => (
  series.reduce((sum, item) => sum + (Array.isArray(item.data) ? item.data.length : 0), 0)
);

export interface SanitizeChartLimits {
  maxSeries?: number;
  maxDataPoints?: number;
  maxSerialized?: number;
}

/**
 * 字段统计的 option 由前端按后端固定语义包构造，容量已被后端的时间桶和 top_n 上限约束，
 * 不该套用防 LLM 失控的阈值；消毒规则本身仍然全部生效。
 */
export const FIELD_STATISTICS_LIMITS: SanitizeChartLimits = {
  maxSeries: 24,
  maxDataPoints: 60000,
  maxSerialized: 4 * 1024 * 1024,
};

export const sanitizeChartOption = (
  raw: unknown,
  limits: SanitizeChartLimits = {},
): SanitizeChartResult => {
  const maxSeries = limits.maxSeries ?? MAX_SERIES;
  const maxDataPoints = limits.maxDataPoints ?? MAX_DATA_POINTS;
  const maxSerialized = limits.maxSerialized ?? MAX_SERIALIZED;

  if (!isRecord(raw)) {
    return { option: null, errorCode: 'INVALID_STRUCTURE' };
  }

  let serialized = '';
  try {
    serialized = JSON.stringify(raw);
  } catch {
    return { option: null, errorCode: 'INVALID_STRUCTURE' };
  }
  if (!serialized) {
    return { option: null, errorCode: 'INVALID_STRUCTURE' };
  }
  if (serialized.length > maxSerialized) {
    return { option: null, errorCode: 'TOO_LARGE' };
  }

  const option = emptyObject();
  Object.keys(raw).forEach((key) => {
    if (!TOP_LEVEL_ALLOW.has(key) || DROP_KEYS.has(key)) return;
    const sanitized = sanitizeValue(raw[key], {
      depth: 1,
      key,
      inTooltip: key === 'tooltip',
      inTitle: key === 'title',
    });
    if (sanitized !== undefined) option[key] = sanitized;
  });

  const seriesSource = Array.isArray(option.series)
    ? option.series
    : isRecord(option.series) ? [option.series] : [];
  const series = seriesSource.filter(item => (
    isRecord(item) && SERIES_TYPES.has(String(item.type || ''))
  ));
  if (!series.length) {
    return { option: null, errorCode: 'INVALID_STRUCTURE' };
  }
  if (series.length > maxSeries || countSeriesData(series) > maxDataPoints) {
    return { option: null, errorCode: 'TOO_LARGE' };
  }
  option.series = series;

  resolveAllowedFormatters(option);
  stripRemainingFnSpecs(option);
  attachTooltipFormatters(option);
  return { option, errorCode: null };
};
