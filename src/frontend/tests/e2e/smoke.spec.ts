import { expect, test } from '../fixtures/test';

test('入口可访问且无错误遮罩', { tag: '@QG-smoke' }, async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('[data-error], .error-overlay, .fatal-error')).toHaveCount(0);
});
