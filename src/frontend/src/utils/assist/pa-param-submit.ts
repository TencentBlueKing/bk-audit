type PaParamMeta = {
  key?: string;
  source_type?: string;
  show_type?: string;
  is_hide?: boolean;
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

const isUserInput = (meta?: PaParamMeta) => meta?.source_type === 'custom' && meta?.show_type === 'show';

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
  const isEqual = String(condition.value) === String(currentParam.value);
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
