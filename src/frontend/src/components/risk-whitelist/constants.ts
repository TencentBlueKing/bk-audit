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
  pending: 'var(--audit-warn-02)',
  active: 'var(--audit-success-02)',
  disabled: 'var(--audit-neutral-text-03)',
  expired: 'var(--audit-warn-02)',
  rejected: 'var(--audit-danger-02)',
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

export const RENEW_DURATION_OPTIONS = DURATION_OPTIONS.filter(item => item.id !== 'permanent');

export const OPERATOR_OPTIONS: Array<{ value: CompareOperator; label: string }> = [
  { value: 'eq', label: '=等于' },
  { value: 'neq', label: '!=不等于' },
];

export const FALLBACK_CONDITION_FIELDS: ConditionFieldOption[] = [
  {
    field: 'strategy_id',
    name: '命中策略(ID)',
    label: '命中策略(ID)(strategy_id)',
    value_type: 'strategy',
    operators: OPERATOR_OPTIONS,
  },
  {
    field: 'event_id',
    name: '原始事件ID',
    label: '原始事件ID(event_id)',
    value_type: 'text',
    operators: OPERATOR_OPTIONS,
  },
  {
    field: 'operator',
    name: '责任人',
    label: '责任人(operator)',
    value_type: 'text',
    operators: OPERATOR_OPTIONS,
  },
  {
    field: 'src_ip',
    name: '操作IP',
    label: '操作IP(src_ip)',
    value_type: 'text',
    operators: OPERATOR_OPTIONS,
  },
  {
    field: 'account',
    name: '账号',
    label: '账号(account)',
    value_type: 'text',
    operators: OPERATOR_OPTIONS,
  },
];

export const createCondition = (
  field = FALLBACK_CONDITION_FIELDS[1],
  connector: LogicConnector = 'and',
): MatchCondition => ({
  field: field.field,
  field_name: field.name,
  field_label: field.label,
  operator: 'eq',
  value: '',
  value_display: '',
  connector,
});

export const createStrategyCondition = (): MatchCondition => createCondition(FALLBACK_CONDITION_FIELDS[0], 'and');

export const createGroup = (connector: LogicConnector = 'and'): MatchGroup => ({
  connector,
  conditions: [createStrategyCondition()],
});

export const createDefaultScope = (): MatchScope => ({
  groups: [{
    connector: 'and',
    conditions: [
      createStrategyCondition(),
      createCondition(FALLBACK_CONDITION_FIELDS[1], 'and'),
    ],
  }],
});

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
