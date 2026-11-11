import dayjs from 'dayjs';
import { describe, expect, it } from 'vitest';

import {
  clampChartHeight,
  sanitizeChartOption,
} from '../../src/views/sec-chat/audit-log-retrieval/utils/sanitize-chart-option';

const validSeries = [{ type: 'line', name: '新增', data: [20, 35, 28] }];

const withSeries = (extra: Record<string, unknown> = {}) => ({
  series: validSeries,
  xAxis: { type: 'category', data: ['2026-03-03', '2026-03-05', '2026-03-07'] },
  yAxis: { type: 'value' },
  ...extra,
});

const SKILL_COMPLIANT_PACKAGE = [
  {
    title: '时序趋势',
    height: 280,
    echarts_option: {
      color: ['#ea3636', '#2dcb56'],
      textStyle: { color: '#63656e', fontSize: 12 },
      animationDuration: 300,
      tooltip: { trigger: 'axis' },
      legend: {
        bottom: 0,
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 12,
        data: ['新增', '已处理'],
      },
      grid: { left: 48, right: 24, top: 24, bottom: 72, containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: ['2026-03-03', '2026-03-05', '2026-03-07'],
        axisLine: { lineStyle: { color: '#dcdee5' } },
        splitLine: { show: false },
        axisLabel: {
          color: '#979ba5',
          formatter: { __fn: 'datetime', options: { format: 'M-D' } },
        },
      },
      yAxis: {
        type: 'value',
        min: 0,
        axisLine: { lineStyle: { color: '#dcdee5' } },
        splitLine: { lineStyle: { color: '#f0f1f5' } },
        axisLabel: { color: '#979ba5' },
      },
      series: [
        { name: '新增', type: 'line', smooth: true, symbol: 'none', areaStyle: { opacity: 0.2 }, data: [20, 35, 28] },
        { name: '已处理', type: 'line', smooth: true, symbol: 'none', areaStyle: { opacity: 0.2 }, data: [10, 18, 22] },
      ],
    },
  },
  {
    title: '维度占比',
    height: 260,
    echarts_option: {
      color: ['#2dcb56', '#ea3636'],
      textStyle: { color: '#63656e', fontSize: 12 },
      animationDuration: 300,
      tooltip: { trigger: 'item', __template: '{marker}{name}' },
      legend: {
        orient: 'vertical',
        right: 40,
        top: 'center',
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 12,
      },
      series: [{
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        data: [
          { name: '成功：528（31.7%）', value: 528 },
          { name: '失败：308（24.68%）', value: 308 },
        ],
      }],
    },
  },
];

