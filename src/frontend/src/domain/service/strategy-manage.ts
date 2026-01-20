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
import SearchModel from '@model/es-query/search';
import StrategyModel from '@model/strategy/strategy';
import StrategyFieldEvent from '@model/strategy/strategy-field-event';

import StrategySource from '../source/strategy-manage';

export default {
  /**
   * @desc 策略列表
   * @param { Object } params
   */
  fetchStrategyList(params: {
    label?: string
    name?: string,
    page: number,
    page_size: number
  }) {
    return StrategySource.getStrategyList(
      params,
      {
        permission: 'page',
      },
    )
      .then(({ data }) => ({
        ...data,
        results: data.results.map(item => new StrategyModel(item)),
      }));
  },
  /**
   * @desc 策略详情
   * @param { Object } params
   */
  fetchStrategyInfo(params: {
    strategy_id : number
  }) {
    return StrategySource.getStrategyInfo(params)
      .then(({ data }) => new StrategyModel(data));
  },
  /**
   * @desc 新建策略
   * @param { Object } params
   */
  saveStrategy(params: Record<string, any>) {
    return StrategySource.saveStrategy(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取所有策略下拉列表
   */
  fetchAllStrategyList() {
    return StrategySource.getAllStrategyList()
      .then(({ data }) => data);
  },
  /**
   * @desc 获取所有策略下拉列表(用于查询，区分all、watch、todo)
   */
  fetchScopedStrategyList(params: Record<string, any>) {
    return StrategySource.getScopedStrategyList(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 告警常量
   */
  fetchStrategyCommon() {
    return StrategySource.getStrategyCommon({ cache: true })
      .then(({ data }) => data);
  },
  /**
   * @desc 重试策略
   */
  retryStrategy(params: {
    strategy_id: number
  }) {
    return StrategySource.retryStrategy(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取处理中的策略状态
   */
  fetchStrategyStatus(params: {
    strategy_ids: string,
  }) {
    return StrategySource.getStrategyStatus(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 更新策略
   */
  updateStrategy(params: StrategyModel) {
    return StrategySource.updateStrategy(params)
      .then(({ data }) => data);
  },


  /**
   * @desc 删除告警策略
   * @param { Number } id
   */
  remove(params: { id: number }) {
    return StrategySource.deleteStrategy(params)
      .then(({ data }) => data);
  },


  /**
   * @desc 启停
   * @param { Object } params
   */
  fetchSwitchStrategy(params: {
    strategy_id: number
    toggle: boolean,
  }) {
    return StrategySource.switchStrategy(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 获取策略字段
   */
  fetchStrategyFields(params: {
    system_id: string;
    action_id: string
  }) {
    return StrategySource.getStrategyFields(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 获取变量值
   * @param { String } field_name
   */
  fetchStrategyFieldValue(params: {
    field_name: string
  }) {
    return StrategySource.getStrategyFieldValue(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 获取表格id
   */
  fetchTable(params: {
    table_type: string;
  }) {
    return StrategySource.getTable(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取表格信息
   */
  fetchTableRtMeta(params: {
    table_id: string
  }) {
    return StrategySource.getTableRtMeta(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取表格最后一条数据
   */
  fetchTableRtLastData(params: {
    table_id: string
  }) {
    return StrategySource.getTableRtLastData(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 批量获取表格下的rt字段
   */
  fetchBatchTableRtFields(params: {
    table_ids: string
  }) {
    return StrategySource.getBatchTableRtFields(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取表格下的rt字段
   */
  fetchTableRtFields(params: {
    table_id: string
  }) {
    return StrategySource.getTableRtFields(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取不同数据源可用调度方式
   */
  fetchSourceType(params: {
    table_id: string
  }) {
    return StrategySource.getSourceType(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取策略标签
   */
  fetchStrategyTags() {
    return StrategySource.getStrategyTags()
      .then(({ data }) => data);
  },
  /**
   * @desc 获取方案列表
   */
  fetchControlList() {
    return StrategySource.getControlList()
      .then(({ data }) => data);
  },


  // event
  /**
   * @desc 查询图表数据
   * @param { Object } params
   */
  fetchGraph(params: {
    start_time: string
    end_time: string,
    strategy_id: number,
    interval: number,
    conditions: Array<Record<string, string>>
  }) {
    return StrategySource.getGraph(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 获取操作事件列表
   * @param {Object} params
   */
  fetchRecentLog(params: {
    start_time: string
    end_time: string,
    strategy_id: number,
    interval: number,
    conditions: Array<Record<string, string>>,
    page: number,
    page_size: number
  }) {
    return StrategySource.getRecentLog(params)
      .then(({ data }) => ({
        ...data,
        results: data.results.map(item => new SearchModel(item)),
      }));
  },
  /**
   * @desc 获取算法下拉
   */
  fetAiopsPlan() {
    return StrategySource.getAiopsPlan()
      .then(({ data }) => data);
  },

  /**
   * @desc 获取算法详情
   * @param { String } id
   */
  fetchAiopsPlanById(params: { id: string }) {
    return StrategySource.getAiopsPlanById(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 获取结果表字段
   * @param { String } system_id
   */
  fetchRtfields(params: { system_id: string }) {
    return StrategySource.getRtfields(params)
      .then(({ data }) => data);
  },

  /**
   * @desc 获取aiops策略详情
   * @param { String } id
   */
  fetchAiopsById(params: { id: string }) {
    return StrategySource.getAiopsById(params)
      .then(({ data }) => data);
  },

  /**
  * @desc 获取策略事件信息
  * @param { String } id
  */
  fetchStrategyEvent(params: { id: string }) {
    return StrategySource.getStrategyEvent(params)
      .then(({ data }) => new StrategyFieldEvent(data));
  },

  /**
  * @desc 获取风险单风险等级
  */
  fetchRiskLevel(params: {
    strategy_ids: string
  }) {
    return StrategySource.getRiskLevel(params)
      .then(({ data }) => data);
  },

  /**
  * @desc 获取风险单运行记录
  */
  fetchRisksRunning(params: {
    limit: number,
    offset: number,
    strategy_id: string
  }) {
    return StrategySource.getRisksRunning(params)
      .then(({ data }) => data);
  },

  /**
  * @desc 获取风险简要列表
  */
  fetchRisksBrief(params: {
    page: number,
    page_size: number,
    strategy_id: string
    end_time: string,
    start_time: string,
  }) {
    return StrategySource.getRisksBrief(params)
      .then(({ data }) => data);
  },

  /**
  * @desc 获取聚合函数列表
  */
  fetchAggregationFunctions() {
    return StrategySource.getAggregationFunctions()
      .then(({ data }) => data);
  },
};
