/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
*/
import dayjs from 'dayjs';

import type {
  CompareOperator,
  ConditionFieldOption,
  LogicConnector,
  MatchCondition,
  MatchGroup,
  MatchScope,
  ValidityMode,
  WhitelistStatus,
  WhitelistType,
} from '@model/risk-whitelist/whitelist';

export const WHITELIST_TYPE_TEXT: Record<WhitelistType, string> = {
  false_positive: '误报加白',
  risk_acceptance: '冒险加白',
};

export const WHITELIST_STATUS_TEXT: Record<WhitelistStatus, string> = {
  pending: '待审批',
  active: '生效中',
  disabled: '已停用',
  expired: '已到期',
  rejected: '已驳回',
};

export const STATUS_DOT_TOKEN: Record<WhitelistStatus, string> = {
  pending: 'var(--bk-theme-color-warn-2)',
  active: 'var(--bk-theme-color-success-2)',
  disabled: 'var(--bk-theme-text-weak)',
  expired: 'var(--bk-theme-color-warn-2)',
  rejected: 'var(--bk-theme-color-danger-2)',
};

export const INTERCEPT_ACTION_TEXT = {
  suppress_new: '抑制新单产生',
  suppress_append: '抑制追加事件',
} as const;

export const DURATION_OPTIONS: Array<{ id: ValidityMode; name: string }> = [
  { id: 'permanent', name: '永久' },
  { id: '7d', name: '7天' },
  { id: '1m', name: '1个月' },
  { id: '3m', name: '3个月' },
  { id: '6m', name: '6个月' },
  { id: '12m', name: '12个月' },
  { id: 'custom', name: '自定义' },
];

export const RENEW_DURATION_OPTIONS = DURATION_OPTIONS.filter(
  (item): item is { id: Exclude<ValidityMode, 'permanent'>; name: string } => item.id !== 'permanent',
);

/**
 * 操作符展示文案：与策略 rule_audit_condition_operator 中文翻译保持一致
 *（见 backend locale zh_CN：=  等于 / in  属于 / like  包含(模糊匹配) …）
 */
export const OPERATOR_LABEL_MAP: Record<CompareOperator, string> = {
  eq: '=  等于',
  neq: '!=  不等于',
  gt: '>  大于',
  lt: '<  小于',
  gte: '>=  大于等于',
  lte: '<=  小于等于',
  include: 'in  属于',
  exclude: 'not in  不属于',
  like: 'like  包含(模糊匹配)',
  not_like: 'not like  不包含(模糊匹配)',
  isnull: 'is null  为空',
  notnull: 'is not null  不为空',
};

const toOperatorOptions = (values: CompareOperator[]) => values.map(value => ({
  value,
  label: OPERATOR_LABEL_MAP[value],
}));

/**
 * 与 RuleAuditConditionOperator 对齐，并按类型分流：
 * - string：等于/不等于/包含/模糊/空值
 * - number：比较与包含，不含 like
 * - strategy（命中策略）：仅等于
 */
export const STRING_OPERATOR_OPTIONS = toOperatorOptions([
  'eq', 'neq', 'include', 'exclude', 'like', 'not_like', 'isnull', 'notnull',
]);

export const NUMBER_OPERATOR_OPTIONS = toOperatorOptions([
  'eq', 'neq', 'gt', 'lt', 'gte', 'lte', 'include', 'exclude', 'isnull', 'notnull',
]);

export const STRATEGY_OPERATOR_OPTIONS = toOperatorOptions(['eq']);

/** @deprecated 兼容旧引用，默认按 string 操作符 */
export const OPERATOR_OPTIONS = STRING_OPERATOR_OPTIONS;

export const VALUELESS_OPERATORS: CompareOperator[] = ['isnull', 'notnull'];

export const isValuelessOperator = (operator?: string) => (
  VALUELESS_OPERATORS.includes(operator as CompareOperator)
);

export const getOperatorsForValueType = (valueType?: ConditionFieldOption['value_type']) => {
  if (valueType === 'strategy') return STRATEGY_OPERATOR_OPTIONS;
  if (valueType === 'number') return NUMBER_OPERATOR_OPTIONS;
  return STRING_OPERATOR_OPTIONS;
};

const buildField = (
  field: string,
  name: string,
  valueType: ConditionFieldOption['value_type'],
  fieldGroup: 'risk' | 'event',
): ConditionFieldOption => ({
  field,
  name,
  // 与场景风险搜索展示一致：中文名(field)
  label: `${name}(${field})`,
  value_type: valueType,
  field_group: fieldGroup,
  operators: getOperatorsForValueType(valueType),
});

