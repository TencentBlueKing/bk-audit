/* eslint-env node, es2020 */
import { build } from 'esbuild';
import assert from 'node:assert/strict';
import { before, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { createMemoryHistory, createRouter } from 'vue-router';

let featureToggle;
before(async () => {
  const source = new URL('../src/utils/feature-toggle.ts', import.meta.url);
  const { outputFiles: [bundle] } = await build({
    entryPoints: [fileURLToPath(source)],
    bundle: true,
    format: 'esm',
    platform: 'node',
    write: false,
  });
  featureToggle = await import(`data:text/javascript;base64,${Buffer.from(bundle.contents).toString('base64')}`);
});

const component = () => null;

const createFeatureFixtureRouter = (config) => {
  const routes = featureToggle.filterAiRoutes([
    {
      path: '/sec-chat',
      name: 'secChat',
      component,
      children: [
        { path: '', name: 'secChatHome', component },
        { path: 'audit-log-retrieval/:conversationId?', name: 'secChatAuditLog', component },
      ],
    },
    { path: '/risk-manage', name: 'riskManage', component },
    { path: '/:pathMatch(.*)*', name: '404', component },
  ], config);

  return createRouter({
    history: createMemoryHistory(),
    routes,
  });
};

test('feature decisions preserve the default-on behavior for old configs', () => {
  const disabled = { feature_toggle: { ai_capability: false } };
  const enabled = { feature_toggle: { ai_capability: true } };
  const legacy = { feature_toggle: {} };

  assert.equal(featureToggle.readStoredAuditConfig({
    getItem: () => JSON.stringify(disabled),
  }).feature_toggle.ai_capability, false);
  assert.equal(featureToggle.isAiCapabilityEnabled(disabled), false);
  assert.equal(featureToggle.isAiCapabilityEnabled(enabled), true);
  assert.equal(featureToggle.isAiCapabilityEnabled(legacy), true);
  assert.equal(featureToggle.isAiCapabilityEnabled({}), true);
});

test('closed AI resolves main, child, and case-variant URLs to the 404 route', () => {
  const router = createFeatureFixtureRouter({ feature_toggle: { ai_capability: false } });

  assert.equal(router.resolve('/sec-chat').name, '404');
  assert.equal(router.resolve('/sec-chat/audit-log-retrieval/123').name, '404');
  assert.equal(router.resolve('/SEC-CHAT/AUDIT-LOG-RETRIEVAL/123').name, '404');
  assert.equal(router.resolve('/risk-manage').name, 'riskManage');
});

test('enabled and legacy AI configs keep the main and child routes available', () => {
  for (const config of [
    { feature_toggle: { ai_capability: true } },
    { feature_toggle: {} },
  ]) {
    const router = createFeatureFixtureRouter(config);
    assert.ok(router.resolve('/sec-chat').matched.some(route => route.name === 'secChat'));
    assert.ok(router.resolve('/sec-chat/audit-log-retrieval/123').matched.some(route => route.name === 'secChat'));
  }
});

test('BKSEC stays hidden until enabled and preserves a requested step 5 until resolution', () => {
  assert.equal(featureToggle.isBksecCapabilityVisible(false, true), false);
  assert.equal(featureToggle.isBksecCapabilityVisible(true, false), false);
  assert.equal(featureToggle.isBksecCapabilityVisible(true, true), true);
  assert.equal(featureToggle.getRequestedStrategyStep('5'), 5);
  assert.equal(featureToggle.getRequestedStrategyStep(['5']), 5);
  assert.equal(featureToggle.clampStrategyStep(5, 4), 4);
  assert.equal(featureToggle.clampStrategyStep(5, 5), 5);
});
