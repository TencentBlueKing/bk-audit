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
import DOMPurify from 'dompurify';

export type ChartSanitizeErrorCode = 'INVALID_STRUCTURE';

export interface SanitizeChartResult {
  option: Record<string, any> | null;
  errorCode: ChartSanitizeErrorCode | null;
}

const DROP_KEYS = new Set([
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

const FN_WHITELIST = new Set(['datetime', 'percent', 'number', 'bytes', 'truncate']);
const TOOLTIP_TAGS = ['span', 'br', 'b', 'strong', 'div'];

const MAX_DEPTH = 20;
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

/**
 * 只改带 T 的 ISO 展示。年月日时分秒按原文字保留，去掉 T 和时区。
 * `2026-09-26`、`09-26`、时间戳都不改。
 */
const ISO_T_DISPLAY = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)(?:Z|[+-]\d{2}:?\d{2})?$/;

const unwrapIsoTDisplay = (raw: unknown): string | null => {
  if (typeof raw !== 'string') return null;
  const matched = ISO_T_DISPLAY.exec(raw.trim());
  if (!matched) return null;
  return `${matched[1]} ${matched[2]}`;
};

const displayCategoryValue = (raw: unknown) => unwrapIsoTDisplay(raw) ?? formatDisplayValue(raw);

const axisTooltipRaw = (param: Record<string, any>) => {
  if (param.axisValue != null && param.axisValue !== '') return param.axisValue;
  if (param.axisValueLabel != null && param.axisValueLabel !== '') return param.axisValueLabel;
  return '';
};

const buildNamedFn = (spec: { __fn: string, options?: Record<string, unknown> }) => {
  if (!FN_WHITELIST.has(spec.__fn)) return null;
  const options = isRecord(spec.options) ? spec.options : {};

  if (spec.__fn === 'datetime') {
    return (params: unknown) => displayCategoryValue(pickFormatterRaw(params));
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
      if (ctx.inTooltip) return undefined;
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

/** 类目原文含 T 时，轴刻度只换展示，不改 data */
const ensureIsoCategoryDisplay = (axis: unknown) => {
  asAxisList(axis).forEach((host) => {
    const categories = Array.isArray(host.data) ? host.data : [];
    if (!categories.some((item: unknown) => unwrapIsoTDisplay(item))) return;
    if (!isRecord(host.axisLabel)) host.axisLabel = {};
    if (host.axisLabel.formatter == null) {
      host.axisLabel.formatter = (params: unknown) => displayCategoryValue(pickFormatterRaw(params));
    }
  });
};

const asZoomList = (dataZoom: unknown): Record<string, any>[] => {
  if (Array.isArray(dataZoom)) return dataZoom.filter(isRecord);
  return isRecord(dataZoom) ? [dataZoom] : [];
};

const zoomAxisIndex = (zoom: Record<string, any>, horizontal: boolean) => {
  const raw = horizontal ? zoom.xAxisIndex : zoom.yAxisIndex;
  if (Array.isArray(raw)) return typeof raw[0] === 'number' ? raw[0] : 0;
  return typeof raw === 'number' && raw >= 0 ? raw : 0;
};

/** 左端标签在滑块外侧右对齐，右端标签向右延伸。边距要盖住字宽和手柄空隙 */
const dataZoomLabelInset = (text: string) => Math.max(48, Math.ceil(text.length * 7 + 24));

const bumpEdge = (current: unknown, inset: number) => (
  typeof current === 'number' && Number.isFinite(current) ? Math.max(current, inset) : inset
);

/**
 * dataZoom 手柄标签不走 axisLabel.formatter，类目原文会原样画出画布。
 * 默认 width 是占位值，会把滑块拉成坐标区全宽，left/right 因此不生效，所以时间轴要清掉 width。
 */
const attachDataZoomLabels = (option: Record<string, any>) => {
  asZoomList(option.dataZoom).forEach((zoom) => {
    if (zoom.type === 'inside') return;
    const horizontal = zoom.orient !== 'vertical';
    const axis = horizontal ? option.xAxis : option.yAxis;
    const index = zoomAxisIndex(zoom, horizontal);
    const host = asAxisList(axis)[index];
    const categories = Array.isArray(host?.data) ? host.data : [];
    if (!categories.some((item: unknown) => unwrapIsoTDisplay(item))) return;

    zoom.labelFormatter = (_value: unknown, valueStr: unknown) => {
      const raw = valueStr != null && valueStr !== '' ? valueStr : _value;
      return displayCategoryValue(raw);
    };

    const longest = categories.reduce((max: string, item: unknown) => {
      const text = displayCategoryValue(item);
      return text.length > max.length ? text : max;
    }, '');
    const inset = dataZoomLabelInset(longest);

    if (horizontal) {
      zoom.left = bumpEdge(zoom.left, inset);
      zoom.right = bumpEdge(zoom.right, inset);
      if (zoom.width == null || zoom.width === 'ph') zoom.width = null;
      return;
    }
    zoom.top = bumpEdge(zoom.top, inset);
    zoom.bottom = bumpEdge(zoom.bottom, inset);
    if (zoom.height == null || zoom.height === 'ph') zoom.height = null;
  });
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
      const title = escapeHtml(displayCategoryValue(axisTooltipRaw(list[0])));
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

/** ECharts 5.4 DataView 会把这些文案直接写入 innerHTML。 */
const escapeDataViewHtmlSinks = (value: unknown, depth = 0) => {
  if (depth > MAX_DEPTH || !value || typeof value !== 'object') return;
  if (Array.isArray(value)) {
    value.forEach(item => escapeDataViewHtmlSinks(item, depth + 1));
    return;
  }
  const option = value as Record<string, any>;
  const toolboxes = Array.isArray(option.toolbox) ? option.toolbox : [option.toolbox];
  toolboxes.filter(isRecord).forEach((toolbox) => {
    const feature = toolbox.feature;
    if (!isRecord(feature) || !isRecord(feature.dataView)) return;
    const dataView = feature.dataView;
    if (typeof dataView.title === 'string') dataView.title = escapeHtml(dataView.title);
    if (Array.isArray(dataView.lang)) {
      dataView.lang = dataView.lang.map(item => (
        typeof item === 'string' ? escapeHtml(item) : item
      ));
    }
  });
  Object.values(option).forEach(item => escapeDataViewHtmlSinks(item, depth + 1));
};

export const sanitizeChartOption = (raw: unknown): SanitizeChartResult => {
  if (!isRecord(raw)) {
    return { option: null, errorCode: 'INVALID_STRUCTURE' };
  }

  const option = sanitizeValue(raw, {
    depth: 0,
    key: '',
    inTooltip: false,
    inTitle: false,
  });
  if (!isRecord(option)) {
    return { option: null, errorCode: 'INVALID_STRUCTURE' };
  }

  resolveAllowedFormatters(option);
  stripRemainingFnSpecs(option);
  ensureIsoCategoryDisplay(option.xAxis);
  ensureIsoCategoryDisplay(option.yAxis);
  attachTooltipFormatters(option);
  attachDataZoomLabels(option);
  escapeDataViewHtmlSinks(option);
  return { option, errorCode: null };
};
