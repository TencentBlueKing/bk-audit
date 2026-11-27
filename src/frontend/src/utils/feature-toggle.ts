export interface AuditFeatureConfig {
  feature_toggle?: Record<string, unknown>;
}

type ConfigStorage = {
  getItem: (key: string) => string | null;
};

/** 当前首屏配置由 main.ts 写入 sessionStorage；读取失败时兼容旧版行为。 */
export const readStoredAuditConfig = (storage?: ConfigStorage): AuditFeatureConfig => {
  try {
    const configStorage = storage ?? (typeof sessionStorage === 'undefined' ? undefined : sessionStorage);
    return JSON.parse(configStorage?.getItem('BK_AUDIT_CONFIG') || '{}') as AuditFeatureConfig;
  } catch {
    return {};
  }
};

/** 仅显式 false 关闭能力，缺字段时沿用旧版本行为。 */
export const isAiCapabilityEnabled = (config?: AuditFeatureConfig | null) => (
  config?.feature_toggle?.ai_capability !== false
);

/** AI 助手父路由关闭时连同子路由一起移除，交由应用的 404 catch-all 处理。 */
export const filterAiRoutes = <T extends { name?: string | symbol }>(
  routes: T[],
  config?: AuditFeatureConfig | null,
) => (
    isAiCapabilityEnabled(config)
      ? routes
      : routes.filter(route => route.name !== 'secChat')
  );

/** 未加载或关闭时都不展示 BKSEC 功能入口。 */
export const isBksecCapabilityVisible = (loaded: boolean, enabled: boolean) => loaded && enabled;

/** 保留 URL 请求的原始步骤，待异步 feature 结果返回后再决定是否截断。 */
export const getRequestedStrategyStep = (step: unknown): 1 | 2 | 3 | 4 | 5 => {
  const value = Array.isArray(step) ? step[0] : step;
  const requestedStep = Number(value);
  return [1, 2, 3, 4, 5].includes(requestedStep)
    ? requestedStep as 1 | 2 | 3 | 4 | 5
    : 1;
};

export const clampStrategyStep = (step: number, maxStep: number) => Math.min(step, maxStep);