describe('sanitizeChartOption', () => {
  it('drops tooltip.formatter xss payloads at every tooltip subtree', () => {
    const xss = '<img src=x onerror=alert(1)>';
    const { option, errorCode } = sanitizeChartOption(withSeries({
      tooltip: { trigger: 'axis', formatter: xss, extraCssText: 'background:url(http://evil)' },
      legend: { tooltip: { formatter: xss } },
      series: [{
        type: 'line',
        data: [1],
        tooltip: { formatter: xss },
      }],
    }));
    expect(errorCode).toBeNull();
    expect(option?.tooltip.extraCssText).toBeUndefined();
    expect(typeof option?.tooltip.formatter).toBe('function');
    expect(typeof option?.legend.tooltip.formatter).toBe('function');
    expect(typeof option?.series[0].tooltip.formatter).toBe('function');
    const html = option?.series[0].tooltip.formatter({
      marker: '<span>dot</span>',
      name: '<img src=x>',
      value: 12,
      percent: 10,
    });
    expect(html).not.toContain('onerror');
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img src=x&gt;');
  });

  it('drops title.link javascript and resource urls', () => {
    const { option, errorCode } = sanitizeChartOption(withSeries({
      title: {
        text: '趋势',
        link: 'javascript:alert(1)',
        sublink: 'https://evil.example',
        target: 'blank',
      },
      series: [{ type: 'line', data: [1], symbol: 'image://http://evil/x.png' }],
    }));
    expect(errorCode).toBeNull();
    expect(option?.title.link).toBeUndefined();
    expect(option?.title.sublink).toBeUndefined();
    expect(option?.title.target).toBeUndefined();
    expect(option?.series[0].symbol).toBeUndefined();
  });

  it('drops media/graphic and prototype pollution keys', () => {
    const raw: Record<string, unknown> = withSeries({
      media: [{ query: {}, option: { graphic: [{ type: 'text', style: { text: 'x' } }] } }],
      graphic: [{ type: 'text' }],
    });
    Object.defineProperty(raw, '__proto__', { value: { polluted: true }, enumerable: true });
    const { option, errorCode } = sanitizeChartOption(raw);
    expect(errorCode).toBeNull();
    expect(option?.media).toBeUndefined();
    expect(option?.graphic).toBeUndefined();
    expect(Object.prototype.hasOwnProperty.call(option, '__proto__')).toBe(false);
    expect(({} as Record<string, unknown>).polluted).toBeUndefined();
  });

  it('rejects 2001 data points as TOO_LARGE', () => {
    const { option, errorCode } = sanitizeChartOption(withSeries({
      series: [{ type: 'line', data: Array.from({ length: 2001 }, (_, index) => index) }],
    }));
    expect(option).toBeNull();
    expect(errorCode).toBe('TOO_LARGE');
  });

  it('rejects series filtered to empty as INVALID_STRUCTURE', () => {
    const { errorCode } = sanitizeChartOption({
      series: [{ type: 'scatter', data: [1] }],
    });
    expect(errorCode).toBe('INVALID_STRUCTURE');
  });

  it('converts __fn at canvas slots and strips leftovers', () => {
    const { option, errorCode } = sanitizeChartOption(withSeries({
      xAxis: {
        type: 'category',
        data: ['2026-03-03'],
        axisLabel: { formatter: { __fn: 'datetime', options: { format: 'M-D' } } },
      },
      legend: { formatter: { __fn: 'truncate', options: { maxLength: 4 } } },
      series: [{
        type: 'line',
        data: [1],
        label: { formatter: { __fn: 'number', options: { unit: '次' } } },
        tooltip: { formatter: { __fn: 'datetime' } },
      }],
    }));
    expect(errorCode).toBeNull();
    expect(typeof option?.xAxis.axisLabel.formatter).toBe('function');
    expect(option?.xAxis.axisLabel.formatter('2026-03-03')).toBe('3-3');
    const ms = 1758499200000;
    const sec = 1758499200;
    expect(option?.xAxis.axisLabel.formatter(ms)).toBe(dayjs(ms).format('M-D'));
    expect(option?.xAxis.axisLabel.formatter(String(ms))).toBe(dayjs(ms).format('M-D'));
    expect(option?.xAxis.axisLabel.formatter(sec)).toBe(dayjs(sec * 1000).format('M-D'));
    expect(option?.xAxis.axisLabel.formatter(String(sec))).toBe(dayjs(sec * 1000).format('M-D'));
    expect(option?.xAxis.axisLabel.formatter('not-a-date')).toBe('not-a-date');
    expect(option?.legend.formatter('很长的名字')).toBe('很长的名...');
    expect(option?.series[0].label.formatter(1234)).toBe('1,234次');
    expect(typeof option?.series[0].tooltip.formatter).toBe('function');
    expect(isFnSpecGone(option?.series[0].tooltip.formatter)).toBe(true);
  });

  it('formats 13-digit ms and 10-digit second timestamps, passes anything else through', () => {
    const { option } = sanitizeChartOption(withSeries({
      xAxis: {
        type: 'category',
        data: [1758499200000],
        axisLabel: { formatter: { __fn: 'datetime', options: { format: 'YYYY-MM-DD' } } },
      },
    }));
    const format = option?.xAxis.axisLabel.formatter;
    expect(format(1758499200000)).toBe('2025-09-22');
    expect(format('1758499200000')).toBe('2025-09-22');
    expect(format(1758499200)).toBe('2025-09-22');
    // 年份、序号这类数字不是时间戳，不能被当成毫秒纪元换算成 1970
    expect(format(2026)).toBe('2026');
    expect(format('登录')).toBe('登录');
  });

  it('falls back to a readable text when a formatter value is not scalar', () => {
    const { option } = sanitizeChartOption(withSeries({
      series: [{
        type: 'line',
        data: [1],
        label: { formatter: { __fn: 'number' } },
      }],
    }));
    const format = option?.series[0].label.formatter;
    expect(format({ value: { a: 1 } })).toBe('{"a":1}');
    expect(format({ value: 1234 })).toBe('1,234');
  });

  it('keeps <b> in tooltip template and drops style attributes by falling back', () => {
    const kept = sanitizeChartOption(withSeries({
      tooltip: { trigger: 'item', __template: '{marker}{name}：<b>{value}</b>' },
    }));
    expect(kept.errorCode).toBeNull();
    const keptHtml = kept.option?.tooltip.formatter({
      marker: '<span>dot</span>',
      name: '成功',
      value: 528,
    });
    expect(keptHtml).toContain('<b>528</b>');
    expect(keptHtml).toContain('<span>dot</span>');

    const styled = sanitizeChartOption(withSeries({
      tooltip: {
        trigger: 'item',
        __template: '<span style="color:red">{name}</span>',
      },
    }));
    const styledHtml = styled.option?.tooltip.formatter({
      marker: '<span>dot</span>',
      name: '成功',
      value: 528,
      percent: 31.7,
    });
    expect(styledHtml).not.toContain('style=');
    expect(styledHtml).toContain('<b>528</b>');
  });

  it('sanitizes the skill-compliant sample without error', () => {
    const trend = sanitizeChartOption(SKILL_COMPLIANT_PACKAGE[0].echarts_option);
    const pie = sanitizeChartOption(SKILL_COMPLIANT_PACKAGE[1].echarts_option);
    expect(trend.errorCode).toBeNull();
    expect(pie.errorCode).toBeNull();
    expect(typeof trend.option?.xAxis.axisLabel.formatter).toBe('function');
    const pieHtml = pie.option?.tooltip.formatter({
      marker: '<span>dot</span>',
      name: '成功：528（31.7%）',
      value: 528,
    });
    expect(pieHtml).toBe('<span>dot</span>成功：528（31.7%）');
  });
});

describe('clampChartHeight', () => {
  it('clamps to 160–800 and falls back to 280', () => {
    expect(clampChartHeight(100)).toBe(160);
    expect(clampChartHeight(900)).toBe(800);
    expect(clampChartHeight('x')).toBe(280);
    expect(clampChartHeight(280)).toBe(280);
  });
});

const isFnSpecGone = (value: unknown) => typeof value === 'function';
