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
import RiskReportSource from '../source/risk-report';

export default {
  /**
   * @desc 生成风险报告（获取task_id）
   */
  riskReportGenerate(params: {
    risk_id: string,
  }) {
    return RiskReportSource.riskReportGenerate(params)
      .then(({ data }) => data);
  },
  fetchRiskReport(params: {
    task_id: string,
    risk_id: string,
  }) {
    return RiskReportSource.fetchRiskReport(params)
      .then(({ data }) => data);
  },
  saveRiskReport(params: {
    risk_id: string,
    content: string,
    auto_generate: boolean,
  }) {
    return RiskReportSource.saveRiskReport(params)
      .then(({ data }) => data);
  },
  updateRiskReport(params: {
    risk_id: string,
    content: string,
    auto_generate: boolean,
  }) {
    return RiskReportSource.updateRiskReport(params)
      .then(({ data }) => data);
  },
};
