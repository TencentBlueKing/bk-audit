/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
*/

import _ from 'lodash';
import type { RouteLocationNormalizedLoaded } from 'vue-router';

import { getStrategyBindingScope } from '../../utils/strategy-routes';

import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

type FlatCondition = {
  field?: string;
  operator?: string;
  value?: string;
};

type RouteLike = Pick<RouteLocationNormalizedLoaded, 'name' | 'meta'> | null | undefined;

export const isEmptyDispatchConditions = (conditions: Record<string, any> | null | undefined) => {
  if (!conditions || Array.isArray(conditions)) {
    return !conditions || !conditions.length;
  }
  return !conditions.conditions?.length;
};

export const toDispatchConditions = (flat: FlatCondition[] | Record<string, any> | undefined) => {
  if (!flat) return {};
  if (!Array.isArray(flat)) {
    if (flat.connector || Array.isArray(flat.conditions)) {
      return isEmptyDispatchConditions(flat) ? {} : flat;
    }
    return {};
  }
  const valid = flat.filter(item => item.field && item.operator);
  if (!valid.length) return {};
  return {
    connector: 'and',
    conditions: valid.map(item => ({
      condition: {
        field: item.field,
        operator: item.operator,
        filter: item.value,
      },
    })),
  };
};

type DispatchConditions = Record<string, any> | FlatCondition[] | undefined;

export const fromDispatchConditions = (conditions: DispatchConditions): FlatCondition[] => {
  if (!conditions) return [{ field: '', operator: 'eq', value: '' }];
  if (Array.isArray(conditions)) {
    return conditions.length
      ? conditions.map(item => ({
        field: item.field ?? '',
        operator: item.operator ?? 'eq',
        value: item.value ?? '',
      }))
      : [{ field: '', operator: 'eq', value: '' }];
  }
  const list = conditions.conditions ?? [];
  if (!list.length) return [{ field: '', operator: 'eq', value: '' }];
  return list.map((item: any) => {
    const condition = item.condition ?? item;
    return {
      field: condition.field ?? '',
      operator: condition.operator ?? 'eq',
      value: condition.filter ?? condition.filters?.[0] ?? condition.value ?? '',
    };
  });
};

const mapAssignModeToDispatch = (mode?: string) => (mode === 'direct' ? 'direct' : 'after_confirm');

const mapDispatchModeToAssign = (mode?: string) => (mode === 'direct' ? 'direct' : 'confirm');

const toTargetSceneId = (rule: Record<string, any>) => {
  if (rule.target_scene_id !== undefined && rule.target_scene_id !== null && rule.target_scene_id !== '') {
    const num = Number(rule.target_scene_id);
    return Number.isNaN(num) ? rule.target_scene_id : num;
  }
  let ids = rule.scene_ids;
  if (!Array.isArray(ids)) {
    const hasSceneId = rule.scene_id !== undefined && rule.scene_id !== null && rule.scene_id !== '';
    ids = hasSceneId ? [rule.scene_id] : [];
  }
  const first = ids.find((id: string | number) => id !== '' && id !== null && id !== undefined);
  if (first === undefined) return undefined;
  const num = Number(first);
  return Number.isNaN(num) ? first : num;
};

const toDispatchRule = (rule: Record<string, any>, isDefault: boolean) => {
  const conditions = isDefault
    ? {}
    : toDispatchConditions(rule.conditions);
  return {
    rule_name: rule.rule_name || rule.name || (isDefault ? '默认分派规则' : '分派规则'),
    conditions,
    target_scene_id: toTargetSceneId(rule),
    processor: rule.processor ?? rule.processors ?? [],
    follower: rule.follower ?? rule.notice_users ?? [],
    confirmer: rule.confirmer ?? rule.confirmers ?? [],
    dispatch_mode: rule.dispatch_mode || mapAssignModeToDispatch(rule.assign_mode),
  };
};

/** 条件分派规则在前，默认分派规则在后，与页面顺序一致 */
const buildDispatchRules = (params: Record<string, any>, isPlatform: boolean) => {
  if (!isPlatform) {
    return [];
  }
  if (Array.isArray(params.dispatch_rules) && params.dispatch_rules.length && !params.assign_rules?.length) {
    return params.dispatch_rules.map((rule: Record<string, any>) => (
      toDispatchRule(rule, isEmptyDispatchConditions(toDispatchConditions(rule.conditions)))
    ));
  }
  const list: Array<Record<string, any>> = [];
  (params.assign_rules || []).forEach((rule: Record<string, any>) => {
    list.push(toDispatchRule(rule, false));
  });
  if (params.default_assign_rule && Object.keys(params.default_assign_rule).length) {
    list.push(toDispatchRule({
      ...params.default_assign_rule,
      name: params.default_assign_rule.rule_name || params.default_assign_rule.name || '默认分派规则',
    }, true));
  }
  return list;
};

