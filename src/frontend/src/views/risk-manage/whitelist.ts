/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
*/

import type { MatchScope } from '@model/risk-whitelist/whitelist';

import { createCondition, createStrategyCondition } from '@components/risk-whitelist/constants';

/** 状态 key 等后端确定后再对齐。当前按需求文档暂定。 */
export const WHITELIST_APPROVING_STATUS = 'whitelist_approving';

export const WHITELIST_APPROVING_TIP = '加白审批中，无法同时手工处理';

export const isWhitelistApproving = (status?: string) => status === WHITELIST_APPROVING_STATUS;

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