/**
 * 匹配范围字段：
 * - 风险字段：仅保留生成/命中时可稳定求值的属性（不含工单处理态字段）
 * - 事件字段：按命中策略动态拉取全量；下列三项仅作默认新增/展示回退
 */
export const FALLBACK_CONDITION_FIELDS: ConditionFieldOption[] = [
  buildField('strategy_id', '风险命中策略(ID)', 'strategy', 'risk'),
  buildField('risk_id', '风险ID', 'text', 'risk'),
  buildField('title', '风险标题', 'text', 'risk'),
  buildField('risk_level', '风险等级', 'text', 'risk'),
  buildField('tags', '风险标签', 'text', 'risk'),
  buildField('operator', '责任人', 'text', 'risk'),
  buildField('current_operator', '当前处理人', 'text', 'risk'),
  buildField('raw_event_id', '原始事件ID', 'text', 'event'),
  buildField('src_ip', '操作IP', 'text', 'event'),
  buildField('account', '账号', 'text', 'event'),
];

/** 字段选择器「风险字段」Tab（不含锁定的命中策略） */
export const RISK_CONDITION_FIELDS = FALLBACK_CONDITION_FIELDS.filter(item => (
  item.field_group === 'risk' && item.field !== 'strategy_id'
));

export const getFieldMeta = (field: string) => (
  FALLBACK_CONDITION_FIELDS.find(item => item.field === field)
);

/** 命中策略仅等于；未知动态事件字段默认按 string */
export const getOperatorsForField = (field?: string) => {
  const meta = field ? getFieldMeta(field) : undefined;
  if (!meta) return STRING_OPERATOR_OPTIONS;
  return meta.operators;
};

export const createCondition = (
  field = FALLBACK_CONDITION_FIELDS.find(item => item.field === 'raw_event_id')
    || FALLBACK_CONDITION_FIELDS[1],
  connector: LogicConnector = 'and',
): MatchCondition => ({
  field: field.field,
  field_name: field.name,
  field_label: field.label,
  operator: field.operators[0]?.value || 'eq',
  value: '',
  value_display: '',
  connector,
});

export const createStrategyCondition = (
  seed?: Partial<Pick<MatchCondition, 'value' | 'value_display'>>,
): MatchCondition => ({
  ...createCondition(FALLBACK_CONDITION_FIELDS[0], 'and'),
  operator: 'eq',
  value: seed?.value || '',
  value_display: seed?.value_display || seed?.value || '',
});

export const createGroup = (
  connector: LogicConnector = 'and',
  strategySeed?: Partial<Pick<MatchCondition, 'value' | 'value_display'>>,
): MatchGroup => ({
  connector,
  conditions: [createStrategyCondition(strategySeed)],
});

export const createDefaultScope = (): MatchScope => ({
  groups: [{
    connector: 'and',
    conditions: [
      createStrategyCondition(),
      createCondition(
        FALLBACK_CONDITION_FIELDS.find(item => item.field === 'raw_event_id')
          || FALLBACK_CONDITION_FIELDS[1],
        'and',
      ),
    ],
  }],
});

export const getFirstStrategySeed = (scope: MatchScope) => {
  const strategy = scope.groups
    .flatMap(group => group.conditions)
    .find(item => item.field === 'strategy_id' && item.value);
  if (!strategy) return undefined;
  return {
    value: String(strategy.value),
    value_display: strategy.value_display || String(strategy.value),
  };
};

export const durationLabel = (mode: ValidityMode, customDays = 1) => {
  if (mode === 'custom') return `${customDays}天`;
  return DURATION_OPTIONS.find(item => item.id === mode)?.name || mode;
};

export const calcExpireAt = (mode: ValidityMode, customDays = 1, from = dayjs()) => {
  if (mode === 'permanent') return '';
  if (mode === 'custom') return from.add(Math.max(customDays, 1), 'day').format('YYYY-MM-DD HH:mm:ss');
  if (mode === '7d') return from.add(7, 'day').format('YYYY-MM-DD HH:mm:ss');
  const months: Record<string, number> = { '1m': 1, '3m': 3, '6m': 6, '12m': 12 };
  return from.add(months[mode] || 1, 'month').format('YYYY-MM-DD HH:mm:ss');
};

export const isOnlyStrategyGroup = (group: MatchGroup) => (
  group.conditions.length === 1 && group.conditions[0].field === 'strategy_id'
);

export const hasStrategyOnlyGroup = (scope: MatchScope) => scope.groups.some(isOnlyStrategyGroup);

export const everyGroupHasStrategy = (scope: MatchScope) => scope.groups.every(group => (
  group.conditions.some(item => item.field === 'strategy_id' && item.value)
));
