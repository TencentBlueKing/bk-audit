import type { IFieldConfig } from '@components/search-box/components/render-field-config/config';

export const applyTableFiltersToSearchModel = (
  searchModel: Record<string, any>,
  filters: Record<string, any>,
  fieldConfig: Record<string, IFieldConfig>,
) => {
  const nextModel = { ...searchModel };
  Object.keys(filters).forEach((field) => {
    if (!fieldConfig[field]) {
      return;
    }
    const value = filters[field];
    const isEmpty = Array.isArray(value)
      ? value.length === 0
      : value === undefined || value === null || value === '';
    if (isEmpty) {
      delete nextModel[field];
      return;
    }
    if (fieldConfig[field].type === 'string') {
      nextModel[field] = Array.isArray(value) ? value[0] : value;
      return;
    }
    if (field === 'has_report') {
      if (typeof value === 'boolean') {
        nextModel[field] = [String(value)];
        return;
      }
      nextModel[field] = Array.isArray(value) ? value.map(String) : [String(value)];
      return;
    }
    if (fieldConfig[field].type === 'select' || fieldConfig[field].type === 'user-selector') {
      nextModel[field] = Array.isArray(value)
        ? value
        : String(value).split(',')
          .map(item => item.trim())
          .filter(Boolean);
      return;
    }
    nextModel[field] = value;
  });
  return nextModel;
};
