import { describe, expect, it } from 'vitest';

import type { AiFieldStatisticsOutput } from '@model/ai-assistant/types';

import {
  formatNumericValue,
  formatStatisticsRatio,
  mapFieldStatisticsOutput,
  parseStatisticsCharts,
} from '@views/sec-chat/audit-log-retrieval/utils/map-statistics-output';

const buildOutput = (patch: Partial<AiFieldStatisticsOutput> = {}): AiFieldStatisticsOutput => ({
  field: { raw_name: 'username', keys: [], display_name: '操作人' },
  statistics_kind: 'CATEGORICAL',
  overview: {
    total_count: 100,
    present_count: 80,
    missing_count: 20,
    present_ratio: 0.8,
  },
  distribution: {
    top_n: 5,
    has_other: true,
    groups: [
      { group_id: 'g1', kind: 'VALUE', value: 'admin', count: 60, ratio: 0.6 },
      { group_id: 'g2', kind: 'OTHER', value: null, count: 20, ratio: 0.2 },
      { group_id: 'g3', kind: 'MISSING', value: null, count: 20, ratio: 0.2 },
    ],
  },
  time_series: {
    requested_interval: 'AUTO',
    effective_interval: 'HOUR',
    timezone: 'Asia/Shanghai',
    bucket_starts: ['2026-09-29T10:00:00+08:00', '2026-09-29T11:00:00+08:00'],
    series: [{ group_id: 'g1', counts: [30, 30] }],
  },
  numeric_summary: null,
  ...patch,
});

describe('mapFieldStatisticsOutput', () => {
  it('比例按 0～1 协议换算成百分比', () => {
    expect(formatStatisticsRatio(0.4729)).toBe('47.29%');
    expect(formatStatisticsRatio(0.6)).toBe('60.00%');
    expect(formatStatisticsRatio(0)).toBe('0.00%');
    expect(formatStatisticsRatio(null)).toBe('—');
    expect(formatStatisticsRatio(0.00004)).toBe('<0.01%');
    expect(formatStatisticsRatio(0, 1, 100000)).toBe('<0.01%');

    const view = mapFieldStatisticsOutput(buildOutput());
    expect(view.overview.presentRatioText).toBe('80.00%');
    expect(view.cards.find(item => item.kind === 'ratio')?.ratio?.[0].percent).toBe('60.00%');
  });

  it('数值摘要展示后端已收口的小数，不再按有效数字重排', () => {
    expect(formatNumericValue(12.3457)).toBe('12.3457');
    expect(formatNumericValue(123456.7891)).toBe('123456.7891');
    expect(formatNumericValue(12)).toBe('12');
  });

  it('舍入成 0 的正比例仍按计数绘图', () => {
    const view = mapFieldStatisticsOutput(buildOutput({
      overview: {
        total_count: 100000,
        present_count: 1,
        missing_count: 99999,
        present_ratio: 0,
      },
      distribution: {
        top_n: 1,
        has_other: false,
        groups: [
          {
            group_id: 'g1',
            kind: 'VALUE',
            value_type: 'string',
            value: 'a',
            count: 1,
            ratio: 0,
          },
        ],
      },
    }));
    const ratio = view.cards.find(item => item.kind === 'ratio')?.ratio || [];
    expect(ratio).toHaveLength(1);
    expect(ratio[0].value).toBe(1);
    expect(ratio[0].percent).toBe('<0.01%');
    expect(view.overview.presentRatioText).toBe('<0.01%');
  });

  it('合成组按 kind 判定，真实取值「其他」不被当成合成组', () => {
    const view = mapFieldStatisticsOutput(buildOutput({
      distribution: {
        top_n: 5,
        has_other: false,
        groups: [
          { group_id: 'g1', kind: 'VALUE', value: '其他', count: 10, ratio: 0.1 },
          { group_id: 'g2', kind: 'OTHER', value: null, count: 5, ratio: 0.05 },
          { group_id: 'g3', kind: 'VALUE', value: '', count: 5, ratio: 0.05 },
        ],
      },
    }));
    const ratio = view.cards.find(item => item.kind === 'ratio')?.ratio || [];
    expect(ratio.map(item => item.name)).toEqual(['其他（原始值）', '其他', '空字符串']);
    expect(ratio[0].kind).toBe('VALUE');
    expect(ratio[1].color).not.toBe(ratio[0].color);
  });

  it('同名数字和字符串分开标注', () => {
    const view = mapFieldStatisticsOutput(buildOutput({
      distribution: {
        top_n: 2,
        has_other: false,
        groups: [
          { group_id: 'g1', kind: 'VALUE', value_type: 'number', value: 120, count: 3, ratio: 0.3 },
          { group_id: 'g2', kind: 'VALUE', value_type: 'string', value: '120', count: 2, ratio: 0.2 },
        ],
      },
    }));
    const ratio = view.cards.find(item => item.kind === 'ratio')?.ratio || [];
    expect(ratio.map(item => item.name)).toEqual(['120（数字）', '120（字符串）']);
    expect(ratio.map(item => item.value)).toEqual([3, 2]);
  });

  it('counts 与 bucket_starts 不等长时缺口补 null 而不是 0', () => {
    const view = mapFieldStatisticsOutput(buildOutput({
      time_series: {
        requested_interval: 'AUTO',
        effective_interval: 'HOUR',
        timezone: 'Asia/Shanghai',
        bucket_starts: ['2026-09-29T10:00:00+08:00', '2026-09-29T11:00:00+08:00', '2026-09-29T12:00:00+08:00'],
        series: [{ group_id: 'g1', counts: [30, 0] }],
      },
    }));
    const trend = view.cards.find(item => item.kind === 'trend')?.trend;
    expect(trend?.series[0].data).toEqual([30, 0, null]);
    expect(trend?.xAxis).toEqual(['09-29 10:00', '09-29 11:00', '09-29 12:00']);
  });

  it('区分「没有日志」和「字段全部缺失」两种空结果', () => {
    const noLogs = mapFieldStatisticsOutput(buildOutput({
      overview: {
        total_count: 0, present_count: 0, missing_count: 0, present_ratio: null,
      },
    }));
    expect(noLogs.emptyKind).toBe('no-logs');

    const fieldMissing = mapFieldStatisticsOutput(buildOutput({
      overview: {
        total_count: 100, present_count: 0, missing_count: 100, present_ratio: 0,
      },
    }));
    expect(fieldMissing.emptyKind).toBe('field-missing');
  });

  it('数值摘要只在 NUMERIC 下暴露', () => {
    const numericSummary = {
      min: 1,
      max: 9,
      avg: 5,
      median: 4,
      median_is_approximate: true,
      valid_count: 80,
      conversion_failed_count: 2,
    };
    expect(mapFieldStatisticsOutput(buildOutput({ numeric_summary: numericSummary })).numericSummary)
      .toBeNull();
    expect(mapFieldStatisticsOutput(buildOutput({
      statistics_kind: 'NUMERIC',
      numeric_summary: numericSummary,
    })).numericSummary).toEqual(numericSummary);
  });
});

