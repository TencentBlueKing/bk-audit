export const supportsFieldReferenceType = (customType: string) => (
  customType === 'datetime'
  || customType === 'textarea'
  || customType === 'input'
  || customType === 'bk_date_picker'
  || customType === ''
);

export const isParamValueEmpty = (value: unknown) => (
  value === ''
  || value === undefined
  || value === null
  || (Array.isArray(value) && value.length === 0)
);

/** 风险字段 ID 一般为 snake_case，避免将自定义值（如 2、日期）误判为字段引用 */
export const isRiskFieldIdFormat = (valueId: string) => (
  /^[a-zA-Z][a-zA-Z0-9_]*$/.test(valueId)
);

export const resolveParamFieldReference = (
  param: { field?: unknown; value?: unknown } | undefined,
  customType: string,
  knownFieldIds: Iterable<string>,
) => {
  if (!param || !supportsFieldReferenceType(customType)) {
    return '';
  }

  const knownFieldIdSet = knownFieldIds instanceof Set
    ? knownFieldIds
    : new Set(knownFieldIds);

  const isKnownFieldId = (fieldId: string) => knownFieldIdSet.has(fieldId);
  const fieldId = typeof param.field === 'string' ? param.field : '';
  const valueId = typeof param.value === 'string' ? param.value : '';

  if (fieldId) {
    if (isParamValueEmpty(param.value) || String(param.value) === fieldId) {
      if (isKnownFieldId(fieldId) || isRiskFieldIdFormat(fieldId)) {
        return fieldId;
      }
    }
    return '';
  }

  if (valueId && isRiskFieldIdFormat(valueId) && isKnownFieldId(valueId)) {
    return valueId;
  }

  return '';
};

export const isParamFieldReference = (
  param: { field?: unknown; value?: unknown } | undefined,
  customType: string,
  knownFieldIds: Iterable<string>,
) => !!resolveParamFieldReference(param, customType, knownFieldIds);
