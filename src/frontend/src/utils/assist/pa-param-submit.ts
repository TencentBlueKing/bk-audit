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
  if (condition.operator !== '=' || !condition.constant_key) {
    return false;
  }
  const expectedValue = condition.value;
  const currentValue = paParams?.[condition.constant_key]?.value;
  if (expectedValue === undefined || expectedValue === null
    || currentValue === undefined || currentValue === null) {
    return false;
  }
  return String(expectedValue) === String(currentValue);
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