/** 从分派规则收集可见场景 ID（去重，保持出现顺序） */
const collectVisibilitySceneIds = (params: Record<string, any>): Array<string | number> => {
  const ids: Array<string | number> = [];
  const seen = new Set<string | number>();

  const addId = (value: unknown) => {
    const normalized = normalizeSceneId(value);
    if (normalized === undefined || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    ids.push(normalized);
  };

  const addFromRule = (rule: Record<string, any> | undefined) => {
    if (!rule) return;
    if (Array.isArray(rule.scene_ids) && rule.scene_ids.length) {
      rule.scene_ids.forEach(addId);
      return;
    }
    addId(toTargetSceneId(rule));
  };

  (params.assign_rules || []).forEach(addFromRule);
  addFromRule(params.default_assign_rule);

  if (!ids.length && Array.isArray(params.dispatch_rules)) {
    params.dispatch_rules.forEach((rule: Record<string, any>) => {
      if (Array.isArray(rule.scene_ids) && rule.scene_ids.length) {
        rule.scene_ids.forEach(addId);
      } else {
        addId(toTargetSceneId(rule));
      }
    });
  }

  return ids;
};

const buildVisibility = (params: Record<string, any>, isPlatform: boolean) => {
  if (!isPlatform) {
    return undefined;
  }
  return {
    visibility_type: 'specific_scenes' as const,
    scene_ids: collectVisibilitySceneIds(params),
  };
};

const pickWhereHaving = (rule: Record<string, any>, fallbackConfigs?: Record<string, any>) => {
  if (rule.conditions && (rule.conditions.where !== undefined || rule.conditions.having !== undefined)) {
    return {
      where: rule.conditions.where ?? null,
      having: rule.conditions.having ?? null,
    };
  }
  const configs = rule.configs || {};
  return {
    where: configs.where ?? fallbackConfigs?.where ?? null,
    having: configs.having ?? fallbackConfigs?.having ?? null,
  };
};

const buildRules = (params: Record<string, any>, isScene: boolean) => {
  const source = params.rules?.length
    ? params.rules
    : [{
      name: '规则1',
      risk_title: params.risk_title,
      risk_level: params.risk_level,
      risk_hazard: params.risk_hazard,
      risk_guidance: params.risk_guidance,
      configs: params.configs,
      processor: params.processor ?? params.processor_groups,
      follower: params.follower ?? params.notice_groups,
    }];

  const fallbackProcessor = params.processor_groups?.length
    ? params.processor_groups
    : (params.default_assign_rule?.processors
      ?? params.default_assign_rule?.processor
      ?? []);
  const fallbackFollower = params.notice_groups?.length
    ? params.notice_groups
    : (params.default_assign_rule?.notice_users
      ?? params.default_assign_rule?.follower
      ?? []);

  return source.map((rule: Record<string, any>, index: number) => {
    const { where, having } = pickWhereHaving(rule, index === 0 ? params.configs : undefined);
    let processor: Array<string | number> = [];
    let follower: Array<string | number> = [];
    if (isScene) {
      processor = rule.processor?.length ? rule.processor : fallbackProcessor;
      follower = rule.follower?.length ? rule.follower : fallbackFollower;
    }
    return {
      rule_name: rule.rule_name || rule.name || `规则${index + 1}`,
      conditions: {
        where,
        having,
      },
      risk_title: rule.risk_title ?? '',
      risk_level: rule.risk_level ?? 'HIGH',
      risk_hazard: rule.risk_hazard ?? '',
      risk_guidance: rule.risk_guidance ?? '',
      processor,
      follower,
    };
  });
};

const stripConfigs = (configs: Record<string, any> | undefined) => {
  if (!configs) return configs || {};
  const next = _.cloneDeep(configs);
  delete next.where;
  delete next.having;
  delete next.table_fields;
  return next;
};

const normalizeSceneId = (value: unknown): string | number | undefined => {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }
  const num = Number(value);
  return Number.isNaN(num) ? value as string | number : num;
};

/** 场景策略提交时解析 scene_id（兼容详情未返回、表单为空字符串等情况） */
export const resolveStrategySceneId = (
  params: Record<string, any>,
  route?: RouteLike,
): string | number | undefined => (
  normalizeSceneId(params.scene_id)
  ?? normalizeSceneId(getStrategyBindingScope(route).scene_id)
  ?? normalizeSceneId(getSceneSystemParams().scope_id)
);

