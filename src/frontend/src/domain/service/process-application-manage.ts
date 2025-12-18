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

import ProcessApplicationManageSource from '../source/process-application-manage';

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
    return ProcessApplicationManageSource.create(params)
      .then(({ data }) => data);
  },
  /**
   * @desc 获取处理套餐列表(下拉列表)
   */
  fetchApplicationsAll() {
    return ProcessApplicationManageSource.getApplicationsAll()
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
