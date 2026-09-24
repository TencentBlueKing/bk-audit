type PaParamMeta = {
  key?: string;
  source_type?: string;
  show_type?: string;
  is_hide?: boolean;
  hide_condition?: PaParamHideCondition[];
  default_value?: unknown;
};

type PaParamValue = {
  field?: unknown;
  value?: unknown;
};

type PaParamHideCondition = {
  constant_key?: string;
  operator?: string;
  value?: unknown;
};

/** 判断标准运维常量是否属于需要前端采集的用户入参。 */
export const isUserInput = (meta?: PaParamMeta) => (
  meta?.source_type === 'custom' && meta?.show_type === 'show'
);

/** 安全判断当前参数值是否命中标准运维的条件隐藏规则。 */
export const matchesPaParamHideCondition = (
  condition: PaParamHideCondition,
  paParams: Record<string, PaParamValue> | undefined,
) => {
  if (!condition.constant_key || !['=', '!='].includes(condition.operator || '')) {
    return false;
  }
  const currentParam = paParams?.[condition.constant_key];
  if (!currentParam) {
    return false;
  }
  const isEqual = JSON.stringify(condition.value) === JSON.stringify(currentParam.value);
  return condition.operator === '=' ? isEqual : !isEqual;
};

/** 标准运维多条条件按 OR 组合，任意条件命中即隐藏参数。 */
export const isPaParamHidden = (
  conditions: Iterable<PaParamHideCondition>,
  paParams: Record<string, PaParamValue> | undefined,
) => {
  for (const condition of conditions) {
    if (matchesPaParamHideCondition(condition, paParams)) {
      return true;
    }
  }
  return false;
};

/**
 * 同步套餐参数的实际渲染状态。
 *
 * 隐藏参数保留本地值，提交时由 buildSubmitPaParams 省略 key，与 BK-SOPS 的表单行为一致；
 * 参数显示且 key 不存在时补建空对象，使“key 存在”与“value 非空”保持独立语义。
 */
export const syncPaParamVisibility = (
  paParams: Record<string, PaParamValue> | undefined,
  metas: Iterable<PaParamMeta>,
) => {
  const params = paParams || {};
  const conditionParams = Object.fromEntries(Object.entries(params).map(([key, param]) => [key, { ...param }]));
  const visibility = new Map<PaParamMeta, boolean>();

  for (const meta of metas) {
    if (!meta.key || !isUserInput(meta)) {
      continue;
    }
    const conditions = Array.isArray(meta.hide_condition) ? meta.hide_condition : [];
    visibility.set(meta, isPaParamHidden(conditions, conditionParams));
  }

  for (const [meta, isHidden] of visibility) {
    const { key } = meta;
    if (!key) {
      continue;
    }
    meta.is_hide = isHidden;
    if (!isHidden && !Object.prototype.hasOwnProperty.call(params, key)) {
      params[key] = { field: '', value: '' };
    }
  }

  return params;
};

/** 只提交本次表单实际渲染的用户入参。 */
export const buildSubmitPaParams = (
  paParams: Record<string, PaParamValue> | undefined,
  metas: Iterable<PaParamMeta>,
) => {
  const metaByKey = new Map<string, PaParamMeta>();
  for (const meta of metas) {
    if (meta?.key) {
      metaByKey.set(meta.key, meta);
    }
  }
  const result: Record<string, PaParamValue> = {};
  Object.entries(paParams || {}).forEach(([key, item]) => {
    const meta = metaByKey.get(key);
    if (!isUserInput(meta)) {
      return;
    }
    if (meta?.is_hide) {
      return;
    }
    result[key] = item;
  });
  return result;
};
