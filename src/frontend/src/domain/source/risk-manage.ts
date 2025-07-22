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
import type RiskManageModel from '@model/risk/risk';
import type StrategyInfo from '@model/risk/strategy-info';

import Request, {
  type IRequestPayload,
  type IRequestResponsePaginationData,
} from '@utils/request';

import ModuleBase from './module-base';

class RiskManage extends ModuleBase {
  constructor() {
    super();
    this.module = '/api/v1/risks';
  }
  // 获取风险列表
  getRiskList(params: {
    page: number,
    page_size: number
  }, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<RiskManageModel>>(`${this.module}/`, {
      params,
      payload,
    });
  }
  // 获取待我处理的风险列表
  getTodoRiskList(params: {
      page: number,
      page_size: number
    }) {
    return Request.get<IRequestResponsePaginationData<RiskManageModel>>(`${this.module}/todo/`, {
      params,
    });
  }
  // 我关注的获取风险列表
  getWatchRiskList(params: {
    page: number,
    page_size: number
  }, payload = {} as IRequestPayload) {
    return Request.get<IRequestResponsePaginationData<RiskManageModel>>(`${this.module}/watch/`, {
      params,
      payload,
    });
  }
  // 获取风险可用字段
  getFields() {
    return Request.get<Array<{
      id: string,
      name: string,
    }>>(`${this.module}/fields/`);
  }
  // 获取风险状态类型
  getRiskStatusCommon() {
    return Request.get<Array<{
      id: string,
      name: string,
    }>>(`${this.module}/status_common/`);
  }
  // 获取风险标签
  getRiskTags(params: Record<string, any>) {
    return Request.get<Array<{
      id: string,
      name: string,
    }>>(`${this.module}/tags/`, {
      params,
    });
  }
  // 获取风险详情
  getRiskById(params: {
    id: string,
  }) {
    return Request.get<RiskManageModel>(`${this.module}/${params.id}/`, {
      params,
    });
  }
  // 获取风险策略信息
  getRiskInfo(params: {
    id: string,
  }) {
    return Request.get<StrategyInfo>(`${this.module}/${params.id}/strategy_info/`);
  }
  // 人工执行处理套餐
  autoProcess(params: {
    risk_id: string
  }) {
    return Request.post(`${this.module}/${params.risk_id}/auto_process/`, {
      params,
    });
  }

  // 人工关单
  close(params: {
    risk_id: string,
    description: string
  }) {
    return Request.post(`${this.module}/${params.risk_id}/close/`, {
      params,
    });
  }

  // 强制终止处理套餐
  forceRevokeAutoProcess(params: {
    risk_id: string
  }) {
    return Request.post(`${this.module}/${params.risk_id}/force_revoke_auto_process/`, {
      params,
    });
  }
  // 重开单据
  reopen(params: {
    risk_id: string,
    new_operators: string[]
  }) {
    return Request.post(`${this.module}/${params.risk_id}/reopen/`, {
      params,
    });
  }

  // 重试处理套餐
  retryAutoProcess(params: {
    node_id: string,
    risk_id: string
  }) {
    return Request.post(`${this.module}/${params.risk_id}/retry_auto_process/`, {
      params,
    });
  }


  // 更新风险标记 / 标记误报
  updateRiskLabel(params: {
    risk_id: string,
    risk_label: string,
    new_operators: string[]
  }) {
    return Request.put(`${this.module}/${params.risk_id}/risk_label/`, {
      params,
    });
  }

  // 人工转单
  transRisk(params: {
    risk_id: string,
    new_operators: string[],
    description: string
  }) {
    return Request.post(`${this.module}/${params.risk_id}/trans/`, {
      params,
    });
  }
}
export default new RiskManage();
