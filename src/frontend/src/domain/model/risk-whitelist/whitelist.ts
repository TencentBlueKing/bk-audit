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

/** 误报加白 / 冒险加白。后端枚举未定，先用这两值对齐需求文档。 */
export type WhitelistType = 'false_positive' | 'risk_acceptance';

/** 待审批 / 生效中 / 已停用 / 已到期 / 已驳回 */
export type WhitelistStatus = 'pending' | 'active' | 'disabled' | 'expired' | 'rejected';

/** 抑制新单产生 / 抑制追加事件 */
export type InterceptAction = 'suppress_new' | 'suppress_append';

export type LogicConnector = 'and' | 'or';

export type CompareOperator = 'eq' | 'neq';

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

export interface ConditionFieldOption {
  field: string;
  label: string;
  name: string;
  value_type: 'text' | 'strategy';
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
  field_value: string;
}

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

export default class RiskWhitelist {
  id: number | string;
  rule_code: string;
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
  flow: WhitelistFlow;

  constructor(payload = {} as Partial<RiskWhitelist>) {
    this.id = payload.id ?? '';
    this.rule_code = payload.rule_code || (payload.id ? `WL-${String(payload.id).padStart(4, '0')}` : '');
    this.match_scope = payload.match_scope || { groups: [] };
    this.whitelist_type = payload.whitelist_type || 'false_positive';
    this.expire_at = payload.expire_at || '';
    this.is_permanent = Boolean(payload.is_permanent);
    this.status = payload.status || 'pending';
    this.reason = payload.reason || '';
    this.hit_count = Number(payload.hit_count || 0);
    this.updated_by = payload.updated_by || '';
    this.updated_at = payload.updated_at || '';
    this.applicant = payload.applicant || '';
    this.validity_mode = payload.validity_mode || (payload.is_permanent ? 'permanent' : '1m');
    this.custom_days = Number(payload.custom_days || 1);
    this.flow = {
      ...emptyFlow(),
      ...(payload.flow || {}),
    };
  }
}
