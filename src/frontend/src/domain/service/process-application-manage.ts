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
import ApplicationManageModel from '@model/application/application';
import type ApplicationCreateManageModel from '@model/application/application-create';
import ExecutionDetail from '@model/application/execution-detail';
import ExecutionRecord from '@model/application/execution-record';

import ProcessApplicationManageSource from '../source/process-application-manage';

import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

export default {
  /**
 * @desc 获取处理套餐列表
 */
  fetchList(params: {
    page: number,
    page_size: number
  }) {
    return ProcessApplicationManageSource.getApplicationList(
      params,
      {
        permission: 'page',
      },
    )
      .then(({ data }) => ({
        ...data,
        results: data.results.map(item => new ApplicationManageModel(item)),
      }));
  },
  /**
     * @desc 创建处理套餐
     */
  create(params: ApplicationCreateManageModel) {
    return ProcessApplicationManageSource.create({ ...params, scene_id: getSceneSystemParams().scope_id })
      .then(({ data }) => data);
  },
  /**
   * @desc 获取处理套餐列表(下拉列表)
   */
  fetchApplicationsAll(params:{
    scene_id?: string
  }) {
    return ProcessApplicationManageSource.getApplicationsAll(params)
      .then(({ data }) => data);
  },
  /**
     * @desc 获取审批内置字段
     */
  fetchInFields() {
    return ProcessApplicationManageSource.getInFields()
      .then(({ data }) => data);
  },
  /**
     * @desc 更新处理套餐
     */
  update(params: ApplicationCreateManageModel) {
    return ProcessApplicationManageSource.update(params)
      .then(({ data }) => data);
  },

  /**
     * @desc 获取处理套餐中的命中风险
     */
  fetchRisks(params: {
    page: number,
    page_size: number,
    id: string
  }) {
    return ProcessApplicationManageSource.getRisks(params)
      .then(({ data }) => data);
  },
  /**
     * @desc 获取处理套餐关联的规则
     */
  fetchRuleList(params: {
    page: number,
    page_size: number,
    id: string
  }) {
    return ProcessApplicationManageSource.getRuleList(params)
      .then(({ data }) => data);
  },
  /**
     * @desc 处理套餐执行记录
     * fetchRisks 是套餐命中风险，与执行记录不是同一资源。
     */
  fetchExecutionRecords(params: {
    page?: number,
    page_size?: number,
    keyword?: string,
    task_id?: string,
    task_name?: string,
    application_id?: string,
    application_name?: string,
    risk_id?: string,
    trigger_type?: string,
    status?: string,
    executor?: string,
    sort?: string | string[],
    scene_id?: string,
  }) {
    return ProcessApplicationManageSource.getExecutionRecords(params)
      .then(({ data }) => ({
        ...data,
        results: (data.results || []).map((item: ConstructorParameters<typeof ExecutionRecord>[0]) => new ExecutionRecord(item)),
      }));
  },
  fetchExecutionDetail(params: { task_id: string }) {
    return ProcessApplicationManageSource.getExecutionDetail(params)
      .then(({ data }) => (data ? new ExecutionDetail(data) : data));
  },
  retryExecution(params: { task_id: string; reason: string }) {
    return ProcessApplicationManageSource.retryExecution(params)
      .then(({ data }) => new ExecutionDetail(data));
  },
  /**
     * @desc 启停处理套餐
     */
  toggleApplication(params: {
    id: string,
    is_enabled: boolean
  }) {
    return ProcessApplicationManageSource.toggleApplication(params)
      .then(({ data }) => data);
  },
};
