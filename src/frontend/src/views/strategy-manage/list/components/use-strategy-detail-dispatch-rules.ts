import { computed, type ComputedRef, toRaw } from 'vue';
import { useI18n } from 'vue-i18n';

import type StrategyModel from '@model/strategy/strategy';

import { isEmptyDispatchConditions, parseStrategyDetailToForm } from '../../strategy-create/utils/strategy-protocol';

import {
  dispatchConditionsToWhere,
  emptyWhere,
  type RuleWhereDisplay,
} from './use-strategy-detail-rules';

export interface DispatchRuleDisplayItem {
  name: string;
  isDefault: boolean;
  where: RuleWhereDisplay;
  sceneIds: Array<string | number>;
  processors: Array<string | number>;
  followers: Array<string | number>;
  dispatchMode: string;
  confirmers: Array<string | number>;
}

const toStrategyRecord = (data: StrategyModel | Record<string, any>): Record<string, any> => {
  const raw = toRaw(data) as Record<string, any>;
  return {
    ...raw,
    configs: raw.configs,
    dispatch_rules: raw.dispatch_rules,
    assign_rules: raw.assign_rules,
    default_assign_rule: raw.default_assign_rule,
  };
};

const buildFieldLabelMap = (fields: Array<Record<string, any>> = []) => {
  const map: Record<string, string> = {};
  fields.forEach((field) => {
    const rawName = field.raw_name || field.value;
    const displayName = field.display_name || field.label;
    if (!rawName && !displayName) return;
    const label = displayName && rawName && displayName !== rawName
      ? `${displayName}(${rawName})`
      : (displayName || rawName || '');
    if (displayName) {
      map[displayName] = label;
    }
    if (rawName) {
      map[rawName] = label;
    }
  });
  return map;
};

const normalizeSceneIds = (rule: Record<string, any> = {}): Array<string | number> => {
  if (Array.isArray(rule.scene_ids) && rule.scene_ids.length) {
    return rule.scene_ids.filter((id: unknown) => id !== '' && id !== null && id !== undefined);
  }
  if (rule.target_scene_id !== undefined && rule.target_scene_id !== null && rule.target_scene_id !== '') {
    return [rule.target_scene_id];
  }
  return [];
};

const resolveDispatchMode = (rule: Record<string, any>) => {
  if (rule.dispatch_mode === 'direct' || rule.assign_mode === 'direct') {
    return 'direct';
  }
  return 'confirm';
};

export const useStrategyDetailDispatchRules = (data: ComputedRef<StrategyModel> | StrategyModel) => {
  const { t } = useI18n();

  const strategyData = computed(() => ('value' in data ? data.value : data));

  const displayRules = computed<DispatchRuleDisplayItem[]>(() => {
    const current = toStrategyRecord(strategyData.value);
    const parsed = parseStrategyDetailToForm(current);
    const fieldMap = buildFieldLabelMap(current.configs?.select || current.configs?.table_fields || []);
    const getFieldLabel = (fieldName: string) => fieldMap[fieldName] || fieldName;

    const assignRules = parsed.assign_rules ?? [];
    const defaultRule = parsed.default_assign_rule ?? {};
    const items: DispatchRuleDisplayItem[] = [];

    assignRules.forEach((rule: Record<string, any>, index: number) => {
      items.push({
        name: rule.name || rule.rule_name || `${t('规则')}${index + 1}`,
        isDefault: false,
        where: dispatchConditionsToWhere(rule.conditions, getFieldLabel),
        sceneIds: normalizeSceneIds(rule),
        processors: rule.processors ?? rule.processor ?? [],
        followers: rule.notice_users ?? rule.follower ?? [],
        dispatchMode: resolveDispatchMode(rule),
        confirmers: rule.confirmers ?? rule.confirmer ?? [],
      });
    });

    const hasDefaultRule = defaultRule && (
      normalizeSceneIds(defaultRule).length
      || defaultRule.processors?.length
      || defaultRule.processor?.length
      || defaultRule.notice_users?.length
      || defaultRule.follower?.length
      || defaultRule.confirmers?.length
      || defaultRule.confirmer?.length
      || Object.keys(defaultRule).length > 0
    );

    if (hasDefaultRule) {
      items.push({
        name: defaultRule.name || defaultRule.rule_name || t('默认分派规则'),
        isDefault: true,
        where: emptyWhere(),
        sceneIds: normalizeSceneIds(defaultRule),
        processors: defaultRule.processors ?? defaultRule.processor ?? [],
        followers: defaultRule.notice_users ?? defaultRule.follower ?? [],
        dispatchMode: resolveDispatchMode(defaultRule),
        confirmers: defaultRule.confirmers ?? defaultRule.confirmer ?? [],
      });
    }

    if (!items.length && Array.isArray(current.dispatch_rules) && current.dispatch_rules.length) {
      const mapped = current.dispatch_rules.map((rule: Record<string, any>, index: number) => {
        const isDefault = isEmptyDispatchConditions(rule.conditions);
        return {
          name: rule.rule_name || rule.name || (isDefault ? t('默认分派规则') : `${t('规则')}${index + 1}`),
          isDefault,
          where: isDefault
            ? emptyWhere()
            : dispatchConditionsToWhere(rule.conditions, getFieldLabel),
          sceneIds: normalizeSceneIds(rule),
          processors: rule.processor ?? rule.processors ?? [],
          followers: rule.follower ?? rule.notice_users ?? [],
          dispatchMode: resolveDispatchMode(rule),
          confirmers: rule.confirmer ?? rule.confirmers ?? [],
        };
      });
      return mapped.filter((rule: DispatchRuleDisplayItem, index: number, list: DispatchRuleDisplayItem[]) => (
        !rule.isDefault || index === list.length - 1
      ));
    }

    return items;
  });

  const resolveSceneLabels = (
    sceneIds: Array<string | number>,
    sceneList: Array<{ scene_id: string | number; name: string }>,
  ) => {
    if (!sceneIds?.length) return '--';
    const labels = sceneIds.map((id) => {
      const scene = sceneList.find(item => `${item.scene_id}` === `${id}`);
      return scene ? `${scene.name} (${scene.scene_id})` : `${id}`;
    });
    return labels.join('、');
  };

  const resolveDispatchModeLabel = (mode: string) => (
    mode === 'direct' ? t('直接分派') : t('确认后分派')
  );

  return {
    displayRules,
    resolveSceneLabels,
    resolveDispatchModeLabel,
  };
};
