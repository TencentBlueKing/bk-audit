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
import RiskRuleModel from '@model/risk-rule/risk-rule';
import type RiskRuleCreateModel from '@model/risk-rule/rule-create';

import RiskRuleManageSource from '../source/rule-manage';

export default {
  /**
   * @desc 获取风险处理规则列表
   * @param { Object } params
   */
  fetchRuleList(params: {
    page: number,
    page_size : number
  }) {
    return RiskRuleManageSource.getRuleList(params, {
      permission: 'page',
    })
      .then(({ data }) => ({
        ...data,
        results: data.results.map(item => new RiskRuleModel(item)),
      }));
  },
  /**
   * @desc 新建风险处理规则
   * @param { Object } params
   */
  create(params: RiskRuleCreateModel) {
    return RiskRuleManageSource.create(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取风险处理规则下拉列表
   */
  fetchRuleAll() {
    return RiskRuleManageSource.getRuleAll()
      .then(({ data }) => data);
  },
  /**
   * @desc 获取风险处理规则匹配方式
   * @param { Object } params
   */
  fetchRiskRuleOprators() {
    return RiskRuleManageSource.getRiskRuleOprators()
      .then(({ data }) => data);
  },
  /**
   * @desc 批量调整风险处理规则优先级
   * @param { Object } params
   */
  setPriorityIndex(params: {
    config: Array<{
      rule_id: string,
      priority_index: number,
      is_enabled: boolean
    }>
  }) {
    return RiskRuleManageSource.setPriorityIndex(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新风险处理规则
   * @param { Object } params
   */
  update(params: RiskRuleCreateModel) {
    return RiskRuleManageSource.update(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 删除风险处理规则
   * @param { Object } params
   */
  deleteRiskRule(params: {
    id: string
  }) {
    return RiskRuleManageSource.deleteRiskRule(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取处理规则命中的风险
   * @param { Object } params
   */
  fetchScopeRisks(params: {
    page: number;
    page_size: number;
    id: string
  }) {
    return RiskRuleManageSource.getScopeRisks(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 启停风险处理规则
   * @param { Object } params
   */
  toggleRiskRules(params: {
    rule_id: string;
    is_enabled: boolean
  }) {
    return RiskRuleManageSource.toggleRiskRules(params)
      .then(({ data }) => data);
  },
};
