export interface StatisticsInputErrorDetail {
  loc: string;
  msg: string;
}

const isRecord = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

/** 业务码错误挂在 Axios response.data，少数路径直接把响应体放在 response 上 */
const readErrorBody = (error: unknown): Record<string, unknown> | null => {
  if (!isRecord(error)) return null;
  const { response } = error;
  if (isRecord(response) && isRecord(response.data)) return response.data;
  if (isRecord(response) && (isRecord(response.errors) || typeof response.code === 'string')) {
    return response;
  }
  if (isRecord(error.data)) return error.data;
  return null;
};

/** 创建统计的参数错误：field_name 标明输入段，errors 里是 loc/msg */
export const readStatisticsInputError = (error: unknown): {
  fieldName: string;
  details: StatisticsInputErrorDetail[];
} | null => {
  const data = readErrorBody(error);
  if (!data) return null;
  const bucket = data.errors;
  if (!bucket || typeof bucket !== 'object' || Array.isArray(bucket)) return null;
  const fieldName = typeof (bucket as { field_name?: unknown }).field_name === 'string'
    ? (bucket as { field_name: string }).field_name
    : '';
  const rawDetails = (bucket as { errors?: unknown }).errors;
  const details = (Array.isArray(rawDetails) ? rawDetails : [])
    .map((item) => {
      if (!item || typeof item !== 'object') return null;
      const loc = Array.isArray((item as { loc?: unknown }).loc)
        ? (item as { loc: unknown[] }).loc.map(part => String(part)).join('.')
        : '';
      const msg = typeof (item as { msg?: unknown }).msg === 'string'
        ? (item as { msg: string }).msg
        : '';
      if (!loc && !msg) return null;
      return { loc, msg };
    })
    .filter((item): item is StatisticsInputErrorDetail => Boolean(item));
  if (!fieldName && !details.length) return null;
  return { fieldName, details };
};

/** 输入面板展示：input_data：field.raw_name: 原因 */
export const formatStatisticsInputError = (error: unknown, fallback = ''): string => {
  const parsed = readStatisticsInputError(error);
  if (!parsed) return fallback;
  const messages = parsed.details.map(item => (
    item.loc && item.msg ? `${item.loc}: ${item.msg}` : item.msg || item.loc
  ));
  return [parsed.fieldName, messages.join('；')].filter(Boolean).join('：');
};
