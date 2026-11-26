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

/** 误报加白 / 冒险加白 */
export type WhitelistType = 'false_positive' | 'risk_acceptance';

/** 待审批 / 生效中 / 已停用 / 已到期 / 已驳回 */
export type WhitelistStatus = 'pending' | 'active' | 'disabled' | 'expired' | 'rejected';

/** 抑制新单产生 / 抑制追加事件 */
export type InterceptAction = 'suppress_new' | 'suppress_append';

export type LogicConnector = 'and' | 'or';

/** 与审计策略规则表达式 RuleAuditConditionOperator 对齐；命中策略仅允许 eq */
export type CompareOperator =
  | 'eq'
  | 'neq'
  | 'gt'
  | 'lt'
  | 'gte'
  | 'lte'
  | 'include'
  | 'exclude'
  | 'like'
  | 'not_like'
  | 'isnull'
  | 'notnull';

/** 同时是后端 duration_days 的取值：permanent / Nd / Nm / custom（另传 expire_at） */
export type ValidityMode = 'permanent' | '7d' | '1m' | '3m' | '6m' | '12m' | 'custom';

export interface MatchCondition {
  field: string;
  field_name: string;
  field_label: string;
  operator: CompareOperator;
  value: string;
  value_display: string;
  /** 与上一条条件的连接，第一条忽略 */
  connector: LogicConnector;
}

export interface MatchGroup {
  /** 与上一组的连接，第一组忽略 */
  connector: LogicConnector;
  conditions: MatchCondition[];
}

export interface MatchScope {
  groups: MatchGroup[];
}

/** 后端求值时组间看 scope.connector，组内看 group.connector */
export interface MatchScopeBody {
  connector: LogicConnector;
  groups: Array<{
    connector: LogicConnector;
    conditions: MatchCondition[];
  }>;
}

export interface WhitelistFlow {
  itsm_sn: string;
  itsm_url: string;
  apply_status: string;
  current_node: string;
  current_approvers: string;
  applicant: string;
  submitted_at: string;
  rejector: string;
  reject_reason: string;
  rejected_at: string;
}

/** string / number 决定可用操作符集合；strategy 固定等于 */
export type ConditionValueType = 'text' | 'number' | 'strategy';

export interface ConditionFieldOption {
  field: string;
  label: string;
  name: string;
  value_type: ConditionValueType;
  /** 风险字段 / 事件字段，对齐场景风险搜索分组 */
  field_group?: 'risk' | 'event';
  operators: Array<{ value: CompareOperator; label: string }>;
}

export interface WhitelistPayload {
  match_scope: MatchScope;
  whitelist_type: WhitelistType;
  validity_mode?: ValidityMode;
  custom_days?: number;
  expire_at?: string;
  reason: string;
  scene_id?: string | number;
}

export interface RenewPayload {
  id: number | string;
  validity_mode: Exclude<ValidityMode, 'permanent'>;
  custom_days?: number;
  expire_at?: string;
  remark?: string;
}

export interface HitRecord {
  id: number | string;
  hit_time: string;
  action: InterceptAction;
  match_scope: MatchScope;
  risk_id: string;
  risk_url: string;
}

export interface EventFieldRow {
  field: string;
  field_name: string;
  field_type: string;
  /** 后端可能返回字符串，dict 也可能是对象或 JSON 字符串 */
  field_value: unknown;
}

/** 列表「包含条件」筛选项：场景下 match_scope 字段去重 */
export interface ContainsFieldOption {
  field: string;
  field_name: string;
}

export interface WhitelistBody {
  match_scope: MatchScopeBody;
  whitelist_type: WhitelistType;
  reason: string;
  duration_days: ValidityMode;
  expire_at?: string;
}

const toConnector = (value?: string): LogicConnector => (value === 'or' ? 'or' : 'and');

export const toMatchScopeBody = (scope: MatchScope): MatchScopeBody => ({
  connector: toConnector(scope.groups[1]?.connector),
  groups: scope.groups.map((group) => {
    const inner = toConnector(group.conditions[1]?.connector);
    return {
      connector: inner,
      conditions: group.conditions.map((condition, index) => ({
        ...condition,
        connector: index > 0 ? inner : 'and',
      })),
    };
  }),
});

/** 组间、组内连接优先取后端口径，缺失时回落到逐组、逐条记录的连接 */
export const fromMatchScopeBody = (raw?: Partial<MatchScopeBody> | null): MatchScope => {
  const groups = raw && Array.isArray(raw.groups) ? raw.groups : [];
  const outer = toConnector(raw?.connector || groups[1]?.connector);
  return {
    groups: groups.map((group, groupIndex) => {
      const conditions = Array.isArray(group.conditions) ? group.conditions : [];
      const inner = toConnector(conditions[1]?.connector || group.connector);
      return {
        connector: groupIndex > 0 ? outer : 'and',
        conditions: conditions.map((condition, index) => ({
          ...condition,
          value: String(condition.value ?? ''),
          value_display: condition.value_display || String(condition.value ?? ''),
          connector: index > 0 ? inner : 'and',
        })),
      };
    }),
  };
};

