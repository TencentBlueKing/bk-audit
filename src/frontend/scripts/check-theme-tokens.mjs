/**
 * 校验审计主题 token 与场景层：
 * 1. src 内旧 token 零定义、零引用；运行时代码、脚本和当前规范文档不得残留旧公共命名空间或旧公共场景类
 * 2. 所有 var(--bk-theme-*) 都在 tokens.css 定义
 * 3. 全局主题文件里的 var(--*) 都指向已登记变量
 * 4. tokens.css 分层引用方向：语义层不写 hex（ext 区除外），场景层不引用原始色阶
 * 5. 场景注册表（@scene 注释）一致：每个场景有 token，声明的场景类存在，deprecated 场景无人使用
 * 6. 业务页（src/views、src/components）的违规按「文件 + 属性 + 规范化值 + 选择器上下文」计指纹
 *    新增指纹为 0，模块存量只减不增（scripts/theme-baseline.json version 2）
 *    上下文只保留选择器链。旧基线把嵌套规则前的声明文本也写进了上下文；
 *    这种基线没有 context: "selector"，--update-baseline 只按「文件 + 规则 + 属性 + 值」核对存量，不把换上下文当成新增。
 *
 * 精确豁免（不计入指纹）：
 * - 自定义属性定义（token 定义，含业务页里的 --* 声明）
 * - 1px 边框 / outline 宽度
 * - 落在 box-shadow 上、且 alpha 属于尺度层阴影的颜色（8% / 10% / 12% / 16% / 20%）
 * - 表格容器内控件自己的 border-radius
 *
 * 用法：
 *   node scripts/check-theme-tokens.mjs                  校验
 *   node scripts/check-theme-tokens.mjs --report         按模块、文件、规则、原值、场景覆盖输出
 *   node scripts/check-theme-tokens.mjs --self-test      只跑豁免样例
 *   node scripts/check-theme-tokens.mjs --update-baseline  违规下降后刷新基线（不允许放宽）
 */
import { readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const srcDir = path.join(root, 'src');
const tokenFile = path.join(srcDir, 'css/tokens.css');
const scenesFile = path.join(srcDir, 'css/theme/scenes.css');
const sceneAuditFile = path.join(root, '.agents/skills/bk-audit-ui-verification/scripts/scene-audit.js');
const baselineFile = path.join(root, 'scripts/theme-baseline.json');
const updateBaseline = process.argv.includes('--update-baseline');
const reportMode = process.argv.includes('--report');
const selfTest = process.argv.includes('--self-test');
const globalFiles = [
  'src/css/tokens.css',
  'src/css/reset.css',
  'src/css/common.css',
  'src/css/theme/index.css',
  'src/css/theme/bkui.css',
  'src/css/theme/tdesign.css',
  'src/css/theme/scenes.css',
];
const sourceExt = new Set(['.vue', '.css', '.less', '.scss', '.ts', '.tsx', '.js', '.mjs']);
const oldToken = /--bk-theme-(?:brand|success|warn|danger)-0[1-7]\b|--bk-theme-neutral-(?:text|border|bg)-0[1-4]\b|--bk-theme-radius-(?:control|container)\b/g;
const definedName = /(--[A-Za-z0-9_-]+)\s*:/g;
const referencedName = /var\(\s*(--[A-Za-z0-9_-]+)/g;
const pageDirs = ['src/views', 'src/components'];
const rules = [
  { id: 'scale-radius-shadow', re: /var\(--bk-theme-(?:radius|shadow)-[\w-]+\)/g, msg: '直接用尺度 radius / shadow，应改场景 token 或场景类' },
  { id: 'literal-radius', re: /border(?:-[a-z]+)*-radius\s*:\s*[^;]*\b[1-9]\d*px/g, msg: '字面量圆角' },
  { id: 'literal-shadow', re: /box-shadow\s*:\s*(?!none\b|var\()\S[^;]*/g, msg: '字面量阴影' },
  { id: 'literal-color', re: /(?<![\w&-])#[0-9a-fA-F]{3,8}\b(?![\w-])|rgba?\([^)]*\)/g, msg: '字面量颜色 / alpha' },
  { id: 'literal-spacing', re: /(?:^|[\s;{])(?:padding|margin|gap|row-gap|column-gap)(?:-[a-z]+)?\s*:\s*[^;]*\b[1-9]\d*px/gm, msg: '字面量 px 间距，应写 var(--bk-theme-space-N)' },
  { id: 'space-40', re: /var\(--bk-theme-space-40\)/g, msg: 'space-40 不在规范档位' },
  { id: 'annotation-color', re: /#e5e5e5\b/gi, msg: '标注外框底色禁止进产品页' },
  { id: 'frozen-utility', re: /class="[^"]*\b(?:m[tbrl](?:8|12|16|24))\b/g, msg: '新代码不用冻结原子类 .mt8 等，改写 var(--bk-theme-space-N)' },
  { id: 'scene-override', re: /\.bk-form-item[^{,]*\{[^}]*margin-bottom|\.bk-(?:dialog|sideslider)-(?:content|footer|header)[^{,]*\{[^}]*padding/g, msg: '业务页覆盖组件级场景属性，改用场景类或改写场景变量' },
];
const LEGAL_SHADOW_ALPHA = [0.08, 0.1, 0.12, 0.16, 0.2];

const errors = [];

function lineOf(text, index) {
  return text.slice(0, index).split('\n').length;
}

function stripComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
}

function normalizeValue(value) {
  return value.replace(/\s+/g, ' ').replace(/\s*!important\s*$/i, '').trim().toLowerCase();
}

function propertyAt(text, index, raw) {
  const named = raw.match(/^[\s;{]*(-{0,2}[a-zA-Z][\w-]*)\s*:/);
  if (named) return named[1].toLowerCase();
  const head = text.slice(Math.max(0, index - 200), index);
  let found = '';
  for (const matched of head.matchAll(/(-{0,2}[a-zA-Z][\w-]*)\s*:/g)) found = matched[1].toLowerCase();
  return found;
}

function enclosingOpen(text, index) {
  let depth = 0;
  for (let i = index; i >= 0; i -= 1) {
    const ch = text[i];
    if (ch === '}') depth += 1;
    else if (ch === '{') {
      if (depth === 0) return i;
      depth -= 1;
    }
  }
  return -1;
}

function selectorsAround(text, index) {
  const found = [];
  let cursor = index;
  for (let i = 0; i < 8; i += 1) {
    const open = enclosingOpen(text, cursor);
    if (open < 0) break;
    const bound = Math.max(text.lastIndexOf('}', open - 1), text.lastIndexOf('{', open - 1));
    const raw = text.slice(bound + 1, open);
    const semi = raw.lastIndexOf(';');
    const selector = (semi >= 0 ? raw.slice(semi + 1) : raw).replace(/\s+/g, ' ').trim();
    if (selector && !selector.startsWith('@')) found.push(selector.slice(-160));
    cursor = open - 1;
  }
  return found;
}

function alphaOf(color) {
  const modern = color.match(/\/\s*(\d+(?:\.\d+)?)(%)?\s*\)/);
  if (modern) {
    const n = Number.parseFloat(modern[1]);
    return modern[2] ? n / 100 : n;
  }
  const rgba = color.match(/rgba\(\s*[\d.\s]+,\s*([\d.]+)\s*\)/i);
  if (rgba) return Number.parseFloat(rgba[1]);
  const hex = color.match(/#([0-9a-f]{8})\b/i);
  if (hex) return Number.parseInt(hex[1].slice(6), 16) / 255;
  return null;
}

function isLegalShadowAlpha(color) {
  const alpha = alphaOf(color);
  if (alpha === null) return false;
  return LEGAL_SHADOW_ALPHA.some((n) => Math.abs(alpha - n) < 0.012);
}

function isOnePixelBorder(prop, value) {
  if (!/^(?:border(?:-(?:top|right|bottom|left))?(?:-width)?|outline(?:-width)?)$/.test(prop)) return false;
  const widths = value.match(/\b\d+(?:\.\d+)?px\b/g) || [];
  return widths.length > 0 && widths.every((w) => w === '1px');
}

function isTableControlRadius(prop, selectors) {
  if (!/(?:^|-)radius$/.test(prop)) return false;
  const joined = selectors.join(' ');
  const inTable = /(?:bk-table|t-table|audit-tdesign-list|audit-render-list)/.test(joined);
  const isControl = /(?:bk-input|bk-select|bk-button|bk-tag|bk-radio|bk-checkbox|bk-date-picker|t-input|t-select|date-picker|bk-tag-input)/.test(joined);
  return inTable && isControl;
}

function isExempt(ruleId, prop, raw, selectors) {
  if (prop.startsWith('--')) return true;
  if (ruleId === 'literal-spacing' && isOnePixelBorder(prop, raw)) return true;
  if (ruleId === 'literal-color' && prop === 'box-shadow' && isLegalShadowAlpha(raw)) return true;
  if (ruleId === 'literal-radius' && isTableControlRadius(prop, selectors)) return true;
  return false;
}

function categoryOf(ruleId, value) {
  if (ruleId === 'literal-spacing') return '间距';
  if (ruleId === 'literal-radius') return '圆角';
  if (ruleId === 'literal-shadow') return '阴影';
  if (ruleId === 'literal-color' || ruleId === 'annotation-color') {
    return alphaOf(value) === null ? '颜色' : 'alpha';
  }
  return '其它';
}

function valueOfMatch(ruleId, raw, prop) {
  if (ruleId === 'literal-radius' || ruleId === 'literal-shadow' || ruleId === 'literal-spacing') {
    const split = raw.split(':');
    return normalizeValue(split.slice(1).join(':'));
  }
  if (ruleId === 'literal-color' || ruleId === 'annotation-color') return normalizeValue(raw);
  if (prop) return normalizeValue(raw);
  return normalizeValue(raw);
}

export function collectHits(styleText, file, templateText = '') {
  const hits = [];
  for (const rule of rules) {
    const target = rule.id === 'frozen-utility' ? templateText : styleText;
    for (const match of target.matchAll(rule.re)) {
      const prop = rule.id === 'frozen-utility' ? 'class' : propertyAt(target, match.index, match[0]);
      const selectors = rule.id === 'frozen-utility' ? [] : selectorsAround(target, match.index);
      const rawValue = valueOfMatch(rule.id, match[0], prop);
      if (isExempt(rule.id, prop, rule.id === 'literal-color' || rule.id === 'annotation-color' ? match[0] : rawValue, selectors)) continue;
      const context = selectors.join(' >> ');
      hits.push({
        file,
        rule: rule.id,
        prop: prop || rule.id,
        value: rawValue,
        context,
        category: categoryOf(rule.id, rawValue),
        fingerprint: [file, rule.id, prop || rule.id, rawValue, context].join('\t'),
      });
    }
  }
  return hits;
}

function runSelfTest() {
  const cases = [
    {
      name: '普通颜色和圆角仍计数',
      css: '.card { color: #fff; border-radius: 2px; padding: 14px; }',
      rules: ['literal-color', 'literal-radius', 'literal-spacing'],
    },
    {
      name: 'token 定义豁免',
      css: '.card { --local-bg: #fff; color: var(--bk-theme-text-default); }',
      rules: [],
    },
    {
      name: '1px 边框宽度豁免，边框色仍计数',
      css: '.card { border: 1px solid #dcdee5; outline: 1px solid #fff; padding: 1px; }',
      rules: ['literal-color', 'literal-color', 'literal-spacing'],
    },
    {
      name: '合法阴影 alpha 不计颜色，阴影本身仍计数',
      css: '.card { box-shadow: 0 4px 16px rgb(31 41 69 / 8%); }',
      rules: ['literal-shadow'],
    },
    {
      name: 'var() 和 none 阴影不计',
      css: '.card { box-shadow: var(--bk-theme-card-shadow); box-shadow: none; }',
      rules: [],
    },
    {
      name: '嵌套上下文只保留选择器',
      css: '.parent { padding: 16px; .child { color: #fff; } }',
      rules: ['literal-spacing', 'literal-color'],
      fingerprints: [
        'fixture.css\tliteral-spacing\tpadding\t16px\t.parent',
        'fixture.css\tliteral-color\tcolor\t#fff\t.child >> .parent',
      ],
    },
    {
      name: '非法定 alpha 的阴影颜色仍计数',
      css: '.card { box-shadow: 0 0 3px rgba(0, 0, 0, 0.4); }',
      rules: ['literal-shadow', 'literal-color'],
    },
    {
      name: '表格内控件圆角豁免，表格外框圆角不豁免',
      css: '.bk-table { .bk-input { border-radius: 2px; } border-radius: 8px; }',
      rules: ['literal-radius'],
    },
  ];
  const failures = [];
  for (const item of cases) {
    const hits = collectHits(item.css, 'fixture.css');
    const got = hits.map((hit) => hit.rule).sort();
    const want = [...item.rules].sort();
    if (got.join(',') !== want.join(',')) failures.push(`${item.name}: 期望 ${want.join(',') || '无'}，实际 ${got.join(',') || '无'}`);
    if (item.fingerprints) {
      const gotFp = hits.map((hit) => hit.fingerprint).sort();
      const wantFp = [...item.fingerprints].sort();
      if (gotFp.join('\n') !== wantFp.join('\n')) failures.push(`${item.name}: 指纹期望 ${wantFp.join(' | ') || '无'}，实际 ${gotFp.join(' | ') || '无'}`);
    }
  }
  if (!isOnePixelBorder('border', '1px solid #dcdee5')) failures.push('1px 边框未被识别');
  if (isOnePixelBorder('border', '2px solid #dcdee5')) failures.push('2px 边框被误豁免');
  if (isOnePixelBorder('padding', '1px')) failures.push('1px 间距被误当成边框');
  if (failures.length) {
    console.error(failures.join('\n'));
    console.error(`\n豁免样例失败，${failures.length} 处。`);
    process.exit(1);
  }
  console.log(`豁免样例通过，${cases.length} 组。`);
}

if (selfTest) {
  runSelfTest();
  process.exit(0);
}

async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.name === 'node_modules' || entry.name === 'dist') continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...await walk(full));
    else if (sourceExt.has(path.extname(entry.name))) files.push(full);
  }
  return files;
}

function moduleOf(rel) {
  return rel.split('/').slice(1, 3).join('/');
}

function parseScenes(tokenText) {
  const sceneRe = /\/\*\s*@scene\s+([\w-]+)\s*\|([^\n*]*)/g;
  const scenes = [];
  for (const match of tokenText.matchAll(sceneRe)) {
    const fields = Object.fromEntries(match[2].split('|').map((part) => {
      const [k, ...v] = part.split(':');
      return v.length ? [k.trim(), v.join(':').trim()] : ['name', k.trim()];
    }));
    const start = match.index + match[0].length;
    const nextMatch = tokenText.slice(start).search(/\/\*\s*@scene\s|\n}/);
    const block = tokenText.slice(start, nextMatch < 0 ? undefined : start + nextMatch);
    const tokens = [...stripComments(block).matchAll(definedName)].map((m) => m[1]);
    scenes.push({ id: match[1], ...fields, tokens, line: lineOf(tokenText, match.index) });
  }
  return scenes;
}

function detectorNames(source) {
  const block = source.match(/const DETECTORS = \{([\s\S]*?)\n  \};/);
  if (!block) return [];
  return [...block[1].matchAll(/^\s*(?:'([^']+)'|([A-Za-z][\w-]*))\s*\(scene\)/gm)].map((m) => m[1] || m[2]);
}

const srcFiles = await walk(srcDir);
const tokenText = await readFile(tokenFile, 'utf8');
const auditDefined = new Set();
for (const match of tokenText.matchAll(definedName)) {
  if (match[1].startsWith('--bk-theme-')) auditDefined.add(match[1]);
}

for (const file of srcFiles) {
  const text = stripComments(await readFile(file, 'utf8'));
  const rel = path.relative(root, file);
  for (const match of text.matchAll(oldToken)) {
    errors.push(`${rel}:${lineOf(text, match.index)} 仍使用旧 token ${match[0]}`);
  }
  for (const match of text.matchAll(referencedName)) {
    const name = match[1];
    if (name.startsWith('--bk-theme-') && !auditDefined.has(name)) {
      errors.push(`${rel}:${lineOf(text, match.index)} 引用了未定义的 ${name}`);
    }
  }
}

const legacyToken = new RegExp(`--${'audit'}-`, 'g');
const legacySceneClass = /(?<![\w-])audit-(?:card|search-card|select-banner|cell-tip|list-toolbar|descriptions--|form--)(?![\w-])/g;
const legacySkip = /theme-freeze|browseros-verify/;
async function walkText(dir, exts) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.name === 'node_modules' || entry.name === 'dist') continue;
    const full = path.join(dir, entry.name);
    if (legacySkip.test(full)) continue;
    if (entry.isDirectory()) files.push(...await walkText(full, exts));
    else if (exts.has(path.extname(entry.name))) files.push(full);
  }
  return files;
}
const legacyFiles = [
  ...srcFiles,
  ...await walkText(path.join(root, 'scripts'), sourceExt),
  ...await walkText(path.join(root, 'docs'), new Set(['.md'])),
];
const seenLegacy = new Set();
for (const file of legacyFiles) {
  if (seenLegacy.has(file) || legacySkip.test(file)) continue;
  seenLegacy.add(file);
  const text = await readFile(file, 'utf8');
  const rel = path.relative(root, file);
  for (const match of text.matchAll(legacyToken)) {
    errors.push(`${rel}:${lineOf(text, match.index)} 残留旧命名空间 ${match[0]}`);
  }
  for (const match of text.matchAll(legacySceneClass)) {
    errors.push(`${rel}:${lineOf(text, match.index)} 残留旧公共场景类 ${match[0]}`);
  }
}

