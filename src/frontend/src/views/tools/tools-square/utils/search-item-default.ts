import type { ToolDetailScopeQuery } from '@/utils/assist/scene-system-params';

/**
 * 从工具详情 input_variable 项读取查询输入默认值。
 * 后端已按 scene_id/system_id 合并 default_value_overrides，应使用 default_value 字段。
 */
export const getSearchItemDefaultValue = (item: {
  default_value?: unknown;
  field_category?: string;
}): unknown => {
  const { default_value: defaultValue, field_category: fieldCategory } = item;
  if (defaultValue !== undefined && defaultValue !== null) {
    return defaultValue;
  }
  if (fieldCategory === 'person_select' || fieldCategory === 'time_range_select') {
    return [];
  }
  return null;
};

/** 按可见范围隔离 sessionStorage 中的用户输入缓存 */
export const buildSearchValuesCacheKey = (
  uid: string,
  scopeQuery: ToolDetailScopeQuery = {},
): string => {
  const { scene_id: sceneId, system_id: systemId } = scopeQuery;
  if (sceneId !== undefined) {
    return `${uid}:scene:${sceneId}`;
  }
  if (systemId) {
    return `${uid}:system:${systemId}`;
  }
  return uid;
};

export const clearSearchValuesCacheByUid = (
  cacheMap: Record<string, Record<string, unknown>>,
  uid: string,
): Record<string, Record<string, unknown>> => {
  const keysToRemove = Object.keys(cacheMap)
    .filter(key => key === uid || key.startsWith(`${uid}:`));
  if (!keysToRemove.length) {
    return cacheMap;
  }
  const next = { ...cacheMap };
  keysToRemove.forEach((key) => {
    delete next[key];
  });
  return next;
};
