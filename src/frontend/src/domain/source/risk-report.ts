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
import Request from '@utils/request';

import ModuleBase from './module-base';

class RiskManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/risk_report';
  }
  /**
   * @desc 生成风险报告（获取task_id）
   */
  riskReportGenerate(params: {
    risk_id: string,
  }) {
    return Request.post<{
      task_id: string,
      status: string,
    }>(`${this.module}/${params.risk_id}/generate/`);
  }
  /**
   * @desc 获取风险报告（查询任务结果）
   */
  fetchRiskReport(params: {
    task_id: string,
    risk_id: string,
  }) {
    return Request.get<{
      task_id: string,
      status: string,
      result: string,
    }>(`${this.module}/task/`, {
      params: {
        task_id: params.task_id,
      },
    });
  }
  /**
   * @desc 保存风险报告
   */
  saveRiskReport(params: {
    risk_id: string,
    content: string,
    auto_generate: boolean,
  }) {
    return Request.post(`${this.module}/${params.risk_id}/save/`, {
      params: {
        content: params.content,
        auto_generate: params.auto_generate,
      },
    });
  }
  /**
   * @desc 更新风险报告
   */
  updateRiskReport(params: {
    risk_id: string,
    content: string,
    auto_generate: boolean,
  }) {
    return Request.put(`${this.module}/${params.risk_id}/`, {
      params: {
        content: params.content,
        auto_generate: params.auto_generate,
      },
    });
  }
}
export default new RiskManage();
