import type { AiLogFieldRef, AiSearchCondition } from '@model/ai-assistant/types';

/** 根目录只传来源检索条件 */
export const rootFieldMetadataParams = (condition: AiSearchCondition) => ({
  condition,
});

/** 可展开根字段一次取回对象后代；数组不走这条请求 */
export const descendantFieldMetadataParams = (
  condition: AiSearchCondition,
  field: Pick<AiLogFieldRef, 'raw_name' | 'keys'>,
) => ({
  condition,
  parent_field: {
    raw_name: field.raw_name,
    keys: field.keys || [],
  },
  include_descendants: true as const,
});

/** 不支持统计时展示的数据类型：优先样本观察类型，没有再用字段声明类型 */
export const unsupportedFieldDataType = (
  fieldType?: string | null,
  observedTypes?: string[] | null,
) => {
  const observed = (observedTypes || [])
    .map(type => String(type).trim())
    .filter(Boolean);
  if (observed.length) return [...new Set(observed)].join('、');
  return String(fieldType || '').trim();
};

/** 嵌套字段用路径区分同名叶子，提交仍使用 raw_name + keys */
export const fieldOptionLabel = (displayName: string, rawName: string, keys: string[]) => {
  const path = keys.filter(Boolean).join('.');
  const name = displayName || '';
  if (path && name && name !== path) return `${name} (${path})`;
  return name || path || rawName;
};

export const collectDescendantFields = <T extends { key: string; field: { keys: string[] } }>(
  fields: T[],
  parentKey: string,
) => {
  const descendants = fields.filter(field => field.key !== parentKey);
  return descendants.sort((left, right) => (
    left.field.keys.join('.').localeCompare(right.field.keys.join('.'), 'en')
  ));
};
