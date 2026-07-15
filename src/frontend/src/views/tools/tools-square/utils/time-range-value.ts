import { DateRange } from '@blueking/date-picker';

/**
 * 将时间范围选择器（time_range_select）的值统一转换为绝对时间字符串。
 * 配置默认值 / URL / sessionStorage 缓存中可能存的是相对时间表达式（如 now-7d），
 * 而后端 execute 只接受绝对时间或时间戳，因此在组装 tool_variables 时必须转换，
 * 不能依赖表单组件是否渲染（隐藏参数、自动执行等场景表单可能未挂载）。
 * 注意：bk_vision 的 time-ranger 类型不走此转换，相对时间直接透传给 BKVision SDK。
 */
export const formatTimeRangeSelectValue = (value: unknown): unknown => {
  if (
    !Array.isArray(value)
    || value.length !== 2
    || value.some(v => v === null || v === undefined || v === '')
  ) {
    return value;
  }
  try {
    const date = new DateRange(value, 'YYYY-MM-DD HH:mm:ss', window.timezone);
    if (date.startDisplayText && date.endDisplayText) {
      return [date.startDisplayText, date.endDisplayText];
    }
  } catch {
    // 转换失败时保留原值，由后端校验兜底
  }
  return value;
};
