import { defineAITestConfig } from '@tencent/aitest/playwright-env';

/**
 * 接入项目唯一配置入口。未写出的项使用包内默认值。
 *
 * 密钥和地址写在 .AITestEnv（勿提交，禁止 Read 进聊天）：
 *   UITEST_BASE_URL     被测服务地址。aitest run / Playwright 的 baseURL。
 *   UITEST_AUTH_URL     登录采集地址，仅 auth-export 使用；需在 OA 白名单。
 *   UITEST_HEADLESS     1 无头 / 0 有头。CI 始终无头。登录采集不跟随此项。
 *
 * defineAITestConfig 可选项（均可省略，需要时取消注释）：
 *   headed / headless   是否弹出浏览器。省略则跟 UITEST_HEADLESS。
 *                       CI / 无显示器仍无头。单次覆盖：npx aitest run --headed
 *   timeout             单条测试超时（毫秒）
 *   expect              如 { timeout: 15_000 } 断言超时
 *   workers             并行 worker 数
 *   testDir             Spec 目录，默认 ./tests/e2e
 *                       不得配成 './tests' 根目录，否则默认 testMatch 会收走单测
 *   storageState        true 强制加载 .aitest/auth/storageState.json
 *                       false 强制不加载；省略则该文件存在才加载
 *   tolerate            页面 console.error / pageerror / 同域 HTTP>=400 白名单
 *                       字符串为包含匹配，也可传正则。框架已忽略主动取消的请求。
 *                       须用户确认后才加，禁止 Agent 擅自放宽。
 *   use                 与 Playwright use 合并（viewport 等）。
 *                       baseURL 默认来自 UITEST_BASE_URL，不必在此重复填写。
 *
 * 也可传入 Playwright 原生字段（retries、reporter、outputDir、projects 等），会覆盖包内默认。
 * globalSetup / globalTeardown 除外：aitest 门禁始终先跑，用户 hook 串联在后面，不能靠覆盖关掉。
 * 运行产物默认在 .aitest/test-results 与 .aitest/reports/html。
 */
export default defineAITestConfig({
  // headed: false,
  // timeout: 60_000,
  // workers: 2,
  // testDir: './tests/e2e',
  // storageState: true,
  // tolerate: [
  //   'ERR_NAME_NOT_RESOLVED',
  // ],
  // use: { viewport: { width: 1440, height: 900 } },
});
