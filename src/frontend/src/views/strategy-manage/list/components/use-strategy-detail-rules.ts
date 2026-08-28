import { computed, type ComputedRef, toRaw } from 'vue';
import { useI18n } from 'vue-i18n';

import type StrategyModel from '@model/strategy/strategy';

import { parseStrategyDetailToForm } from '../../strategy-create/utils/strategy-protocol';

export interface RuleWhereDisplay {
  connector: string;
  conditions: Array<Record<string, any>>;
}

export interface RuleDisplayItem {
  name: string;
  where: RuleWhereDisplay;
  risk_title: string;
  risk_level: string;
  risk_hazard: string;
  risk_guidance: string;
  processor: Array<string | number>;
  follower: Array<string | number>;
}

export interface ConditionDisplayRow {
  showInnerConnector: boolean;
  innerConnector: string;
  fieldLabel: string;
  operatorLabel: string;
  values: string[];
}

export const emptyWhere = (): RuleWhereDisplay => ({
  connector: 'and',
  conditions: [],
});

export const getConditionFieldLabel = (field: Record<string, any> | undefined) => {
  if (!field) return '';
  const displayName = field.display_name || field.field_name || '';
  const rawName = field.raw_name || field.field_name || '';
  if (displayName && rawName && displayName !== rawName) {
    return `${displayName}(${rawName})`;
  }
  return displayName || rawName;
};

const getGroupChildConditions = (group: Record<string, any>) => {
  if (group.conditions?.length) {
    return group.conditions;
  }
  if (group.condition) {
    return [{ condition: group.condition }];
  }
  return [];
};

const getConditionValues = (condition: Record<string, any>) => {
  if (condition.filters?.length) {
    return condition.filters.map((item: unknown) => String(item));
  }
  if (condition.filter !== undefined && condition.filter !== null && condition.filter !== '') {
    return [String(condition.filter)];
  }
  return [];
};

export const mergeHavingIntoWhere = (
  where?: RuleWhereDisplay | null,
  having?: RuleWhereDisplay | null,
): RuleWhereDisplay => {
  const base = where?.conditions?.length
    ? { connector: where.connector || 'and', conditions: [...where.conditions] }
    : emptyWhere();
  if (!having?.conditions?.length) {
    return base;
  }
  const merged = [...base.conditions, ...having.conditions];
  merged.sort((a, b) => (a.index ?? 0) - (b.index ?? 0));
  return {
    connector: base.connector,
    conditions: merged,
  };
};

export const getRuleWhere = (rule: Record<string, any>): RuleWhereDisplay => {
  const where = rule.conditions?.where ?? rule.configs?.where;
  const having = rule.conditions?.having ?? rule.configs?.having;
  return mergeHavingIntoWhere(where, having);
};

export const buildConditionDisplayRows = (
  where: RuleWhereDisplay,
  getOperatorLabel: (operator: string) => string,
): ConditionDisplayRow[] => {
  const rows: ConditionDisplayRow[] = [];
  where.conditions.forEach((group) => {
    const childConditions = getGroupChildConditions(group);
    childConditions.forEach((child, childIndex) => {
      const condition = child.condition ?? child;
      if (!condition) return;

      const fieldLabel = getConditionFieldLabel(condition.field) || condition.field_name || '';
      const operatorLabel = condition.operator ? getOperatorLabel(condition.operator) : '';
      const values = getConditionValues(condition);

      if (!fieldLabel && !operatorLabel && !values.length) {
        return;
      }

      rows.push({
        showInnerConnector: childIndex > 0,
        innerConnector: (group.connector || 'and').toUpperCase(),
        fieldLabel,
        operatorLabel,
        values,
      });
    });
  });
  return rows;
};

export const dispatchConditionsToWhere = (
  conditions: Record<string, any> | undefined,
  getFieldLabel: (fieldName: string) => string,
): RuleWhereDisplay => {
  if (!conditions?.conditions?.length) {
    return emptyWhere();
  }
  return {
    connector: conditions.connector || 'and',
    conditions: [{
      connector: 'and',
      conditions: conditions.conditions.map((item: Record<string, any>) => {
        const cond = item.condition ?? item;
        const fieldName = typeof cond.field === 'string'
          ? cond.field
          : (cond.field?.raw_name || cond.field?.field_name || '');
        return {
          condition: {
            field: {
              field_name: getFieldLabel(fieldName),
            },
            operator: cond.operator,
            filter: cond.filter ?? cond.filters?.[0],
          },
        };
      }),
    }],
  };
};

