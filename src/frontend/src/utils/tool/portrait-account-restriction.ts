/**
 * 审计用户画像的账号类型使用限制。
 * 页面内取值与画像查询表单一致：企业微信 ctx、openid、微信 form_wechat、QQ form_qq；
 * 接口 config.usage_limits / allowed_account_types 使用 form_ctx、form_openid、form_wechat、form_qq。
 */

export const PORTRAIT_ACCOUNT_TYPES = [
  { value: 'ctx', label: '企业微信' },
  { value: 'openid', label: 'openid' },
  { value: 'form_wechat', label: '微信' },
  { value: 'form_qq', label: 'QQ' },
] as const;

export type PortraitAccountType = (typeof PORTRAIT_ACCOUNT_TYPES)[number]['value'];

export interface UsageRestrictionRow {
  id: string;
  kind: 'allowed_values';
  param: 'type';
  allowed: string[];
}

export interface UsageRestrictions {
  scenes?: Record<string, UsageRestrictionRow[]>;
  systems?: Record<string, UsageRestrictionRow[]>;
}

export interface UsageLimits {
  scenes?: Record<string, { account_type?: string[] }>;
  systems?: Record<string, { account_type?: string[] }>;
}

const ACCOUNT_TYPE_TO_API: Record<string, string> = {
  ctx: 'form_ctx',
  openid: 'form_openid',
  form_wechat: 'form_wechat',
  form_qq: 'form_qq',
};

const ACCOUNT_TYPE_FROM_API: Record<string, string> = Object.fromEntries(Object.entries(ACCOUNT_TYPE_TO_API)
  .map(([local, api]) => [api, local]));

const toApiAccountType = (value: string) => ACCOUNT_TYPE_TO_API[value] || value;

const fromApiAccountType = (value: string) => ACCOUNT_TYPE_FROM_API[value] || value;

/** 接口返回 null / undefined 表示不限制。 */
export const allowedAccountTypesFromApi = (value?: string[] | null): string[] | null => (
  Array.isArray(value) ? value.map(fromApiAccountType) : null
);

const limitsBucketToRows = (bucket?: Record<string, { account_type?: string[] }>) => {
  const result: Record<string, UsageRestrictionRow[]> = {};
  Object.entries(bucket || {}).forEach(([id, limit]) => {
    if (!Array.isArray(limit?.account_type)) return;
    result[id] = [{
      id: `ur_${id}`,
      kind: 'allowed_values',
      param: 'type',
      allowed: limit.account_type.map(fromApiAccountType),
    }];
  });
  return result;
};

const rowsBucketToLimits = (bucket?: Record<string, UsageRestrictionRow[]>) => {
  const result: Record<string, { account_type: string[] }> = {};
  Object.entries(bucket || {}).forEach(([id, rows]) => {
    const row = (rows || []).find(item => item.param === 'type');
    if (!row) return;
    result[id] = { account_type: (row.allowed || []).map(toApiAccountType) };
  });
  return result;
};

export const usageLimitsToRestrictions = (limits?: UsageLimits | null): UsageRestrictions => ({
  scenes: limitsBucketToRows(limits?.scenes),
  systems: limitsBucketToRows(limits?.systems),
});

export const usageRestrictionsToLimits = (restrictions?: UsageRestrictions | null) => ({
  scenes: rowsBucketToLimits(restrictions?.scenes),
  systems: rowsBucketToLimits(restrictions?.systems),
});

const ACCOUNT_LABEL = Object.fromEntries(PORTRAIT_ACCOUNT_TYPES.map(item => [item.value, item.label]));

export const portraitAccountLabel = (value: string) => ACCOUNT_LABEL[value] || value;

export const emptyUsageRestrictions = (): UsageRestrictions => ({ scenes: {}, systems: {} });

export const portraitDenialMessage = (accountType: string) => (
  `当前空间不允许使用「${portraitAccountLabel(accountType)}」进行查询`
);

/** allowed 为 null 表示当前空间未配置限制，四个账号类型都可用。 */
export const findPortraitUsageDenial = (allowed: string[] | null, accountType: string): string => {
  if (!allowed || allowed.includes(accountType)) return '';
  return portraitDenialMessage(accountType);
};

