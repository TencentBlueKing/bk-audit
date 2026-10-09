/**
 * 审计用户画像的账号类型使用限制。
 * 取值与画像查询表单一致：企业微信 ctx、openid、微信 form_wechat、QQ form_qq。
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

export interface PortraitScopeQuery {
  scene_id?: number;
  system_id?: string;
}

const ACCOUNT_LABEL = Object.fromEntries(PORTRAIT_ACCOUNT_TYPES.map(item => [item.value, item.label]));

export const portraitAccountLabel = (value: string) => ACCOUNT_LABEL[value] || value;

export const emptyUsageRestrictions = (): UsageRestrictions => ({ scenes: {}, systems: {} });

const rowsOf = (restrictions: UsageRestrictions | undefined, scope: PortraitScopeQuery): UsageRestrictionRow[] => {
  if (scope.scene_id !== undefined && scope.scene_id !== null) {
    return restrictions?.scenes?.[String(scope.scene_id)] || [];
  }
  if (scope.system_id) {
    return restrictions?.systems?.[String(scope.system_id)] || [];
  }
  return [];
};

/** 当前空间未配置时返回 null，表示四个账号类型都可用。 */
export const allowedAccountTypesForScope = (
  restrictions: UsageRestrictions | undefined,
  scope: PortraitScopeQuery,
): string[] | null => {
  const row = rowsOf(restrictions, scope).find(item => item.param === 'type');
  if (!row) return null;
  return row.allowed || [];
};

export const portraitDenialMessage = (accountType: string) => (
  `当前空间不允许使用「${portraitAccountLabel(accountType)}」进行查询`
);

export const findPortraitUsageDenial = (
  restrictions: UsageRestrictions | undefined,
  scope: PortraitScopeQuery,
  accountType: string,
): string => {
  const allowed = allowedAccountTypesForScope(restrictions, scope);
  if (!allowed || allowed.includes(accountType)) return '';
  return portraitDenialMessage(accountType);
};

const canonicalBucket = (bucket?: Record<string, UsageRestrictionRow[]>) => {
  const result: Record<string, string[]> = {};
  Object.keys(bucket || {}).sort().forEach((id) => {
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
