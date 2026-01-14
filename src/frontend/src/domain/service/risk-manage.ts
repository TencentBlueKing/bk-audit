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
import RiskManageModel from '@model/risk/risk';

import RiskManageSource from '../source/risk-manage';

export default {
  /**
   * @desc 获取风险列表
   */
  fetchRiskList(params: {
    page: number,
    page_size: number
  }) {
    return RiskManageSource.getRiskList(params, {
      permission: 'page',
    })
      .then(({ data }) => ({
        ...data,
        results: data.results.map(item => new RiskManageModel(item)),
      }));
  },
  /**
   * @desc 获取正在生成的事件列表
   */
  fetchAddEventList(params: {
    id: string
  }) {
    return RiskManageSource.getAddEventList(params)
      .then(({ data }) => ({
        ...data,
      }));
  },
  /**
   * @desc 获取待我处理风险列表
   */
  fetchTodoRiskList(params: {
      page: number,
      page_size: number
    }) {
    return RiskManageSource.getTodoRiskList(params)
      .then(({ data }) => ({
        ...data,
        results: data.results.map(item => new RiskManageModel(item)),
      }));
  },
  /**
   * @desc 我关注的获取风险列表
   */
  fetchWatchRiskList(params: {
    page: number,
    page_size: number
  }) {
    return RiskManageSource.getWatchRiskList(params, {
      permission: 'page',
    })
      .then(({ data }) => ({
        ...data,
        results: data.results.map(item => new RiskManageModel(item)),
      }));
  },
  /**
   * @desc 获取风险可用字段
   */
  fetchFields() {
    return RiskManageSource.getFields()
      .then(({ data }) => data);
  },
  /**
   * @desc 根据策略获取对应的事件字段
   */
  fetchEventFields(params: {
    strategy_ids: string[]
  }) {
    return RiskManageSource.getEventFields(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取风险状态类型
   */
  fetchRiskStatusCommon() {
    return RiskManageSource.getRiskStatusCommon()
      .then(({ data }) => data);
  },
  /**
   * @desc 获取风险标签
   */
  fetchRiskTags(params: Record<string, any>) {
    return RiskManageSource.getRiskTags(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取风险列表
   */
  fetchRiskById(params: {
    id: string
  }) {
    return RiskManageSource.getRiskById(params)
      .then(({ data }) => data);
  },
  /**
  * @desc 获取风险策略信息
  */
  fetchRiskInfo(params: {
    id: string
  }) {
    return RiskManageSource.getRiskInfo(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 人工执行处理套餐
   * @params risk_id
   */
  autoProcess(params: {
    risk_id: string
  }) {
    return RiskManageSource.autoProcess(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 人工关单
   * @params risk_id/description
   */
  close(params: {
    risk_id: string,
    description: string
  }) {
    return RiskManageSource.close(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 强制终止处理套餐
   * @params risk_id
   */
  forceRevokeAutoProcess(params: {
    risk_id: string,
  }) {
    return RiskManageSource.forceRevokeAutoProcess(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 重开单据
   * @params risk_id/new_operators
   */
  reopen(params: {
    risk_id: string,
    new_operators: string[]
  }) {
    return RiskManageSource.reopen(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 重试处理套餐
   * @params risk_id/new_operators
   */
  retryAutoProcess(params: {
    node_id: string,
    risk_id: string
  }) {
    return RiskManageSource.retryAutoProcess(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新风险标记 / 标记误报
   */
  updateRiskLabel(params: {
    risk_id: string,
    risk_label: string,
    new_operators: string[]
  }) {
    return RiskManageSource.updateRiskLabel(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 人工转单
   */
  transRisk(params: {
    risk_id: string,
    new_operators: string[],
    description: string
  }) {
    return RiskManageSource.transRisk(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 批量转单
   */
  batchTransRisk(params: {
    risk_ids: string[],
    new_operators: string[],
    description: string
  }) {
    return RiskManageSource.batchTransRisk(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 批量导出
   */
  batchExport(params: {
    risk_ids: string[],
    risk_view_type: string,
  }) {
    return RiskManageSource.batchExport(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 手动增加事件
   */
  addEvent(params: Record<string, any>) {
    return RiskManageSource.addEvent(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 获取报告风险变量列表
   */
  getReportRiskVar(params:  Record<string, any>) {
    return RiskManageSource.getReportRiskVar(params)
      .then(({ data }) => data);
  },
  /**
   * @desc AI智能体预览
   */
  getAiPreview(params: {
    id: string,
    risk_id: string,
    ai_variables: Array<{
      name: string,
      prompt_template: string
    }>
  }) {
    return RiskManageSource.getAiPreview(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 报告预览
   */
  getReportPreview(params: {
    risk_id: string,
    report_config: {
      template: string,
      frontend_template: string,
      ai_variables: Array<{
        name: string,
        prompt_template: string
      }>
    }
  }) {
    return RiskManageSource.getReportPreview(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 查询任务结果
   */
  getTaskRiskReport(params: {
    task_id: string,
  }) {
    return RiskManageSource.getTaskRiskReport(params)
      .then(({ data }) => data);
  },
};
