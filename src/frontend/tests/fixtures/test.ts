import { expect, type Page, test as base } from '@playwright/test';
import { ApiRecorder } from '@tencent/aitest/api-recorder';
import { assertNoPageErrors } from '@tencent/aitest/page-errors';
import { dumpFailureAriaSnapshot, getAITestTolerate } from '@tencent/aitest/playwright-env';

/**
 * 默认 fixture：context 级 console.error / pageerror / 同 origin HTTP>=400，
 * 以及可在动作之后 waitFor 的 apiRecorder（缓冲已返回的 JSON）。
 */
export type ToleratePattern = string | RegExp;

function sameOrigin(url: string, baseURL: string | undefined): boolean {
  if (!baseURL) return true;
  try {
    return new URL(url).origin === new URL(baseURL).origin;
  } catch {
    return false;
  }
}

export const test = base.extend<{ errors: string[]; apiRecorder: ApiRecorder }>({
  errors: [async ({ context, baseURL }, use, testInfo) => {
    const errors: string[] = [];
    const attach = (page: Page) => {
      page.on('console', (m) => {
        if (m.type() === 'error') errors.push(`console.error: ${m.text()}`);
      });
      page.on('pageerror', (e) => {
        errors.push(`pageerror: ${e.message}`);
      });
      page.on('response', (r) => {
        if (sameOrigin(r.url(), baseURL) && r.status() >= 400) {
          errors.push(`http ${r.status()}: ${r.url()}`);
        }
      });
    };
    context.pages().forEach(attach);
    context.on('page', attach);
    await use(errors);
    if (testInfo.tags.includes('@no-error-check')) return;
    assertNoPageErrors(errors, getAITestTolerate());
  }, { auto: true }],
  apiRecorder: async ({ context, baseURL }, use) => {
    const recorder = new ApiRecorder(context, baseURL);
    await use(recorder);
    recorder.dispose();
  },
});

test.afterEach(async ({ page }, testInfo) => {
  await dumpFailureAriaSnapshot(page, testInfo);
});

export const describe = test.describe;
export { expect };