const globalDefined = new Set();
const globalTexts = new Map();
for (const rel of globalFiles) {
  const text = stripComments(await readFile(path.join(root, rel), 'utf8'));
  globalTexts.set(rel, text);
  for (const match of text.matchAll(definedName)) globalDefined.add(match[1]);
}
for (const [rel, text] of globalTexts) {
  for (const match of text.matchAll(referencedName)) {
    if (!globalDefined.has(match[1])) {
      errors.push(`${rel}:${lineOf(text, match.index)} 全局主题引用了未登记变量 ${match[1]}`);
    }
  }
}

const sceneMarker = tokenText.indexOf('场景层。业务页');
if (sceneMarker < 0) errors.push('src/css/tokens.css 缺少「场景层」分隔注释');
const tokenNoComment = stripComments(tokenText);
const declRe = /(--bk-theme-[\w-]+)\s*:\s*([^;]+);/g;
for (const match of tokenNoComment.matchAll(declRe)) {
  const [, name, value] = match;
  const inScene = sceneMarker >= 0 && match.index > sceneMarker;
  const isPrimitive = /^--bk-theme-color-/.test(name);
  if (!isPrimitive && !inScene && /#[0-9a-fA-F]{3,8}\b/.test(value)) {
    errors.push(`src/css/tokens.css:${lineOf(tokenText, match.index)} 语义 / 尺度层 ${name} 写了 hex，应放进 --bk-theme-color-ext-* 再引用`);
  }
  if (inScene && /#[0-9a-fA-F]{3,8}\b/.test(value)) {
    errors.push(`src/css/tokens.css:${lineOf(tokenText, match.index)} 场景层 ${name} 写了 hex`);
  }
  if (inScene && /var\(--bk-theme-color-(?:brand|neutral|success|warn|danger)-\d/.test(value)) {
    errors.push(`src/css/tokens.css:${lineOf(tokenText, match.index)} 场景层 ${name} 直接引用原始色阶，应经语义层`);
  }
}

const scenesText = await readFile(scenesFile, 'utf8');
const scenes = parseScenes(tokenText);
const sceneIds = new Set();
for (const scene of scenes) {
  if (sceneIds.has(scene.id)) errors.push(`src/css/tokens.css:${scene.line} 场景 ${scene.id} 重复注册`);
  sceneIds.add(scene.id);
  if (!scene.tokens.length) errors.push(`src/css/tokens.css:${scene.line} 场景 ${scene.id} 没有 token`);
  if (!['active', 'placeholder', 'deprecated'].includes(scene.status)) {
    errors.push(`src/css/tokens.css:${scene.line} 场景 ${scene.id} status 不在 active|placeholder|deprecated`);
  }
  for (const cls of (scene.class || '').split(/\s+/).filter((c) => c.startsWith('.'))) {
    const re = new RegExp(`${cls.replace(/[.-]/g, (c) => `\\${c}`)}(?![\\w-])`);
    if (!re.test(scenesText)) errors.push(`src/css/tokens.css:${scene.line} 场景 ${scene.id} 声明的类 ${cls} 不在 theme/scenes.css`);
  }
}
const deprecatedTokens = scenes.filter((s) => s.status === 'deprecated').flatMap((s) => s.tokens);

const hits = [];
for (const file of srcFiles) {
  const rel = path.relative(root, file);
  if (!pageDirs.some((dir) => rel.startsWith(dir))) continue;
  if (!['.vue', '.css', '.less', '.scss'].includes(path.extname(file))) continue;
  const text = stripComments(await readFile(file, 'utf8'));
  const styleText = path.extname(file) === '.vue'
    ? [...text.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join('\n')
    : text;
  const templateText = path.extname(file) === '.vue' ? (text.match(/<template>[\s\S]*<\/template>/) || [''])[0] : '';
  hits.push(...collectHits(styleText, rel, templateText));
  for (const name of deprecatedTokens) {
    if (text.includes(`var(${name})`)) errors.push(`${rel} 仍在使用已废弃场景 token ${name}`);
  }
}

const hitCounts = {};
const moduleCounts = {};
for (const hit of hits) {
  hitCounts[hit.fingerprint] = (hitCounts[hit.fingerprint] ?? 0) + 1;
  const mod = moduleOf(hit.file);
  moduleCounts[mod] = (moduleCounts[mod] ?? 0) + 1;
}

function readBaseline(raw) {
  if (!raw || raw.version !== 2 || !raw.hits || !raw.modules) {
    return { version: raw && raw.version === 2 ? 2 : 1, hits: {}, modules: {} };
  }
  return raw;
}

let baseline = { version: 0, hits: {}, modules: {} };
try {
  baseline = readBaseline(JSON.parse(await readFile(baselineFile, 'utf8')));
} catch {
  baseline = { version: 0, hits: {}, modules: {} };
}

function printReport() {
  const byModule = {};
  const byFile = {};
  const byRule = {};
  const byValue = {};
  for (const hit of hits) {
    const mod = moduleOf(hit.file);
    byModule[mod] = (byModule[mod] ?? 0) + 1;
    byFile[hit.file] = byFile[hit.file] ?? {};
    byFile[hit.file][hit.rule] = (byFile[hit.file][hit.rule] ?? 0) + 1;
    byRule[hit.rule] = (byRule[hit.rule] ?? 0) + 1;
    const valueKey = `${hit.category}\t${hit.value}`;
    byValue[valueKey] = (byValue[valueKey] ?? 0) + 1;
  }
  const ruleIds = rules.map((r) => r.id);
  console.log('## 按模块');
  console.log(`| 模块 | 合计 | ${ruleIds.join(' | ')} |`);
  console.log(`| ${['---', '---', ...ruleIds].join(' | ')} |`);
  const moduleRules = {};
  for (const hit of hits) {
    const mod = moduleOf(hit.file);
    moduleRules[mod] ??= {};
    moduleRules[mod][hit.rule] = (moduleRules[mod][hit.rule] ?? 0) + 1;
  }
  Object.entries(byModule).sort((a, b) => b[1] - a[1]).forEach(([mod, total]) => {
    console.log(`| ${[mod, total, ...ruleIds.map((id) => moduleRules[mod][id] ?? 0)].join(' | ')} |`);
  });

  console.log('\n## 按规则');
  console.log('| 规则 | 合计 |');
  console.log('| --- | --- |');
  Object.entries(byRule).sort((a, b) => b[1] - a[1]).forEach(([rule, n]) => {
    console.log(`| ${rule} | ${n} |`);
  });

  console.log('\n## 按文件');
  console.log(`| 文件 | 合计 | ${ruleIds.join(' | ')} |`);
  console.log(`| ${['---', '---', ...ruleIds].join(' | ')} |`);
  Object.entries(byFile)
    .map(([file, row]) => [file, Object.values(row).reduce((a, b) => a + b, 0), row])
    .sort((a, b) => b[1] - a[1])
    .forEach(([file, total, row]) => {
      console.log(`| ${[file, total, ...ruleIds.map((id) => row[id] ?? 0)].join(' | ')} |`);
    });

  console.log('\n## 按原值');
  console.log('| 类别 | 原值 | 合计 |');
  console.log('| --- | --- | --- |');
  Object.entries(byValue).sort((a, b) => b[1] - a[1]).forEach(([key, n]) => {
    const [category, value] = key.split('\t');
    console.log(`| ${category} | \`${value.replace(/\|/g, '\\|')}\` | ${n} |`);
  });

  const detectors = detectorNames(sceneAuditSource);
  console.log('\n## 场景覆盖');
  console.log('| 场景 | detect | 识别器 | status |');
  console.log('| --- | --- | --- | --- |');
  for (const scene of scenes) {
    const ready = detectors.includes(scene.detect) ? '有' : '无';
    console.log(`| ${scene.id} | ${scene.detect || '-'} | ${ready} | ${scene.status || '-'} |`);
  }
  const grand = hits.length;
  console.log(`\n共 ${Object.keys(byModule).length} 个模块、${Object.keys(byFile).length} 个文件、${grand} 处。旧 token ${errors.filter((e) => e.includes('旧 token')).length}，未定义 token ${errors.filter((e) => e.includes('未定义')).length}。`);
}

let sceneAuditSource = '';
try {
  sceneAuditSource = await readFile(sceneAuditFile, 'utf8');
} catch {
  sceneAuditSource = '';
}

if (reportMode) {
  printReport();
  if (errors.length) {
    console.error(errors.join('\n'));
    console.error(`\n主题 token 校验失败，${errors.length} 处。`);
    process.exit(1);
  }
  process.exit(0);
}

function valueKey(fp) {
  return fp.split('\t').slice(0, 4).join('\t');
}

function countBy(entries, keyOf) {
  const counts = {};
  for (const [fp, n] of entries) {
    const key = keyOf(fp);
    counts[key] = (counts[key] ?? 0) + n;
  }
  return counts;
}

function refuseWiden() {
  if (baseline.version !== 2) return;
  const selectorContext = baseline.context === 'selector';
  if (selectorContext) {
    for (const [fp, n] of Object.entries(hitCounts)) {
      const prev = baseline.hits[fp] ?? 0;
      if (n > prev) errors.push(`新增违规 ${fp}：${prev} → ${n}`);
    }
  } else {
    const prevValues = countBy(Object.entries(baseline.hits), valueKey);
    const nextValues = countBy(Object.entries(hitCounts), valueKey);
    for (const [key, n] of Object.entries(nextValues)) {
      const prev = prevValues[key] ?? 0;
      if (n > prev) errors.push(`新增违规 ${key}：${prev} → ${n}`);
    }
  }
  for (const [mod, n] of Object.entries(moduleCounts)) {
    const prev = baseline.modules[mod] ?? 0;
    if (n > prev) errors.push(`模块 ${mod} 存量 ${prev} → ${n}，不能用 --update-baseline 放宽`);
  }
}

if (updateBaseline) {
  refuseWiden();
  if (!errors.length) {
    const sortedHits = Object.fromEntries(Object.keys(hitCounts).sort().map((k) => [k, hitCounts[k]]));
    const sortedModules = Object.fromEntries(Object.keys(moduleCounts).sort().map((k) => [k, moduleCounts[k]]));
    const next = {
      version: 2,
      context: 'selector',
      modules: sortedModules,
      hits: sortedHits,
    };
    await writeFile(baselineFile, `${JSON.stringify(next, null, 2)}\n`);
    console.log(`已刷新 ${path.relative(root, baselineFile)}：${Object.keys(sortedHits).length} 个指纹，${hits.length} 处，${Object.keys(sortedModules).length} 个模块。`);
  }
} else if (baseline.version !== 2 || baseline.context !== 'selector') {
  errors.push('基线上下文仍含声明文本，或尚未冻结为选择器指纹。违规下降后执行 --update-baseline，不能沿用旧上下文。');
} else {
  const ruleMsg = Object.fromEntries(rules.map((r) => [r.id, r.msg]));
  for (const [fp, n] of Object.entries(hitCounts)) {
    const prev = baseline.hits[fp] ?? 0;
    if (n > prev) {
      const [file, , prop, value] = fp.split('\t');
      const rule = hits.find((hit) => hit.fingerprint === fp)?.rule ?? '';
      errors.push(`${file} ${ruleMsg[rule] || rule} ${prop}=${value}：${prev} → ${n}`);
    }
  }
  for (const [mod, n] of Object.entries(moduleCounts)) {
    const prev = baseline.modules[mod] ?? 0;
    if (n > prev) errors.push(`模块 ${mod} 存量 ${prev} → ${n}`);
  }
}

if (errors.length) {
  console.error(errors.join('\n'));
  console.error(`\n主题 token 校验失败，${errors.length} 处。`);
  process.exit(1);
}

console.log(`主题 token 校验通过：${auditDefined.size} 个 --bk-theme-*，${scenes.length} 个场景，已扫描 src ${srcFiles.length} 个文件；业务页存量违规 ${hits.length} 处（指纹只减不增，模块存量只减不增）。`);