/** 新建/编辑提交：将向导表单转为新协议 body */
export const buildStrategyCreatePayload = (
  params: Record<string, any>,
  route?: RouteLike,
) => {
  const next = _.cloneDeep(params);
  const scope = getStrategyBindingScope(route);
  const isEdit = !!next.strategy_id;
  const bindingType = params.binding_type || scope.binding_type;
  const isSceneBinding = bindingType === 'scene_binding';

  if (!isEdit) {
    next.binding_type = bindingType;
    if (isSceneBinding) {
      const sceneId = resolveStrategySceneId(params, route);
      if (sceneId !== undefined) {
        next.scene_id = sceneId;
      } else {
        delete next.scene_id;
      }
    } else {
      delete next.scene_id;
    }
  } else {
    delete next.binding_type;
    delete next.bind_type;
    delete next.scene_id;
  }

  const isScene = isSceneBinding;

  const isRuleStrategy = !next.strategy_type || next.strategy_type === 'rule';
  if (isRuleStrategy) {
    next.rules = buildRules(next, isScene);
    next.configs = stripConfigs(next.configs);
    delete next.risk_level;
    delete next.risk_hazard;
    delete next.risk_guidance;
    delete next.risk_title;
  }

  next.dispatch_rules = buildDispatchRules(next, scope.isPlatform);

  const visibility = buildVisibility(next, scope.isPlatform);
  if (visibility) {
    next.visibility = visibility;
  } else {
    delete next.visibility;
  }

  delete next.assign_rules;
  delete next.default_assign_rule;
  delete next.processor_groups;
  delete next.notice_groups;
  delete next.visibility_type;
  delete next.scene_ids;
  delete next.system_ids;

  return next;
};

const fromDispatchRuleToForm = (rule: Record<string, any>) => ({
  name: rule.rule_name || rule.name,
  conditions: fromDispatchConditions(rule.conditions),
  scene_ids: rule.target_scene_id !== undefined && rule.target_scene_id !== null && rule.target_scene_id !== ''
    ? [rule.target_scene_id]
    : (rule.scene_ids ?? []),
  processors: rule.processor ?? rule.processors ?? [],
  notice_users: rule.follower ?? rule.notice_users ?? [],
  assign_mode: mapDispatchModeToAssign(rule.dispatch_mode || rule.assign_mode),
  confirmers: rule.confirmer ?? rule.confirmers ?? [],
});

/** 详情回填：新协议字段转回向导内部结构 */
export const parseStrategyDetailToForm = (d: Record<string, any>) => {
  let assignRules = d.assign_rules;
  let defaultAssignRule = d.default_assign_rule;

  if (d.dispatch_rules?.length) {
    const mapped = d.dispatch_rules.map((item: Record<string, any>) => fromDispatchRuleToForm(item));
    const defaultIndex = d.dispatch_rules.findIndex((item: Record<string, any>) => (
      isEmptyDispatchConditions(item.conditions)
    ));
    const resolvedDefaultIndex = defaultIndex >= 0 ? defaultIndex : mapped.length - 1;
    defaultAssignRule = mapped[resolvedDefaultIndex];
    assignRules = mapped.filter((_: Record<string, any>, index: number) => index !== resolvedDefaultIndex);
  }

  const rules = (d.rules?.length ? d.rules : null)?.map((rule: Record<string, any>, index: number) => ({
    name: rule.rule_name || rule.name || `规则${index + 1}`,
    rule_name: rule.rule_name || rule.name,
    risk_title: rule.risk_title ?? d.risk_title ?? '',
    risk_level: rule.risk_level ?? d.risk_level ?? 'HIGH',
    risk_hazard: rule.risk_hazard ?? d.risk_hazard ?? '',
    risk_guidance: rule.risk_guidance ?? d.risk_guidance ?? '',
    processor: rule.processor ?? [],
    follower: rule.follower ?? [],
    conditions: rule.conditions ?? {
      where: rule.configs?.where ?? (index === 0 ? d.configs?.where : null),
      having: rule.conditions?.having ?? rule.configs?.having ?? (index === 0 ? d.configs?.having : null),
    },
    configs: {
      ...(d.configs || {}),
      ...(rule.configs || {}),
      where: rule.conditions?.where ?? rule.configs?.where ?? (index === 0 ? d.configs?.where : undefined),
      having: rule.conditions?.having ?? rule.configs?.having ?? (index === 0 ? d.configs?.having : undefined),
    },
  })) ?? (d.configs?.where || d.risk_title ? [{
    name: '规则1',
    risk_title: d.risk_title ?? '',
    risk_level: d.risk_level ?? 'HIGH',
    risk_hazard: d.risk_hazard ?? '',
    risk_guidance: d.risk_guidance ?? '',
    conditions: {
      where: d.configs?.where ?? null,
      having: d.configs?.having ?? null,
    },
  }] : undefined);

  const firstRule = rules?.[0];
  const bindingType = d.binding_type;
  const sceneId = normalizeSceneId(d.scene_id)
    ?? (bindingType === 'scene_binding' || bindingType === undefined
      ? normalizeSceneId(getSceneSystemParams().scope_id)
      : undefined);
  return {
    rules,
    assign_rules: assignRules ?? [],
    default_assign_rule: defaultAssignRule ?? {},
    dispatch_rules: d.dispatch_rules,
    binding_type: bindingType,
    visibility: d.visibility,
    scene_id: sceneId,
    risk_title: firstRule?.risk_title ?? d.risk_title ?? '',
    risk_level: firstRule?.risk_level ?? d.risk_level ?? '',
    risk_hazard: firstRule?.risk_hazard ?? d.risk_hazard ?? '',
    risk_guidance: firstRule?.risk_guidance ?? d.risk_guidance ?? '',
  };
};
