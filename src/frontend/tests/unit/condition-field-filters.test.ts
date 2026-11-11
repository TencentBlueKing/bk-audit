import { describe, expect, it, vi } from 'vitest';

import {
  buildAiSearchCondition,
  createConditionFieldConfigFromSystemFields,
} from '@views/sec-chat/audit-log-retrieval/config/condition-fields';
import type { SystemFieldRow } from '@views/sec-chat/types';

vi.mock('@/utils/sync-datetime-from-url', () => ({
  isRelativeDatetimeOrigin: () => false,
}));

const resultCode: SystemFieldRow = {
  rawName: 'result_code',
  keys: [],
  displayName: '操作结果',
  nlName: '操作结果',
  description: '',
  allowOperators: ['eq', 'neq', 'include', 'exclude'],
  fieldType: 'int',
  options: [
    { id: '0', name: '成功' },
    { id: '-1', name: '其他' },
  ],
};

const datetime = ['2026-01-01 00:00:00', '2026-01-02 00:00:00'];

const build = (value: { operator: string; value: string }) => {
  const fieldConfig = createConditionFieldConfigFromSystemFields([resultCode], []);
  return buildAiSearchCondition({
    scopeId: '1',
    fieldConfig,
    searchModel: {
      datetime,
      result_code: value,
    },
  });
};

describe('筛选常见值不是白名单', () => {
  it('带 options 的字段可以自由输入并选择操作符', () => {
    const fieldConfig = createConditionFieldConfigFromSystemFields([resultCode], []);
    expect(fieldConfig.result_code.type).toBe('log-field');
    expect(fieldConfig.result_code.suggestOptions).toEqual(resultCode.options);
  });

  it('非零使用 neq 和数字 0，-1 只匹配真实 -1', () => {
    expect(build({ operator: 'neq', value: '0' })?.conditions[0]).toEqual({
      field: { raw_name: 'result_code', keys: [] },
      operator: 'neq',
      filters: [0],
    });
    expect(build({ operator: 'eq', value: '-1' })?.conditions[0].filters).toEqual([-1]);
    expect(build({ operator: 'eq', value: '107' })?.conditions[0].filters).toEqual([107]);
  });
});