export const toWhitelistBody = (payload: WhitelistPayload): WhitelistBody => {
  const durationDays = payload.validity_mode || 'permanent';
  return {
    match_scope: toMatchScopeBody(payload.match_scope),
    whitelist_type: payload.whitelist_type,
    reason: payload.reason,
    duration_days: durationDays,
    ...(durationDays === 'custom' && payload.expire_at ? { expire_at: payload.expire_at } : {}),
  };
};

const joinNames = (list: unknown): string => {
  if (!Array.isArray(list)) return '';
  return list
    .map((item) => {
      if (item && typeof item === 'object') {
        const named = item as Record<string, any>;
        // detail_info 的 current_processors 用人名字段 processor
        return named.name
          || named.display_name
          || named.username
          || named.processor
          || named.id
          || '';
      }
      return item;
    })
    .filter(Boolean)
    .join(', ');
};

const emptyFlow = (): WhitelistFlow => ({
  itsm_sn: '',
  itsm_url: '',
  apply_status: '',
  current_node: '',
  current_approvers: '',
  applicant: '',
  submitted_at: '',
  rejector: '',
  reject_reason: '',
  rejected_at: '',
});

/**
 * 列表/详情/批量 detail_info 的 flow 归一化。
 * 兼容嵌套 flow，或 ITSM 字段摊平在根上（sn / current_steps / created_at 等）。
 */
export const toWhitelistFlow = (
  payload: Record<string, any> = {},
  fallback: Partial<WhitelistFlow> = {},
): WhitelistFlow => {
  const nested = payload.flow && typeof payload.flow === 'object' ? payload.flow : {};
  const source = {
    ...payload,
    ...nested,
  };
  return {
    ...emptyFlow(),
    itsm_sn: source.itsm_sn || source.sn || fallback.itsm_sn || '',
    itsm_url: source.itsm_url || fallback.itsm_url || '',
    apply_status: source.status_display || source.apply_status || source.status || fallback.apply_status || '',
    current_node: joinNames(source.current_steps) || source.current_node || fallback.current_node || '',
    current_approvers: joinNames(source.current_processors)
      || source.current_approvers
      || fallback.current_approvers
      || '',
    applicant: source.applicant || source.creator || fallback.applicant || '',
    submitted_at: source.submitted_at || source.created_at || fallback.submitted_at || '',
    rejector: source.rejector || fallback.rejector || '',
    reject_reason: source.reject_reason || fallback.reject_reason || '',
    rejected_at: source.rejected_at || fallback.rejected_at || '',
  };
};

export default class RiskWhitelist {
  id: number | string;
  rule_code: string;
  scene_id: number | string;
  risk_id: string;
  match_scope: MatchScope;
  whitelist_type: WhitelistType;
  expire_at: string;
  is_permanent: boolean;
  status: WhitelistStatus;
  reason: string;
  hit_count: number;
  updated_by: string;
  updated_at: string;
  applicant: string;
  validity_mode: ValidityMode;
  custom_days: number;
  itsm_sn: string;
  itsm_url: string;
  actions: string[];
  flow: WhitelistFlow;

  constructor(payload = {} as Record<string, any>) {
    this.id = payload.id ?? '';
    this.rule_code = payload.rule_code || (payload.id ? String(payload.id) : '');
    this.scene_id = payload.scene_id ?? '';
    this.risk_id = payload.risk_id || '';
    this.match_scope = fromMatchScopeBody(payload.match_scope);
    this.whitelist_type = payload.whitelist_type || 'false_positive';
    this.expire_at = payload.expire_at || '';
    this.is_permanent = Boolean(payload.is_permanent);
    this.status = payload.status || 'pending';
    this.reason = payload.reason || '';
    this.hit_count = Number(payload.hit_count || 0);
    this.updated_by = payload.updated_by || '';
    this.updated_at = payload.updated_at || '';
    this.applicant = payload.applicant || '';
    this.validity_mode = payload.validity_mode || (this.is_permanent ? 'permanent' : '1m');
    this.custom_days = Number(payload.custom_days || 1);
    this.itsm_sn = payload.itsm_sn || '';
    this.itsm_url = payload.itsm_url || '';
    this.actions = Array.isArray(payload.actions) ? payload.actions : [];
    this.flow = toWhitelistFlow(payload, {
      itsm_sn: this.itsm_sn,
      itsm_url: this.itsm_url,
      applicant: this.applicant,
    });
  }
}