describe('parseStatisticsCharts', () => {
  it('解析合法图表数组', () => {
    const content = JSON.stringify([
      { title: '登录趋势', height: 320, echarts_option: { series: [{ type: 'line', data: [1, 2] }] } },
    ]);
    const result = parseStatisticsCharts(content);
    expect(result.failure).toBeNull();
    expect(result.charts).toHaveLength(1);
    expect(result.charts[0].title).toBe('登录趋势');
    expect(result.charts[0].height).toBe(320);
  });

  it('标签内原文带首尾换行也能解析', () => {
    // 后端按标签切分后不做 strip，Agent 换行书写时首尾会带 \n
    const content = `\n[{"title":"日志总数","height":280,"echarts_option":{\n  "series": []\n}}]\n`;
    const result = parseStatisticsCharts(content);
    expect(result.failure).toBeNull();
    expect(result.charts[0].title).toBe('日志总数');
  });

  it('整份不可用时给出降级原因', () => {
    expect(parseStatisticsCharts('这是一段自然语言').failure).toBe('NOT_JSON');
    expect(parseStatisticsCharts('').failure).toBe('NOT_JSON');
    expect(parseStatisticsCharts('{"title":"x"}').failure).toBe('NOT_ARRAY');
    expect(parseStatisticsCharts('[]').failure).toBe('EMPTY');
    expect(parseStatisticsCharts('[{"title":"缺配置"}]').failure).toBe('INVALID_ITEM');
  });

  it('部分元素不合法时保留错误卡，不整份降级', () => {
    const content = JSON.stringify([
      { title: '正常', echarts_option: { series: [] } },
      { title: '缺配置' },
    ]);
    const result = parseStatisticsCharts(content);
    expect(result.failure).toBeNull();
    expect(result.charts[0].errorCode).toBeUndefined();
    expect(result.charts[1].errorCode).toBe('INVALID_STRUCTURE');
  });
});