const toStrategyRecord = (data: StrategyModel | Record<string, any>): Record<string, any> => {
  const raw = toRaw(data) as Record<string, any>;
  return {
    ...raw,
    rules: raw.rules,
    configs: raw.configs,
    dispatch_rules: raw.dispatch_rules,
    assign_rules: raw.assign_rules,
    default_assign_rule: raw.default_assign_rule,
    risk_title: raw.risk_title,
    risk_level: raw.risk_level,
    risk_hazard: raw.risk_hazard,
    risk_guidance: raw.risk_guidance,
  };
};

export const useStrategyDetailRules = (data: ComputedRef<StrategyModel> | StrategyModel) => {
  const { t } = useI18n();

  const strategyData = computed(() => ('value' in data ? data.value : data));

  const riskLevelMap: Record<string, { label: string; color: string }> = {
    HIGH: {
      label: t('高'),
      color: '#ea3636',
    },
    MIDDLE: {
      label: t('中'),
      color: '#ff9c01',
    },
    LOW: {
      label: t('低'),
      color: '#979ba5',
    },
  };

  const mapCurrentRules = (
    current: Record<string, any>,
    rules: Array<Record<string, any>>,
  ) => rules.map((rule: Record<string, any>, index: number) => ({
    name: rule.rule_name || rule.name || `${t('规则')}${index + 1}`,
    rule_name: rule.rule_name || rule.name,
    risk_title: rule.risk_title ?? current.risk_title ?? '',
    risk_level: rule.risk_level ?? current.risk_level ?? 'HIGH',
    risk_hazard: rule.risk_hazard ?? current.risk_hazard ?? '',
    risk_guidance: rule.risk_guidance ?? current.risk_guidance ?? '',
    processor: rule.processor ?? [],
    follower: rule.follower ?? [],
    conditions: rule.conditions ?? {
      where: rule.configs?.where ?? (index === 0 ? current.configs?.where : null),
      having: rule.conditions?.having ?? rule.configs?.having ?? (index === 0 ? current.configs?.having : null),
    },
    configs: rule.configs,
  }));

  const resolveRuleList = (current: Record<string, any>, parsed: ReturnType<typeof parseStrategyDetailToForm>) => {
    if (parsed.rules?.length) {
      return parsed.rules;
    }
    if (Array.isArray(current.rules) && current.rules.length) {
      return mapCurrentRules(current, current.rules);
    }
    return [];
  };

  const displayRules = computed<RuleDisplayItem[]>(() => {
    const current = toStrategyRecord(strategyData.value);
    const parsed = parseStrategyDetailToForm(current);
    const ruleList = resolveRuleList(current, parsed);
    if (!ruleList.length) {
      return [];
    }
    return ruleList.map((rule: Record<string, any>, index: number) => ({
      name: rule.rule_name || rule.name || `${t('规则')}${index + 1}`,
      where: getRuleWhere(rule),
      risk_title: rule.risk_title ?? '',
      risk_level: rule.risk_level ?? '',
      risk_hazard: rule.risk_hazard ?? '',
      risk_guidance: rule.risk_guidance ?? '',
      processor: rule.processor ?? [],
      follower: rule.follower ?? [],
    }));
  });

  const resolveGroupNames = (
    ids: Array<string | number>,
    userGroupList: Array<{ id: number; name: string }>,
  ) => resolveNoticeGroupNames(ids, userGroupList);

  return {
    displayRules,
    riskLevelMap,
    getConditionFieldLabel,
    resolveGroupNames,
  };
};

export const resolveNoticeGroupNames = (
  ids: Array<string | number>,
  userGroupList: Array<{ id: number; name: string }>,
) => {
  if (!ids?.length) return '--';
  const names = ids
    .map(id => userGroupList.find(item => item.id === id || `${item.id}` === `${id}`)?.name || `${id}`)
    .filter(Boolean);
  return names.length ? names.join('、') : '--';
};
