import { describe, expect, it } from 'vitest';

import type { AiSearchCondition } from '@model/ai-assistant/types';

import {
  collectDescendantFields,
  descendantFieldMetadataParams,
  fieldOptionLabel,
  rootFieldMetadataParams,
  unsupportedFieldDataType,
} from '@views/sec-chat/audit-log-retrieval/utils/field-metadata-catalog';

const condition = { scope_type: 'system', scope_id: '1' } as AiSearchCondition;

describe('字段目录请求与分组', () => {
  it('根目录只传检索条件', () => {
    expect(rootFieldMetadataParams(condition)).toEqual({ condition });
  });

  it('可展开根字段带 parent_field 和 include_descendants', () => {
    expect(descendantFieldMetadataParams(condition, {
      raw_name: 'extend_data',
      keys: [],
    })).toEqual({
      condition,
      parent_field: { raw_name: 'extend_data', keys: [] },
      include_descendants: true,
    });
  });

  it('嵌套字段展示路径，根字段保持显示名', () => {
    expect(fieldOptionLabel('扩展', 'extend_data', [])).toBe('扩展');
    expect(fieldOptionLabel('子字段', 'extend_data', ['a', 'b'])).toBe('子字段 (a.b)');
    expect(fieldOptionLabel('a.b', 'extend_data', ['a', 'b'])).toBe('a.b');
  });

  it('不支持统计时优先展示样本观察到的数据类型', () => {
    expect(unsupportedFieldDataType('text', ['array'])).toBe('array');
    expect(unsupportedFieldDataType('object', [])).toBe('object');
    expect(unsupportedFieldDataType('', ['object', 'object', 'array'])).toBe('object、array');
    expect(unsupportedFieldDataType('', [])).toBe('');
  });

  it('后代去掉父字段自身并按路径排序', () => {
    const fields = collectDescendantFields([
      { key: 'parent', field: { keys: [] } },
      { key: 'c', field: { keys: ['a', 'c'] } },
      { key: 'b', field: { keys: ['a', 'b'] } },
      { key: 'a', field: { keys: ['a'] } },
    ], 'parent');
    expect(fields.map(field => field.key)).toEqual(['a', 'b', 'c']);
  });
});
