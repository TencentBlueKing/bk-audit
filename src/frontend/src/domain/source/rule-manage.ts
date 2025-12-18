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

import type RiskRuleModel from '@model/risk-rule/risk-rule';
import type RiskRuleCreateModel from '@model/risk-rule/rule-create';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

class RuleManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/risk_rules';
  }
  // 获取风险处理规则列表
  getRuleList(params: {
    page: number,
    page_size : number
  }, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<RiskRuleModel>>(`${this.module}/`, {
      params,
      payload,
    });
  }
  // 新建风险处理规则
  create(params: RiskRuleCreateModel) {
    return Request.post(`${this.module}/`, {
      params,
    });
  }
  // 获取风险处理规则列表
  getRuleAll() {
    return Request.get<Array<{
      id: string,
      name: string,
      version: number,
    }>>(`${this.module}/all/`);
  }
  // 获取风险处理规则匹配方式
  getRiskRuleOprators() {
    return Request.get<Array<{
      id: string,
      name: string
    }>>(`${this.module}/operators/`);
  }
  // 批量调整风险处理规则优先级
  setPriorityIndex(params: {
    config: Array<{
      rule_id: string,
      priority_index: number,
      is_enabled: boolean
    }>
  }) {
    return Request.put(`${this.module}/set_priority_index/`, {
      params,
    });
  }
  // 更新风险处理规则
  update(params: RiskRuleCreateModel) {
    return Request.put(`${this.module}/${params.rule_id}/`, {
      params,
    });
  }
  // 删除风险处理规则
  deleteRiskRule(params: {
    id: string
  }) {
    return Request.delete(`${this.module}/${params.id}/`, {
      params,
    });
  }
  // 获取处理规则命中的风险
  getScopeRisks(params: {
    page: number;
    page_size: number;
    id: string
  }) {
    return Request.get<IRequestResponsePaginationData<RiskRuleModel>>(`${this.module}/${params.id}/risks/`, {
      params,
    });
  }
  // 启停风险处理规则
  toggleRiskRules(params: {
    rule_id: string;
    is_enabled: boolean
  }) {
    return Request.put<RiskRuleModel>(`${this.module}/${params.rule_id}/toggle/`, {
      params,
    });
  }
}
export default new RuleManage();
