import { expect, test } from '../fixtures/test';

test.describe('风险白名单列表与新建 @REQ-138862832 @QG-risk-whitelist', () => {
  test('打开列表后，页面与真实列表结果一致', async ({ page }) => {
    const responsePromise = page.waitForResponse((response) => (
      response.url().includes('/api/v1/risk_whitelists/')
      && response.request().method() === 'GET'
    ));
    await page.goto('/risk-whitelist/list');
    const response = await responsePromise;
    expect(response.ok(), '风险白名单列表接口应成功').toBeTruthy();

    const body = await response.json() as { data?: { results?: unknown[] }; results?: unknown[] };
    const results = body.data?.results ?? body.results;
    expect(Array.isArray(results), '列表响应应包含 results').toBeTruthy();

    await expect(page.getByRole('columnheader', { name: '规则标识' })).toHaveText('规则标识');
    if (results.length === 0) {
      await expect(page.getByTestId('risk-whitelist-empty')).toHaveText('暂无风险白名单');
      return;
    }

    const first = results[0] as { rule_code?: string };
    const ruleCode = String(first.rule_code || '');
    expect(ruleCode, '有数据时接口应返回规则标识').not.toBe('');
    await expect(page.getByRole('cell', { name: ruleCode, exact: true })).toHaveText(ruleCode);
  });

  test('仅有策略条件时不能误报，未选策略不能提交', async ({ page }) => {
    await page.goto('/risk-whitelist/list');
    await page.getByRole('button', { name: '新建白名单' }).click();

    const form = page.locator('.risk-whitelist-form');
    await expect(form.getByRole('radio')).toHaveText([
      '误报加白',
      '冒险加白',
      '7天',
      '1个月',
      '3个月',
      '6个月',
      '12个月',
      '自定义',
    ]);
    await expect(form.getByRole('radio', { name: '误报加白' })).toBeDisabled();
    await expect(form.getByRole('radio', { name: '冒险加白' })).toBeChecked();
    await expect(form.getByText('只有命中策略条件时不允许误报加白', { exact: true }))
      .toHaveText('只有命中策略条件时不允许误报加白');

    await page.getByRole('button', { name: '提交' }).click();
    await expect(form.getByText('请完善匹配范围', { exact: true })).toHaveText('请完善匹配范围');
  });
});
