import type Config from '@model/root/config';

/** 配置完成后才渲染自定义元素；缺少配置或加载失败时保留原账号展示。 */
export async function configureTenantDisplayName(config?: Config['tenant_config']) {
  if (config?.BKPAAS_MULTI_TENANT_MODE !== true
    || !config.BK_TENANT_ID
    || !/^https:\/\//i.test(config.BK_USER_WEB_APIGW_URL)) {
    return false;
  }
  try {
    const { default: BkUserDisplayName } = await import('@blueking/bk-user-display-name');
    BkUserDisplayName.configure({
      tenantId: config.BK_TENANT_ID,
      apiBaseUrl: config.BK_USER_WEB_APIGW_URL,
    });
    return true;
  } catch {
    return false;
  }
}
