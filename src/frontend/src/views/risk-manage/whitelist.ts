/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
    10|  software distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
*/

import type { MatchScope } from '@model/risk-whitelist/whitelist';

import { createCondition, createStrategyCondition } from '@components/risk-whitelist/constants';

export const buildScopeFromRisk = (detail: {
  strategy_id?: string | number;
  strategy_name?: string;
  raw_event_id?: string;
}): MatchScope => {
  const strategyId = detail.strategy_id === undefined || detail.strategy_id === null
    ? ''
    : String(detail.strategy_id);
  const strategy = createStrategyCondition();
  strategy.value = strategyId;
  strategy.value_display = detail.strategy_name
    ? `${detail.strategy_name}(${strategyId})`
    : strategyId;
  const conditions = [strategy];
  if (detail.raw_event_id) {
    const event = createCondition();
    event.value = detail.raw_event_id;
    event.value_display = detail.raw_event_id;
    conditions.push(event);
  }
  return {
    groups: [{
      connector: 'and',
      conditions,
    }],
  };
};

/** ITSM / 前端展示里视为「加白仍在审批中」的状态（不含已废弃的 risk.status=whitelist_approving） */
const PENDING_WHITELIST_STATUS = new Set([
  'pending',
  'approving',
  'pending_approve',
  'WAIT',
  'RUNNING',
  'RECEIVING',
  'DISTRIBUTING',
  'SUSPEND',
  '审批中',
  '待审批',
  '待处理',
  '待认领',
  '待分派',
  '被挂起',
]);

const TERMINAL_WHITELIST_STATUS = new Set([
  'approved',
  'passed',
  'active',
  'rejected',
  'FINISHED',
  'TERMINATED',
  'FAILED',
  'REVOKED',
  '已通过',
  '生效中',
  '已驳回',
  '已结束',
  '被终止',
  '执行失败',
  '被撤销',
]);

const readWhitelistApplyStatus = (node: Record<string, any> | undefined) => {
  const source = node?.whitelist || node?.extra || {};
  return {
    status: String(source.itsm_status || source.apply_status || source.status || '').trim(),
    display: String(source.itsm_status_display || '').trim(),
  };
};

/** 最新 WhitelistApply 节点仍处于 ITSM 审批中时需要轮询详情 */
export const hasPendingWhitelistApply = (
  ticketHistory?: Array<Record<string, any>>,
): boolean => {
  if (!Array.isArray(ticketHistory) || !ticketHistory.length) {
    return false;
  }
  const latest = [...ticketHistory].reverse()
    .find(item => item?.action === 'WhitelistApply');
  if (!latest) {
    return false;
  }
  const { status, display } = readWhitelistApplyStatus(latest);
  if (TERMINAL_WHITELIST_STATUS.has(status) || TERMINAL_WHITELIST_STATUS.has(display)) {
    return false;
  }
  // 刚提单时字段可能尚未回填，按待审批处理
  if (!status && !display) {
    return true;
  }
  return PENDING_WHITELIST_STATUS.has(status) || PENDING_WHITELIST_STATUS.has(display);
};

/** 详情 60s 轮询：套餐审批/执行中，或存在待审批的加白 ITSM 单 */
export const shouldPollRiskDetail = (data: {
  status?: string;
  ticket_history?: Array<Record<string, any>>;
}): boolean => {
  if (['for_approve', 'auto_process'].includes(String(data.status || ''))) {
    return true;
  }
  return hasPendingWhitelistApply(data.ticket_history);
};
