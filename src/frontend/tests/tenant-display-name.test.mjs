/* eslint-env node, es2020 */
import { build } from 'esbuild';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

test('official display-name element queries the bound tenant and preserves an unknown ID', async (t) => {
  const elements = new Map();
  const config = {
    BKPAAS_MULTI_TENANT_MODE: true,
    BK_TENANT_ID: 'tencent',
    BK_USER_WEB_APIGW_URL: 'https://apigw.example.test/bk-user-web/prod',
  };
  Object.assign(globalThis, {
    HTMLElement: class {
      constructor() {
        this.userId = '';
      }

      getAttribute(name) {
        return name === 'user-id' ? this.userId : null;
      }
    },
    customElements: {
      define: elements.set.bind(elements),
      get: elements.get.bind(elements),
    },
  });
  const fetch = t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(options.credentials, 'include');
    assert.deepEqual(options.headers, { 'X-Bk-Tenant-Id': 'tencent' });
    return new Response(JSON.stringify({
      data: url.includes('/123456/') ? { display_name: '张三(zhangsan)' } : {},
    }));
  });

  const source = new URL('../src/utils/assist/tenant-display-name.ts', import.meta.url);
  const { outputFiles: [bundle] } = await build({
    entryPoints: [fileURLToPath(source)],
    bundle: true,
    format: 'esm',
    platform: 'node',
    write: false,
  });
  const { configureTenantDisplayName } = await import(`data:text/javascript;base64,${Buffer.from(bundle.contents).toString('base64')}`);

  assert.equal(await configureTenantDisplayName({ ...config, BKPAAS_MULTI_TENANT_MODE: false }), false);
  assert.equal(await configureTenantDisplayName({ ...config, BK_USER_WEB_APIGW_URL: '/stag' }), false);
  assert.equal(await configureTenantDisplayName({ ...config, BK_TENANT_ID: '' }), false);
  assert.equal(await configureTenantDisplayName(), false);
  assert.equal(elements.size, 0);
  assert.equal(await configureTenantDisplayName(config), true);

  const DisplayName = elements.get('bk-user-display-name');
  const element = new DisplayName();
  element.userId = '123456';
  assert.equal(await element.getDisplayName(), '张三(zhangsan)');
  assert.equal(element.userId, '123456');
  element.userId = '789012';
  assert.equal(await element.getDisplayName(), '789012');
  assert.equal(fetch.mock.calls.length, 2);
  assert.equal(
    fetch.mock.calls[0].arguments[0],
    'https://apigw.example.test/bk-user-web/prod/api/v3/open-web/tenant/users/123456/display_info/',
  );
});