const canonicalBucket = (bucket?: Record<string, UsageRestrictionRow[]>) => {
  const result: Record<string, string[]> = {};
  Object.keys(bucket || {}).sort()
    .forEach((id) => {
      const allowed = (bucket?.[id] || []).find(item => item.param === 'type')?.allowed || [];
      result[id] = [...allowed];
    });
  return result;
};

export const canonicalUsageRestrictions = (raw?: UsageRestrictions | null) => ({
  scenes: canonicalBucket(raw?.scenes),
  systems: canonicalBucket(raw?.systems),
});

export const usageRestrictionsChanged = (
  before?: UsageRestrictions | null,
  after?: UsageRestrictions | null,
) => JSON.stringify(canonicalUsageRestrictions(before)) !== JSON.stringify(canonicalUsageRestrictions(after));

export interface UsageScopeCard {
  type: 'scene' | 'system';
  id: number | string;
  name: string;
}

/** 已添加限制但没有取值时不能保存。四个都选中时可以保存，并提示等同于不限制。 */
export const validateUsageRestrictions = (
  restrictions: UsageRestrictions | undefined,
  cards: UsageScopeCard[],
) => {
  let equivalentToUnrestricted = false;
  for (const card of cards) {
    const bucket = card.type === 'scene' ? restrictions?.scenes : restrictions?.systems;
    const row = (bucket?.[String(card.id)] || []).find(item => item.param === 'type');
    if (!row) continue;
    if (!row.allowed?.length) {
      return {
        ok: false,
        message: `${card.name}：至少选择 1 个允许的取值`,
        equivalentToUnrestricted: false,
      };
    }
    if (row.allowed.length >= PORTRAIT_ACCOUNT_TYPES.length) {
      equivalentToUnrestricted = true;
    }
  }
  return { ok: true, message: '', equivalentToUnrestricted };
};

export const affectedRestrictionScopeNames = (
  before: UsageRestrictions | undefined,
  after: UsageRestrictions | undefined,
  cards: UsageScopeCard[],
) => {
  const previous = canonicalUsageRestrictions(before);
  const next = canonicalUsageRestrictions(after);
  const names: string[] = [];
  cards.forEach((card) => {
    const bucketName = card.type === 'scene' ? 'scenes' : 'systems';
    const id = String(card.id);
    const left = previous[bucketName][id] || [];
    const right = next[bucketName][id] || [];
    if (JSON.stringify(left) !== JSON.stringify(right)) {
      names.push(card.name);
    }
  });
  // 可见范围里已经拿掉的空间，变更也要出现在确认文案里
  const known = new Set(cards.map(card => `${card.type}:${card.id}`));
  (['scenes', 'systems'] as const).forEach((bucketName) => {
    const ids = new Set([...Object.keys(previous[bucketName]), ...Object.keys(next[bucketName])]);
    ids.forEach((id) => {
      const type = bucketName === 'scenes' ? 'scene' : 'system';
      if (known.has(`${type}:${id}`)) return;
      if (JSON.stringify(previous[bucketName][id] || []) !== JSON.stringify(next[bucketName][id] || [])) {
        names.push(id);
      }
    });
  });
  return [...new Set(names)];
};

export const pruneUsageRestrictions = (
  restrictions: UsageRestrictions | undefined,
  sceneIds: number[],
  systemIds: string[],
  visibilityType?: string,
): UsageRestrictions => {
  if (!visibilityType
    || visibilityType === 'all_visible'
    || visibilityType === 'all_scenes'
    || visibilityType === 'all_systems') {
    return emptyUsageRestrictions();
  }
  const scenes: Record<string, UsageRestrictionRow[]> = {};
  const systems: Record<string, UsageRestrictionRow[]> = {};
  const keepScenes = visibilityType === 'specific_scenes' || visibilityType === 'scenes_and_systems';
  const keepSystems = visibilityType === 'specific_systems' || visibilityType === 'scenes_and_systems';
  if (keepScenes) {
    sceneIds.forEach((id) => {
      const rows = restrictions?.scenes?.[String(id)];
      if (rows?.length) scenes[String(id)] = rows;
    });
  }
  if (keepSystems) {
    systemIds.forEach((id) => {
      const rows = restrictions?.systems?.[String(id)];
      if (rows?.length) systems[String(id)] = rows;
    });
  }
  return { scenes, systems };
};
