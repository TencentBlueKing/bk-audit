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
  api: string;
  constructor() {
    super();
    this.module = '/api/v1/risks';
    this.api = '/api/v1';
  }
  // 获取风险列表
  getRiskList(params: {
    page: number,
    page_size: number
  }, payload = {} as IRequestPayload) {
    return Request.post<IRequestResponsePaginationData<RiskManageModel>>(`${this.module}/?page=${params.page}&page_size=${params.page_size}`, {
      params,
      payload,
    });
  }
  // 获取正在生成的事件列表
  getAddEventList(params: {
    id: string
  }) {
    return Request.get(`${this.module}/${params.id}/`, {
      params,
    });
  }
  // 编辑风险标题
  updateRiskTitle(params: {
    risk_id: string | number,
    title: string
  }) {
    return Request.put(`${this.module}/${params.risk_id}/`, {
      params,
    });
  }
  // 获取待我处理的风险列表
  getTodoRiskList(params: {
      page: number,
      page_size: number
    }) {
    return Request.post<IRequestResponsePaginationData<RiskManageModel>>(`${this.module}/todo/?page=${params.page}&page_size=${params.page_size}`, {
      params,
    });
  }
  // 我关注的获取风险列表
  getWatchRiskList(params: {
    page: number,
    page_size: number
  }, payload = {} as IRequestPayload) {
    return Request.post<IRequestResponsePaginationData<RiskManageModel>>(`${this.module}/watch/?page=${params.page}&page_size=${params.page_size}`, {
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

  // 获取风险事件可用字段
  getEventFields(params: Record<string, any>) {
    if (!('strategy_ids' in params)) {
      return Request.get(`${this.module}/event_fields/`, {
        params,
      });
    }
    // 将数组转为URL查询字符串格式
    const urlParams = new URLSearchParams();
    params?.strategy_ids.forEach((id: string | number) => {
      urlParams.append('strategy_ids', id.toString());
    });
    return Request.get(`${this.module}/event_fields/?${urlParams.toString()}`, {
    });
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
  // 批量转单
  batchTransRisk(params: {
    risk_ids: string[],
    new_operators: string[],
    description: string
  }) {
    return Request.post(`${this.module}/bulk_trans/`, {
      params,
    });
  }
  // 批量导出
  batchExport(params: {
      risk_ids: string[],
      risk_view_type: string,
    }) {
    return Request.post(`${this.module}/export/`, {
      params,
      responseType: 'blob',
    });
  }
  addEvent(params: Record<string, any>) {
    return Request.post(`${this.api}/events/`, {
      params,
    });
  }
  getReportRiskVar(params:  Record<string, any>) {
    return Request.get(`${this.path}/report/risk_variables/`, {
      params,
    });
  }

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
    return Request.post(`${this.path}/report/preview/`, {
      params,
    });
  }


  getAiPreview(params: {
    id: string,
    risk_id: string,
    ai_variables: Array<{
      name: string,
      prompt_template: string
    }>
  }) {
    return Request.post(`${this.api}/risk_report/${params.id}/ai_preview/`, {
      params,
    });
  }
  getTaskRiskReport(params: {
    task_id: string,
  }) {
    return Request.get(`${this.api}/risk_report/task/`, {
      params,
    });
  }
}
export default new RiskManage();
